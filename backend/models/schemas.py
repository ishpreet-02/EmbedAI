"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Literal
from datetime import datetime

from services.origins import normalize_origin, validate_origin_format


# ── Auth Schemas ──────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str


# ── Chatbot Schemas ───────────────────────────────────────

class CreateChatbotRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    website_url: str = Field(..., min_length=5)


class UpdateChatbotRequest(BaseModel):
    allowed_origins: list[str]

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("Maximum 20 allowed origins")
        normalized: list[str] = []
        for origin in v:
            origin = origin.strip()
            if not origin:
                continue
            if not validate_origin_format(origin):
                raise ValueError(
                    f"Invalid origin: {origin}. Use format https://yourdomain.com"
                )
            norm = normalize_origin(origin)
            if norm not in normalized:
                normalized.append(norm)
        return normalized


class ChatbotResponse(BaseModel):
    id: str
    user_id: str
    name: str
    website_url: str
    status: str
    qdrant_collection: Optional[str] = None
    pages_indexed: Optional[int] = None
    chunks_stored: Optional[int] = None
    allowed_origins: list[str] = []
    created_at: str


class ChatbotStatusResponse(BaseModel):
    id: str
    status: str
    pages_indexed: Optional[int] = None
    chunks_stored: Optional[int] = None


# ── Chat Schemas ──────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    visitor_id: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str


class ConversationResponse(BaseModel):
    id: str
    chatbot_id: str
    visitor_id: str
    created_at: str
    message_count: Optional[int] = None
