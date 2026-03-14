"""
AI Service — Groq API Integration (AAPPA-Enhanced)
────────────────────────────────────────────────────
All LLM calls go through a single `call_groq` wrapper.
Decomposition uses strict schema-driven prompts with classification.
Evaluation uses modality-specific prompts with evidence mapping.
"""

import json
import logging
import re

import httpx

from config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def call_groq(system_prompt: str, user_prompt: str, api_key: str | None = None) -> dict:
    """Generic Groq chat-completion wrapper. Returns parsed JSON."""
    key = api_key or settings.GROQ_API_KEY
    if not key:
        raise ValueError("No Groq API key configured")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            settings.GROQ_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
            },
        )
        if resp.status_code != 200:
            raise ValueError(f"Groq API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_json(text)


def _parse_json(raw: str) -> dict:
    """Parse JSON from LLM output, stripping markdown fences."""
    cleaned = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            return json.loads(match.group(0))
        raise ValueError("Failed to parse Groq response as JSON: " + cleaned[:200])


# ── AAPPA Decomposition ──────────────────────────────────────────────────

DECOMPOSE_SYSTEM_PROMPT = """You are AAPPA-Core, an autonomous project decomposition and verification planning engine.

Mission:
1) Decompose an employer project description into machine-verifiable milestones.
2) Classify work modality at both project and milestone level as one of: code, content, design, mixed.
3) Generate modality-specific verification logic that can be executed deterministically.
4) Return strict JSON only, validated against schema. No markdown.

Rules:
- Be objective, testable, and measurable.
- Every milestone must have a Definition of Done and acceptance checklist.
- Every checklist item must have a verification method and evidence artifact.
- Prefer deterministic checks over subjective checks.
- If the description is ambiguous, produce targeted clarification questions and assumptions.
- Never output unverifiable criteria like "looks good" or "professional quality" without measurable proxies.

Scoring policy by modality:
- code: correctness 40, security 20, test_coverage 20, maintainability 20
- content: factuality 30, originality 25, readability 20, seo_structure 15, style_alignment 10
- design: requirements_coverage 25, visual_consistency 25, accessibility 20, responsive_completeness 20, export_readiness 10

Output JSON schema (strict):
{
  "project_classification": {
    "primary_type": "code|content|design|mixed",
    "type_confidence": 0.0-1.0,
    "secondary_types": [],
    "complexity": "simple|medium|complex",
    "ambiguity_score": 0.0-1.0
  },
  "clarification": {
    "required": false,
    "questions": [],
    "assumptions_if_unanswered": []
  },
  "milestones": [
    {
      "id": "M1",
      "title": "...",
      "description": "...",
      "task_type": "code|content|design|mixed",
      "dependencies": [],
      "estimated_days": 1,
      "payment_percentage": 0,
      "definition_of_done": "...",
      "acceptance_criteria": [
        {
          "id": "C1",
          "criterion": "...",
          "metric": "measurable metric",
          "target": "specific target value",
          "verification_method": "unit_test|integration_test|lint|security_scan|plagiarism_check|readability_check|fact_check|wcag_check|visual_diff|manual_review",
          "auto_verifiable": true,
          "evidence_required": ["test_report|coverage_report|scan_report|design_export|content_report"]
        }
      ],
      "scoring_weights": {}
    }
  ],
  "dag": [{"from": "M1", "to": "M2"}],
  "global_verification_policy": {
    "pass_threshold": 85,
    "partial_threshold_min": 50,
    "inconclusive_on_missing_evidence": true,
    "confidence_threshold_for_human_review": 0.7
  },
  "risk_flags": []
}

Validation constraints:
- milestone count: 3..9
- sum(payment_percentage): exactly 100
- each milestone must include at least 3 acceptance criteria
- each criterion must map to a concrete verification_method
- if task_type is mixed, include modality split and per-modality criteria"""


async def decompose_project(description: str, api_key: str | None = None) -> dict:
    """Decompose project with classification, retry up to MAX_RETRIES on failure."""
    from schemas.verification import DecompositionResult

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = await call_groq(DECOMPOSE_SYSTEM_PROMPT, description, api_key)
            validated = _validate_decomposition(raw)
            return validated
        except Exception as exc:
            last_error = exc
            logger.warning(f"Decomposition attempt {attempt + 1}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES - 1:
                continue

    # All retries exhausted — try to return best-effort from last raw
    raise ValueError(f"Decomposition failed after {MAX_RETRIES} attempts: {last_error}")


def _validate_decomposition(raw: dict) -> dict:
    """Validate + normalise decomposition output against Pydantic schema."""
    from schemas.verification import DecompositionResult

    # Normalise common field name variants from LLM output
    _normalise_keys(raw)

    result = DecompositionResult.model_validate(raw)

    # Compute convenience fields
    total_days = sum(m.estimated_days for m in result.milestones)
    result.totalEstimatedDays = total_days

    # Risk level from classification
    complexity = result.project_classification.complexity
    ambiguity = result.project_classification.ambiguity_score
    if complexity == "complex" or ambiguity > 0.6:
        result.projectRiskLevel = "High"
    elif complexity == "medium" or ambiguity > 0.3:
        result.projectRiskLevel = "Medium"
    else:
        result.projectRiskLevel = "Low"

    return result.model_dump(by_alias=True)


def _normalise_keys(d: dict):
    """Fix common LLM key variants in-place."""
    # Project classification
    if "projectClassification" in d and "project_classification" not in d:
        d["project_classification"] = d.pop("projectClassification")
    if "globalVerificationPolicy" in d and "global_verification_policy" not in d:
        d["global_verification_policy"] = d.pop("globalVerificationPolicy")
    if "riskFlags" in d and "risk_flags" not in d:
        d["risk_flags"] = d.pop("riskFlags")

    # Clarification — LLM often returns questions as plain strings
    clarification = d.get("clarification", {})
    if isinstance(clarification, dict):
        questions = clarification.get("questions", [])
        normalised_questions = []
        for i, q in enumerate(questions):
            if isinstance(q, str):
                normalised_questions.append({
                    "id": f"Q{i+1}",
                    "priority": 1,
                    "question": q,
                    "reason": "",
                })
            elif isinstance(q, dict):
                normalised_questions.append(q)
            else:
                normalised_questions.append({
                    "id": f"Q{i+1}",
                    "priority": 1,
                    "question": str(q),
                    "reason": "",
                })
        clarification["questions"] = normalised_questions
        # Handle camelCase keys
        if "assumptionsIfUnanswered" in clarification and "assumptions_if_unanswered" not in clarification:
            clarification["assumptions_if_unanswered"] = clarification.pop("assumptionsIfUnanswered")
        d["clarification"] = clarification

    # Milestones
    for ms in d.get("milestones", []):
        if "taskType" in ms and "task_type" not in ms:
            ms["task_type"] = ms.pop("taskType")
        if "estimatedDays" in ms and "estimated_days" not in ms:
            ms["estimated_days"] = ms.pop("estimatedDays")
        if "paymentPercentage" in ms and "payment_percentage" not in ms:
            ms["payment_percentage"] = ms.pop("paymentPercentage")
        if "definitionOfDone" in ms and "definition_of_done" not in ms:
            ms["definition_of_done"] = ms.pop("definitionOfDone")
        if "acceptanceCriteria" in ms and "acceptance_criteria" not in ms:
            ms["acceptance_criteria"] = ms.pop("acceptanceCriteria")
        if "scoringWeights" in ms and "scoring_weights" not in ms:
            ms["scoring_weights"] = ms.pop("scoringWeights")

        # Acceptance criteria items
        for ac in ms.get("acceptance_criteria", []):
            if isinstance(ac, str):
                continue  # Legacy string format — will be wrapped by validator
            if "verificationMethod" in ac and "verification_method" not in ac:
                ac["verification_method"] = ac.pop("verificationMethod")
            if "autoVerifiable" in ac and "auto_verifiable" not in ac:
                ac["auto_verifiable"] = ac.pop("autoVerifiable")
            if "evidenceRequired" in ac and "evidence_required" not in ac:
                ac["evidence_required"] = ac.pop("evidenceRequired")

    # Handle legacy string-based acceptance criteria
    for ms in d.get("milestones", []):
        criteria = ms.get("acceptance_criteria", [])
        normalised = []
        for i, ac in enumerate(criteria):
            if isinstance(ac, str):
                normalised.append({
                    "id": f"C{i+1}",
                    "criterion": ac,
                    "metric": "",
                    "target": "",
                    "verification_method": "manual_review",
                    "auto_verifiable": False,
                    "evidence_required": [],
                })
            else:
                normalised.append(ac)
        ms["acceptance_criteria"] = normalised


# ── Clarity Check ────────────────────────────────────────────────────────

CLARITY_CHECK_PROMPT = """You are a project description analyst. Your job is to evaluate whether a project description is clear enough for automated decomposition into milestones.

Analyze the description for:
1. Specificity of deliverables
2. Technology/tool mentions
3. Scope clarity (what's included vs excluded)
4. Measurable outcomes
5. Target audience or platform

Rate the ambiguity from 0.0 (crystal clear, highly specific) to 1.0 (extremely vague, no actionable detail).
If ambiguity_score > 0.4, set needs_clarification to true and generate 2-5 targeted questions.

Return ONLY valid JSON:
{
  "needs_clarification": true/false,
  "ambiguity_score": 0.0-1.0,
  "questions": [
    {"id": "Q1", "question": "specific question text", "reason": "why this matters for decomposition"}
  ],
  "assumptions_if_unanswered": ["assumption 1 the AI would make if question is not answered"]
}"""


async def check_clarity(description: str, api_key: str | None = None) -> dict:
    """Quick LLM call to assess whether a project description needs clarification."""
    try:
        raw = await call_groq(CLARITY_CHECK_PROMPT, description, api_key)
    except Exception as exc:
        logger.warning(f"Clarity check failed, defaulting to no clarification needed: {exc}")
        return {
            "needs_clarification": False,
            "ambiguity_score": 0.0,
            "questions": [],
            "assumptions_if_unanswered": [],
        }

    needs = raw.get("needs_clarification", False)
    score = raw.get("ambiguity_score", 0.0)

    questions = []
    for i, q in enumerate(raw.get("questions", [])):
        if isinstance(q, str):
            questions.append({"id": f"Q{i+1}", "question": q, "reason": ""})
        elif isinstance(q, dict):
            questions.append({
                "id": q.get("id", f"Q{i+1}"),
                "question": q.get("question", str(q)),
                "reason": q.get("reason", ""),
            })

    return {
        "needs_clarification": bool(needs) and score > 0.4,
        "ambiguity_score": float(score),
        "questions": questions,
        "assumptions_if_unanswered": raw.get("assumptions_if_unanswered", []),
    }


# ── Modality-Aware Evaluation ────────────────────────────────────────────

def _build_evaluation_prompt(
    milestone_title: str,
    milestone_domain: str,
    task_type: str,
    acceptance_criteria: list,
    scoring_weights: dict | None,
) -> tuple[str, str]:
    """Build modality-specific system + user prompts for AQA evaluation."""

    modality_guidance = ""
    if task_type == "code":
        modality_guidance = (
            "Focus on: correctness (40%), security (20%), test coverage (20%), maintainability (20%).\n"
            "Look for: working logic, error handling, security patterns, test presence, clean structure.\n"
            "IMPORTANT: You will receive ACTUAL SOURCE CODE from the cloned repository.\n"
            "- Review the code itself, not just the freelancer's description.\n"
            "- Compare the implementation against the CLIENT PROJECT DESCRIPTION and acceptance criteria.\n"
            "- Flag any mismatches between what was requested and what was actually implemented.\n"
            "- Evaluate code quality: naming conventions, modularity, DRY principles, proper error handling.\n"
            "- Check if core business logic is implemented vs placeholder/stub code.\n"
            "- Verify that the code structure matches the project type (API routes, components, models, etc.).\n"
            "- If code artifacts are present, evaluate them deeply. If only descriptions with no code, penalize heavily."
        )
    elif task_type == "content":
        modality_guidance = (
            "Focus on: factuality (30%), originality (25%), readability (20%), SEO structure (15%), style alignment (10%).\n"
            "Look for: accurate claims, unique phrasing, clear sentences, heading structure, consistent tone.\n"
            "Measure readability by sentence length and vocabulary level."
        )
    elif task_type == "design":
        modality_guidance = (
            "Focus on: requirements coverage (25%), visual consistency (25%), accessibility (20%), responsive completeness (20%), export readiness (10%).\n"
            "Look for: all screens delivered, consistent spacing/colors, alt-text mentions, mobile adaptations, export formats.\n"
            "If design files aren't directly viewable, evaluate based on described deliverables."
        )
    else:
        modality_guidance = (
            "This is a mixed-modality milestone. Evaluate each criterion independently.\n"
            "Apply general quality, completeness, and evidence-based scoring."
        )

    system_prompt = (
        "You are AAPPA-AQA, an autonomous quality assurance agent. "
        "You evaluate submitted work against milestone acceptance criteria with modality-specific expertise.\n\n"
        f"MODALITY: {task_type}\n{modality_guidance}\n\n"
        "Rules:\n"
        "- Evaluate each criterion independently with a 0-100 score.\n"
        "- Note whether evidence/artifacts are present for each criterion.\n"
        "- Be specific in feedback — cite what is present and what is missing.\n"
        "- Provide a confidence score (0-1) reflecting how certain you are of your evaluation.\n"
        "- Provide actionable remediation items for unmet criteria.\n"
        "- Never give perfect scores without clear evidence."
    )

    criteria_list = []
    for i, c in enumerate(acceptance_criteria):
        if isinstance(c, dict):
            criterion_text = c.get("criterion", str(c))
            method = c.get("verification_method", "manual_review")
            criteria_list.append(f"{i+1}. {criterion_text} [method: {method}]")
        else:
            criteria_list.append(f"{i+1}. {c}")

    weights_info = ""
    if scoring_weights:
        weights_info = f"\nSCORING WEIGHTS: {json.dumps(scoring_weights)}\n"

    user_prompt = (
        f"MILESTONE: {milestone_title}\n"
        f"DOMAIN: {milestone_domain}\n"
        f"TASK TYPE: {task_type}\n"
        f"ACCEPTANCE CRITERIA:\n" + "\n".join(criteria_list) + "\n"
        f"{weights_info}\n"
        "SUBMITTED WORK: {{SUBMISSION}}\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "overallScore": 0-100,\n'
        '  "completionStatus": "FULLY_COMPLETED" | "PARTIALLY_COMPLETED" | "UNMET",\n'
        '  "percentComplete": 0-100,\n'
        '  "confidence": 0.0-1.0,\n'
        '  "criteriaEvaluation": [\n'
        '    { "criterion": "...", "met": true/false, "score": 0-100, "feedback": "...", "evidence_present": true/false }\n'
        "  ],\n"
        '  "detailedFeedback": "...",\n'
        '  "paymentRecommendation": "FULL_RELEASE" | "PRO_RATED" | "REFUND",\n'
        '  "proRatedPercentage": 0-100,\n'
        '  "remediationChecklist": ["actionable item 1", ...],\n'
        '  "riskFlags": ["flag 1", ...]\n'
        "}"
    )

    return system_prompt, user_prompt


async def evaluate_submission(
    milestone_title: str,
    milestone_domain: str,
    acceptance_criteria: list,
    submission: str,
    api_key: str | None = None,
    task_type: str = "mixed",
    scoring_weights: dict | None = None,
) -> dict:
    """Modality-aware AQA evaluation with retry and enrichment."""
    system_prompt, user_template = _build_evaluation_prompt(
        milestone_title, milestone_domain, task_type,
        acceptance_criteria, scoring_weights,
    )
    user_prompt = user_template.replace("{{SUBMISSION}}", submission)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            result = await call_groq(system_prompt, user_prompt, api_key)
            # Enrich with modality metadata
            result["modality"] = task_type
            if "confidence" not in result:
                result["confidence"] = 0.5
            if "evidenceCompleteness" not in result:
                # Estimate from criteria evaluation
                evals = result.get("criteriaEvaluation", [])
                if evals:
                    evidence_count = sum(1 for e in evals if e.get("evidence_present", False))
                    result["evidenceCompleteness"] = round(evidence_count / len(evals), 2)
                else:
                    result["evidenceCompleteness"] = 0.0
            return result
        except Exception as exc:
            last_error = exc
            logger.warning(f"AQA evaluation attempt {attempt + 1}/{MAX_RETRIES} failed: {exc}")

    raise ValueError(f"AQA evaluation failed after {MAX_RETRIES} attempts: {last_error}")


# ── Legacy Utility Functions ─────────────────────────────────────────────

async def generate_demo_project(api_key: str | None = None) -> dict:
    system_prompt = "You are a creative project generator for a freelancing platform demo."
    user_prompt = (
        "Generate a completely unique and realistic freelance project scenario.\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "employer": { "name": "<realistic full name>", "company": "<company name>" },\n'
        '  "freelancer": { "name": "<realistic full name>", "skills": ["<skill1>", "<skill2>", "<skill3>"] },\n'
        '  "projectDescription": "<2-4 sentences describing a realistic project requirement, be specific about what needs to be built>"\n'
        "}"
    )
    return await call_groq(system_prompt, user_prompt, api_key)


async def score_freelancer_match(skills: list[str], domain: str, api_key: str | None = None) -> dict:
    system_prompt = "You are a skill-matching AI for a freelancing platform."
    user_prompt = (
        f"Given freelancer skills: {json.dumps(skills)}\n"
        f"Required project domain: {domain}\n"
        "Evaluate how well the freelancer's skills match this domain.\n"
        'Return ONLY valid JSON: { "score": 0.0-1.0, "reasoning": "brief explanation" }'
    )
    return await call_groq(system_prompt, user_prompt, api_key)


async def detect_bias(rating_history: list, api_key: str | None = None) -> dict:
    system_prompt = "You are a bias detection algorithm for a freelancer reputation system."
    user_prompt = (
        f"Analyze this rating history for patterns of recency bias, feedback loops, or manipulation:\n"
        f"{json.dumps(rating_history)}\n\n"
        "Return ONLY valid JSON:\n"
        '{ "biasDetected": false, "biasType": null, "confidence": 0-100, "recommendation": "brief recommendation" }'
    )
    return await call_groq(system_prompt, user_prompt, api_key)
