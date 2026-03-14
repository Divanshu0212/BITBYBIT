"""
Design Verification Schemas — Typed contracts for design-specific AQA
─────────────────────────────────────────────────────────────────────
Defines the request/response models for POST /api/design/verify-design
and internal design verification pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class DesignMilestoneRequirements(BaseModel):
    milestone_title: str
    milestone_description: str = ""
    definition_of_done: str = ""
    required_screens: list[str] = []
    required_components: list[str] = []
    style_reference: str | None = None


class DesignToolUrl(BaseModel):
    platform: str
    url: str


class DesignMetrics(BaseModel):
    """Precomputed design metrics (can be auto-computed or supplied)."""
    total_urls: int = Field(ge=0, default=0)
    design_tool_urls: list[DesignToolUrl] = []
    design_tool_count: int = Field(ge=0, default=0)
    export_formats: list[str] = []
    export_format_count: int = Field(ge=0, default=0)
    accessibility_signal_count: int = Field(ge=0, default=0)
    responsive_signal_count: int = Field(ge=0, default=0)
    color_spec_count: int = Field(ge=0, default=0)
    typography_spec_count: int = Field(ge=0, default=0)
    screen_mention_count: int = Field(ge=0, default=0)
    component_mention_count: int = Field(ge=0, default=0)
    design_system_signal_count: int = Field(ge=0, default=0)
    screen_coverage: float = Field(ge=0, le=1, default=1.0)
    component_coverage: float = Field(ge=0, le=1, default=1.0)
    word_count: int = Field(ge=0, default=0)


class FigmaMetadata(BaseModel):
    file_name: str = ""
    last_modified: str = ""
    page_count: int = 0
    page_names: list[str] = []
    frame_count: int = 0
    frame_names: list[str] = []
    component_count: int = 0
    component_names: list[str] = []


class DesignScores(BaseModel):
    requirements_coverage: int = Field(ge=0, le=100)
    visual_consistency: int = Field(ge=0, le=100)
    accessibility: int = Field(ge=0, le=100)
    responsive_completeness: int = Field(ge=0, le=100)
    export_readiness: int = Field(ge=0, le=100)


class DesignVerificationRequest(BaseModel):
    """Payload for POST /api/design/verify-design."""
    project_id: str
    milestone_id: str
    milestone_requirements: DesignMilestoneRequirements
    freelancer_submission: str = Field(min_length=1, max_length=50000)
    design_metrics: DesignMetrics | None = None


class DesignVerificationResponse(BaseModel):
    """Structured output from the design verification pipeline."""
    project_id: str
    milestone_id: str
    scores: DesignScores
    composite_milestone_score: float = Field(ge=0, le=100)
    verdict: Literal["FULLY_COMPLETED", "PARTIALLY_COMPLETED", "UNMET"]
    payout_percentage: float = Field(ge=0, le=100)
    major_issues: list[str] = []
    improvement_suggestions: list[str] = []
    confidence: float = Field(ge=0, le=1)

    evaluation_status: str = "EVALUATED"
    metrics_used: DesignMetrics | None = None
    figma_metadata: FigmaMetadata | None = None
