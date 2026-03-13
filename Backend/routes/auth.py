"""
Auth Routes — /api/auth
───────────────────────
Registration, login, profile, and API key management.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import create_access_token, get_current_user
from models.user import User
from schemas.auth import GroqKeyUpdate, TokenResponse, UserLogin, UserRegister, UserResponse
from services.auth import authenticate_user, register_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# In-memory per-user Groq key store (production would use encrypted DB column)
_user_api_keys: dict[str, str] = {}


def _build_user_response(user: User, profile=None) -> UserResponse:
    # Use passed profile or try to access it (may be None for employers)
    if profile is None:
        try:
            profile = user.freelancer_profile
        except Exception:
            profile = None
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at,
        skills=profile.skills if profile else None,
        bio=profile.bio if profile else None,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        user = await register_user(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    token = create_access_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user=_build_user_response(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        user = await authenticate_user(db, data.email, data.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    token = create_access_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user=_build_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return _build_user_response(user)


@router.put("/api-key", status_code=status.HTTP_204_NO_CONTENT)
async def set_api_key(
    data: GroqKeyUpdate,
    user: Annotated[User, Depends(get_current_user)],
):
    """Store Groq API key for the current session."""
    _user_api_keys[str(user.id)] = data.api_key


def get_user_api_key(user_id: str) -> str | None:
    """Retrieve stored API key for a user."""
    return _user_api_keys.get(user_id)
