"""
AI Chatbot SaaS Platform — FastAPI entry point.
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

from config import FRONTEND_URL
from routers import auth, chatbots, chat

# ── App ───────────────────────────────────────────────────

app = FastAPI(
    title="AI Chatbot SaaS Platform",
    description="Scrape any website → Build a RAG chatbot → Embed it anywhere",
    version="1.0.0",
    debug=os.getenv("DEBUG", "false").lower() == "true",
)

# ── Rate Limiter (slowapi) ────────────────────────────────

app.state.limiter = chat.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "*" # Allow all for the widget embed
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

# ── Health check ──────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "service": "AI Chatbot SaaS Platform"}


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "AI Chatbot SaaS Platform API",
        "docs": "/docs",
        "health": "/health",
    }
