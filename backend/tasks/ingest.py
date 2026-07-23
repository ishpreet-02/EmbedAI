"""
Background ingestion task.
Runs scraping and vector ingestion in a Celery worker.
"""

import asyncio
import logging
from datetime import datetime, timezone
from celery_app import celery_app
from services.scraper import scrape_website
from services.rag import ingest_pages, generate_and_store_summary, clear_response_cache_for_collection
from services.database import get_supabase

logger = logging.getLogger(__name__)


async def run_ingestion(chatbot_id: str, website_url: str, collection_name: str):
    """
    Full ingestion pipeline (runs in background):
    1. Update status to 'processing'
    2. Scrape the website
    3. Chunk + embed + store in Qdrant  ← Week 3
    4. Update status to 'ready' or 'failed'
    """
    supabase = get_supabase()

    try:
        # ── Step 1: Mark as processing ────────────────────
        supabase.table("chatbots").update({
            "status": "processing",
            "website_summary": None,
            "key_pages": None,
            "summary_generated_at": None,
        }).eq("id", chatbot_id).execute()

        logger.info(f"[Ingest] Starting scrape for chatbot {chatbot_id}: {website_url}")

        # ── Step 2: Scrape the website ────────────────────
        pages = await scrape_website(website_url)

        if not pages:
            logger.warning(f"[Ingest] No pages scraped from {website_url}")
            supabase.table("chatbots").update({
                "status": "failed",
                "pages_indexed": 0,
                "chunks_stored": 0,
            }).eq("id", chatbot_id).execute()
            return

        logger.info(f"[Ingest] Scraped {len(pages)} pages from {website_url}")

        # ── Step 3: Chunk → Embed → Store in Qdrant ──────
        # ingest_pages is CPU-bound (sentence-transformers runs on CPU).
        # run_in_executor moves it off the async event loop so other
        # requests aren't blocked while embeddings are computed.
        logger.info(f"[Ingest] Starting RAG ingestion into collection: {collection_name}")

        loop = asyncio.get_event_loop()
        chunks_stored = await loop.run_in_executor(
            None,           # Default ThreadPoolExecutor
            ingest_pages,   # Sync function
            pages,          # arg 1
            collection_name # arg 2
        )

        if chunks_stored == 0:
            logger.warning(f"[Ingest] Ingestion produced 0 chunks — marking failed")
            supabase.table("chatbots").update({
                "status": "failed",
                "pages_indexed": len(pages),
                "chunks_stored": 0,
            }).eq("id", chatbot_id).execute()
            return

        logger.info(f"[Ingest] Stored {chunks_stored} chunks in Qdrant")

        # ── Step 3.5: Generate + store website summary ────
        # Uses Groq to create a comprehensive description of the whole site.
        # Stored as a special Qdrant point so general questions ('what is this?')
        # always receive a high-quality, coherent answer.
        logger.info(f"[Ingest] Generating website summary for {website_url}")
        try:
            summary_payload = await loop.run_in_executor(
                None,
                generate_and_store_summary,
                pages,
                collection_name,
                website_url,
            )
            if summary_payload and summary_payload.get("summary"):
                supabase.table("chatbots").update({
                    "website_summary": summary_payload["summary"],
                    "key_pages": summary_payload.get("key_pages"),
                    "summary_generated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", chatbot_id).execute()
        except Exception as sum_err:
            # Non-fatal — chatbot still works without summary
            logger.warning(f"[Ingest] Summary generation failed (non-fatal): {sum_err}")

        clear_response_cache_for_collection(collection_name)

        # ── Step 4: Mark as ready ─────────────────────────
        supabase.table("chatbots").update({
            "status": "ready",
            "pages_indexed": len(pages),
            "chunks_stored": chunks_stored,
        }).eq("id", chatbot_id).execute()

        logger.info(
            f"[Ingest] DONE — Chatbot {chatbot_id} ready! "
            f"({len(pages)} pages, {chunks_stored} chunks)"
        )

    except Exception as e:
        logger.error(f"[Ingest] Failed for chatbot {chatbot_id}: {e}", exc_info=True)
        supabase.table("chatbots").update({
            "status": "failed",
        }).eq("id", chatbot_id).execute()


@celery_app.task(name="tasks.ingest.run_ingestion_task")
def run_ingestion_task(chatbot_id: str, website_url: str, collection_name: str):
    """
    Celery entrypoint for website ingestion.

    The core pipeline stays async because scraping uses Playwright. Celery calls this
    sync wrapper in a separate worker process.
    """
    logger.info(f"[Celery] Queue worker started ingestion for chatbot {chatbot_id}")
    asyncio.run(run_ingestion(chatbot_id, website_url, collection_name))
    logger.info(f"[Celery] Queue worker finished ingestion for chatbot {chatbot_id}")
