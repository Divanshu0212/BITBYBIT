"""
AI Routes — /api/ai
────────────────────
Direct AI endpoints for decomposition, evaluation, demo generation,
skill matching, and bias detection. Authenticated.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from middleware.auth import get_current_user
from models.user import User
from routes.auth import get_user_api_key
from schemas.project import DecomposeRequest, FreelancerMatchRequest, WorkSubmission
from services import ai as ai_service

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/decompose")
async def decompose(
    data: DecomposeRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    if not data.description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Description required")
    api_key = get_user_api_key(str(user.id))
    try:
        return await ai_service.decompose_project(data.description, api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/evaluate")
async def evaluate(
    data: dict,
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Evaluate submitted work against milestone criteria.
    Body: { milestone_title, milestone_domain, acceptance_criteria: [...], submission }
    """
    api_key = get_user_api_key(str(user.id))
    try:
        return await ai_service.evaluate_submission(
            milestone_title=data.get("milestone_title", ""),
            milestone_domain=data.get("milestone_domain", ""),
            acceptance_criteria=data.get("acceptance_criteria", []),
            submission=data.get("submission", ""),
            api_key=api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/demo")
async def generate_demo(user: Annotated[User, Depends(get_current_user)]):
    api_key = get_user_api_key(str(user.id))
    try:
        return await ai_service.generate_demo_project(api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/score-match")
async def score_match(
    data: FreelancerMatchRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    api_key = get_user_api_key(str(user.id))
    try:
        return await ai_service.score_freelancer_match(data.skills, data.domain, api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/detect-bias")
async def detect_bias(
    data: dict,
    user: Annotated[User, Depends(get_current_user)],
):
    api_key = get_user_api_key(str(user.id))
    try:
        return await ai_service.detect_bias(data.get("rating_history", []), api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
