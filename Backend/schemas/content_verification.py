"""
Content Verification Schemas — Typed contracts for content-specific AQA
────────────────────────────────────────────────────────────────────────
Defines the request/response models for POST /api/verify-content
and internal content verification pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class MilestoneRequirements(BaseModel):
    milestone_title: str
    milestone_description: str = ""
    definition_of_done: str = ""
    required_keywords: list[str] = []
    target_audience: str = "general"
    required_sections: list[str] = []
    optional_style_reference: str | None = None


class ContentMetrics(BaseModel):
    """Precomputed content metrics (can be auto-computed or supplied)."""
    word_count: int = Field(ge=0)
    paragraph_count: int = Field(ge=0)
    readability_score: float = Field(ge=0, le=100)
    grammar_error_count: int = Field(ge=0)
    similarity_ratio: float = Field(ge=0, le=1)
    keyword_coverage: float = Field(ge=0, le=1)


class ContentVerificationRequest(BaseModel):
    """Payload for POST /api/verify-content."""
    project_id: str
    milestone_id: str
    milestone_requirements: MilestoneRequirements
    freelancer_submission: str = Field(min_length=1, max_length=50000)
    content_metrics: ContentMetrics | None = None


class ContentScores(BaseModel):
    requirement_coverage: int = Field(ge=0, le=100)
    structure: int = Field(ge=0, le=100)
    content_quality: int = Field(ge=0, le=100)
    readability: int = Field(ge=0, le=100)
    originality: int = Field(ge=0, le=100)
    grammar: int = Field(ge=0, le=100)
    keyword_coverage: int = Field(ge=0, le=100)


class ContentVerificationResponse(BaseModel):
    """Structured output from the content verification pipeline."""
    project_id: str
    milestone_id: str
    scores: ContentScores
    composite_milestone_score: float = Field(ge=0, le=100)
    verdict: Literal["FULLY_COMPLETED", "PARTIALLY_COMPLETED", "UNMET"]
    payout_percentage: float = Field(ge=0, le=100)
    major_issues: list[str] = []
    improvement_suggestions: list[str] = []
    confidence: float = Field(ge=0, le=1)

    evaluation_status: str = "EVALUATED"
    metrics_used: ContentMetrics | None = None
