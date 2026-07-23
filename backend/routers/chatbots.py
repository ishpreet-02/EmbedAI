"""
Chatbot CRUD router — create, list, get, delete chatbots.
"""

import uuid

from fastapi import APIRouter, HTTPException, status, Depends

from config import FRONTEND_URL
from models.schemas import (
    CreateChatbotRequest,
    UpdateChatbotRequest,
    ChatbotResponse,
    ChatbotStatusResponse,
    ChatbotScopeResponse,
)
from middleware.auth import get_current_user
from services.database import get_supabase
from services.origins import default_allowed_origins
from services.qdrant_service import delete_collection, collection_exists, get_collection_source_scope
from tasks.ingest import run_ingestion_task

import logging
logger = logging.getLogger(__name__)

LEGACY_DEFAULT_HEADER = "AI Assistant"
LEGACY_DEFAULT_WELCOME = "Hi there! How can I help you today?"


def _company_name(chatbot: dict) -> str:
    """Use the dashboard chatbot name as the customer-facing company/brand name."""
    name = str(chatbot.get("name") or "").strip()
    return name or "this company"


def _default_widget_header(company_name: str) -> str:
    normalized = company_name.strip()
    lower = normalized.lower()
    if lower.endswith((" ai", " assistant", " bot", " chatbot")):
        return normalized
    return f"{normalized} AI"


def _default_widget_welcome(ai_name: str, company_name: str) -> str:
    return (
        f"Hi, I'm {ai_name}, your AI Assistant from {company_name}. "
        "I noticed you were checking out our website. Are there any specific "
        "solutions or products you want to know more about?"
    )


def _resolved_widget_header(chatbot: dict) -> str:
    stored = str(chatbot.get("widget_header") or "").strip()
    if stored and stored != LEGACY_DEFAULT_HEADER:
        return stored
    return _default_widget_header(_company_name(chatbot))


def _resolved_widget_welcome(chatbot: dict) -> str:
    stored = str(chatbot.get("widget_welcome") or "").strip()
    if stored and stored != LEGACY_DEFAULT_WELCOME:
        return stored

    company_name = _company_name(chatbot)
    ai_name = _resolved_widget_header(chatbot)
    return _default_widget_welcome(ai_name, company_name)


def _queue_ingestion(chatbot_id: str, website_url: str, collection_name: str) -> None:
    """Queue website ingestion in Celery."""
    try:
        run_ingestion_task.delay(chatbot_id, website_url, collection_name)
        logger.info(f"[Celery] Queued ingestion for chatbot {chatbot_id}")
    except Exception as e:
        logger.error(f"[Celery] Failed to queue ingestion for chatbot {chatbot_id}: {e}", exc_info=True)
        get_supabase().table("chatbots").update({"status": "failed"}).eq("id", chatbot_id).execute()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to queue ingestion job. Make sure Redis is running and REDIS_URL is correct.",
        )

router = APIRouter(prefix="/api/chatbots", tags=["Chatbots"])


@router.post("/", response_model=ChatbotResponse, status_code=status.HTTP_201_CREATED)
async def create_chatbot(
    body: CreateChatbotRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new chatbot and queue it for ingestion."""
    supabase = get_supabase()

    collection_name = f"chatbot_{uuid.uuid4().hex[:12]}"
    default_header = _default_widget_header(body.name)
    default_welcome = _default_widget_welcome(default_header, body.name)

    result = supabase.table("chatbots").insert({
        "user_id": current_user["id"],
        "name": body.name,
        "website_url": body.website_url,
        "status": "pending",
        "qdrant_collection": collection_name,
        "allowed_origins": default_allowed_origins(body.website_url, FRONTEND_URL),
        "widget_header": default_header,
        "widget_welcome": default_welcome,
    }).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chatbot",
        )

    chatbot = result.data[0]

    _queue_ingestion(chatbot["id"], body.website_url, collection_name)

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

    update_data: dict = {}
    if body.allowed_origins is not None:
        update_data["allowed_origins"] = body.allowed_origins
    if body.widget_color is not None:
        update_data["widget_color"] = body.widget_color
    if body.widget_header is not None:
        update_data["widget_header"] = body.widget_header
    if body.widget_welcome is not None:
        update_data["widget_welcome"] = body.widget_welcome
    if body.widget_position is not None:
        update_data["widget_position"] = body.widget_position

    if not update_data:
        return _to_chatbot_response(_get_owned_chatbot(chatbot_id, current_user["id"]))

    result = (
        supabase.table("chatbots")
        .update(update_data)
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

    try:
        delete_collection(chatbot["qdrant_collection"])
    except Exception as e:
        logger.warning(
            f"[Delete] Could not delete Qdrant collection for chatbot {chatbot_id}: {e}"
        )

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


@router.post("/{chatbot_id}/resync", response_model=ChatbotStatusResponse)
async def resync_chatbot(
    chatbot_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Re-run scraping + ingestion for an existing chatbot (e.g. after site update)."""
    supabase = get_supabase()

    chatbot = _get_owned_chatbot(chatbot_id, current_user["id"])

    # Reset status to pending so the UI shows the progress
    supabase.table("chatbots").update({"status": "pending", "pages_indexed": 0, "chunks_stored": 0}).eq("id", chatbot_id).execute()

    # Clear any cached responses for this chatbot
    from services.rag import clear_response_cache_for_collection
    clear_response_cache_for_collection(chatbot["qdrant_collection"])

    _queue_ingestion(chatbot["id"], chatbot["website_url"], chatbot["qdrant_collection"])

    logger.info(f"[Resync] Queued resync for chatbot {chatbot_id}")

    return ChatbotStatusResponse(
        id=chatbot_id,
        status="pending",
        pages_indexed=0,
        chunks_stored=0,
    )


@router.get("/{chatbot_id}/scope", response_model=ChatbotScopeResponse)
async def get_chatbot_scope(
    chatbot_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Inspect which source URLs are currently indexed for this chatbot."""
    chatbot = _get_owned_chatbot(chatbot_id, current_user["id"])
    collection_name = chatbot.get("qdrant_collection")

    if not collection_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chatbot does not have a collection yet",
        )

    if not collection_exists(collection_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    scope = get_collection_source_scope(collection_name)
    return ChatbotScopeResponse(
        chatbot_id=chatbot["id"],
        website_url=chatbot["website_url"],
        status=chatbot["status"],
        qdrant_collection=collection_name,
        scanned_points=scope["scanned_points"],
        summary_points=scope["summary_points"],
        indexed_url_count=scope["indexed_url_count"],
        indexed_urls=scope["indexed_urls"],
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


@router.get("/{chatbot_id}/widget-config")
async def get_widget_config(chatbot_id: str):
    """
    PUBLIC endpoint — no auth required.
    Called by the embedded widget on every page load to get dynamic config.
    Returns color, header text, welcome message, and bubble position.
    """
    supabase = get_supabase()

    result = (
        supabase.table("chatbots")
        .select("name, widget_color, widget_header, widget_welcome, widget_position, status")
        .eq("id", chatbot_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    data = result.data
    return {
        "color":    data.get("widget_color")   or "#6366f1",
        "header":   _resolved_widget_header(data),
        "welcome":  _resolved_widget_welcome(data),
        "position": data.get("widget_position") or "right",
    }


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
        website_summary=chatbot.get("website_summary"),
        key_pages=chatbot.get("key_pages"),
        summary_generated_at=str(chatbot.get("summary_generated_at")) if chatbot.get("summary_generated_at") else None,
        allowed_origins=chatbot.get("allowed_origins") or [],
        widget_color=chatbot.get("widget_color") or "#6366f1",
        widget_header=_resolved_widget_header(chatbot),
        widget_welcome=_resolved_widget_welcome(chatbot),
        widget_position=chatbot.get("widget_position") or "right",
        created_at=str(chatbot["created_at"]),
    )
