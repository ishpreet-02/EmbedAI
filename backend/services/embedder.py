"""
Embedding service — lazy-loads all-MiniLM-L6-v2 on first use.
Runs entirely locally, zero API cost, 384-dim vectors.
"""

import logging
from sentence_transformers import SentenceTransformer

import torch

logger = logging.getLogger(__name__)

# Optimize PyTorch memory for free tier
torch.set_num_threads(1)
torch.set_grad_enabled(False)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # Qdrant collection must match this

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        try:
            logger.info(f"[Embedder] Loading {EMBEDDING_MODEL} (downloads ~90MB on first run)...")
            _model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("[Embedder] Model ready.")
        except Exception as e:
            logger.error(f"[Embedder] Failed to load embedding model: {e}", exc_info=True)
            raise RuntimeError(
                f"Embedding model '{EMBEDDING_MODEL}' could not be loaded. "
                "Check disk space, network access for the initial download, "
                "and that sentence-transformers is installed correctly."
            ) from e
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text chunks. Returns list of 384-dim float vectors."""
    return _get_model().encode(texts, show_progress_bar=False).tolist()


def embed_query(query: str) -> list[float]:
    """Embed a single query string. Returns a single 384-dim vector."""
    return _get_model().encode([query], show_progress_bar=False)[0].tolist()
