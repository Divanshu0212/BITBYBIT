"""
Content Verification Routes — /api/content
────────────────────────────────────────────
Standalone content quality verification endpoint
and milestone-integrated content verification.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import require_role
from models.project import Milestone, Project
from models.user import User
from routes.auth import get_user_api_key
from schemas.content_verification import (
    ContentVerificationRequest,
    ContentVerificationResponse,
)
from services import content_verifier

router = APIRouter(prefix="/api/content", tags=["Content Verification"])


@router.post("/verify-content", response_model=ContentVerificationResponse)
async def verify_content(
    data: ContentVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("employer", "freelancer"))],
):
    """
    Standalone content quality verification.

    Flow:
    1. Receive submission + milestone requirements
    2. Compute metrics locally (or use supplied metrics)
    3. Run 7-step evaluation (deterministic + LLM)
    4. Return structured JSON with CMS, verdict, payout%
    5. If project_id/milestone_id map to real records, store result
    """
    api_key = get_user_api_key(str(user.id))

    metrics_dict = data.content_metrics.model_dump() if data.content_metrics else None

    result = await content_verifier.verify_content(
        project_id=data.project_id,
        milestone_id=data.milestone_id,
        milestone_requirements=data.milestone_requirements.model_dump(),
        freelancer_submission=data.freelancer_submission,
        content_metrics=metrics_dict,
        api_key=api_key,
    )

    if result.get("evaluation_status") in ("INSUFFICIENT_DATA", "INCOMPLETE_SUBMISSION"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result,
        )

    # Persist result if milestone exists in DB
    await _persist_if_exists(db, data.project_id, data.milestone_id, result)

    return ContentVerificationResponse(**result)


@router.post(
    "/projects/{project_id}/milestones/{milestone_id}/verify",
    response_model=ContentVerificationResponse,
)
async def verify_milestone_content(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("employer", "freelancer"))],
):
    """
    Verify content for an existing milestone using its stored submission
    and acceptance criteria. Useful for re-verification or employer review.
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
        "required_keywords": _extract_keywords(milestone),
        "target_audience": "general",
        "required_sections": _extract_required_sections(milestone),
    }

    api_key = get_user_api_key(str(user.id))

    result = await content_verifier.verify_content(
        project_id=str(project_id),
        milestone_id=str(milestone_id),
        milestone_requirements=requirements,
        freelancer_submission=milestone.submission,
        api_key=api_key,
    )

    milestone.aqa_result = result
    await db.flush()

    return ContentVerificationResponse(**result)


# ── Helpers ──────────────────────────────────────────────────────────────

def _extract_keywords(milestone: Milestone) -> list[str]:
    """Pull keywords from acceptance criteria and verification profile."""
    keywords = []
    v_profile = milestone.verification_profile or {}

    for ac in v_profile.get("structured_criteria", []):
        if isinstance(ac, dict):
            criterion = ac.get("criterion", "")
            for word in criterion.split():
                if len(word) > 5 and word.isalpha():
                    keywords.append(word.lower())

    return list(set(keywords))[:20]


def _extract_required_sections(milestone: Milestone) -> list[str]:
    """Derive required sections from acceptance criteria."""
    sections = []
    v_profile = milestone.verification_profile or {}
    for ac in v_profile.get("structured_criteria", []):
        if isinstance(ac, dict):
            criterion = ac.get("criterion", "")
            if any(kw in criterion.lower() for kw in ("section", "heading", "include", "cover", "address")):
                sections.append(criterion)

    return sections[:10]


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
