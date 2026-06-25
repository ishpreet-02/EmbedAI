"""
Directly test run_ingestion function to see any errors or logging.
"""
import asyncio
import logging
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout)

from tasks.ingest import run_ingestion
from services.database import get_supabase

async def test():
    supabase = get_supabase()
    # Create a temporary chatbot to test
    result = supabase.table("chatbots").insert({
        "user_id": "5fbda703-944f-444a-b7d1-6d219fabbb3b",
        "name": "Direct Test Bot",
        "website_url": "https://books.toscrape.com",
        "status": "pending",
        "qdrant_collection": "test_direct_coll",
    }).execute()
    
    chatbot = result.data[0]
    chatbot_id = chatbot["id"]
    print(f"Created temp chatbot: {chatbot_id}")
    
    try:
        await run_ingestion(chatbot_id, "https://books.toscrape.com", "test_direct_coll")
    finally:
        # Cleanup
        supabase.table("chatbots").delete().eq("id", chatbot_id).execute()
        print("Cleaned up temp chatbot")

if __name__ == "__main__":
    asyncio.run(test())
