"""
PFI Routes — /api/pfi
──────────────────────
PFI scores, leaderboard, and history. Authenticated.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import get_current_user
from models.user import User
from services import pfi as pfi_service

router = APIRouter(prefix="/api/pfi", tags=["PFI"])


@router.get("/scores/{user_id}")
async def get_pfi_score(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    pfi = await pfi_service.get_pfi_score(db, user_id)
    if not pfi:
        return {
            "user_id": str(user_id),
            "score": 50,
            "rating": 1500,
            "rd": 350,
            "volatility": 0.06,
            "confidence": "Low",
            "risk": "Moderate Risk",
        }

    return {
        "user_id": str(pfi.user_id),
        "score": pfi.score,
        "rating": pfi.rating,
        "rd": pfi.rd,
        "volatility": pfi.volatility,
        "confidence": pfi_service.get_confidence_label(pfi.rd),
        "risk": pfi_service.get_risk_label(pfi.score),
    }


@router.get("/leaderboard")
async def get_leaderboard(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
):
    entries = await pfi_service.get_leaderboard(db, limit)
    return [
        {
            "user_id": str(e.user_id),
            "score": e.score,
            "rating": e.rating,
            "rd": e.rd,
            "confidence": pfi_service.get_confidence_label(e.rd),
            "risk": pfi_service.get_risk_label(e.score),
        }
        for e in entries
    ]


@router.get("/history/{user_id}")
async def get_pfi_history(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    history = await pfi_service.get_pfi_history(db, user_id)
    return [
        {
            "score": h.score,
            "rating": h.rating,
            "event_type": h.event_type,
            "timestamp": h.timestamp.isoformat(),
        }
        for h in history
    ]
