"""
Qdrant operations — one collection per chatbot, fully isolated.
Uses delete + create instead of recreate_collection (deprecated in qdrant-client >= 1.7).
"""

import logging
import tenacity
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY
from services.embedder import EMBEDDING_DIM

logger = logging.getLogger(__name__)

RETRY = tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
)

# Single client reused across all requests
# If QDRANT_API_KEY is set → connect to Qdrant Cloud via HTTPS
# Otherwise → connect to local Docker Qdrant
if QDRANT_API_KEY:
    _client = QdrantClient(
        url=f"https://{QDRANT_HOST}",
        api_key=QDRANT_API_KEY,
    )
    logger.info(f"[Qdrant] Connected to Qdrant Cloud: {QDRANT_HOST}")
else:
    _client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    logger.info(f"[Qdrant] Connected to local Qdrant: {QDRANT_HOST}:{QDRANT_PORT}")


@RETRY
def create_collection(collection_name: str) -> None:
    """
    Create a fresh Qdrant collection for a chatbot.
    Deletes the existing collection first if it exists (safe re-ingest).
    """
    try:
        _client.delete_collection(collection_name)
        logger.info(f"[Qdrant] Deleted old collection: {collection_name}")
    except Exception:
        pass  # Didn't exist — that's fine

    _client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    logger.info(f"[Qdrant] Created collection: {collection_name}")


@RETRY
def upsert_chunks(
    collection_name: str,
    chunks: list[dict],       # [{"text": ..., "url": ..., "title": ...}]
    embeddings: list[list[float]],
) -> None:
    """Store embedded chunks into Qdrant with source metadata as payload."""
    points = [
        PointStruct(
            id=i,
            vector=embeddings[i],
            payload={
                "text": chunks[i]["text"],
                "url": chunks[i].get("url", ""),
                "title": chunks[i].get("title", ""),
            },
        )
        for i in range(len(chunks))
    ]
    _client.upsert(collection_name=collection_name, points=points)
    logger.info(f"[Qdrant] Stored {len(points)} chunks in '{collection_name}'")


@RETRY
def search_chunks(
    collection_name: str,
    query_vector: list[float],
    limit: int = 5,
) -> list[dict]:
    """
    Cosine similarity search — returns top-k most relevant chunks.
    Returns [{"text": ..., "url": ..., "title": ..., "score": ...}]
    """
    results = _client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=limit,
    )
    return [
        {
            "text": r.payload.get("text", ""),
            "url": r.payload.get("url", ""),
            "title": r.payload.get("title", ""),
            "score": r.score,
        }
        for r in results
    ]


@RETRY
def collection_exists(collection_name: str) -> bool:
    """Returns True if the collection exists and is queryable."""
    try:
        _client.get_collection(collection_name)
        return True
    except Exception:
        return False


def delete_collection(collection_name: str) -> None:
    """Delete a chatbot's Qdrant collection (called when chatbot is deleted)."""
    try:
        _client.delete_collection(collection_name)
        logger.info(f"[Qdrant] Deleted collection: {collection_name}")
    except Exception as e:
        logger.warning(f"[Qdrant] Could not delete collection '{collection_name}': {e}")
