"""
Freelancer Routes — /api/freelancer
─────────────────────────────────────
View assigned projects, activate milestones, submit work,
auto-trigger AQA evaluation, and view PFI scores.
All endpoints require freelancer role.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import require_role
from models.project import Milestone, Project
from models.pfi import HITLQueue
from models.user import User
from routes.auth import get_user_api_key
from schemas.project import ProjectResponse, WorkSubmission
from services import ai as ai_service
from services import escrow as escrow_service
from services import pfi as pfi_service

router = APIRouter(prefix="/api/freelancer", tags=["Freelancer"])

freelancer_dep = require_role("freelancer")


# ── Projects ─────────────────────────────────────────────────────────────

@router.get("/projects", response_model=list[ProjectResponse])
async def list_assigned_projects(
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Project)
        .where(Project.freelancer_id == user.id)
        .order_by(Project.created_at.desc())
    )
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project or project.freelancer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not assigned to you")
    return ProjectResponse.model_validate(project)


# ── Milestone Operations ─────────────────────────────────────────────────

@router.post("/projects/{project_id}/milestones/{milestone_id}/activate")
async def activate_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project or project.freelancer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    escrow = await escrow_service.get_escrow_by_project(db, project_id)
    if not escrow:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No escrow account for project")

    try:
        _, milestone = await escrow_service.activate_milestone(db, escrow.id, milestone_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"status": milestone.status, "milestone_id": str(milestone.id)}


@router.post("/projects/{project_id}/milestones/{milestone_id}/submit")
async def submit_work(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    data: WorkSubmission,
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project or project.freelancer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    escrow = await escrow_service.get_escrow_by_project(db, project_id)
    if not escrow:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No escrow account")

    milestone = await db.get(Milestone, milestone_id)
    if not milestone or milestone.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")

    # 1. Submit work
    try:
        await escrow_service.submit_work(db, escrow.id, milestone_id, data.submission_text, data.submission_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # 2. Move to AQA review
    await escrow_service.set_aqa_review(db, escrow.id, milestone_id)

    # 3. Run AI evaluation
    api_key = get_user_api_key(str(user.id))
    full_submission = data.submission_text
    if data.submission_url:
        full_submission += f"\n\nURL: {data.submission_url}"

    try:
        aqa_result = await ai_service.evaluate_submission(
            milestone_title=milestone.title,
            milestone_domain=milestone.domain or "General",
            acceptance_criteria=milestone.acceptance_criteria or [],
            submission=full_submission,
            api_key=api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AQA evaluation failed: {exc}")

    # Store AQA result
    await db.refresh(milestone)
    milestone.aqa_result = aqa_result

    # 4. Auto-action based on score
    overall_score = aqa_result.get("overallScore", 0)
    action_taken = ""

    if overall_score >= 60:
        # Auto-pay
        pct = 100 if aqa_result.get("paymentRecommendation") == "FULL_RELEASE" else (
            aqa_result.get("proRatedPercentage", aqa_result.get("percentComplete", 60))
        )
        await escrow_service.release_payment(db, escrow.id, milestone_id, pct)
        action_taken = f"PAID ({pct}%)"

        # Update PFI
        await _update_freelancer_pfi(db, user.id, project)

    elif overall_score < 40:
        # Auto-refund
        await escrow_service.initiate_refund(
            db, escrow.id, milestone_id,
            f"AQA score: {overall_score}/100 — {aqa_result.get('completionStatus', 'UNMET')}"
        )
        action_taken = "REFUND_INITIATED"

        await _update_freelancer_pfi(db, user.id, project)
    else:
        # 40-60 range: push to HITL queue
        hitl = HITLQueue(
            milestone_id=milestone_id,
            project_id=project_id,
            aqa_result=aqa_result,
            submission=full_submission,
        )
        db.add(hitl)
        action_taken = "HITL_QUEUED"

    await db.flush()

    return {
        "aqa_result": aqa_result,
        "action_taken": action_taken,
        "milestone_status": milestone.status,
    }


async def _update_freelancer_pfi(db: AsyncSession, user_id: uuid.UUID, project: Project):
    """Recalculate freelancer PFI after milestone completion."""
    milestones = list(project.milestones)
    terminal = {"PAID_FULL", "PAID_PARTIAL", "REFUND_INITIATED"}
    resolved = [m for m in milestones if m.status in terminal]

    aqa_scores = []
    for m in resolved:
        if m.aqa_result and "overallScore" in m.aqa_result:
            aqa_scores.append(m.aqa_result["overallScore"])

    history = {
        "completed_milestones": len([m for m in resolved if m.status in ("PAID_FULL", "PAID_PARTIAL")]),
        "total_milestones": len(milestones),
        "on_time_deliveries": len([m for m in resolved if m.status == "PAID_FULL"]),
        "total_deliveries": len(resolved),
        "aqa_scores": aqa_scores,
        "disputes": len([m for m in resolved if m.status == "REFUND_INITIATED"]),
        "total_jobs": len(resolved),
    }

    await pfi_service.update_pfi_for_milestone(db, user_id, history)


# ── PFI for Self ─────────────────────────────────────────────────────────

@router.get("/pfi")
async def get_own_pfi(
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    pfi = await pfi_service.get_pfi_score(db, user.id)
    if not pfi:
        return {"score": 50, "rating": 1500, "rd": 350, "volatility": 0.06, "confidence": "Low", "risk": "Moderate Risk"}

    return {
        "score": pfi.score,
        "rating": pfi.rating,
        "rd": pfi.rd,
        "volatility": pfi.volatility,
        "confidence": pfi_service.get_confidence_label(pfi.rd),
        "risk": pfi_service.get_risk_label(pfi.score),
    }


@router.get("/pfi/history")
async def get_pfi_history(
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    history = await pfi_service.get_pfi_history(db, user.id)
    return [
        {
            "score": h.score,
            "rating": h.rating,
            "event_type": h.event_type,
            "timestamp": h.timestamp.isoformat(),
        }
        for h in history
    ]
