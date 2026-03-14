"""
Verification Engine — Modality-Aware Submission Verification
─────────────────────────────────────────────────────────────
Orchestrate deterministic checks → LLM evaluation → composite scoring
→ payment decision.  Each modality (code/content/design) has its own
deterministic heuristics.  LLM is the fallback for what can't be
measured programmatically.

For CODE modality with a GitHub repo URL:
  Layer 1: Static Analysis (AST) — 15%
  Layer 2: Runtime Tests (Sandbox) — 35%
  Layer 3: SonarQube Quality Gate — 20%
  Layer 4: LLM Semantic Review — 30%
"""

import logging
import re
from typing import Literal

from services import ai as ai_service

logger = logging.getLogger(__name__)


# ── Layer Weights for Code Pipeline ─────────────────────────────────────

CODE_LAYER_WEIGHTS = {
    "static": 0.15,
    "runtime": 0.35,
    "sonarqube": 0.20,
    "llm": 0.30,
}


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


# ── Heuristic Deterministic Checks (non-repo fallback) ──────────────────

def run_code_checks(submission: str) -> dict[str, float]:
    """Heuristic deterministic checks for code submissions (no repo URL)."""
    scores: dict[str, float] = {}

    lines = submission.strip().split("\n")
    line_count = len(lines)
    scores["line_count_check"] = min(100, line_count * 2)

    code_patterns = [
        r"\b(def|function|class|const|let|var|import|from|return|if|for|while|try|catch|async|await)\b",
    ]
    pattern_hits = sum(
        len(re.findall(p, submission, re.IGNORECASE)) for p in code_patterns
    )
    scores["structure_check"] = min(100, pattern_hits * 5)

    has_url = bool(re.search(r"https?://\S+", submission))
    scores["artifact_url_check"] = 100 if has_url else 0

    error_patterns = r"\b(try|catch|except|raise|throw|Error|Exception|finally)\b"
    error_hits = len(re.findall(error_patterns, submission))
    scores["error_handling_check"] = min(100, error_hits * 15)

    test_patterns = r"\b(test_|_test|describe\(|it\(|expect\(|assert|pytest|jest|mocha|unittest)\b"
    test_hits = len(re.findall(test_patterns, submission, re.IGNORECASE))
    scores["test_presence_check"] = min(100, test_hits * 20)

    return scores


def run_content_checks(submission: str) -> dict[str, float]:
    """Heuristic deterministic checks for content submissions."""
    scores: dict[str, float] = {}

    words = submission.split()
    word_count = len(words)
    scores["word_count_check"] = min(100, word_count / 5)

    sentences = re.split(r"[.!?]+", submission)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    if 10 <= avg_sentence_len <= 25:
        scores["readability_check"] = 90
    elif 5 <= avg_sentence_len <= 30:
        scores["readability_check"] = 60
    else:
        scores["readability_check"] = 30

    paragraphs = [p.strip() for p in submission.split("\n\n") if p.strip()]
    scores["paragraph_structure_check"] = min(100, len(paragraphs) * 15)

    headings = re.findall(r"^#{1,6}\s+.+", submission, re.MULTILINE)
    scores["heading_structure_check"] = min(100, len(headings) * 20)

    return scores


def run_design_checks(submission: str) -> dict[str, float]:
    """Heuristic deterministic checks for design submissions."""
    scores: dict[str, float] = {}

    design_formats = r"\.(png|jpg|jpeg|svg|pdf|fig|sketch|xd|ai|psd|webp)\b"
    format_hits = len(re.findall(design_formats, submission, re.IGNORECASE))
    scores["export_format_check"] = min(100, format_hits * 25)

    design_urls = re.findall(r"https?://\S+", submission)
    design_tool_hits = sum(
        1 for url in design_urls
        if any(tool in url.lower() for tool in ["figma", "dribbble", "behance", "canva", "zeplin", "invision"])
    )
    scores["design_tool_url_check"] = min(100, (len(design_urls) * 20) + (design_tool_hits * 30))

    a11y_patterns = r"\b(accessibility|a11y|alt.text|aria|wcag|contrast|screen.reader)\b"
    a11y_hits = len(re.findall(a11y_patterns, submission, re.IGNORECASE))
    scores["accessibility_mention_check"] = min(100, a11y_hits * 25)

    responsive_patterns = r"\b(responsive|mobile|tablet|breakpoint|viewport|media.query|adaptive)\b"
    resp_hits = len(re.findall(responsive_patterns, submission, re.IGNORECASE))
    scores["responsive_check"] = min(100, resp_hits * 25)

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

    det_avg = sum(deterministic_scores.values()) / len(deterministic_scores) if deterministic_scores else 0
    llm_avg = sum(llm_scores.values()) / len(llm_scores) if llm_scores else 0

    if deterministic_scores and llm_scores:
        composite = det_avg * 0.3 + llm_avg * 0.7
        agreement = 1 - abs(det_avg - llm_avg) / 100
        confidence = 0.6 + 0.4 * agreement
    elif deterministic_scores:
        composite = det_avg
        confidence = 0.5
    else:
        composite = llm_avg
        confidence = 0.5

    return round(composite, 1), round(confidence, 2)


def compute_code_pipeline_score(
    static_scores: dict[str, float],
    runtime_scores: dict[str, float],
    sonar_scores: dict[str, float],
    llm_scores: dict[str, float],
    sonar_gate_status: str | None = None,
) -> tuple[float, float]:
    """
    Compute weighted score for the 4-layer code pipeline.
    Returns (composite_score, confidence).

    Hard rules:
    - LLM alone cannot produce FULLY_COMPLETE (need at least one static/runtime pass)
    - SonarQube FAIL caps score at 70
    """
    w = CODE_LAYER_WEIGHTS

    static_avg = sum(static_scores.values()) / len(static_scores) if static_scores else 0
    runtime_avg = sum(runtime_scores.values()) / len(runtime_scores) if runtime_scores else 0
    sonar_avg = sum(sonar_scores.values()) / len(sonar_scores) if sonar_scores else 50
    llm_avg = sum(llm_scores.values()) / len(llm_scores) if llm_scores else 0

    composite = (
        static_avg * w["static"] +
        runtime_avg * w["runtime"] +
        sonar_avg * w["sonarqube"] +
        llm_avg * w["llm"]
    )

    # Hard rule: SonarQube FAIL caps overall score at 70
    if sonar_gate_status == "ERROR":
        composite = min(composite, 70)

    # Confidence: higher when more layers have data
    layers_with_data = sum([
        bool(static_scores), bool(runtime_scores),
        bool(sonar_scores), bool(llm_scores),
    ])
    base_confidence = 0.3 + (layers_with_data / 4) * 0.5

    # Agreement bonus
    all_avgs = [a for a in [static_avg, runtime_avg, sonar_avg, llm_avg] if a > 0]
    if len(all_avgs) >= 2:
        spread = max(all_avgs) - min(all_avgs)
        agreement = 1 - (spread / 100)
        base_confidence += 0.2 * agreement

    confidence = min(1.0, round(base_confidence, 2))

    # Hard rule: LLM alone can't produce full score
    has_deterministic_pass = (static_avg >= 50 or runtime_avg >= 50)
    if not has_deterministic_pass and composite >= 85:
        composite = 84  # Cap just below full-pay threshold
        confidence = min(confidence, 0.65)

    return round(composite, 1), confidence


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
    if confidence < 0.7:
        return {
            "action": "HITL",
            "reason": f"Low confidence ({confidence:.0%}). Score: {score:.0f}/100.",
            "recommended_pct": int(score) if score >= 50 else 0,
        }

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
    repo_url: str | None = None,
    commit_hash: str | None = None,
) -> dict:
    """
    Main entry point: classify → deterministic checks → LLM eval → score → decide.
    For code milestones with repo_url: runs the full 4-layer GitHub pipeline.
    Returns enriched AQA result dict.
    """
    # 1. Classify modality
    modality = classify_submission(task_type, milestone_domain)

    # 2. Route based on modality + repo availability
    if modality == "code" and repo_url:
        return await _run_code_pipeline(
            milestone_title=milestone_title,
            milestone_domain=milestone_domain,
            acceptance_criteria=acceptance_criteria,
            scoring_weights=scoring_weights,
            submission=submission,
            repo_url=repo_url,
            commit_hash=commit_hash,
            api_key=api_key,
        )

    # 3. Standard path (heuristic + LLM)
    return await _run_standard_pipeline(
        milestone_title=milestone_title,
        milestone_domain=milestone_domain,
        modality=modality,
        acceptance_criteria=acceptance_criteria,
        scoring_weights=scoring_weights,
        submission=submission,
        api_key=api_key,
    )


async def _run_code_pipeline(
    milestone_title: str,
    milestone_domain: str,
    acceptance_criteria: list,
    scoring_weights: dict | None,
    submission: str,
    repo_url: str,
    commit_hash: str | None,
    api_key: str | None,
) -> dict:
    """
    Full 4-layer code verification pipeline:
    L1: Static (AST) → L2: Runtime (tests) → L3: SonarQube → L4: LLM Semantic
    """
    from services import code_verifier

    # Layers 1-3: Clone repo and run deterministic analysis
    logger.info(f"Starting code pipeline for repo: {repo_url}")
    try:
        pipeline_result = await code_verifier.run_full_pipeline(
            repo_url=repo_url,
            commit_hash=commit_hash,
            milestone_id=milestone_title.replace(" ", "_")[:20],
        )
    except ValueError as exc:
        logger.error(f"Code pipeline failed: {exc}")
        # Fallback to standard heuristic path
        return await _run_standard_pipeline(
            milestone_title=milestone_title,
            milestone_domain=milestone_domain,
            modality="code",
            acceptance_criteria=acceptance_criteria,
            scoring_weights=scoring_weights,
            submission=submission,
            api_key=api_key,
        )

    # Layer 4: LLM Semantic Review
    logger.info("Running Layer 4: LLM Semantic Review")
    llm_result = await ai_service.evaluate_submission(
        milestone_title=milestone_title,
        milestone_domain=milestone_domain,
        acceptance_criteria=acceptance_criteria,
        submission=submission,
        api_key=api_key,
        task_type="code",
        scoring_weights=scoring_weights,
    )

    # Extract LLM per-criterion scores
    llm_scores = {}
    criteria_evals = llm_result.get("criteriaEvaluation", [])
    for i, ce in enumerate(criteria_evals):
        llm_scores[f"criterion_{i}"] = ce.get("score", 50)

    # Get layer scores from pipeline
    layer_results = pipeline_result.get("layer_results", {})
    static_scores = layer_results.get("static", {}).get("scores", {})
    runtime_scores = layer_results.get("runtime", {}).get("scores", {})
    sonar_scores = layer_results.get("sonarqube", {}).get("scores", {})

    # Get SonarQube gate status for hard rules
    sonar_gate_status = None
    sonar_gate_score = sonar_scores.get("sonar_gate", 50)
    if sonar_gate_score <= 25:
        sonar_gate_status = "ERROR"
    elif sonar_gate_score <= 65:
        sonar_gate_status = "WARN"

    # Compute composite with 4-layer weights
    composite_score, confidence = compute_code_pipeline_score(
        static_scores, runtime_scores, sonar_scores, llm_scores,
        sonar_gate_status,
    )

    # Evidence completeness
    evidence_completeness = llm_result.get("evidenceCompleteness", 0.0)
    # Boost evidence completeness when we have real repo analysis
    if pipeline_result.get("deterministic_scores"):
        det_score_count = len(pipeline_result["deterministic_scores"])
        evidence_completeness = max(evidence_completeness, min(1.0, det_score_count / 10))

    # Payment decision
    decision = make_payment_decision(composite_score, confidence, evidence_completeness)

    # Map to standard AQA fields
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

    # Build enriched result with full pipeline data
    enriched = {
        "overallScore": overall_score,
        "completionStatus": completion_status,
        "paymentRecommendation": payment_rec,
        "proRatedPercentage": pro_rated,
        "percentComplete": llm_result.get("percentComplete", overall_score),
        "modality": "code",
        "confidence": confidence,
        "evidenceCompleteness": evidence_completeness,
        "modalityScores": {
            "deterministic": pipeline_result.get("deterministic_scores", {}),
            "llm": llm_scores,
            "weights": CODE_LAYER_WEIGHTS,
        },
        "criteriaEvaluation": criteria_evals,
        "detailedFeedback": llm_result.get("detailedFeedback", ""),
        "remediationChecklist": llm_result.get("remediationChecklist", []),
        "riskFlags": llm_result.get("riskFlags", []),
        "decision": decision,
        # Code-pipeline specific
        "codePipeline": {
            "repoUrl": repo_url,
            "commitHash": pipeline_result.get("commit_hash", "unknown"),
            "language": pipeline_result.get("language", "unknown"),
            "layerScores": {
                "static": _avg(static_scores),
                "runtime": _avg(runtime_scores),
                "sonarqube": _avg(sonar_scores),
                "llm": _avg(llm_scores),
            },
            "layerDetails": {
                "static": layer_results.get("static", {}).get("details", {}),
                "runtime": layer_results.get("runtime", {}).get("details", {}),
                "sonarqube": layer_results.get("sonarqube", {}).get("details", {}),
                "security": layer_results.get("security", {}).get("details", {}),
                "dependency": layer_results.get("dependency", {}).get("details", {}),
            },
            "securityIssues": layer_results.get("security", {}).get("issues", []),
            "pfiSignals": pipeline_result.get("pfi_signals", {}),
        },
        # Dispute evidence
        "disputeEvidence": _build_dispute_evidence(pipeline_result, llm_result, composite_score, decision),
    }

    return enriched


async def _run_standard_pipeline(
    milestone_title: str,
    milestone_domain: str,
    modality: str,
    acceptance_criteria: list,
    scoring_weights: dict | None,
    submission: str,
    api_key: str | None,
) -> dict:
    """Standard verification path: heuristic checks + LLM."""
    # Deterministic checks based on modality
    if modality == "code":
        det_scores = run_code_checks(submission)
    elif modality == "content":
        det_scores = run_content_checks(submission)
    elif modality == "design":
        det_scores = run_design_checks(submission)
    else:
        det_scores = {}
        det_scores.update({f"code_{k}": v for k, v in run_code_checks(submission).items()})
        det_scores.update({f"content_{k}": v for k, v in run_content_checks(submission).items()})
        det_scores.update({f"design_{k}": v for k, v in run_design_checks(submission).items()})

    # LLM evaluation
    llm_result = await ai_service.evaluate_submission(
        milestone_title=milestone_title,
        milestone_domain=milestone_domain,
        acceptance_criteria=acceptance_criteria,
        submission=submission,
        api_key=api_key,
        task_type=modality,
        scoring_weights=scoring_weights,
    )

    llm_scores = {}
    criteria_evals = llm_result.get("criteriaEvaluation", [])
    for i, ce in enumerate(criteria_evals):
        llm_scores[f"criterion_{i}"] = ce.get("score", 50)

    composite_score, confidence = compute_composite_score(det_scores, llm_scores, modality)
    evidence_completeness = llm_result.get("evidenceCompleteness", 0.0)
    decision = make_payment_decision(composite_score, confidence, evidence_completeness)

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

    return {
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
        "decision": decision,
    }


# ── Helpers ──────────────────────────────────────────────────────────────

def _avg(scores: dict[str, float]) -> float:
    """Average of score values, defaulting to 0 if empty."""
    return round(sum(scores.values()) / len(scores), 1) if scores else 0.0


def _build_dispute_evidence(
    pipeline_result: dict,
    llm_result: dict,
    composite_score: float,
    decision: dict,
) -> str:
    """Build human-readable dispute evidence summary."""
    lines = [
        f"Overall Score: {composite_score:.0f}/100",
        f"Decision: {decision.get('action', 'N/A')} — {decision.get('reason', '')}",
        "",
        "== Layer Results ==",
    ]

    # Layer scores
    layer_results = pipeline_result.get("layer_results", {})
    for layer_name in ("static", "runtime", "sonarqube", "security"):
        layer = layer_results.get(layer_name, {})
        details = layer.get("details", {})
        for key, detail in details.items():
            score = layer.get("scores", {}).get(key, "N/A")
            lines.append(f"  [{layer_name}] {key}: {score}/100 — {detail}")

    # LLM feedback
    feedback = llm_result.get("detailedFeedback", "")
    if feedback:
        lines.append("")
        lines.append(f"== LLM Feedback ==")
        lines.append(feedback[:500])

    # Security issues
    security_issues = layer_results.get("security", {}).get("issues", [])
    if security_issues:
        lines.append("")
        lines.append(f"== Security Issues ({len(security_issues)}) ==")
        for issue in security_issues[:10]:
            lines.append(f"  ⚠ {issue}")

    return "\n".join(lines)
