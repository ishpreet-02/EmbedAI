"""
EmbedAI — FastAPI entry point.
"""

import logging
import traceback

# Show all logs in terminal
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import os

from config import get_cors_origins
from routers import auth, chatbots, chat

# ── App ───────────────────────────────────────────────────

app = FastAPI(
    title="EmbedAI",
    description="Scrape any website → Build a RAG chatbot → Embed it anywhere",
    version="1.0.0",
    debug=os.getenv("DEBUG", "false").lower() == "true",
    redirect_slashes=False,
)

# ── Rate Limiter (slowapi) ────────────────────────────────

app.state.limiter = chat.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────
# Regex covers Vercel preview URLs + customer sites embedding the widget.
# Explicit origins from FRONTEND_URL / CORS_ORIGINS cover the dashboard.

CORS_ORIGIN_REGEX = r"https?://.*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Visitor-Id", "X-Conversation-Id"],
)

# ── Routers ───────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(chatbots.router)
app.include_router(chat.router)

# ── Static Files (Widget) ─────────────────────────────────

# Serve widget.js — checks multiple paths:
# 1. Docker mount at /app/static/widget.js
# 2. Backend's own widget/ directory (for Render deploy)
# 3. Local dev path (../widget/chatbot-widget.js)
WIDGET_DOCKER_PATH = os.path.join(os.path.dirname(__file__), "static", "widget.js")
WIDGET_BACKEND_PATH = os.path.join(os.path.dirname(__file__), "widget", "chatbot-widget.js")
WIDGET_LOCAL_PATH = os.path.join(os.path.dirname(__file__), "..", "widget", "chatbot-widget.js")

if os.path.exists("widget"):
    app.mount("/widget-assets", StaticFiles(directory="widget"), name="widget")


@app.get("/widget.js", include_in_schema=False)
async def serve_widget_js():
    """Serve the embeddable chat widget script."""
    for path in [WIDGET_DOCKER_PATH, WIDGET_BACKEND_PATH, WIDGET_LOCAL_PATH]:
        if os.path.exists(path):
            return FileResponse(
                path,
                media_type="application/javascript",
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*",
                },
            )
    return JSONResponse(
        status_code=404,
        content={"detail": "widget.js not found"},
    )

# ── Exception handler (shows full errors in dev) ─────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    response = JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
    # Ensure CORS headers on error responses (browser otherwise reports a CORS failure)
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# ── Health check ──────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "service": "EmbedAI"}


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "EmbedAI API",
        "docs": "/docs",
        "health": "/health",
    }
