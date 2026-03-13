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
    "milestone_accuracy": 0.35,
    "deadline_adherence": 0.25,
    "aqa_score_average": 0.25,
    "dispute_rate": 0.15,
}

GLICKO2_DEFAULTS = {
    "initial_rating": 1500,
    "initial_rd": 350,
    "initial_volatility": 0.06,
    "tau": 0.5,
}


# ── Base Score ───────────────────────────────────────────────────────────

def calculate_base_score(history: dict) -> int:
    """
    Calculate weighted base PFI score.
    history keys: completed_milestones, total_milestones, on_time_deliveries,
                  total_deliveries, aqa_scores (list[int]), disputes, total_jobs
    """
    w = PFI_WEIGHTS

    milestone_accuracy = (
        (history["completed_milestones"] / history["total_milestones"]) * 100
        if history["total_milestones"] > 0 else 50
    )
    deadline_adherence = (
        (history["on_time_deliveries"] / history["total_deliveries"]) * 100
        if history["total_deliveries"] > 0 else 50
    )
    aqa_scores = history.get("aqa_scores", [])
    aqa_average = (
        sum(aqa_scores) / len(aqa_scores)
        if aqa_scores else 50
    )
    dispute_rate = (
        (1 - history["disputes"] / history["total_jobs"]) * 100
        if history["total_jobs"] > 0 else 50
    )

    return round(
        milestone_accuracy * w["milestone_accuracy"]
        + deadline_adherence * w["deadline_adherence"]
        + aqa_average * w["aqa_score_average"]
        + dispute_rate * w["dispute_rate"]
    )


# ── Glicko-2 ─────────────────────────────────────────────────────────────

def apply_glicko2(
    rating: int, rd: int, volatility: float, outcomes: list[dict]
) -> dict:
    """
    Simplified Glicko-2 rating update.
    outcomes: list of { "score": 0-1, "expected": 0-1 }
    Returns: { "rating": int, "rd": int, "volatility": float }
    """
    tau = GLICKO2_DEFAULTS["tau"]

    if not outcomes:
        new_rd = min(math.sqrt(rd * rd + volatility * volatility), 350)
        return {"rating": rating, "rd": round(new_rd), "volatility": volatility}

    # Convert to Glicko-2 scale
    mu = (rating - 1500) / 173.7178
    phi = rd / 173.7178

    # Compute variance
    v_inv = 0.0
    delta_sum = 0.0
    for o in outcomes:
        e = o["expected"]
        g = 1 / math.sqrt(1 + 3 * phi * phi / (math.pi * math.pi))
        v_inv += g * g * e * (1 - e)
        delta_sum += g * (o["score"] - e)

    v = 1 / max(v_inv, 0.001)
    delta = v * delta_sum

    # Simplified volatility update (Illinois algorithm)
    a = math.log(volatility * volatility)
    delta_sq = delta * delta
    phi_sq = phi * phi

    def f(x):
        ex = math.exp(x)
        denom = 2 * (phi_sq + v + ex) ** 2
        return (ex * (delta_sq - phi_sq - v - ex)) / denom - (x - a) / (tau * tau)

    big_a = a
    if delta_sq > phi_sq + v:
        big_b = math.log(delta_sq - phi_sq - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        big_b = a - k * tau

    f_a = f(big_a)
    f_b = f(big_b)
    new_sigma = volatility

    for _ in range(20):
        c = big_a + (big_a - big_b) * f_a / (f_b - f_a)
        f_c = f(c)
        if f_c * f_b < 0:
            pass  # f_a stays
        else:
            f_a = f_a / 2
        new_sigma = math.exp(c / 2)
        if abs(c - big_a) < 0.0001:
            break
        big_a = c
        f_a = f_c

    new_sigma = max(0.01, min(new_sigma, 0.2))

    # Update phi and mu
    phi_star = math.sqrt(phi_sq + new_sigma * new_sigma)
    new_phi = 1 / math.sqrt(1 / (phi_star * phi_star) + 1 / v)
    new_mu = mu + new_phi * new_phi * (delta / v)

    return {
        "rating": round(173.7178 * new_mu + 1500),
        "rd": round(173.7178 * new_phi),
        "volatility": round(new_sigma, 3),
    }


# ── Final PFI ────────────────────────────────────────────────────────────

def compute_final_pfi(base_score: int, glicko_rating: int) -> int:
    """Combine base score (60%) and normalised Glicko-2 rating (40%)."""
    norm_glicko = max(0, min(100, ((glicko_rating - 1000) / 1000) * 100))
    return round(0.6 * base_score + 0.4 * norm_glicko)


def get_confidence_label(rd: int) -> str:
    if rd < 100:
        return "High"
    if rd < 200:
        return "Moderate"
    return "Low"


def get_risk_label(score: int) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Low Risk"
    if score >= 40:
        return "Moderate Risk"
    if score >= 20:
        return "High Risk"
    return "Extreme Risk"


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
    aqa_scores = history.get("aqa_scores", [])
    outcomes = [{"score": s / 100, "expected": 0.5} for s in aqa_scores]
    glicko = apply_glicko2(pfi.rating, pfi.rd, pfi.volatility, outcomes)
    final = compute_final_pfi(base, glicko["rating"])

    pfi.score = final
    pfi.rating = glicko["rating"]
    pfi.rd = glicko["rd"]
    pfi.volatility = glicko["volatility"]
    pfi.updated_at = datetime.now(timezone.utc)

    # Record history
    hist = PFIHistory(
        user_id=user_id,
        score=final,
        rating=glicko["rating"],
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
