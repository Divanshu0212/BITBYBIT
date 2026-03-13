"""
AI Service — Groq API Integration
───────────────────────────────────
All LLM calls go through a single `call_groq` wrapper.
Functions mirror the frontend `geminiApi.js`.
"""

import json
import re

import httpx

from config import settings


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


# ── Domain Functions ─────────────────────────────────────────────────────

async def decompose_project(description: str, api_key: str | None = None) -> dict:
    system_prompt = (
        "You are an expert project manager AI. Given a vague project description, decompose it into:\n"
        "1. A list of 3-7 time-bound milestones, each with:\n"
        "   - title (string)\n"
        "   - description (string)\n"
        "   - domain (string, e.g. \"Backend Development\", \"UI/UX Design\", \"Content Writing\")\n"
        "   - estimatedDays (number)\n"
        "   - acceptanceCriteria (array of 3-5 specific, testable strings)\n"
        "   - complexityScore (1-10)\n"
        "2. dag: array of { from: milestoneIndex, to: milestoneIndex }\n"
        "3. totalEstimatedDays (number)\n"
        "4. projectRiskLevel: \"Low\" | \"Medium\" | \"High\"\n\n"
        "Return ONLY valid JSON. No markdown, no explanation."
    )
    return await call_groq(system_prompt, description, api_key)


async def evaluate_submission(
    milestone_title: str,
    milestone_domain: str,
    acceptance_criteria: list[str],
    submission: str,
    api_key: str | None = None,
) -> dict:
    system_prompt = "You are an autonomous quality assurance agent. Evaluate submitted work against milestone acceptance criteria."
    criteria_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(acceptance_criteria))
    user_prompt = (
        f"MILESTONE: {milestone_title}\n"
        f"DOMAIN: {milestone_domain}\n"
        f"ACCEPTANCE CRITERIA:\n{criteria_list}\n"
        f"SUBMITTED WORK: {submission}\n\n"
        "Evaluate each criterion and return ONLY valid JSON:\n"
        "{\n"
        '  "overallScore": 0-100,\n'
        '  "completionStatus": "FULLY_COMPLETED" | "PARTIALLY_COMPLETED" | "UNMET",\n'
        '  "percentComplete": 0-100,\n'
        '  "criteriaEvaluation": [\n'
        '    { "criterion": "...", "met": true/false, "score": 0-100, "feedback": "..." }\n'
        "  ],\n"
        '  "detailedFeedback": "...",\n'
        '  "paymentRecommendation": "FULL_RELEASE" | "PRO_RATED" | "REFUND",\n'
        '  "proRatedPercentage": 0-100\n'
        "}"
    )
    return await call_groq(system_prompt, user_prompt, api_key)


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
