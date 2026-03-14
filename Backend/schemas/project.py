from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, date
from typing import Any, Optional


class ProjectCreate(BaseModel):
    description: str = Field(min_length=10, max_length=5000)
    budget: float | None = Field(None, gt=0)
    deadline: date | None = None


class ProjectFund(BaseModel):
    amount: float = Field(gt=0, le=1_000_000)


class MilestoneResponse(BaseModel):
    id: UUID
    index: int
    title: str
    description: str | None = None
    domain: str | None = None
    estimated_days: int | None = None
    complexity_score: int | None = None
    acceptance_criteria: list[str] | None = None
    task_type: str | None = None
    scoring_weights: dict | None = None
    verification_profile: dict | None = None
    status: str
    payment_amount: float
    payment_released: float
    submission: str | None = None
    submission_url: str | None = None
    aqa_result: dict | None = None

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: UUID
    employer_id: UUID
    freelancer_id: UUID | None = None
    description: str
    budget: float | None = None
    deadline: date | None = None
    status: str
    risk_level: str | None = None
    total_estimated_days: int | None = None
    decomposition: dict | None = None
    project_type: str | None = None
    created_at: datetime
    milestones: list[MilestoneResponse] = []

    model_config = {"from_attributes": True}


class DecomposeRequest(BaseModel):
    description: str | None = None  # Override project description


class WorkSubmission(BaseModel):
    submission_text: str = Field(min_length=1, max_length=10000)
    submission_url: str | None = Field(None, max_length=1000)
    repo_url: str | None = Field(None, max_length=500, description="GitHub repo URL (mandatory for code milestones)")
    commit_hash: str | None = Field(None, max_length=64, description="Exact commit hash to verify")


class HITLResolveRequest(BaseModel):
    action: str = Field(pattern="^(approve|full_pay|refund|resubmit)$")
    reason: str | None = None


class DemoProjectResponse(BaseModel):
    employer: dict
    freelancer: dict
    project_description: str


class FreelancerMatchRequest(BaseModel):
    skills: list[str]
    domain: str


class ProposalCreate(BaseModel):
    cover_letter: str = Field(min_length=20, max_length=5000)
    bid_amount: float | None = Field(None, gt=0)
    estimated_days: int | None = Field(None, gt=0)


class ProposalResponse(BaseModel):
    id: UUID
    project_id: UUID
    freelancer_id: UUID
    cover_letter: str
    bid_amount: float | None = None
    estimated_days: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    # Populated in the route
    freelancer_name: str | None = None
    freelancer_email: str | None = None
    freelancer_skills: list[str] | None = None
    freelancer_bio: str | None = None
    freelancer_pfi_score: int | None = None

    model_config = {"from_attributes": True}
