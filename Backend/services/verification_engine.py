"""
Verification Engine — Modality-Aware Submission Verification
─────────────────────────────────────────────────────────────
Orchestrate deterministic checks → LLM evaluation → composite scoring
→ payment decision.  Each modality (code/content/design) has its own
deterministic heuristics.  LLM is the fallback for what can't be
measured programmatically.

TODO hooks are left for external tools (linters, plagiarism API, etc.).
"""

import logging
import re
from typing import Literal

from services import ai as ai_service

logger = logging.getLogger(__name__)


# ── Modality Classification ─────────────────────────────────────────────

def classify_submission(task_type: str | None, domain: str | None) -> str:
    """Return normalised modality: code|content|design|mixed."""
    if task_type and task_type in ("code", "content", "design", "mixed"):
        return task_type

    # Heuristic fallback from domain string
    d = (domain or "").lower()
    code_keywords = {"backend", "frontend", "api", "development", "programming", "software", "engineering", "devops", "database"}
    content_keywords = {"writing", "content", "blog", "copywriting", "seo", "documentation", "translation"}
    design_keywords = {"design", "ui", "ux", "graphic", "branding", "illustration", "wireframe"}

    code_hits = sum(1 for k in code_keywords if k in d)
    content_hits = sum(1 for k in content_keywords if k in d)
    design_hits = sum(1 for k in design_keywords if k in d)

    best = max(code_hits, content_hits, design_hits)
    if best == 0:
        return "mixed"
    if code_hits == best:
        return "code"
    if content_hits == best:
        return "content"
    return "design"


# ── Deterministic Checks ────────────────────────────────────────────────

def run_code_checks(submission: str) -> dict[str, float]:
    """Heuristic deterministic checks for code submissions."""
    scores: dict[str, float] = {}

    # Line count — proxy for substance
    lines = submission.strip().split("\n")
    line_count = len(lines)
    scores["line_count_check"] = min(100, line_count * 2)  # 50+ lines → 100

    # Structural keywords that indicate implementation
    code_patterns = [
        r"\b(def|function|class|const|let|var|import|from|return|if|for|while|try|catch|async|await)\b",
    ]
    pattern_hits = sum(
        len(re.findall(p, submission, re.IGNORECASE)) for p in code_patterns
    )
    scores["structure_check"] = min(100, pattern_hits * 5)

    # URL/repo presence
    has_url = bool(re.search(r"https?://\S+", submission))
    scores["artifact_url_check"] = 100 if has_url else 0

    # Error handling presence
    error_patterns = r"\b(try|catch|except|raise|throw|Error|Exception|finally)\b"
    error_hits = len(re.findall(error_patterns, submission))
    scores["error_handling_check"] = min(100, error_hits * 15)

    # Test presence
    test_patterns = r"\b(test_|_test|describe\(|it\(|expect\(|assert|pytest|jest|mocha|unittest)\b"
    test_hits = len(re.findall(test_patterns, submission, re.IGNORECASE))
    scores["test_presence_check"] = min(100, test_hits * 20)

    # TODO: lint_score from external linter
    # TODO: security_scan_score from external scanner

    return scores


def run_content_checks(submission: str) -> dict[str, float]:
    """Heuristic deterministic checks for content submissions."""
    scores: dict[str, float] = {}

    # Word count
    words = submission.split()
    word_count = len(words)
    scores["word_count_check"] = min(100, word_count / 5)  # 500+ words → 100

    # Sentence / paragraph structure
    sentences = re.split(r"[.!?]+", submission)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    # Good readability: 15-20 words per sentence
    if 10 <= avg_sentence_len <= 25:
        scores["readability_check"] = 90
    elif 5 <= avg_sentence_len <= 30:
        scores["readability_check"] = 60
    else:
        scores["readability_check"] = 30

    paragraphs = [p.strip() for p in submission.split("\n\n") if p.strip()]
    scores["paragraph_structure_check"] = min(100, len(paragraphs) * 15)

    # Heading structure (markdown)
    headings = re.findall(r"^#{1,6}\s+.+", submission, re.MULTILINE)
    scores["heading_structure_check"] = min(100, len(headings) * 20)

    # TODO: plagiarism_score from external API
    # TODO: grammar_score from external API

    return scores


def run_design_checks(submission: str) -> dict[str, float]:
    """Heuristic deterministic checks for design submissions."""
    scores: dict[str, float] = {}

    # File/export format mentions
    design_formats = r"\.(png|jpg|jpeg|svg|pdf|fig|sketch|xd|ai|psd|webp)\b"
    format_hits = len(re.findall(design_formats, submission, re.IGNORECASE))
    scores["export_format_check"] = min(100, format_hits * 25)

    # URL to design tool or deliverable
    design_urls = re.findall(r"https?://\S+", submission)
    design_tool_hits = sum(
        1 for url in design_urls
        if any(tool in url.lower() for tool in ["figma", "dribbble", "behance", "canva", "zeplin", "invision"])
    )
    scores["design_tool_url_check"] = min(100, (len(design_urls) * 20) + (design_tool_hits * 30))

    # Accessibility mention
    a11y_patterns = r"\b(accessibility|a11y|alt.text|aria|wcag|contrast|screen.reader)\b"
    a11y_hits = len(re.findall(a11y_patterns, submission, re.IGNORECASE))
    scores["accessibility_mention_check"] = min(100, a11y_hits * 25)

    # Responsive mention
    responsive_patterns = r"\b(responsive|mobile|tablet|breakpoint|viewport|media.query|adaptive)\b"
    resp_hits = len(re.findall(responsive_patterns, submission, re.IGNORECASE))
    scores["responsive_check"] = min(100, resp_hits * 25)

    # TODO: visual_diff_score from external image comparison
    # TODO: wcag_audit_score from external accessibility scanner

    return scores


# ── Score Aggregation ────────────────────────────────────────────────────

def compute_composite_score(
    deterministic_scores: dict[str, float],
    llm_scores: dict[str, float],
    modality: str,
) -> tuple[float, float]:
    """
    Blend deterministic and LLM scores.
    Returns (composite_score, confidence).

    Deterministic scores get 30% weight, LLM gets 70%.
    If no deterministic scores exist, LLM gets 100%.
    Confidence is higher when deterministic evidence is available.
    """
    if not deterministic_scores and not llm_scores:
        return 0.0, 0.0

    # Average each group
    det_avg = sum(deterministic_scores.values()) / len(deterministic_scores) if deterministic_scores else 0
    llm_avg = sum(llm_scores.values()) / len(llm_scores) if llm_scores else 0

    if deterministic_scores and llm_scores:
        composite = det_avg * 0.3 + llm_avg * 0.7
        # Confidence: higher when both sources agree
        agreement = 1 - abs(det_avg - llm_avg) / 100
        confidence = 0.6 + 0.4 * agreement  # 0.6–1.0
    elif deterministic_scores:
        composite = det_avg
        confidence = 0.5  # No LLM confirmation
    else:
        composite = llm_avg
        confidence = 0.5  # No deterministic evidence

    return round(composite, 1), round(confidence, 2)


# ── Payment Decision ─────────────────────────────────────────────────────

def make_payment_decision(
    score: float,
    confidence: float,
    evidence_completeness: float,
) -> dict:
    """
    Determine payment action based on score, confidence, and evidence.
    Thresholds: ≥85 full, 50–84 partial, <50 refund.
    Low confidence (<0.7) → HITL regardless of score.
    """
    # Low confidence → human review
    if confidence < 0.7:
        return {
            "action": "HITL",
            "reason": f"Low confidence ({confidence:.0%}). Score: {score:.0f}/100.",
            "recommended_pct": int(score) if score >= 50 else 0,
        }

    # Low evidence → cautious
    if evidence_completeness < 0.3 and score < 85:
        return {
            "action": "HITL",
            "reason": f"Insufficient evidence ({evidence_completeness:.0%}). Score: {score:.0f}/100.",
            "recommended_pct": int(score) if score >= 50 else 0,
        }

    if score >= 85:
        return {
            "action": "FULL_PAY",
            "reason": f"Score {score:.0f}/100 meets full-pay threshold.",
            "recommended_pct": 100,
        }
    elif score >= 50:
        pct = int(score)
        return {
            "action": "PARTIAL_PAY",
            "reason": f"Score {score:.0f}/100 — pro-rated at {pct}%.",
            "recommended_pct": pct,
        }
    else:
        return {
            "action": "REFUND",
            "reason": f"Score {score:.0f}/100 below minimum threshold.",
            "recommended_pct": 0,
        }


# ── Orchestrator ─────────────────────────────────────────────────────────

async def orchestrate_verification(
    milestone_title: str,
    milestone_domain: str,
    task_type: str | None,
    acceptance_criteria: list,
    scoring_weights: dict | None,
    submission: str,
    api_key: str | None = None,
) -> dict:
    """
    Main entry point: classify → deterministic checks → LLM eval → score → decide.
    Returns enriched AQA result dict.
    """
    # 1. Classify modality
    modality = classify_submission(task_type, milestone_domain)

    # 2. Run deterministic checks
    if modality == "code":
        det_scores = run_code_checks(submission)
    elif modality == "content":
        det_scores = run_content_checks(submission)
    elif modality == "design":
        det_scores = run_design_checks(submission)
    else:
        # Mixed: run all and merge
        det_scores = {}
        det_scores.update({f"code_{k}": v for k, v in run_code_checks(submission).items()})
        det_scores.update({f"content_{k}": v for k, v in run_content_checks(submission).items()})
        det_scores.update({f"design_{k}": v for k, v in run_design_checks(submission).items()})

    # 3. LLM evaluation
    llm_result = await ai_service.evaluate_submission(
        milestone_title=milestone_title,
        milestone_domain=milestone_domain,
        acceptance_criteria=acceptance_criteria,
        submission=submission,
        api_key=api_key,
        task_type=modality,
        scoring_weights=scoring_weights,
    )

    # Extract LLM per-criterion scores
    llm_scores = {}
    criteria_evals = llm_result.get("criteriaEvaluation", [])
    for i, ce in enumerate(criteria_evals):
        llm_scores[f"criterion_{i}"] = ce.get("score", 50)

    # 4. Compute composite
    composite_score, confidence = compute_composite_score(det_scores, llm_scores, modality)

    # Evidence completeness from LLM result
    evidence_completeness = llm_result.get("evidenceCompleteness", 0.0)

    # 5. Payment decision
    decision = make_payment_decision(composite_score, confidence, evidence_completeness)

    # 6. Map decision to standard AQA fields
    overall_score = int(composite_score)

    if decision["action"] == "FULL_PAY":
        completion_status = "FULLY_COMPLETED"
        payment_rec = "FULL_RELEASE"
        pro_rated = 100
    elif decision["action"] == "PARTIAL_PAY":
        completion_status = "PARTIALLY_COMPLETED"
        payment_rec = "PRO_RATED"
        pro_rated = decision["recommended_pct"]
    elif decision["action"] == "HITL":
        completion_status = "PARTIALLY_COMPLETED"
        payment_rec = "PRO_RATED"
        pro_rated = decision["recommended_pct"]
    else:
        completion_status = "UNMET"
        payment_rec = "REFUND"
        pro_rated = 0

    # 7. Build enriched result
    enriched = {
        "overallScore": overall_score,
        "completionStatus": completion_status,
        "paymentRecommendation": payment_rec,
        "proRatedPercentage": pro_rated,
        "percentComplete": llm_result.get("percentComplete", overall_score),
        "modality": modality,
        "confidence": confidence,
        "evidenceCompleteness": evidence_completeness,
        "modalityScores": {
            "deterministic": det_scores,
            "llm": llm_scores,
        },
        "criteriaEvaluation": criteria_evals,
        "detailedFeedback": llm_result.get("detailedFeedback", ""),
        "remediationChecklist": llm_result.get("remediationChecklist", []),
        "riskFlags": llm_result.get("riskFlags", []),
        # Decision metadata
        "decision": decision,
    }

    return enriched
