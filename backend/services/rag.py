"""
RAG pipeline — text chunking, ingestion, and streaming query.
"""

import logging
from typing import Generator
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

    # Create collection and store
    create_collection(collection_name)
    upsert_chunks(collection_name, chunks, embeddings)

    return len(chunks)


# ── Query ─────────────────────────────────────────────────

def query_rag(question: str, collection_name: str) -> Generator[str, None, None]:
    """
    RAG query pipeline — yields response tokens as they stream from Groq.
    
    Flow:
      1. Embed question locally
      2. Cosine search Qdrant → top 5 chunks
      3. Build prompt: system prompt + context + question
      4. Stream Groq LLaMA 3 response token by token
    """
    # 1. Embed the question
    query_vector = embed_query(question)

    # 2. Search Qdrant
    results = search_chunks(collection_name, query_vector, limit=TOP_K)

    # Filter out low-relevance noise
    results = [r for r in results if r["score"] > 0.3]

    if not results:
        yield "I don't have enough information to answer that. Please contact us directly."
        return

    # 3. Build context block from retrieved chunks
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

    # 4. Stream from Groq
    logger.info(f"[RAG] Querying Groq with {len(results)} context chunks (top score: {results[0]['score']:.3f})")

    stream = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        stream=True,
        max_tokens=512,
        temperature=0.1,  # Low = factual, less creative
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta