"""
Verification Schemas — Typed contracts for decomposition + AQA
──────────────────────────────────────────────────────────────
Pydantic models that validate AI output and standardize the
AQA result shape across all modalities.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Literal


# ── Decomposition Output Schemas ─────────────────────────────────────────

class ProjectClassification(BaseModel):
    primary_type: Literal["code", "content", "design", "mixed"]
    type_confidence: float = Field(ge=0, le=1)
    secondary_types: list[str] = []
    complexity: Literal["simple", "medium", "complex"] = "medium"
    ambiguity_score: float = Field(ge=0, le=1, default=0.0)


class ClarificationQuestion(BaseModel):
    id: str
    priority: int = 1
    question: str
    reason: str = ""


class Clarification(BaseModel):
    required: bool = False
    questions: list[ClarificationQuestion] = []
    assumptions_if_unanswered: list[str] = []


class AcceptanceCriterionSpec(BaseModel):
    id: str
    criterion: str
    metric: str = ""
    target: str = ""
    verification_method: str = "manual_review"  # unit_test|lint|security_scan|plagiarism_check|readability_check|fact_check|wcag_check|visual_diff|manual_review
    auto_verifiable: bool = False
    evidence_required: list[str] = []


class MilestoneSpec(BaseModel):
    id: str
    title: str
    description: str = ""
    task_type: Literal["code", "content", "design", "mixed"]
    dependencies: list[str] = []
    estimated_days: int = Field(ge=1)
    payment_percentage: float = Field(ge=0, le=100)
    definition_of_done: str = ""
    acceptance_criteria: list[AcceptanceCriterionSpec] = Field(min_length=1)
    scoring_weights: dict[str, float] = {}


class DAGEdge(BaseModel):
    """from/to use milestone id strings like 'M1', 'M2'."""
    source: str = Field(alias="from", default="")
    target: str = Field(alias="to", default="")

    model_config = {"populate_by_name": True}


class VerificationPolicy(BaseModel):
    pass_threshold: int = 85
    partial_threshold_min: int = 50
    inconclusive_on_missing_evidence: bool = True
    confidence_threshold_for_human_review: float = 0.7


class DecompositionResult(BaseModel):
    """Full validated output from the AAPPA decomposition prompt."""
    project_classification: ProjectClassification
    clarification: Clarification = Clarification()
    milestones: list[MilestoneSpec] = Field(min_length=1, max_length=12)
    dag: list[DAGEdge] = []
    global_verification_policy: VerificationPolicy = VerificationPolicy()
    risk_flags: list[str] = []

    # Computed helpers (not from AI)
    totalEstimatedDays: int | None = None
    projectRiskLevel: str | None = None

    @field_validator("milestones")
    @classmethod
    def check_payment_sums(cls, v):
        total = sum(m.payment_percentage for m in v)
        if abs(total - 100) > 1.0:  # 1% tolerance for rounding
            # Auto-normalise instead of rejecting
            for m in v:
                m.payment_percentage = round(m.payment_percentage * 100 / total, 2)
        return v


# ── AQA Result Schemas (standardized contract) ──────────────────────────

MODALITY_WEIGHTS = {
    "code": {
        "correctness": 40, "security": 20,
        "test_coverage": 20, "maintainability": 20,
    },
    "content": {
        "factuality": 30, "originality": 25,
        "readability": 20, "seo_structure": 15, "style_alignment": 10,
    },
    "design": {
        "requirements_coverage": 25, "visual_consistency": 25,
        "accessibility": 20, "responsive_completeness": 20, "export_readiness": 10,
    },
}


class CriterionEval(BaseModel):
    criterion: str
    met: bool
    score: int = Field(ge=0, le=100)
    feedback: str = ""
    verification_method: str = "llm_review"
    evidence_present: bool = False


class ModalityScores(BaseModel):
    """Sub-scores split by source."""
    deterministic: dict[str, float] = {}   # tool-derived scores
    llm: dict[str, float] = {}             # LLM-derived scores
    weights: dict[str, float] = {}         # applied weights


class AQAResult(BaseModel):
    """Standardized AQA result contract across all modalities."""
    overallScore: int = Field(ge=0, le=100)
    completionStatus: Literal["FULLY_COMPLETED", "PARTIALLY_COMPLETED", "UNMET"]
    paymentRecommendation: Literal["FULL_RELEASE", "PRO_RATED", "REFUND"]
    proRatedPercentage: int = Field(ge=0, le=100, default=0)
    percentComplete: int = Field(ge=0, le=100, default=0)

    # New fields
    modality: str = "mixed"
    confidence: float = Field(ge=0, le=1, default=0.5)
    evidenceCompleteness: float = Field(ge=0, le=1, default=0.0)
    modalityScores: ModalityScores = ModalityScores()

    criteriaEvaluation: list[CriterionEval] = []
    detailedFeedback: str = ""
    remediationChecklist: list[str] = []
    riskFlags: list[str] = []
