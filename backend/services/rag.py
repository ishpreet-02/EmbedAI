"""
RAG pipeline — text chunking, ingestion, and streaming query.
"""

import logging
from functools import lru_cache
from typing import Generator

import tenacity
from langchain_text_splitters import RecursiveCharacterTextSplitter
from groq import Groq

from config import GROQ_API_KEY
from services.embedder import embed_texts, embed_query
from services.qdrant_service import create_collection, upsert_chunks, search_chunks

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────

GROQ_MODEL = "llama-3.3-70b-versatile"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 5
CACHE_MAX_SIZE = 200

SYSTEM_PROMPT = """You are a helpful customer support assistant for a business website.
Answer visitor questions using ONLY the context provided below.
Be concise, friendly, and accurate. 
If the answer is not in the context, say exactly: "I don't have that information. Please contact us directly for help."
Never make up information that isn't in the context."""

# ── Singletons ────────────────────────────────────────────

groq_client = Groq(api_key=GROQ_API_KEY)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
)
def _create_groq_stream(messages: list[dict]):
    """Start a Groq streaming completion — retried if the API is briefly unavailable."""
    return groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        stream=True,
        max_tokens=512,
        temperature=0.1,
    )


# ── Ingestion ─────────────────────────────────────────────

def chunk_pages(pages: list[dict]) -> list[dict]:
    """
    Split scraped pages into chunks for embedding.
    Input: [{"text": ..., "url": ..., "title": ...}]
    Output: [{"text": ..., "url": ..., "title": ...}]  (more items, shorter text)
    """
    chunks = []
    seen_texts = set()
    for page in pages:
        page_chunks = _splitter.split_text(page["text"])
        for chunk_text in page_chunks:
            # Skip near-duplicate chunks (same text from repeated nav/footer)
            normalized = chunk_text.strip().lower()[:200]
            if normalized in seen_texts:
                continue
            seen_texts.add(normalized)
            chunks.append({
                "text": chunk_text,
                "url": page.get("url", ""),
                "title": page.get("title", ""),
            })
    logger.info(f"[RAG] {len(pages)} pages → {len(chunks)} chunks (after dedup)")
    return chunks


def ingest_pages(pages: list[dict], collection_name: str) -> int:
    """
    Full ingestion pipeline (sync — called via run_in_executor from async context):
      1. Chunk pages with LangChain RecursiveCharacterTextSplitter
      2. Embed all chunks locally with sentence-transformers
      3. Create isolated Qdrant collection
      4. Store all vectors + metadata
    Returns number of chunks stored.
    """
    chunks = chunk_pages(pages)
    if not chunks:
        logger.warning("[RAG] No chunks to ingest — aborting")
        return 0

    # Embed all chunks in one batched call (much faster than one-by-one)
    logger.info(f"[RAG] Embedding {len(chunks)} chunks locally...")
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)
    logger.info("[RAG] Embedding complete")

    # Create collection and store (Qdrant ops are retried internally)
    create_collection(collection_name)
    upsert_chunks(collection_name, chunks, embeddings)

    return len(chunks)


# ── Query ─────────────────────────────────────────────────

# Plain dict cache: key = (normalized_question, collection_name), value = full response string
# Using a plain dict instead of lru_cache so we can:
#   1. Still stream tokens for first-time questions
#   2. Return instantly from cache for repeated questions
#   3. Selectively clear cache entries per chatbot collection
_response_cache: dict[tuple[str, str], str] = {}


def _stream_rag_uncached(question: str, collection_name: str) -> Generator[str, None, None]:
    """
    RAG query pipeline — yields response tokens as they stream from Groq.
    Not cached; use query_rag() for cache-aware streaming.
    """
    query_vector = embed_query(question)
    results = search_chunks(collection_name, query_vector, limit=TOP_K)
    results = [r for r in results if r["score"] > 0.3]

    if not results:
        yield "I don't have enough information to answer that. Please contact us directly."
        return

    context_parts = []
    for r in results:
        source = f" [from: {r['url']}]" if r.get("url") else ""
        context_parts.append(f"{r['text']}{source}")

    context = "\n\n---\n\n".join(context_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}",
        },
    ]

    logger.info(
        f"[RAG] Querying Groq with {len(results)} context chunks "
        f"(top score: {results[0]['score']:.3f})"
    )

    stream = _create_groq_stream(messages)

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def query_rag(question: str, collection_name: str) -> Generator[str, None, None]:
    """
    Cache-aware streaming RAG query.
    - First time a question is asked: streams live from Groq, then caches the full response.
    - Repeated identical questions: returns instantly from the in-memory cache.
    """
    key = (question.strip().lower(), collection_name)

    cached = _response_cache.get(key)
    if cached is not None:
        logger.info(f"[RAG] Cache hit for '{question[:60]}'")
        yield cached
        return

    # Stream live and accumulate tokens to cache after completion
    parts: list[str] = []
    for token in _stream_rag_uncached(question.strip(), collection_name):
        parts.append(token)
        yield token

    # Store in cache; evict oldest entry if at capacity
    if len(_response_cache) >= CACHE_MAX_SIZE:
        oldest_key = next(iter(_response_cache))
        del _response_cache[oldest_key]
    _response_cache[key] = "".join(parts)


def clear_response_cache() -> None:
    """Clear all cached chat responses."""
    _response_cache.clear()


def clear_response_cache_for_collection(collection_name: str) -> None:
    """Clear cached answers only for a specific chatbot (called after re-ingestion)."""
    keys_to_delete = [k for k in _response_cache if k[1] == collection_name]
    for k in keys_to_delete:
        del _response_cache[k]
    if keys_to_delete:
        logger.info(f"[RAG] Cleared {len(keys_to_delete)} cache entries for '{collection_name}'")
