"""
Employer Routes — /api/employer
────────────────────────────────
Project creation, AI decomposition, funding, proposal review,
HITL resolution, and analytics. All endpoints require employer role.
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
from models.escrow import EscrowAccount
from models.pfi import HITLQueue, PFIScore
from models.user import User, FreelancerProfile
from models.proposal import Proposal
from routes.auth import get_user_api_key
from schemas.project import (
    ClarifyRequest,
    DecomposeRequest,
    HITLResolveRequest,
    ProjectCreate,
    ProjectFund,
    ProjectResponse,
    ProposalResponse,
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
    created = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(Project.id == project.id)
    )
    return ProjectResponse.model_validate(created.scalar_one())


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
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
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(Project.id == project_id, Project.employer_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.delete("/projects/{project_id}", status_code=status.HTTP_200_OK)
async def delete_project(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a project. Only allowed for projects that are not active (no ongoing work)."""
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.status == "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an active project with ongoing work. Complete or cancel it first.",
        )

    await db.delete(project)
    await db.flush()
    return {"status": "deleted", "project_id": str(project_id)}


# ── Clarity Check ────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/clarify")
async def clarify_project(
    project_id: uuid.UUID,
    body: ClarifyRequest,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Check if a project description needs clarification before decomposition."""
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    api_key = get_user_api_key(str(user.id))
    description = body.description or project.description

    try:
        result = await ai_service.check_clarity(description, api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return result


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

    if body.clarification_answers:
        qa_block = "\n\nClarification Q&A:\n" + "\n".join(
            f"Q: {a.question}\nA: {a.answer}"
            for a in body.clarification_answers
        )
        description = description + qa_block

    try:
        result = await ai_service.decompose_project(description, api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Update project with classification
    project.decomposition = result
    project.risk_level = result.get("projectRiskLevel", "Medium")
    project.total_estimated_days = result.get("totalEstimatedDays")
    project.status = "decomposed"

    # Persist project-level classification
    classification = result.get("project_classification", {})
    project.project_type = classification.get("primary_type", "mixed")

    # Clear old milestones and create new ones
    existing = await db.execute(select(Milestone).where(Milestone.project_id == project_id))
    for ms in existing.scalars().all():
        await db.delete(ms)
    await db.flush()

    # Build verification policy from result
    verification_policy = result.get("global_verification_policy", {})

    for i, ms_data in enumerate(result.get("milestones", [])):
        # Extract structured acceptance criteria
        raw_criteria = ms_data.get("acceptance_criteria", ms_data.get("acceptanceCriteria", []))
        # Flatten for storage: keep both structured form in verification_profile and flat strings
        flat_criteria = []
        structured_criteria = []
        for ac in raw_criteria:
            if isinstance(ac, dict):
                flat_criteria.append(ac.get("criterion", str(ac)))
                structured_criteria.append(ac)
            else:
                flat_criteria.append(str(ac))
                structured_criteria.append({"id": f"C{len(structured_criteria)+1}", "criterion": str(ac)})

        # Build verification profile for this milestone
        v_profile = {
            "structured_criteria": structured_criteria,
            "policy": verification_policy,
            "definition_of_done": ms_data.get("definition_of_done", ""),
        }

        ms = Milestone(
            project_id=project.id,
            index=i,
            title=ms_data.get("title", f"Milestone {i+1}"),
            description=ms_data.get("description"),
            domain=ms_data.get("task_type", ms_data.get("domain", "mixed")),
            estimated_days=ms_data.get("estimated_days", ms_data.get("estimatedDays")),
            complexity_score=ms_data.get("complexityScore", 5),
            acceptance_criteria=flat_criteria,
            task_type=ms_data.get("task_type", project.project_type),
            scoring_weights=ms_data.get("scoring_weights"),
            verification_profile=v_profile,
            status="PENDING",
        )
        db.add(ms)

    await db.flush()
    # Re-fetch with milestones eagerly loaded for safe serialization
    refreshed = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(Project.id == project.id)
    )
    return ProjectResponse.model_validate(refreshed.scalar_one())


# ── Publish for Proposals ─────────────────────────────────────────────────

@router.post("/projects/{project_id}/publish", response_model=ProjectResponse)
async def publish_project(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Publish a decomposed project so freelancers can browse and submit proposals.
    Escrow is created later when a proposal is accepted (with the freelancer's bid amount)."""
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.status not in ("decomposed", "draft"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project must be decomposed before publishing")

    project.status = "funded"
    await db.flush()
    refreshed = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(Project.id == project.id)
    )
    return ProjectResponse.model_validate(refreshed.scalar_one())


@router.post("/projects/{project_id}/fund", response_model=ProjectResponse)
async def fund_project(
    project_id: uuid.UUID,
    data: ProjectFund,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Legacy funding endpoint kept for backward compatibility."""
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.status not in ("decomposed", "draft"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project must be decomposed before funding")

    project.budget = data.amount
    project.status = "funded"
    await db.flush()
    refreshed = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(Project.id == project.id)
    )
    return ProjectResponse.model_validate(refreshed.scalar_one())


# ── Proposal Management ─────────────────────────────────────────────────

@router.get("/projects/{project_id}/proposals")
async def list_proposals(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all proposals for a specific project (employer view)."""
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(Proposal)
        .where(Proposal.project_id == project_id)
        .order_by(Proposal.created_at.desc())
    )
    proposals = result.scalars().all()

    output = []
    for prop in proposals:
        # Get freelancer info
        freelancer = await db.get(User, prop.freelancer_id)
        pfi_result = await db.execute(
            select(PFIScore).where(PFIScore.user_id == prop.freelancer_id)
        )
        pfi = pfi_result.scalar_one_or_none()
        profile = freelancer.freelancer_profile if freelancer else None

        output.append({
            "id": str(prop.id),
            "project_id": str(prop.project_id),
            "freelancer_id": str(prop.freelancer_id),
            "cover_letter": prop.cover_letter,
            "bid_amount": prop.bid_amount,
            "estimated_days": prop.estimated_days,
            "status": prop.status,
            "created_at": prop.created_at.isoformat(),
            "updated_at": prop.updated_at.isoformat(),
            "freelancer_name": freelancer.name if freelancer else None,
            "freelancer_email": freelancer.email if freelancer else None,
            "freelancer_skills": profile.skills if profile else [],
            "freelancer_bio": profile.bio if profile else None,
            "freelancer_pfi_score": pfi.score if pfi else 50,
        })
    return output


@router.post("/projects/{project_id}/proposals/{proposal_id}/accept", response_model=ProjectResponse)
async def accept_proposal(
    project_id: uuid.UUID,
    proposal_id: uuid.UUID,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Accept a proposal — assigns the freelancer and activates the project."""
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.freelancer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project already has an assigned freelancer")

    proposal = await db.get(Proposal, proposal_id)
    if not proposal or proposal.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Proposal is not pending")

    # Verify freelancer exists
    freelancer = await db.get(User, proposal.freelancer_id)
    if not freelancer or freelancer.role != "freelancer":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Freelancer not found")

    # Accept this proposal
    proposal.status = "accepted"

    # Reject all other pending proposals for this project
    other_proposals = await db.execute(
        select(Proposal).where(
            Proposal.project_id == project_id,
            Proposal.id != proposal_id,
            Proposal.status == "pending",
        )
    )
    for other in other_proposals.scalars().all():
        other.status = "rejected"

    # Assign freelancer to the project
    project.freelancer_id = proposal.freelancer_id
    project.status = "active"

    # Create escrow with the freelancer's bid amount (or project budget as fallback)
    escrow_amount = proposal.bid_amount or project.budget
    if not escrow_amount or escrow_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot accept: proposal has no bid amount and project has no budget set.",
        )

    project.budget = escrow_amount

    escrow = await escrow_service.get_escrow_by_project(db, project_id)
    if not escrow:
        escrow = await escrow_service.create_escrow(db, project_id)
    try:
        await escrow_service.deposit_funds(db, escrow.id, escrow_amount)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.flush()
    refreshed = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(Project.id == project.id)
    )
    return ProjectResponse.model_validate(refreshed.scalar_one())


@router.post("/projects/{project_id}/proposals/{proposal_id}/reject")
async def reject_proposal(
    project_id: uuid.UUID,
    proposal_id: uuid.UUID,
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Reject a single proposal."""
    project = await db.get(Project, project_id)
    if not project or project.employer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    proposal = await db.get(Proposal, proposal_id)
    if not proposal or proposal.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Proposal is not pending")

    proposal.status = "rejected"
    await db.flush()
    return {"status": "rejected", "proposal_id": str(proposal_id)}


# ── Legacy: Direct Freelancer Assignment (kept for backward compat) ──────

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
    refreshed = await db.execute(
        select(Project)
        .options(selectinload(Project.milestones))
        .where(Project.id == project.id)
    )
    return ProjectResponse.model_validate(refreshed.scalar_one())


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


# ── Freelancer Listing (kept for backward compat) ───────────────────────

@router.get("/freelancers")
async def list_freelancers(
    user: Annotated[User, Depends(employer_dep)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all freelancers with their PFI scores."""
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

    # Count proposals
    total_proposals = 0

    for p in all_projects:
        escrow = await escrow_service.get_escrow_by_project(db, p.id)
        if escrow:
            total_in_escrow += escrow.locked_funds
            total_released += escrow.released_funds
            total_refunded += escrow.refunded_funds

        # Count proposals for this project
        prop_count = await db.execute(
            select(func.count(Proposal.id)).where(Proposal.project_id == p.id)
        )
        total_proposals += prop_count.scalar() or 0

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
        "totalProposals": total_proposals,
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
