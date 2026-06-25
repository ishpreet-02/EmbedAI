"""
Centralized Supabase client — lazy initialization.
Allows the server to start even if SUPABASE_URL is not yet configured.
"""

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

_client: Client | None = None


def get_supabase() -> Client:
    """Return the Supabase client, creating it on first call."""
    global _client
    if _client is None:
        if not SUPABASE_URL or SUPABASE_URL == "your_supabase_url_here":
            raise RuntimeError(
                "Supabase is not configured. "
                "Set SUPABASE_URL and SUPABASE_KEY in backend/.env"
            )
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
