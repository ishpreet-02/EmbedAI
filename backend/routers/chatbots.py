"""
Chatbot CRUD router — create, list, get, delete chatbots.
"""

import uuid
import threading
import asyncio

from fastapi import APIRouter, HTTPException, status, Depends

from config import FRONTEND_URL
from models.schemas import (
    CreateChatbotRequest,
    UpdateChatbotRequest,
    ChatbotResponse,
    ChatbotStatusResponse,
)
from middleware.auth import get_current_user
from services.database import get_supabase
from services.origins import default_allowed_origins
from tasks.ingest import run_ingestion

import logging
logger = logging.getLogger(__name__)


def _run_ingestion_in_thread(chatbot_id: str, website_url: str, collection_name: str):
    """Run the async ingestion in a separate thread with its own event loop."""
    try:
        logger.info(f"[Thread] Starting ingestion thread for chatbot {chatbot_id}")
        asyncio.run(run_ingestion(chatbot_id, website_url, collection_name))
        logger.info(f"[Thread] Ingestion thread completed for chatbot {chatbot_id}")
    except Exception as e:
        logger.error(f"[Thread] Ingestion thread CRASHED for chatbot {chatbot_id}: {e}", exc_info=True)

router = APIRouter(prefix="/api/chatbots", tags=["Chatbots"])


@router.post("/", response_model=ChatbotResponse, status_code=status.HTTP_201_CREATED)
async def create_chatbot(
    body: CreateChatbotRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new chatbot and queue it for ingestion."""
    supabase = get_supabase()

    collection_name = f"chatbot_{uuid.uuid4().hex[:12]}"

    result = supabase.table("chatbots").insert({
        "user_id": current_user["id"],
        "name": body.name,
        "website_url": body.website_url,
        "status": "pending",
        "qdrant_collection": collection_name,
        "allowed_origins": default_allowed_origins(body.website_url, FRONTEND_URL),
    }).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chatbot",
        )

    chatbot = result.data[0]

    # Trigger background scraping task in a separate thread
    thread = threading.Thread(
        target=_run_ingestion_in_thread,
        args=(chatbot["id"], body.website_url, collection_name),
        daemon=True,
    )
    thread.start()

    return _to_chatbot_response(chatbot)


@router.get("/", response_model=list[ChatbotResponse])
async def list_chatbots(current_user: dict = Depends(get_current_user)):
    """List all chatbots belonging to the current user."""
    supabase = get_supabase()

    result = (
        supabase.table("chatbots")
        .select("*")
        .eq("user_id", current_user["id"])
        .order("created_at", desc=True)
        .execute()
    )

    return [_to_chatbot_response(c) for c in result.data]


@router.get("/{chatbot_id}", response_model=ChatbotResponse)
async def get_chatbot(
    chatbot_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single chatbot by ID (must belong to current user)."""

    chatbot = _get_owned_chatbot(chatbot_id, current_user["id"])
    return _to_chatbot_response(chatbot)


@router.patch("/{chatbot_id}", response_model=ChatbotResponse)
async def update_chatbot(
    chatbot_id: str,
    body: UpdateChatbotRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update chatbot settings (e.g. widget allowed origins)."""
    supabase = get_supabase()
    _get_owned_chatbot(chatbot_id, current_user["id"])

    result = (
        supabase.table("chatbots")
        .update({"allowed_origins": body.allowed_origins})
        .eq("id", chatbot_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chatbot",
        )

    return _to_chatbot_response(result.data[0])


@router.delete("/{chatbot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chatbot(
    chatbot_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a chatbot and its data."""
    supabase = get_supabase()

    chatbot = _get_owned_chatbot(chatbot_id, current_user["id"])

    # TODO (Week 3): Also delete the Qdrant collection
    # qdrant.delete_collection(chatbot["qdrant_collection"])

    # Delete associated messages → conversations → chatbot
    conversations = (
        supabase.table("conversations")
        .select("id")
        .eq("chatbot_id", chatbot_id)
        .execute()
    )
    for conv in conversations.data:
        supabase.table("messages").delete().eq("conversation_id", conv["id"]).execute()

    supabase.table("conversations").delete().eq("chatbot_id", chatbot_id).execute()
    supabase.table("chatbots").delete().eq("id", chatbot_id).execute()


@router.get("/{chatbot_id}/status", response_model=ChatbotStatusResponse)
async def get_chatbot_status(
    chatbot_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Poll the ingestion status of a chatbot."""

    chatbot = _get_owned_chatbot(chatbot_id, current_user["id"])
    return ChatbotStatusResponse(
        id=chatbot["id"],
        status=chatbot["status"],
        pages_indexed=chatbot.get("pages_indexed"),
        chunks_stored=chatbot.get("chunks_stored"),
    )


@router.get("/{chatbot_id}/conversations")
async def get_chatbot_conversations(
    chatbot_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all conversations for a chatbot (must belong to current user)."""
    supabase = get_supabase()

    _get_owned_chatbot(chatbot_id, current_user["id"])

    conversations = (
        supabase.table("conversations")
        .select("id, visitor_id, created_at")
        .eq("chatbot_id", chatbot_id)
        .order("created_at", desc=True)
        .execute()
    )

    return conversations.data or []


# ── Helpers ───────────────────────────────────────────────

def _get_owned_chatbot(chatbot_id: str, user_id: str) -> dict:
    """Fetch a chatbot and verify it belongs to the user."""
    supabase = get_supabase()

    result = supabase.table("chatbots").select("*").eq("id", chatbot_id).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chatbot not found",
        )

    chatbot = result.data[0]
    if chatbot["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your chatbot",
        )

    return chatbot


def _to_chatbot_response(chatbot: dict) -> ChatbotResponse:
    return ChatbotResponse(
        id=chatbot["id"],
        user_id=chatbot["user_id"],
        name=chatbot["name"],
        website_url=chatbot["website_url"],
        status=chatbot["status"],
        qdrant_collection=chatbot.get("qdrant_collection"),
        pages_indexed=chatbot.get("pages_indexed"),
        chunks_stored=chatbot.get("chunks_stored"),
        allowed_origins=chatbot.get("allowed_origins") or [],
        created_at=str(chatbot["created_at"]),
    )
