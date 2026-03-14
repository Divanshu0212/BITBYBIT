"""
Content Quality Verification Agent — 7-Step Evaluation Pipeline
───────────────────────────────────────────────────────────────
Evaluates freelancer-submitted written deliverables against
milestone requirements using a hybrid deterministic + LLM approach.

Deterministic scores: structure, originality, grammar, keyword_coverage
LLM-evaluated scores: requirement_coverage, content_quality, readability

CMS weights:
    requirement_coverage = 25%
    structure            = 15%
    content_quality      = 20%
    readability          = 10%
    originality          = 15%
    grammar              = 10%
    keyword_coverage     =  5%
"""

import logging
import re

from services import ai as ai_service
from services.content_metrics import compute_content_metrics

logger = logging.getLogger(__name__)

CMS_WEIGHTS = {
    "requirement_coverage": 0.25,
    "structure": 0.15,
    "content_quality": 0.20,
    "readability": 0.10,
    "originality": 0.15,
    "grammar": 0.10,
    "keyword_coverage": 0.05,
}


# ── Public API ───────────────────────────────────────────────────────────

async def verify_content(
    project_id: str,
    milestone_id: str,
    milestone_requirements: dict,
    freelancer_submission: str,
    content_metrics: dict | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Full content verification pipeline.

    1. Compute metrics (if not supplied)
    2. Score deterministic dimensions
    3. Score LLM-evaluated dimensions
    4. Compute CMS
    5. Determine verdict
    6. Return structured JSON
    """
    if not freelancer_submission or not freelancer_submission.strip():
        return _error_response(project_id, milestone_id, "INCOMPLETE_SUBMISSION")

    title = milestone_requirements.get("milestone_title", "")
    if not title:
        return _error_response(project_id, milestone_id, "INSUFFICIENT_DATA")

    # 1 — Compute metrics locally
    required_keywords = milestone_requirements.get("required_keywords", [])
    if content_metrics is None:
        content_metrics = compute_content_metrics(
            freelancer_submission,
            required_keywords=required_keywords,
        )

    # 2 — Deterministic scores
    det_scores = _compute_deterministic_scores(content_metrics, milestone_requirements)

    # 3 — LLM-evaluated scores
    llm_scores, llm_meta = await _evaluate_with_llm(
        project_id, milestone_id,
        milestone_requirements, content_metrics,
        freelancer_submission, api_key,
    )

    # 4 — Merge scores (deterministic overrides for rule-based dimensions)
    scores = {
        "requirement_coverage": llm_scores.get("requirement_coverage", det_scores.get("requirement_coverage", 50)),
        "structure": det_scores["structure"],
        "content_quality": llm_scores.get("content_quality", 50),
        "readability": _blend_readability(
            det_scores["readability"], llm_scores.get("readability", det_scores["readability"])
        ),
        "originality": det_scores["originality"],
        "grammar": det_scores["grammar"],
        "keyword_coverage": det_scores["keyword_coverage"],
    }

    # 5 — Composite Milestone Score
    cms = sum(scores[k] * CMS_WEIGHTS[k] for k in CMS_WEIGHTS)
    cms = round(cms, 1)

    # 6 — Verdict
    verdict, payout = _determine_verdict(
        cms, scores["requirement_coverage"], scores["originality"],
        milestone_requirements, freelancer_submission,
    )

    # 7 — Issues and suggestions
    major_issues = _detect_major_issues(scores, content_metrics, milestone_requirements)
    suggestions = llm_meta.get("improvement_suggestions", [])
    if not suggestions:
        suggestions = _generate_improvement_suggestions(scores, content_metrics)

    confidence = _compute_confidence(scores, content_metrics, llm_meta)

    return {
        "project_id": project_id,
        "milestone_id": milestone_id,
        "scores": scores,
        "composite_milestone_score": cms,
        "verdict": verdict,
        "payout_percentage": payout,
        "major_issues": major_issues,
        "improvement_suggestions": suggestions,
        "confidence": confidence,
        "evaluation_status": "EVALUATED",
        "metrics_used": content_metrics,
    }


# ── Step 2: Deterministic Scoring ────────────────────────────────────────

def _compute_deterministic_scores(metrics: dict, requirements: dict) -> dict:
    return {
        "requirement_coverage": _score_requirement_coverage_heuristic(metrics, requirements),
        "structure": _score_structure(metrics, requirements),
        "readability": _score_readability(metrics, requirements),
        "originality": _score_originality(metrics["similarity_ratio"]),
        "grammar": _score_grammar(metrics["grammar_error_count"], metrics["word_count"]),
        "keyword_coverage": _score_keyword_coverage(metrics["keyword_coverage"]),
    }


def _score_requirement_coverage_heuristic(metrics: dict, requirements: dict) -> int:
    """
    Baseline requirement coverage from required_sections + keyword presence.
    LLM overrides this for the final score.
    """
    score = 50
    required_sections = requirements.get("required_sections", [])
    keyword_cov = metrics.get("keyword_coverage", 0)

    if required_sections:
        score = int(keyword_cov * 100 * 0.5 + 50 * 0.5)
    else:
        score = int(keyword_cov * 100 * 0.3 + 70 * 0.7)

    if metrics["word_count"] < 50:
        score = min(score, 20)

    return max(0, min(100, score))


def _score_structure(metrics: dict, requirements: dict) -> int:
    """
    Step 2 — Structural Compliance from word_count, paragraph_count, headings.
    """
    wc = metrics["word_count"]
    pc = metrics["paragraph_count"]

    wc_score = _word_count_score(wc)
    para_score = min(100, pc * 12) if pc > 0 else 0

    section_score = 70
    required_sections = requirements.get("required_sections", [])
    if required_sections:
        section_score = min(100, int(metrics.get("keyword_coverage", 0.5) * 100))

    return max(0, min(100, int(wc_score * 0.4 + para_score * 0.3 + section_score * 0.3)))


def _word_count_score(wc: int) -> int:
    if wc < 50:
        return 10
    if wc < 100:
        return 30
    if wc < 200:
        return 50
    if wc < 500:
        return 70
    if wc <= 3000:
        return 95
    if wc <= 5000:
        return 85
    return 70


def _score_readability(metrics: dict, requirements: dict) -> int:
    """
    Step 4 — Readability suitability based on FK score and target audience.
    """
    fk = metrics["readability_score"]
    audience = requirements.get("target_audience", "general").lower()

    ideal_ranges = {
        "general": (60, 80),
        "technical": (30, 60),
        "academic": (20, 50),
        "children": (80, 100),
        "beginner": (70, 90),
        "expert": (20, 45),
        "business": (45, 65),
        "professional": (40, 60),
    }

    low, high = ideal_ranges.get(audience, (50, 80))
    mid = (low + high) / 2

    if low <= fk <= high:
        return 95
    distance = min(abs(fk - low), abs(fk - high))
    penalty = min(60, distance * 2)
    return max(10, 95 - int(penalty))


def _score_originality(similarity_ratio: float) -> int:
    """Step 5 — Originality from similarity_ratio (deterministic)."""
    if similarity_ratio < 0.15:
        return 95
    if similarity_ratio < 0.25:
        return 80
    if similarity_ratio <= 0.35:
        return 60
    if similarity_ratio <= 0.50:
        return 35
    return 15


def _score_grammar(error_count: int, word_count: int) -> int:
    """Step 6 — Grammar quality from error count, normalised by content length."""
    if word_count == 0:
        return 0

    error_rate = error_count / max(word_count / 100, 1)

    if error_rate < 0.5:
        return 95
    if error_rate < 1.5:
        return 85
    if error_rate < 3:
        return 70
    if error_rate < 6:
        return 55
    if error_rate < 10:
        return 35
    return 15


def _score_keyword_coverage(coverage: float) -> int:
    """Step 7 — Keyword coverage score."""
    if coverage >= 0.95:
        return 100
    if coverage >= 0.80:
        return 90
    if coverage >= 0.60:
        return 75
    if coverage >= 0.40:
        return 55
    if coverage >= 0.20:
        return 35
    return 15


# ── Step 3: LLM Evaluation ──────────────────────────────────────────────

_CONTENT_EVAL_SYSTEM_PROMPT = """You are an Autonomous Content Quality Verification Agent.

Evaluate the freelancer's written submission against the milestone requirements.
You are given precomputed content metrics — use them to inform your evaluation.

You must evaluate THREE dimensions:

1. REQUIREMENT_COVERAGE (0–100): Does the content answer the milestone objective?
   Are all major deliverables addressed? Are required sections present?
   Check definition_of_done compliance.

2. CONTENT_QUALITY (0–100): Evaluate logical flow, clarity, depth of explanation,
   completeness of ideas. Is the writing substantive or superficial?

3. READABILITY (0–100): Does the readability level match the target audience?
   Use the provided readability_score. A technical paper should be dense; a blog
   should be accessible.

RULES:
- Evaluate ONLY against the provided requirements
- Do NOT invent missing requirements
- If uncertain, lower your confidence score
- Be specific in feedback — cite what is present and what is missing
- Never give 100 without clear evidence of excellence

Return ONLY valid JSON:
{
  "requirement_coverage": 0,
  "content_quality": 0,
  "readability": 0,
  "major_issues": [],
  "improvement_suggestions": [],
  "confidence": 0.0,
  "reasoning": ""
}"""


def _build_content_eval_user_prompt(
    project_id: str,
    milestone_id: str,
    requirements: dict,
    metrics: dict,
    submission: str,
) -> str:
    kw_list = ", ".join(requirements.get("required_keywords", [])) or "none specified"
    section_list = ", ".join(requirements.get("required_sections", [])) or "none specified"

    return (
        f"PROJECT_ID: {project_id}\n"
        f"MILESTONE_ID: {milestone_id}\n\n"
        "MILESTONE_REQUIREMENTS:\n"
        f"- milestone_title: {requirements.get('milestone_title', 'N/A')}\n"
        f"- milestone_description: {requirements.get('milestone_description', 'N/A')}\n"
        f"- definition_of_done: {requirements.get('definition_of_done', 'N/A')}\n"
        f"- required_keywords: {kw_list}\n"
        f"- target_audience: {requirements.get('target_audience', 'general')}\n"
        f"- required_sections: {section_list}\n"
        f"- optional_style_reference: {requirements.get('optional_style_reference', 'none')}\n\n"
        "CONTENT_METRICS:\n"
        f"- word_count: {metrics['word_count']}\n"
        f"- paragraph_count: {metrics['paragraph_count']}\n"
        f"- readability_score: {metrics['readability_score']}\n"
        f"- grammar_error_count: {metrics['grammar_error_count']}\n"
        f"- similarity_ratio: {metrics['similarity_ratio']}\n"
        f"- keyword_coverage: {metrics['keyword_coverage']}\n\n"
        "FREELANCER_SUBMISSION:\n"
        f"{submission[:8000]}"
    )


async def _evaluate_with_llm(
    project_id: str,
    milestone_id: str,
    requirements: dict,
    metrics: dict,
    submission: str,
    api_key: str | None,
) -> tuple[dict, dict]:
    """
    Call the LLM for subjective content evaluation.
    Returns (scores_dict, metadata_dict).
    Falls back to empty scores on failure.
    """
    user_prompt = _build_content_eval_user_prompt(
        project_id, milestone_id, requirements, metrics, submission,
    )

    try:
        result = await ai_service.call_groq(
            _CONTENT_EVAL_SYSTEM_PROMPT, user_prompt, api_key,
        )

        scores = {
            "requirement_coverage": _clamp(result.get("requirement_coverage", 50)),
            "content_quality": _clamp(result.get("content_quality", 50)),
            "readability": _clamp(result.get("readability", 50)),
        }
        meta = {
            "major_issues": result.get("major_issues", []),
            "improvement_suggestions": result.get("improvement_suggestions", []),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
        }
        return scores, meta

    except Exception as exc:
        logger.warning(f"Content LLM evaluation failed: {exc}")
        return {}, {"confidence": 0.3}


# ── Verdict ──────────────────────────────────────────────────────────────

def _determine_verdict(
    cms: float,
    requirement_coverage: int,
    originality: int,
    requirements: dict,
    submission: str,
) -> tuple[str, float]:
    """
    Deterministic verdict logic.

    FULLY_COMPLETED:  CMS >= 85 AND requirement_coverage >= 80 AND originality >= 70
    PARTIALLY_COMPLETED: CMS 50–84
    UNMET: CMS < 50 OR major requirements missing
    """
    major_missing = _check_major_requirements_missing(requirements, submission)

    if major_missing:
        return "UNMET", 0.0

    if cms >= 85 and requirement_coverage >= 80 and originality >= 70:
        return "FULLY_COMPLETED", 100.0

    if cms >= 50:
        return "PARTIALLY_COMPLETED", round(cms, 1)

    return "UNMET", 0.0


def _check_major_requirements_missing(requirements: dict, submission: str) -> bool:
    """Check if critical milestone deliverables are entirely absent."""
    required_sections = requirements.get("required_sections", [])
    if not required_sections:
        return False

    submission_lower = submission.lower()
    found = sum(1 for s in required_sections if s.lower() in submission_lower)
    coverage = found / len(required_sections) if required_sections else 1.0

    return coverage < 0.3


# ── Issues & Suggestions ────────────────────────────────────────────────

def _detect_major_issues(scores: dict, metrics: dict, requirements: dict) -> list[str]:
    issues = []

    if scores["requirement_coverage"] < 50:
        issues.append("Submission does not adequately address the milestone requirements")
    if scores["originality"] < 40:
        issues.append(f"High content duplication detected (similarity_ratio={metrics['similarity_ratio']:.2f})")
    if scores["grammar"] < 40:
        issues.append(f"Excessive grammar errors ({metrics['grammar_error_count']} detected)")
    if metrics["word_count"] < 100:
        issues.append(f"Submission is extremely short ({metrics['word_count']} words)")
    if scores["keyword_coverage"] < 40:
        missing_pct = int((1 - metrics["keyword_coverage"]) * 100)
        issues.append(f"{missing_pct}% of required keywords are missing from the submission")
    if scores["content_quality"] < 40:
        issues.append("Content quality is below acceptable threshold — lacks depth or clarity")

    required_sections = requirements.get("required_sections", [])
    if required_sections and scores["structure"] < 40:
        issues.append("Required sections are missing or poorly structured")

    return issues


def _generate_improvement_suggestions(scores: dict, metrics: dict) -> list[str]:
    suggestions = []
    if scores["requirement_coverage"] < 70:
        suggestions.append("Review the milestone definition of done and ensure all deliverables are addressed")
    if scores["structure"] < 70:
        suggestions.append("Add clear headings and organize content into well-defined sections")
    if scores["content_quality"] < 70:
        suggestions.append("Expand on key points with examples, data, or deeper analysis")
    if scores["readability"] < 70:
        suggestions.append("Adjust sentence complexity to better match the target audience")
    if scores["originality"] < 70:
        suggestions.append("Reduce repetitive phrasing and add more unique, original content")
    if scores["grammar"] < 70:
        suggestions.append("Proofread for grammar errors — consider using a grammar checking tool")
    if scores["keyword_coverage"] < 70:
        suggestions.append("Naturally incorporate missing required keywords into the content")
    return suggestions


# ── Confidence ───────────────────────────────────────────────────────────

def _compute_confidence(scores: dict, metrics: dict, llm_meta: dict) -> float:
    """
    Overall confidence (0-1) based on:
    - LLM self-reported confidence
    - Content length (very short = lower confidence)
    - Score agreement between deterministic and LLM dimensions
    """
    llm_conf = llm_meta.get("confidence", 0.5)

    length_factor = min(1.0, metrics.get("word_count", 0) / 300)

    all_scores = list(scores.values())
    if all_scores:
        spread = max(all_scores) - min(all_scores)
        agreement = 1 - (spread / 100)
    else:
        agreement = 0.5

    confidence = (llm_conf * 0.5) + (length_factor * 0.25) + (agreement * 0.25)
    return round(max(0.1, min(1.0, confidence)), 2)


# ── Readability Blend ────────────────────────────────────────────────────

def _blend_readability(det_score: int, llm_score: int) -> int:
    """Blend deterministic and LLM readability scores (60/40 split)."""
    return max(0, min(100, int(det_score * 0.6 + llm_score * 0.4)))


# ── Helpers ──────────────────────────────────────────────────────────────

def _clamp(value: int | float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(value)))


def _error_response(project_id: str, milestone_id: str, status: str) -> dict:
    return {
        "project_id": project_id,
        "milestone_id": milestone_id,
        "scores": {k: 0 for k in CMS_WEIGHTS},
        "composite_milestone_score": 0,
        "verdict": "UNMET",
        "payout_percentage": 0,
        "major_issues": [f"Evaluation could not be performed: {status}"],
        "improvement_suggestions": [],
        "confidence": 0.0,
        "evaluation_status": status,
        "metrics_used": None,
    }
