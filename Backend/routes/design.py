"""
Design Verification Routes — /api/design
──────────────────────────────────────────
Standalone design quality verification endpoint
and milestone-integrated design verification.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import require_role
from models.project import Milestone, Project
from models.user import User
from routes.auth import get_user_api_key
from schemas.design_verification import (
    DesignVerificationRequest,
    DesignVerificationResponse,
)
from services import design_verifier

router = APIRouter(prefix="/api/design", tags=["Design Verification"])


@router.post("/verify-design", response_model=DesignVerificationResponse)
async def verify_design(
    data: DesignVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("employer", "freelancer"))],
):
    """
    Standalone design quality verification.

    Flow:
    1. Receive submission + milestone requirements
    2. Compute design metrics locally (or use supplied metrics)
    3. Optionally enrich via Figma API metadata
    4. Run 5-dimension evaluation (deterministic + LLM)
    5. Return structured JSON with CMS, verdict, payout%
    6. If project_id/milestone_id map to real records, store result
    """
    api_key = get_user_api_key(str(user.id))

    metrics_dict = data.design_metrics.model_dump() if data.design_metrics else None

    result = await design_verifier.verify_design(
        project_id=data.project_id,
        milestone_id=data.milestone_id,
        milestone_requirements=data.milestone_requirements.model_dump(),
        freelancer_submission=data.freelancer_submission,
        design_metrics=metrics_dict,
        api_key=api_key,
    )

    if result.get("evaluation_status") in ("INSUFFICIENT_DATA", "INCOMPLETE_SUBMISSION"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result,
        )

    await _persist_if_exists(db, data.project_id, data.milestone_id, result)

    return DesignVerificationResponse(**result)


@router.post(
    "/projects/{project_id}/milestones/{milestone_id}/verify",
    response_model=DesignVerificationResponse,
)
async def verify_milestone_design(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("employer", "freelancer"))],
):
    """
    Verify design for an existing milestone using its stored submission
    and acceptance criteria.  Useful for re-verification or employer review.
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.employer_id != user.id and project.freelancer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised for this project")

    milestone = await db.get(Milestone, milestone_id)
    if not milestone or milestone.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")

    if not milestone.submission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No submission to verify — freelancer has not submitted work yet",
        )

    v_profile = milestone.verification_profile or {}
    requirements = {
        "milestone_title": milestone.title,
        "milestone_description": milestone.description or "",
        "definition_of_done": v_profile.get("definition_of_done", ""),
        "required_screens": _extract_required_screens(milestone),
        "required_components": _extract_required_components(milestone),
        "style_reference": None,
    }

    api_key = get_user_api_key(str(user.id))

    result = await design_verifier.verify_design(
        project_id=str(project_id),
        milestone_id=str(milestone_id),
        milestone_requirements=requirements,
        freelancer_submission=milestone.submission,
        api_key=api_key,
    )

    milestone.aqa_result = result
    await db.flush()

    return DesignVerificationResponse(**result)


# ── Helpers ──────────────────────────────────────────────────────────────

def _extract_required_screens(milestone: Milestone) -> list[str]:
    """Derive required screens from acceptance criteria."""
    screens = []
    v_profile = milestone.verification_profile or {}
    screen_keywords = ("screen", "page", "view", "layout", "mockup", "wireframe", "design")

    for ac in v_profile.get("structured_criteria", []):
        if isinstance(ac, dict):
            criterion = ac.get("criterion", "")
            if any(kw in criterion.lower() for kw in screen_keywords):
                screens.append(criterion)

    return screens[:15]


def _extract_required_components(milestone: Milestone) -> list[str]:
    """Derive required components from acceptance criteria."""
    components = []
    v_profile = milestone.verification_profile or {}
    comp_keywords = ("component", "button", "form", "icon", "nav", "card", "modal", "input")

    for ac in v_profile.get("structured_criteria", []):
        if isinstance(ac, dict):
            criterion = ac.get("criterion", "")
            if any(kw in criterion.lower() for kw in comp_keywords):
                components.append(criterion)

    return components[:15]


async def _persist_if_exists(
    db: AsyncSession,
    project_id: str,
    milestone_id: str,
    result: dict,
) -> None:
    """Store the verification result on the milestone if it exists in DB."""
    try:
        pid = uuid.UUID(project_id)
        mid = uuid.UUID(milestone_id)
    except (ValueError, AttributeError):
        return

    milestone = await db.get(Milestone, mid)
    if milestone and milestone.project_id == pid:
        milestone.aqa_result = result
        await db.flush()
