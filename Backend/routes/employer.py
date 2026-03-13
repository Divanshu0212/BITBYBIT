"""
Employer Routes — /api/employer
────────────────────────────────
Project creation, AI decomposition, funding, freelancer assignment,
HITL resolution, and analytics. All endpoints require employer role.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import require_role
from models.project import Milestone, Project
from models.escrow import EscrowAccount
from models.pfi import HITLQueue, PFIScore
from models.user import User, FreelancerProfile
from routes.auth import get_user_api_key
from schemas.project import (
    DecomposeRequest,
    HITLResolveRequest,
    ProjectCreate,
    ProjectFund,
    ProjectResponse,
)
from services import ai as ai_service
from services import escrow as escrow_service

router = APIRouter(prefix="/api/employer", tags=["Employer"])

employer_dep = require_role("employer")


# ── Projects ─────────────────────────────────────────────────────────────

@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = Project(
        employer_id=user.id,
        description=data.description,
        budget=data.budget,
        deadline=data.deadline,
        status="draft",
    )
    db.add(project)
    await db.flush()
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Project)
        .where(Project.employer_id == user.id)
        .order_by(Project.created_at.desc())
    )
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


# ── AI Decomposition ────────────────────────────────────────────────────

@router.post("/projects/{project_id}/decompose", response_model=ProjectResponse)
async def decompose_project(
    project_id: uuid.UUID,
    body: DecomposeRequest,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    api_key = get_user_api_key(str(user.id))
    description = body.description or project.description

    try:
        result = await ai_service.decompose_project(description, api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Update project
    project.decomposition = result
    project.risk_level = result.get("projectRiskLevel", "Medium")
    project.total_estimated_days = result.get("totalEstimatedDays")
    project.status = "decomposed"

    # Clear old milestones and create new ones
    await db.execute(
        select(Milestone).where(Milestone.project_id == project_id)
    )
    # Delete existing milestones
    existing = await db.execute(select(Milestone).where(Milestone.project_id == project_id))
    for ms in existing.scalars().all():
        await db.delete(ms)
    await db.flush()

    for i, ms_data in enumerate(result.get("milestones", [])):
        ms = Milestone(
            project_id=project.id,
            index=i,
            title=ms_data.get("title", f"Milestone {i+1}"),
            description=ms_data.get("description"),
            domain=ms_data.get("domain"),
            estimated_days=ms_data.get("estimatedDays"),
            complexity_score=ms_data.get("complexityScore", 5),
            acceptance_criteria=ms_data.get("acceptanceCriteria", []),
            status="PENDING",
        )
        db.add(ms)

    await db.flush()
    # Re-fetch to get milestones
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


# ── Funding ──────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/fund", response_model=ProjectResponse)
async def fund_project(
    project_id: uuid.UUID,
    data: ProjectFund,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.status not in ("decomposed", "draft"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project must be decomposed before funding")

    # Create or get escrow
    escrow = await escrow_service.get_escrow_by_project(db, project_id)
    if not escrow:
        escrow = await escrow_service.create_escrow(db, project_id)

    try:
        await escrow_service.deposit_funds(db, escrow.id, data.amount)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    project.budget = data.amount
    project.status = "funded"
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


# ── Freelancer Assignment ────────────────────────────────────────────────

@router.post("/projects/{project_id}/assign/{freelancer_id}", response_model=ProjectResponse)
async def assign_freelancer(
    project_id: uuid.UUID,
    freelancer_id: uuid.UUID,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Verify freelancer exists and is a freelancer
    freelancer = await db.get(User, freelancer_id)
    if not freelancer or freelancer.role != "freelancer":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Freelancer not found")

    project.freelancer_id = freelancer_id
    project.status = "active" if project.status == "funded" else project.status
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


# ── HITL Resolution ──────────────────────────────────────────────────────

@router.post("/projects/{project_id}/hitl/{milestone_id}/resolve")
async def resolve_hitl(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    data: HITLResolveRequest,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    escrow = await escrow_service.get_escrow_by_project(db, project_id)
    if not escrow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No escrow for project")

    milestone = await db.get(Milestone, milestone_id)
    if not milestone or milestone.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")

    # Resolve the HITL queue entry
    result = await db.execute(
        select(HITLQueue).where(
            HITLQueue.milestone_id == milestone_id,
            HITLQueue.status == "pending",
        )
    )
    hitl = result.scalar_one_or_none()
    if hitl:
        hitl.status = "resolved"
        hitl.resolution = data.action
        hitl.resolution_reason = data.reason
        hitl.resolved_by = user.id

    try:
        if data.action == "approve":
            aqa = milestone.aqa_result or {}
            pct = aqa.get("proRatedPercentage", aqa.get("percentComplete", 50))
            await escrow_service.release_payment(db, escrow.id, milestone_id, pct)
        elif data.action == "full_pay":
            await escrow_service.release_payment(db, escrow.id, milestone_id, 100)
        elif data.action == "refund":
            await escrow_service.initiate_refund(db, escrow.id, milestone_id, data.reason or "HITL override: refund")
        elif data.action == "resubmit":
            milestone.status = "IN_PROGRESS"
            milestone.submission = None
            milestone.submission_url = None
            escrow.state = "MILESTONE_ACTIVE"
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.flush()
    return {"status": "resolved", "action": data.action}


# ── Freelancer Listing ───────────────────────────────────────────────────

@router.get("/freelancers")
async def list_freelancers(
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all freelancers with their PFI scores for assignment."""
    result = await db.execute(
        select(User).where(User.role == "freelancer")
    )
    freelancers = result.scalars().all()
    output = []
    for fl in freelancers:
        profile = fl.freelancer_profile
        # Get PFI score
        pfi_result = await db.execute(
            select(PFIScore).where(PFIScore.user_id == fl.id)
        )
        pfi = pfi_result.scalar_one_or_none()
        output.append({
            "id": str(fl.id),
            "name": fl.name,
            "email": fl.email,
            "skills": profile.skills if profile else [],
            "bio": profile.bio if profile else None,
            "pfi_score": pfi.score if pfi else 50,
            "pfi_rating": pfi.rating if pfi else 1500,
        })
    return output


# ── HITL Queue for Project ───────────────────────────────────────────────

@router.get("/projects/{project_id}/hitl")
async def list_hitl_items(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List pending HITL items for a specific project."""
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(HITLQueue).where(
            HITLQueue.project_id == project_id,
            HITLQueue.status == "pending",
        )
    )
    items = result.scalars().all()
    return [
        {
            "id": str(item.id),
            "milestone_id": str(item.milestone_id),
            "project_id": str(item.project_id),
            "aqa_result": item.aqa_result,
            "submission": item.submission,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


# ── Analytics ────────────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Count projects
    proj_result = await db.execute(
        select(func.count(Project.id)).where(Project.employer_id == user.id)
    )
    total_projects = proj_result.scalar() or 0

    # Fetch all employer projects and their milestones
    projects = await db.execute(
        select(Project).where(Project.employer_id == user.id)
    )
    all_projects = list(projects.scalars().all())

    total_milestones = 0
    activated = 0
    submitted = 0
    aqa_passed = 0
    paid = 0
    total_in_escrow = 0.0
    total_released = 0.0
    total_refunded = 0.0

    for p in all_projects:
        escrow = await escrow_service.get_escrow_by_project(db, p.id)
        if escrow:
            total_in_escrow += escrow.locked_funds
            total_released += escrow.released_funds
            total_refunded += escrow.refunded_funds

        for ms in p.milestones:
            total_milestones += 1
            if ms.status != "PENDING":
                activated += 1
            if ms.status in ("WORK_SUBMITTED", "AQA_REVIEW", "PAID_FULL", "PAID_PARTIAL", "REFUND_INITIATED"):
                submitted += 1
            if ms.status in ("PAID_FULL", "PAID_PARTIAL"):
                aqa_passed += 1
            if ms.status == "PAID_FULL":
                paid += 1

    return {
        "totalProjects": total_projects,
        "totalMilestones": total_milestones,
        "totalInEscrow": round(total_in_escrow, 2),
        "totalReleased": round(total_released, 2),
        "totalRefunded": round(total_refunded, 2),
        "funnel": {
            "activated": activated,
            "submitted": submitted,
            "aqaPassed": aqa_passed,
            "paid": paid,
        },
    }
