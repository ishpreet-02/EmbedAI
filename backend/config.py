"""
Application configuration — loads environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Supabase ──────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# ── JWT ───────────────────────────────────────────────────
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES: int = int(os.getenv("JWT_EXPIRATION_MINUTES", "1440"))

# ── Groq LLM ─────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# ── Qdrant ────────────────────────────────────────────
QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")  # Set for Qdrant Cloud

# ── Redis / Celery ───────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── CORS ──────────────────────────────────────────────────
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Comma-separated extra origins, e.g. "https://getembedai.vercel.app,https://preview.vercel.app"
_CORS_ORIGINS_RAW: str = os.getenv("CORS_ORIGINS", "")


def get_cors_origins() -> list[str]:
    """Explicit origins always allowed (dashboard + local dev)."""
    origins = [
        FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]
    if _CORS_ORIGINS_RAW:
        origins.extend(o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip())
    return list(dict.fromkeys(origins))
