"""
Auth router — signup, login, me.
"""

import asyncio

from fastapi import APIRouter, HTTPException, status, Depends
from passlib.context import CryptContext

from models.schemas import SignupRequest, LoginRequest, AuthResponse, UserResponse
from middleware.auth import create_access_token, get_current_user
from services.database import get_supabase

router = APIRouter(prefix="/api/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    """Create a new user account and return a JWT."""
    supabase = get_supabase()

    # Check if email already exists
    existing = await asyncio.to_thread(
        lambda: supabase.table("users").select("id").eq("email", body.email).execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash password and insert user
    hashed = pwd_context.hash(body.password)
    result = await asyncio.to_thread(
        lambda: supabase.table("users").insert({
            "email": body.email,
            "password": hashed,
        }).execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

    user = result.data[0]
    token = create_access_token({"sub": user["id"], "email": user["email"]})

    return AuthResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "created_at": user["created_at"]},
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    """Authenticate user and return a JWT."""
    supabase = get_supabase()

    result = await asyncio.to_thread(
        lambda: supabase.table("users").select("*").eq("email", body.email).execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = result.data[0]

    try:
        is_valid = pwd_context.verify(body.password, user["password"])
    except Exception:
        is_valid = False

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user["id"], "email": user["email"]})

    return AuthResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "created_at": user["created_at"]},
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user."""
    supabase = get_supabase()

    result = await asyncio.to_thread(
        lambda: (
            supabase.table("users")
            .select("id, email, created_at")
            .eq("id", current_user["id"])
            .execute()
        )
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user = result.data[0]
    return UserResponse(
        id=user["id"],
        email=user["email"],
        created_at=str(user["created_at"]),
    )