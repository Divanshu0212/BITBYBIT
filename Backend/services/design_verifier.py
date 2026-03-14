"""
Design Quality Verification Agent — 5-Dimension Evaluation Pipeline
───────────────────────────────────────────────────────────────────
Evaluates freelancer-submitted design deliverables against milestone
requirements following the AAPPA Technical Blueprint.

CMS weights (from AAPPA §AQAS — Design & Visual Deliverables):
    requirements_coverage     = 25%
    visual_consistency        = 25%
    accessibility             = 20%
    responsive_completeness   = 20%
    export_readiness          = 10%

Architecture — 8 GB VPS safe:
    • Deterministic scores: export_readiness, accessibility (partial),
      responsive_completeness (partial)
    • LLM-evaluated scores: requirements_coverage, visual_consistency
    • Optional Figma API enrichment: lightweight JSON metadata fetch
    • No image downloads, no headless browsers, no local ML models
"""

import logging

from config import settings
from services import ai as ai_service
from services.design_metrics import compute_design_metrics, fetch_figma_metadata

logger = logging.getLogger(__name__)

CMS_WEIGHTS = {
    "requirements_coverage": 0.25,
    "visual_consistency": 0.25,
    "accessibility": 0.20,
    "responsive_completeness": 0.20,
    "export_readiness": 0.10,
}


# ── Public API ───────────────────────────────────────────────────────────

async def verify_design(
    project_id: str,
    milestone_id: str,
    milestone_requirements: dict,
    freelancer_submission: str,
    design_metrics: dict | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Full design verification pipeline.

    1. Compute design metrics (if not supplied)
    2. Optionally fetch Figma metadata
    3. Score deterministic dimensions
    4. Score LLM-evaluated dimensions
    5. Compute CMS → verdict → payout
    """
    if not freelancer_submission or not freelancer_submission.strip():
        return _error_response(project_id, milestone_id, "INCOMPLETE_SUBMISSION")

    title = milestone_requirements.get("milestone_title", "")
    if not title:
        return _error_response(project_id, milestone_id, "INSUFFICIENT_DATA")

    required_screens = milestone_requirements.get("required_screens", [])
    required_components = milestone_requirements.get("required_components", [])

    # 1 — Compute metrics locally
    if design_metrics is None:
        design_metrics = compute_design_metrics(
            freelancer_submission,
            required_screens=required_screens,
            required_components=required_components,
        )

    # 2 — Optional Figma enrichment
    figma_meta = None
    figma_token = settings.FIGMA_ACCESS_TOKEN
    if figma_token:
        for tool_url in design_metrics.get("design_tool_urls", []):
            if tool_url.get("platform", "").startswith("figma"):
                figma_meta = await fetch_figma_metadata(tool_url["url"], figma_token)
                if figma_meta:
                    design_metrics["figma_metadata"] = figma_meta
                break

    # 3 — Deterministic scores
    det_scores = _compute_deterministic_scores(design_metrics, milestone_requirements, figma_meta)

    # 4 — LLM-evaluated scores
    llm_scores, llm_meta = await _evaluate_with_llm(
        project_id, milestone_id,
        milestone_requirements, design_metrics,
        freelancer_submission, api_key,
    )

    # 5 — Merge (LLM for subjective dimensions, deterministic for measurable ones)
    scores = {
        "requirements_coverage": llm_scores.get(
            "requirements_coverage",
            det_scores["requirements_coverage"],
        ),
        "visual_consistency": llm_scores.get(
            "visual_consistency",
            det_scores["visual_consistency"],
        ),
        "accessibility": _blend(
            det_scores["accessibility"],
            llm_scores.get("accessibility", det_scores["accessibility"]),
            det_weight=0.5,
        ),
        "responsive_completeness": _blend(
            det_scores["responsive_completeness"],
            llm_scores.get("responsive_completeness", det_scores["responsive_completeness"]),
            det_weight=0.5,
        ),
        "export_readiness": det_scores["export_readiness"],
    }

    # 6 — Composite Milestone Score
    cms = sum(scores[k] * CMS_WEIGHTS[k] for k in CMS_WEIGHTS)
    cms = round(cms, 1)

    # 7 — Verdict
    verdict, payout = _determine_verdict(
        cms, scores["requirements_coverage"], design_metrics,
    )

    major_issues = _detect_major_issues(scores, design_metrics, milestone_requirements)
    suggestions = llm_meta.get("improvement_suggestions", [])
    if not suggestions:
        suggestions = _generate_suggestions(scores, design_metrics)
    confidence = _compute_confidence(scores, design_metrics, llm_meta, figma_meta)

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
        "metrics_used": design_metrics,
        "figma_metadata": figma_meta,
    }


# ── Deterministic Scoring ────────────────────────────────────────────────

def _compute_deterministic_scores(
    metrics: dict,
    requirements: dict,
    figma_meta: dict | None,
) -> dict:
    return {
        "requirements_coverage": _score_requirements_coverage(metrics, requirements, figma_meta),
        "visual_consistency": _score_visual_consistency(metrics, figma_meta),
        "accessibility": _score_accessibility(metrics),
        "responsive_completeness": _score_responsive(metrics, figma_meta),
        "export_readiness": _score_export_readiness(metrics),
    }


def _score_requirements_coverage(
    metrics: dict, requirements: dict, figma_meta: dict | None,
) -> int:
    """
    Heuristic requirements coverage from screen/component mentions,
    Figma frame count, and URL presence.  LLM overrides for final score.
    """
    sub_scores = []

    screen_cov = metrics.get("screen_coverage", 0.5)
    sub_scores.append(int(screen_cov * 100))

    comp_cov = metrics.get("component_coverage", 0.5)
    sub_scores.append(int(comp_cov * 100))

    if metrics.get("design_tool_count", 0) > 0:
        sub_scores.append(80)
    elif metrics.get("total_urls", 0) > 0:
        sub_scores.append(50)
    else:
        sub_scores.append(10)

    if figma_meta:
        frame_count = figma_meta.get("frame_count", 0)
        required_screens = requirements.get("required_screens", [])
        if required_screens:
            ratio = min(1.0, frame_count / max(len(required_screens), 1))
            sub_scores.append(int(ratio * 100))
        elif frame_count >= 5:
            sub_scores.append(85)
        elif frame_count >= 2:
            sub_scores.append(60)
        else:
            sub_scores.append(30)

    return _clamp(int(sum(sub_scores) / max(len(sub_scores), 1)))


def _score_visual_consistency(metrics: dict, figma_meta: dict | None) -> int:
    """
    Heuristic visual consistency from design system signals, color/typography
    mentions, and Figma component count.
    """
    score = 40

    ds_signals = metrics.get("design_system_signal_count", 0)
    score += min(20, ds_signals * 5)

    color_hits = metrics.get("color_spec_count", 0)
    score += min(15, color_hits * 3)

    typo_hits = metrics.get("typography_spec_count", 0)
    score += min(15, typo_hits * 3)

    if figma_meta:
        comp_count = figma_meta.get("component_count", 0)
        if comp_count >= 10:
            score += 10
        elif comp_count >= 3:
            score += 5

    return _clamp(score)


def _score_accessibility(metrics: dict) -> int:
    """Accessibility score from a11y keyword signals."""
    hits = metrics.get("accessibility_signal_count", 0)

    if hits >= 8:
        return 95
    if hits >= 5:
        return 80
    if hits >= 3:
        return 65
    if hits >= 1:
        return 45
    return 15


def _score_responsive(metrics: dict, figma_meta: dict | None) -> int:
    """Responsive completeness from responsive signals and Figma frames."""
    hits = metrics.get("responsive_signal_count", 0)

    base = 15
    if hits >= 8:
        base = 90
    elif hits >= 5:
        base = 75
    elif hits >= 3:
        base = 60
    elif hits >= 1:
        base = 40

    if figma_meta:
        frame_names = [n.lower() for n in figma_meta.get("frame_names", [])]
        has_mobile = any("mobile" in n or "phone" in n or "375" in n or "320" in n for n in frame_names)
        has_tablet = any("tablet" in n or "768" in n or "ipad" in n for n in frame_names)
        has_desktop = any("desktop" in n or "1440" in n or "1024" in n or "web" in n for n in frame_names)
        variant_count = sum([has_mobile, has_tablet, has_desktop])
        if variant_count >= 3:
            base = max(base, 90)
        elif variant_count >= 2:
            base = max(base, 75)
        elif variant_count >= 1:
            base = max(base, 55)

    return _clamp(base)


def _score_export_readiness(metrics: dict) -> int:
    """Export readiness from file formats and design tool URL presence."""
    format_count = metrics.get("export_format_count", 0)
    tool_count = metrics.get("design_tool_count", 0)

    score = 10
    score += min(40, format_count * 10)
    score += min(40, tool_count * 20)

    if any(
        fmt in metrics.get("export_formats", [])
        for fmt in ("svg", "pdf", "png")
    ):
        score += 10

    return _clamp(score)


# ── LLM Evaluation ──────────────────────────────────────────────────────

_DESIGN_EVAL_SYSTEM_PROMPT = """You are AAPPA-AQA, an autonomous design quality verification agent.

Evaluate the freelancer's design submission against the milestone requirements.
You are given precomputed design metrics — use them to inform your evaluation.
You CANNOT see the actual design files — evaluate based on the submission
description, URLs provided, and any Figma metadata included.

Evaluate FIVE dimensions (0–100 each):

1. REQUIREMENTS_COVERAGE (25%): Are all required screens/pages/components delivered?
   Does the work match the milestone specification? Are design tool URLs or
   exports provided as evidence?

2. VISUAL_CONSISTENCY (25%): Is there evidence of a consistent design system?
   Color palette, typography, spacing, component reuse. Does the submission
   describe visual coherence across screens?

3. ACCESSIBILITY (20%): Are accessibility considerations addressed?
   WCAG compliance mentions, alt-text, contrast ratios, keyboard navigation,
   focus states, screen reader support.

4. RESPONSIVE_COMPLETENESS (20%): Are mobile, tablet, and desktop variants
   provided? Are breakpoints mentioned? Does the design adapt to different
   screen sizes?

5. EXPORT_READINESS (10%): Are proper file formats provided (SVG, PNG, PDF)?
   Are design files organized and ready for developer handoff? Are assets
   properly named and exported?

RULES:
- Evaluate ONLY against the provided requirements
- If a design tool URL is provided (Figma, etc.), credit it as strong evidence
- If Figma metadata is included, use frame/component counts as hard evidence
- Without viewable artifacts, rely on the quality of the submission description
- Lower confidence when you cannot verify visual claims directly
- Never give 100 without clear evidence of excellence

Return ONLY valid JSON:
{
  "requirements_coverage": 0,
  "visual_consistency": 0,
  "accessibility": 0,
  "responsive_completeness": 0,
  "export_readiness": 0,
  "major_issues": [],
  "improvement_suggestions": [],
  "confidence": 0.0,
  "reasoning": ""
}"""


def _build_design_eval_user_prompt(
    project_id: str,
    milestone_id: str,
    requirements: dict,
    metrics: dict,
    submission: str,
) -> str:
    screens_list = ", ".join(requirements.get("required_screens", [])) or "none specified"
    components_list = ", ".join(requirements.get("required_components", [])) or "none specified"

    tool_urls = "; ".join(
        f"{u['platform']}: {u['url']}" for u in metrics.get("design_tool_urls", [])
    ) or "none detected"

    formats_list = ", ".join(metrics.get("export_formats", [])) or "none detected"

    figma_section = ""
    figma_meta = metrics.get("figma_metadata")
    if figma_meta:
        figma_section = (
            "\nFIGMA_METADATA:\n"
            f"- file_name: {figma_meta.get('file_name', 'N/A')}\n"
            f"- page_count: {figma_meta.get('page_count', 0)}\n"
            f"- page_names: {', '.join(figma_meta.get('page_names', []))}\n"
            f"- frame_count: {figma_meta.get('frame_count', 0)}\n"
            f"- frame_names: {', '.join(figma_meta.get('frame_names', [])[:20])}\n"
            f"- component_count: {figma_meta.get('component_count', 0)}\n"
            f"- component_names: {', '.join(figma_meta.get('component_names', [])[:20])}\n"
        )

    return (
        f"PROJECT_ID: {project_id}\n"
        f"MILESTONE_ID: {milestone_id}\n\n"
        "MILESTONE_REQUIREMENTS:\n"
        f"- milestone_title: {requirements.get('milestone_title', 'N/A')}\n"
        f"- milestone_description: {requirements.get('milestone_description', 'N/A')}\n"
        f"- definition_of_done: {requirements.get('definition_of_done', 'N/A')}\n"
        f"- required_screens: {screens_list}\n"
        f"- required_components: {components_list}\n"
        f"- style_reference: {requirements.get('style_reference', 'none')}\n\n"
        "DESIGN_METRICS:\n"
        f"- design_tool_urls: {tool_urls}\n"
        f"- export_formats: {formats_list}\n"
        f"- accessibility_signals: {metrics.get('accessibility_signal_count', 0)}\n"
        f"- responsive_signals: {metrics.get('responsive_signal_count', 0)}\n"
        f"- color_specifications: {metrics.get('color_spec_count', 0)}\n"
        f"- typography_specifications: {metrics.get('typography_spec_count', 0)}\n"
        f"- screen_mentions: {metrics.get('screen_mention_count', 0)}\n"
        f"- component_mentions: {metrics.get('component_mention_count', 0)}\n"
        f"- design_system_signals: {metrics.get('design_system_signal_count', 0)}\n"
        f"- screen_coverage: {metrics.get('screen_coverage', 0):.1%}\n"
        f"- component_coverage: {metrics.get('component_coverage', 0):.1%}\n"
        f"{figma_section}\n"
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
    Call the LLM for subjective design evaluation.
    Returns (scores_dict, metadata_dict).
    Falls back to empty scores on failure.
    """
    user_prompt = _build_design_eval_user_prompt(
        project_id, milestone_id, requirements, metrics, submission,
    )

    try:
        result = await ai_service.call_groq(
            _DESIGN_EVAL_SYSTEM_PROMPT, user_prompt, api_key,
        )

        scores = {
            "requirements_coverage": _clamp(result.get("requirements_coverage", 50)),
            "visual_consistency": _clamp(result.get("visual_consistency", 50)),
            "accessibility": _clamp(result.get("accessibility", 50)),
            "responsive_completeness": _clamp(result.get("responsive_completeness", 50)),
            "export_readiness": _clamp(result.get("export_readiness", 50)),
        }
        meta = {
            "major_issues": result.get("major_issues", []),
            "improvement_suggestions": result.get("improvement_suggestions", []),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
        }
        return scores, meta

    except Exception as exc:
        logger.warning(f"Design LLM evaluation failed: {exc}")
        return {}, {"confidence": 0.3}


# ── Verdict ──────────────────────────────────────────────────────────────

def _determine_verdict(
    cms: float,
    requirements_coverage: int,
    metrics: dict,
) -> tuple[str, float]:
    """
    FULLY_COMPLETED:     CMS >= 85 AND requirements_coverage >= 80
    PARTIALLY_COMPLETED: CMS 50–84
    UNMET:               CMS < 50 OR no design artifacts at all
    """
    no_artifacts = (
        metrics.get("design_tool_count", 0) == 0
        and metrics.get("export_format_count", 0) == 0
        and metrics.get("total_urls", 0) == 0
    )
    if no_artifacts and metrics.get("word_count", 0) < 50:
        return "UNMET", 0.0

    if cms >= 85 and requirements_coverage >= 80:
        return "FULLY_COMPLETED", 100.0

    if cms >= 50:
        return "PARTIALLY_COMPLETED", round(cms, 1)

    return "UNMET", 0.0


# ── Issues & Suggestions ────────────────────────────────────────────────

def _detect_major_issues(
    scores: dict, metrics: dict, requirements: dict,
) -> list[str]:
    issues = []

    if metrics.get("design_tool_count", 0) == 0 and metrics.get("total_urls", 0) == 0:
        issues.append("No design tool URLs or file links provided — no verifiable artifacts")

    if scores["requirements_coverage"] < 50:
        issues.append("Major required screens or components are missing from the submission")

    if scores["accessibility"] < 30:
        issues.append("No accessibility considerations addressed (WCAG, contrast, alt-text)")

    if scores["responsive_completeness"] < 30:
        issues.append("No responsive/mobile variants provided")

    if scores["export_readiness"] < 30:
        issues.append("No export-ready file formats detected (PNG, SVG, PDF)")

    if scores["visual_consistency"] < 40:
        issues.append("No evidence of a consistent design system (colors, typography, spacing)")

    required_screens = requirements.get("required_screens", [])
    if required_screens and metrics.get("screen_coverage", 0) < 0.3:
        missing_pct = int((1 - metrics.get("screen_coverage", 0)) * 100)
        issues.append(f"{missing_pct}% of required screens are missing")

    return issues


def _generate_suggestions(scores: dict, metrics: dict) -> list[str]:
    suggestions = []

    if scores["requirements_coverage"] < 70:
        suggestions.append("Ensure all required screens and components are delivered and clearly labeled")

    if scores["visual_consistency"] < 70:
        suggestions.append("Document the design system — include color palette, typography scale, and spacing grid")

    if scores["accessibility"] < 70:
        suggestions.append("Add accessibility documentation: contrast ratios, alt-text plan, keyboard nav, WCAG compliance level")

    if scores["responsive_completeness"] < 70:
        suggestions.append("Provide mobile, tablet, and desktop variants with clear breakpoint specifications")

    if scores["export_readiness"] < 70:
        suggestions.append("Export assets in developer-ready formats (SVG for icons, PNG @2x for rasters, PDF for print)")

    if metrics.get("design_tool_count", 0) == 0:
        suggestions.append("Share a Figma/Sketch/Adobe XD link so reviewers can inspect the design directly")

    return suggestions


# ── Confidence ───────────────────────────────────────────────────────────

def _compute_confidence(
    scores: dict,
    metrics: dict,
    llm_meta: dict,
    figma_meta: dict | None,
) -> float:
    """
    Design confidence is lower than code/content because the LLM
    cannot actually view the designs.  Figma metadata significantly
    boosts confidence.
    """
    llm_conf = llm_meta.get("confidence", 0.4)

    has_design_url = metrics.get("design_tool_count", 0) > 0
    has_figma_data = figma_meta is not None
    has_exports = metrics.get("export_format_count", 0) > 0

    evidence_factor = 0.2
    if has_design_url:
        evidence_factor += 0.15
    if has_figma_data:
        evidence_factor += 0.20
    if has_exports:
        evidence_factor += 0.10

    all_scores = list(scores.values())
    if all_scores:
        spread = max(all_scores) - min(all_scores)
        agreement = 1 - (spread / 100)
    else:
        agreement = 0.5

    confidence = (llm_conf * 0.4) + (evidence_factor * 0.35) + (agreement * 0.25)

    if not has_design_url and not has_figma_data:
        confidence = min(confidence, 0.6)

    return round(max(0.1, min(1.0, confidence)), 2)


# ── Helpers ──────────────────────────────────────────────────────────────

def _clamp(value: int | float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(value)))


def _blend(det_score: int, llm_score: int, det_weight: float = 0.5) -> int:
    return _clamp(int(det_score * det_weight + llm_score * (1 - det_weight)))


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
        "figma_metadata": None,
    }
