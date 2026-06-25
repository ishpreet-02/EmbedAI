"""
Embedding service — loads all-MiniLM-L6-v2 once at module level.
Runs entirely locally, zero API cost, 384-dim vectors.
"""

import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # Qdrant collection must match this

logger.info(f"[Embedder] Loading {EMBEDDING_MODEL} (downloads ~90MB on first run)...")
_model = SentenceTransformer(EMBEDDING_MODEL)
logger.info("[Embedder] Model ready.")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text chunks. Returns list of 384-dim float vectors."""
    return _model.encode(texts, show_progress_bar=False).tolist()


def embed_query(query: str) -> list[float]:
    """Embed a single query string. Returns a single 384-dim vector."""
    return _model.encode([query], show_progress_bar=False)[0].tolist()