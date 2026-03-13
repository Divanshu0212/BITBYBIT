"""
Escrow Routes — /api/escrow
────────────────────────────
Public escrow status and ledger retrieval (authenticated).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth import get_current_user
from models.escrow import EscrowAccount, LedgerEntry
from models.project import Project
from models.user import User
from schemas.escrow import EscrowResponse, LedgerEntryResponse, LedgerResponse
from services.escrow import get_escrow_by_project, verify_ledger_integrity

router = APIRouter(prefix="/api/escrow", tags=["Escrow"])


@router.get("/projects/{project_id}", response_model=EscrowResponse)
async def get_escrow(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Must be employer or assigned freelancer
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.employer_id != user.id and project.freelancer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    escrow = await get_escrow_by_project(db, project_id)
    if not escrow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No escrow for project")

    return EscrowResponse.model_validate(escrow)


@router.get("/projects/{project_id}/ledger", response_model=LedgerResponse)
async def get_ledger(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.employer_id != user.id and project.freelancer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    escrow = await get_escrow_by_project(db, project_id)
    if not escrow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No escrow for project")

    result = await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.escrow_id == escrow.id)
        .order_by(LedgerEntry.timestamp)
    )
    entries = result.scalars().all()

    return LedgerResponse(
        escrow=EscrowResponse.model_validate(escrow),
        entries=[LedgerEntryResponse.model_validate(e) for e in entries],
    )


@router.get("/projects/{project_id}/verify")
async def verify_integrity(
    project_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Verify the SHA-256 chain hash integrity of the escrow ledger."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.employer_id != user.id and project.freelancer_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    escrow = await get_escrow_by_project(db, project_id)
    if not escrow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No escrow for project")

    return await verify_ledger_integrity(db, escrow.id)
