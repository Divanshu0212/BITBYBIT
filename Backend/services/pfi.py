"""
PFI Service — Professional Fidelity Index
──────────────────────────────────────────
Python port of the frontend pfiCalculator.js.
Implements:
• Weighted base score (milestone accuracy, deadline adherence, AQA avg, dispute rate)
• Glicko-2 rating system with simplified volatility update
• Combined final PFI score
• Database persistence with history tracking
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.pfi import PFIScore, PFIHistory

# ── Configuration ────────────────────────────────────────────────────────

PFI_WEIGHTS = {
    "completion_history": 0.35,  
    "quality_metrics": 0.30,     
    "reliability": 0.20,         
    "experience": 0.15,          
}

# ── Config ──────────────────────────────────────────────────────────────

def calculate_base_score(history: dict) -> float:
    """
    Calculate weighted base PFI score for credit-card style system.
    Returns a float from 0-100 which gets mapped to 200-900 later.
    """
    w = PFI_WEIGHTS

    total_jobs = history.get("total_jobs", 0)
    disputes = history.get("disputes", 0)
    completed = history.get("completed_milestones", 0)
    total_ms = history.get("total_milestones", 0)

    # 1. Completion & Dispute History
    ms_accuracy = (completed / total_ms * 100) if total_ms > 0 else 50
    dispute_penalty = (disputes / total_jobs * 100) if total_jobs > 0 else 0
    completion_score = max(0, ms_accuracy - (dispute_penalty * 2))

    # 2. Quality Metrics (AQA)
    aqa_scores = history.get("aqa_scores", [])
    quality_score = sum(aqa_scores) / len(aqa_scores) if aqa_scores else 50

    # 3. Reliability (Deadlines)
    deliveries = history.get("total_deliveries", 0)
    on_time = history.get("on_time_deliveries", 0)
    reliability_score = (on_time / deliveries * 100) if deliveries > 0 else 50

    # 4. Experience / Tenure
    experience_score = min(100, (total_ms / 50) * 100)

    base_100 = (
        completion_score * w["completion_history"]
        + quality_score * w["quality_metrics"]
        + reliability_score * w["reliability"]
        + experience_score * w["experience"]
    )
    return base_100


# ── Final PFI ────────────────────────────────────────────────────────────

def compute_final_pfi(base_100: float) -> int:
    """Map base score (0-100) to the 300-1000 robust credit score range."""
    pfi_score = 300 + (base_100 / 100) * 700
    return round(max(300, min(1000, pfi_score)))


def get_confidence_label(rd: int) -> str:
    if rd < 100:
        return "High"
    if rd < 200:
        return "Moderate"
    return "Low"


def get_risk_label(score: int) -> str:
    if score >= 850:
        return "Elite"
    if score >= 720:
        return "Trusted"
    if score >= 580:
        return "Established"
    if score >= 450:
        return "Developing"
    return "Unproven"


# ── Database Operations ──────────────────────────────────────────────────

async def get_pfi_score(db: AsyncSession, user_id: uuid.UUID) -> PFIScore | None:
    result = await db.execute(
        select(PFIScore).where(PFIScore.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_pfi_for_milestone(
    db: AsyncSession,
    user_id: uuid.UUID,
    history: dict,
    event_type: str = "MILESTONE_COMPLETED",
) -> PFIScore:
    """Full PFI recalculation after a milestone event."""
    pfi = await get_pfi_score(db, user_id)
    if not pfi:
        pfi = PFIScore(user_id=user_id)
        db.add(pfi)
        await db.flush()

    base = calculate_base_score(history)
    final = compute_final_pfi(base)

    pfi.score = final
    pfi.updated_at = datetime.now(timezone.utc)

    # Record history
    hist = PFIHistory(
        user_id=user_id,
        score=final,
        rating=1500,  # Legacy field unused
        event_type=event_type,
    )
    db.add(hist)
    await db.flush()
    return pfi


async def get_leaderboard(db: AsyncSession, limit: int = 50) -> list[PFIScore]:
    result = await db.execute(
        select(PFIScore).order_by(PFIScore.score.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_pfi_history(db: AsyncSession, user_id: uuid.UUID) -> list[PFIHistory]:
    result = await db.execute(
        select(PFIHistory)
        .where(PFIHistory.user_id == user_id)
        .order_by(PFIHistory.timestamp)
    )
    return list(result.scalars().all())
