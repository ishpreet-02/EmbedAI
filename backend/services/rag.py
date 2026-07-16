"""
RAG pipeline — text chunking, ingestion, and streaming query.
"""

import re
import logging
from typing import Generator

import tenacity
from langchain_text_splitters import RecursiveCharacterTextSplitter
from groq import Groq

from config import GROQ_API_KEY
from services.embedder import embed_texts, embed_query
from services.qdrant_service import (
    create_collection, upsert_chunks, search_chunks,
    upsert_single_point, get_summary_chunk,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────

GROQ_MODEL       = "llama-3.3-70b-versatile"
CHUNK_SIZE       = 500
CHUNK_OVERLAP    = 50
TOP_K            = 5
CACHE_MAX_SIZE   = 200

# Fixed UUID reserved for the website summary point in Qdrant
SUMMARY_POINT_ID = "00000000-0000-0000-0000-000000000001"

# Keywords/phrases that signal a general "tell me about this website" question
_GENERAL_TRIGGERS = [
    "what is this",
    "what's this",
    "what are you",
    "about this site",
    "about this website",
    "about this platform",
    "about this app",
    "about this tool",
    "about this project",
    "about this service",
    "about this product",
    "about this company",
    "what does this",
    "what do you do",
    "what can i do",
    "what can you do",
    "explain this",
    "explain the website",
    "explain the site",
    "explain the platform",
    "tell me about",
    "summarize this",
    "summarize the",
    "give me a summary",
    "give me an overview",
    "overview of this",
    "overview of the",
    "describe this",
    "describe the website",
    "who is this for",
    "who is it for",
    "what is the purpose",
    "purpose of this",
    "why would i use",
    "why would someone use",
    "why should i use",
    "what kind of website",
    "what kind of site",
    "what kind of platform",
    "what is this about",
    "what is this website",
    "what is this site",
    "what is this platform",
    "explain it",
    "how does this work",
    "what does it do",
]

# ── Prompts ───────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful AI assistant embedded on a website.
Your job is to help visitors understand the website and answer their questions.

STRICT RULES — follow these without exception:
1. Answer ONLY using the context provided below. Never invent, assume, or add information.
2. For questions about what the website is, does, or offers — synthesize the context into a clear, natural explanation. Combine information from multiple sections if needed.
3. For specific factual questions — give precise, direct answers from the context.
4. When asked to explain simply or "like a beginner" — use plain, friendly language while staying factual.
5. If the answer is genuinely not in the context, say exactly:
   "I don't have that information. Please contact us directly for help."
6. Never answer general knowledge questions (capitals, sports, weather, etc.) — these are outside scope.
7. If the context only partially supports a claim, explicitly hedge using phrases like
    "Based on the available information..." or "The site suggests...".
8. Do NOT generalize company-wide policy from a single testimonial or quote.
    Treat testimonials as individual experiences unless a policy page confirms it.
    If evidence is only one person's statement, do NOT conclude or imply a
    company policy exists, even with hedging language.
    In those cases, state only what that individual said and explicitly note that
    no company-wide policy is confirmed in the provided context.
9. Do NOT present regional numbers (country, office, unit, or team) as global totals.
    If only regional data is present, label it clearly as regional.
10. Be concise and friendly. Avoid bullet-point dumps unless the question asks for a list."""


SUMMARY_SYSTEM_PROMPT = """You are an expert at understanding websites from their content.
Based ONLY on the provided website content, write a comprehensive but concise summary (150-250 words).

Cover ALL of the following that are present in the content:
- What the website/platform is
- What problem it solves or what it helps users do
- Main features or capabilities
- Who the intended users are
- Any other key details a new visitor would want to know

Be factual. Use only information present in the content. Do not invent features or make assumptions."""

# ── Singletons ────────────────────────────────────────────

groq_client = Groq(api_key=GROQ_API_KEY)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)

# ── In-memory response cache ──────────────────────────────

_response_cache: dict[tuple[str, str], str] = {}


# ── Groq call with retry ──────────────────────────────────

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
    Input:  [{"text": ..., "url": ..., "title": ...}]
    Output: [{"text": ..., "url": ..., "title": ...}]  (more items, shorter text)
    """
    chunks = []
    seen_texts = set()
    for page in pages:
        page_chunks = _splitter.split_text(page["text"])
        for chunk_text in page_chunks:
            normalized = chunk_text.strip().lower()[:200]
            if normalized in seen_texts:
                continue
            seen_texts.add(normalized)
            chunks.append({
                "text":  chunk_text,
                "url":   page.get("url", ""),
                "title": page.get("title", ""),
            })
    logger.info(f"[RAG] {len(pages)} pages → {len(chunks)} chunks (after dedup)")
    return chunks


def ingest_pages(pages: list[dict], collection_name: str) -> int:
    """
    Full ingestion pipeline (sync):
      1. Chunk pages
      2. Embed all chunks locally
      3. Create isolated Qdrant collection
      4. Store all vectors + metadata
    Returns number of chunks stored.
    """
    chunks = chunk_pages(pages)
    if not chunks:
        logger.warning("[RAG] No chunks to ingest — aborting")
        return 0

    logger.info(f"[RAG] Embedding {len(chunks)} chunks locally...")
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)
    logger.info("[RAG] Embedding complete")

    create_collection(collection_name)
    upsert_chunks(collection_name, chunks, embeddings)

    return len(chunks)


# ── Website Summary Generation ────────────────────────────

_PRIORITY_KEYWORDS = ["about", "home", "feature", "service", "faq",
                       "help", "overview", "pricing", "product", "what"]


def _select_key_pages(pages: list[dict], max_pages: int = 8) -> list[dict]:
    """Prioritise homepage / about / features pages for the summary."""
    priority, others = [], []
    for page in pages:
        url   = page.get("url", "").lower()
        title = page.get("title", "").lower()
        if any(kw in url or kw in title for kw in _PRIORITY_KEYWORDS):
            priority.append(page)
        else:
            others.append(page)
    return (priority + others)[:max_pages]


def generate_and_store_summary(
    pages: list[dict],
    collection_name: str,
    website_url: str,
) -> dict | None:
    """
    Generate a website-level summary using Groq and store it as a special
    Qdrant point so it can be retrieved for general "about this site" questions.
    Sync — designed to be called via run_in_executor.
    """
    key_pages = _select_key_pages(pages)
    if not key_pages:
        logger.warning("[RAG] No pages available for summary generation")
        return

    combined = ""
    for page in key_pages:
        text  = page.get("text", "").strip()[:2000]   # cap per page
        url   = page.get("url", "")
        title = page.get("title", "")
        combined += f"\n\n--- {title} ({url}) ---\n{text}"

    if not combined.strip():
        return

    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user",   "content": f"Website content:\n{combined}"},
    ]

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=400,
            temperature=0.1,
        )
        summary = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[RAG] Summary generation failed: {e}")
        return

    if not summary:
        return

    logger.info(f"[RAG] Generated website summary ({len(summary)} chars)")

    # Embed and store as a special point in Qdrant
    vector = embed_query(summary)
    upsert_single_point(
        collection_name=collection_name,
        point_id=SUMMARY_POINT_ID,
        vector=vector,
        payload={
            "text":       summary,
            "url":        website_url,
            "title":      "Website Summary",
            "is_summary": True,
        },
    )
    logger.info(f"[RAG] Website summary stored in '{collection_name}'")
    return {
        "summary": summary,
        "key_pages": key_pages,
    }


# ── Query Intent Detection ────────────────────────────────

def _is_general_question(question: str) -> bool:
    """
    Return True if the question is asking about the website as a whole
    (e.g. 'What is this website?', 'Tell me about this platform').
    Uses a fast keyword scan — no ML needed for this level of intent detection.
    """
    q = question.strip().lower()
    return any(trigger in q for trigger in _GENERAL_TRIGGERS)


# ── Query ─────────────────────────────────────────────────

def _stream_rag_uncached(question: str, collection_name: str) -> Generator[str, None, None]:
    """
    RAG query pipeline — yields response tokens streaming from Groq.

    Two retrieval strategies:
    - General question  → always include the website summary + broader chunk retrieval
    - Specific question → standard semantic search with score threshold
    """
    is_general = _is_general_question(question)
    query_vector = embed_query(question)

    if is_general:
        # Broader retrieval: get more chunks (homepage, about, features)
        results = search_chunks(collection_name, query_vector, limit=TOP_K + 3)

        # Always prepend the pre-generated summary for general questions
        summary_chunk = get_summary_chunk(collection_name)
        if summary_chunk:
            existing_texts = {r["text"] for r in results}
            if summary_chunk["text"] not in existing_texts:
                results = [summary_chunk] + results

        # For general questions use a lower score threshold — we want broad coverage
        results = [r for r in results if r.get("score", 1.0) > 0.1]
    else:
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

    if is_general:
        logger.info(f"[RAG] General question — using summary + {len(results)} chunks")
    else:
        logger.info(
            f"[RAG] Specific question — {len(results)} chunks "
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
    - First time: streams live from Groq, then caches the full response.
    - Repeated identical question: returns instantly from cache.
    """
    key = (question.strip().lower(), collection_name)

    cached = _response_cache.get(key)
    if cached is not None:
        logger.info(f"[RAG] Cache hit for '{question[:60]}'")
        yield cached
        return

    parts: list[str] = []
    for token in _stream_rag_uncached(question.strip(), collection_name):
        parts.append(token)
        yield token

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
