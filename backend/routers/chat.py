"""
Chat endpoint — public API called by the embeddable widget.
No JWT required: visitors on the business website aren't logged in.
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.schemas import ChatRequest
from services.database import get_supabase
from services.origins import extract_request_origin, is_origin_allowed
from services.rag import query_rag
from services.qdrant_service import collection_exists

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


def _check_widget_origin(request: Request, allowed_origins: list[str] | None) -> None:
    origin = extract_request_origin(
        request.headers.get("origin"),
        request.headers.get("referer"),
    )
    if not is_origin_allowed(origin, allowed_origins):
        raise HTTPException(
            status_code=403,
            detail="This domain is not authorized to use this chatbot",
        )


# ── Endpoints ─────────────────────────────────────────────

@router.post("/{chatbot_id}")
@limiter.limit("20/minute")
def chat(request: Request, chatbot_id: str, body: ChatRequest):
    """
    Public streaming chat endpoint — called by the embeddable widget.
    
    Flow:
      1. Validate chatbot exists and status == 'ready'
      2. Create a conversation record in Supabase
      3. Save the user's message
      4. Stream the RAG response back token by token
      5. Save the full assistant response after streaming completes
    
    Note: This is a sync endpoint (def, not async) so the sync generator
    in StreamingResponse runs directly without event loop conflicts.
    """
    supabase = get_supabase()

    # ── 1. Validate chatbot ───────────────────────────────
    result = (
        supabase.table("chatbots")
        .select("id, status, qdrant_collection, name, allowed_origins")
        .eq("id", chatbot_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    chatbot = result.data

    _check_widget_origin(request, chatbot.get("allowed_origins"))

    if chatbot["status"] != "ready":
        raise HTTPException(
            status_code=503,
            detail=f"Chatbot is not ready yet (status: {chatbot['status']}). "
                   f"Please wait for ingestion to complete.",
        )

    collection_name = chatbot["qdrant_collection"]

    if not collection_exists(collection_name):
        raise HTTPException(
            status_code=503,
            detail="Knowledge base not found. Please re-create the chatbot.",
        )

    # ── 2. Resolve conversation ────────────────────────────
    visitor_id = body.visitor_id or f"visitor_{uuid.uuid4().hex[:8]}"
    conversation_id = None

    # If the client sent a conversation_id, verify it exists AND belongs
    # to this chatbot before reusing it — never trust client input blindly.
    if body.conversation_id:
        existing = (
            supabase.table("conversations")
            .select("id")
            .eq("id", body.conversation_id)
            .eq("chatbot_id", chatbot_id)
            .execute()
        )
        if existing.data:
            conversation_id = body.conversation_id

    # No valid existing conversation → create a new one
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        supabase.table("conversations").insert({
            "id": conversation_id,
            "chatbot_id": chatbot_id,
            "visitor_id": visitor_id,
        }).execute()

    # ── 3. Save user message ───────────────────────────────
    supabase.table("messages").insert({
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": "user",
        "content": body.message,
    }).execute()

    # ── 4 + 5. Stream response and save when done ─────────
    full_response: list[str] = []

    def generate():
        try:
            for token in query_rag(body.message, collection_name):
                full_response.append(token)
                yield token
        except Exception as e:
            logger.error(f"[Chat] RAG error for chatbot {chatbot_id}: {e}", exc_info=True)
            yield "\n\n[An error occurred. Please try again.]"
        finally:
            # Runs after all tokens are streamed — save the full response
            if full_response:
                try:
                    supabase.table("messages").insert({
                        "id": str(uuid.uuid4()),
                        "conversation_id": conversation_id,
                        "role": "assistant",
                        "content": "".join(full_response),
                    }).execute()
                    logger.info(
                        f"[Chat] Saved conversation {conversation_id} "
                        f"({len(''.join(full_response))} chars)"
                    )
                except Exception as e:
                    logger.error(f"[Chat] Failed to save assistant message: {e}")

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            # Widget can read these from the response headers
            "X-Visitor-Id": visitor_id,
            "X-Conversation-Id": conversation_id,
            "Access-Control-Expose-Headers": "X-Visitor-Id, X-Conversation-Id",
        },
    )


@router.get("/{chatbot_id}/history")
def get_history(request: Request, chatbot_id: str, conversation_id: str):
    """
    Fetch all messages in a conversation.
    Public endpoint — the widget can use this to restore chat on page reload.
    """
    supabase = get_supabase()

    chatbot = (
        supabase.table("chatbots")
        .select("allowed_origins")
        .eq("id", chatbot_id)
        .single()
        .execute()
    )

    if not chatbot.data:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    _check_widget_origin(request, chatbot.data.get("allowed_origins"))

    # Verify conversation belongs to this chatbot (prevents cross-chatbot reads)
    conv = (
        supabase.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("chatbot_id", chatbot_id)
        .single()
        .execute()
    )

    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        supabase.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )

    return {
        "conversation_id": conversation_id,
        "messages": messages.data or [],
    }
