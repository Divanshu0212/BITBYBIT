"""
Freelancer Routes — /api/freelancer
─────────────────────────────────────
Browse open projects, submit proposals, view assigned projects,
activate milestones, submit work, auto-trigger AQA evaluation,
and view PFI scores. All endpoints require freelancer role.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import require_role
from models.project import Milestone, Project
from models.pfi import HITLQueue
from models.user import User
from models.proposal import Proposal
from routes.auth import get_user_api_key
from schemas.project import ProjectResponse, WorkSubmission, ProposalCreate
from services import ai as ai_service
from services import escrow as escrow_service
from services import pfi as pfi_service
from services import verification_engine

router = APIRouter(prefix="/api/freelancer", tags=["Freelancer"])

freelancer_dep = require_role("freelancer")


# ── Browse Open Projects ─────────────────────────────────────────────────

@router.get("/open-projects")
async def list_open_projects(
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Browse projects that are funded and open for proposals (no freelancer assigned yet)."""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(
            Project.status == "funded",
            Project.freelancer_id.is_(None),
        )
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    output = []
    for p in projects:
        # Check if this freelancer has already submitted a proposal
        existing_prop = await db.execute(
            select(Proposal).where(
                Proposal.project_id == p.id,
                Proposal.freelancer_id == user.id,
            )
        )
        has_proposed = existing_prop.scalar_one_or_none() is not None

        # Count proposals for the project
        prop_count = await db.execute(
            select(func.count(Proposal.id)).where(Proposal.project_id == p.id)
        )
        proposal_count = prop_count.scalar() or 0

        # Get employer name
        employer = await db.get(User, p.employer_id)

        output.append({
            "id": str(p.id),
            "description": p.description,
            "budget": p.budget,
            "deadline": p.deadline.isoformat() if p.deadline else None,
            "status": p.status,
            "risk_level": p.risk_level,
            "total_estimated_days": p.total_estimated_days,
            "created_at": p.created_at.isoformat(),
            "milestone_count": len(p.milestones),
            "milestones": [
                {
                    "title": ms.title,
                    "domain": ms.domain,
                    "estimated_days": ms.estimated_days,
                    "complexity_score": ms.complexity_score,
                }
                for ms in sorted(p.milestones, key=lambda m: m.index)
            ],
            "employer_name": employer.name if employer else "Unknown",
            "proposal_count": proposal_count,
            "has_proposed": has_proposed,
        })
    return output


# ── Proposals ────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/propose")
async def submit_proposal(
    project_id: uuid.UUID,
    data: ProposalCreate,
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Submit a proposal for an open project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.status != "funded":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is not accepting proposals")
    if project.freelancer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project already has an assigned freelancer")

    # Check for existing proposal
    existing = await db.execute(
        select(Proposal).where(
            Proposal.project_id == project_id,
            Proposal.freelancer_id == user.id,
            Proposal.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a pending proposal for this project")

    proposal = Proposal(
        project_id=project_id,
        freelancer_id=user.id,
        cover_letter=data.cover_letter,
        bid_amount=data.bid_amount,
        estimated_days=data.estimated_days,
    )
    db.add(proposal)
    await db.flush()

    return {
        "id": str(proposal.id),
        "project_id": str(proposal.project_id),
        "status": proposal.status,
        "message": "Proposal submitted successfully!",
    }


@router.get("/proposals")
async def list_own_proposals(
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all proposals submitted by the current freelancer."""
    result = await db.execute(
        select(Proposal)
        .where(Proposal.freelancer_id == user.id)
        .order_by(Proposal.created_at.desc())
    )
    proposals = result.scalars().all()

    output = []
    for prop in proposals:
        # Get project info
        project = await db.get(Project, prop.project_id)
        employer = await db.get(User, project.employer_id) if project else None

        output.append({
            "id": str(prop.id),
            "project_id": str(prop.project_id),
            "cover_letter": prop.cover_letter,
            "bid_amount": prop.bid_amount,
            "estimated_days": prop.estimated_days,
            "status": prop.status,
            "created_at": prop.created_at.isoformat(),
            "project_description": project.description if project else None,
            "project_budget": project.budget if project else None,
            "employer_name": employer.name if employer else "Unknown",
        })
    return output


@router.delete("/proposals/{proposal_id}")
async def withdraw_proposal(
    proposal_id: uuid.UUID,
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Withdraw a pending proposal."""
    proposal = await db.get(Proposal, proposal_id)
    if not proposal or proposal.freelancer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending proposals can be withdrawn")

    proposal.status = "withdrawn"
    await db.flush()
    return {"status": "withdrawn", "proposal_id": str(proposal_id)}


# ── Assigned Projects ────────────────────────────────────────────────────

@router.get("/projects", response_model=list[ProjectResponse])
async def list_assigned_projects(
    user: Annotated[User, Depends(freelancer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
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
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(Project.id == project_id, Project.freelancer_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
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

    # 3. Run verification engine (modality-aware)
    api_key = get_user_api_key(str(user.id))
    full_submission = data.submission_text
    if data.submission_url:
        full_submission += f"\n\nURL: {data.submission_url}"

    try:
        aqa_result = await verification_engine.orchestrate_verification(
            milestone_title=milestone.title,
            milestone_domain=milestone.domain or "General",
            task_type=milestone.task_type,
            acceptance_criteria=milestone.acceptance_criteria or [],
            scoring_weights=milestone.scoring_weights,
            submission=full_submission,
            api_key=api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Verification failed: {exc}")

    # Store AQA result
    await db.refresh(milestone)
    milestone.aqa_result = aqa_result

    # 4. Action based on verification engine decision
    decision = aqa_result.get("decision", {})
    action = decision.get("action", "HITL")
    action_taken = ""

    if action == "FULL_PAY":
        await escrow_service.release_payment(db, escrow.id, milestone_id, 100)
        action_taken = "PAID (100%)"
        await _update_freelancer_pfi(db, user.id, project.id)

    elif action == "PARTIAL_PAY":
        pct = decision.get("recommended_pct", 50)
        await escrow_service.release_payment(db, escrow.id, milestone_id, pct)
        action_taken = f"PAID ({pct}%)"
        await _update_freelancer_pfi(db, user.id, project.id)

    elif action == "REFUND":
        reason = decision.get("reason", "Score below minimum threshold")
        await escrow_service.initiate_refund(db, escrow.id, milestone_id, reason)
        action_taken = "REFUND_INITIATED"
        await _update_freelancer_pfi(db, user.id, project.id)

    else:
        # HITL — low confidence or insufficient evidence
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


async def _update_freelancer_pfi(db: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID):
    """Recalculate freelancer PFI after milestone completion."""
    ms_result = await db.execute(
        select(Milestone).where(Milestone.project_id == project_id)
    )
    milestones = ms_result.scalars().all()
    terminal = {"PAID_FULL", "PAID_PARTIAL", "REFUND_INITIATED"}
    resolved = [m for m in milestones if m.status in terminal]

    aqa_scores = []
    for m in resolved:
        if m.aqa_result and "overallScore" in m.aqa_result:
            aqa_scores.append(m.aqa_result["overallScore"])

    on_time_count = 0
    for m in resolved:
        if m.status in ("PAID_FULL", "PAID_PARTIAL"):
            if m.started_at and m.submitted_at and m.estimated_days:
                elapsed_days = (m.submitted_at - m.started_at).total_seconds() / 86400
                if elapsed_days <= m.estimated_days:
                    on_time_count += 1
            elif m.status == "PAID_FULL":
                on_time_count += 1

    history = {
        "completed_milestones": len([m for m in resolved if m.status in ("PAID_FULL", "PAID_PARTIAL")]),
        "total_milestones": len(milestones),
        "on_time_deliveries": on_time_count,
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
        return {"score": 500, "risk": "Developing"}

    return {
        "score": pfi.score,
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
            "event_type": h.event_type,
            "timestamp": h.timestamp.isoformat(),
        }
        for h in history
    ]
