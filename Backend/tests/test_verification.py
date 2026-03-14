"""
Tests for AAPPA Verification Engine
─────────────────────────────────────
Unit tests for classification, deterministic checks, score aggregation,
payment decision logic, and schema validation.
"""

import pytest
from services.verification_engine import (
    classify_submission,
    run_code_checks,
    run_content_checks,
    run_design_checks,
    compute_composite_score,
    compute_code_pipeline_score,
    make_payment_decision,
)


# ── Classification Tests ─────────────────────────────────────────────────

class TestClassifySubmission:
    def test_explicit_code(self):
        assert classify_submission("code", None) == "code"

    def test_explicit_content(self):
        assert classify_submission("content", None) == "content"

    def test_explicit_design(self):
        assert classify_submission("design", None) == "design"

    def test_explicit_mixed(self):
        assert classify_submission("mixed", None) == "mixed"

    def test_fallback_none_uses_domain(self):
        assert classify_submission(None, "Backend Development") == "code"

    def test_fallback_domain_content(self):
        assert classify_submission(None, "Blog Writing and SEO") == "content"

    def test_fallback_domain_design(self):
        assert classify_submission(None, "UI/UX Design") == "design"

    def test_fallback_unknown_domain(self):
        assert classify_submission(None, "Random Unknown") == "mixed"

    def test_fallback_none_none(self):
        assert classify_submission(None, None) == "mixed"


# ── Deterministic Code Checks ───────────────────────────────────────────

class TestCodeChecks:
    def test_substantial_code(self):
        code = """
import os
import sys

def process_data(input_file):
    try:
        with open(input_file) as f:
            data = f.read()
        if not data:
            raise ValueError("Empty file")
        for line in data.split('\\n'):
            yield line.strip()
    except FileNotFoundError:
        print("File not found")
        return []

class DataProcessor:
    def __init__(self):
        self.cache = {}
    
    async def fetch(self, url):
        return await self.client.get(url)

def test_process_data():
    result = list(process_data("test.txt"))
    assert len(result) > 0

URL: https://github.com/user/repo
"""
        scores = run_code_checks(code)
        assert scores["structure_check"] > 0
        assert scores["error_handling_check"] > 0
        assert scores["test_presence_check"] > 0
        assert scores["artifact_url_check"] == 100

    def test_empty_submission(self):
        scores = run_code_checks("")
        assert scores["structure_check"] == 0
        assert scores["artifact_url_check"] == 0


# ── Deterministic Content Checks ────────────────────────────────────────

class TestContentChecks:
    def test_well_structured_content(self):
        content = """# Introduction

This is the first paragraph about our topic. It covers important points 
that are relevant to the reader.

## Key Findings

The research shows several interesting trends. First, we observed a 
significant increase in engagement. Second, the conversion rates improved.

## Conclusion

In summary, the results demonstrate clear benefits. Future work should 
explore additional variables.
"""
        scores = run_content_checks(content)
        assert scores["heading_structure_check"] > 0
        assert scores["paragraph_structure_check"] > 0
        assert scores["readability_check"] > 0

    def test_minimal_content(self):
        scores = run_content_checks("Short.")
        assert scores["word_count_check"] < 50


# ── Deterministic Design Checks ─────────────────────────────────────────

class TestDesignChecks:
    def test_design_with_artifacts(self):
        submission = """
Completed the landing page design in Figma.

Deliverables:
- homepage-desktop.png (1440x900)
- homepage-mobile.png (375x812)
- components.svg export
- Design system PDF

Links:
- Figma: https://figma.com/file/abc123
- Prototype: https://figma.com/proto/abc123

Accessibility notes:
- All images have alt text descriptions
- Color contrast meets WCAG AA standards
- Responsive breakpoints: 375px, 768px, 1024px, 1440px
"""
        scores = run_design_checks(submission)
        assert scores["export_format_check"] > 0
        assert scores["design_tool_url_check"] > 0
        assert scores["accessibility_mention_check"] > 0
        assert scores["responsive_check"] > 0

    def test_empty_design(self):
        scores = run_design_checks("Done with design.")
        assert scores["export_format_check"] == 0


# ── Composite Score Aggregation ──────────────────────────────────────────

class TestCompositeScore:
    def test_both_sources(self):
        det = {"check_a": 80, "check_b": 60}
        llm = {"crit_0": 90, "crit_1": 70}
        score, confidence = compute_composite_score(det, llm, "code")
        # det_avg=70, llm_avg=80 → 70*0.3 + 80*0.7 = 77
        assert 75 <= score <= 80
        assert confidence > 0.6

    def test_deterministic_only(self):
        det = {"check_a": 100}
        score, confidence = compute_composite_score(det, {}, "code")
        assert score == 100
        assert confidence == 0.5

    def test_llm_only(self):
        llm = {"crit_0": 50}
        score, confidence = compute_composite_score({}, llm, "code")
        assert score == 50
        assert confidence == 0.5

    def test_empty_both(self):
        score, confidence = compute_composite_score({}, {}, "code")
        assert score == 0
        assert confidence == 0

    def test_agreement_boosts_confidence(self):
        det = {"a": 80}
        llm = {"b": 80}
        _, conf_agree = compute_composite_score(det, llm, "code")

        det2 = {"a": 20}
        llm2 = {"b": 80}
        _, conf_disagree = compute_composite_score(det2, llm2, "code")
        assert conf_agree > conf_disagree


# ── Payment Decision Tests ───────────────────────────────────────────────

class TestPaymentDecision:
    def test_full_pay_above_85(self):
        result = make_payment_decision(90, 0.9, 0.8)
        assert result["action"] == "FULL_PAY"
        assert result["recommended_pct"] == 100

    def test_partial_pay_50_to_84(self):
        result = make_payment_decision(70, 0.85, 0.7)
        assert result["action"] == "PARTIAL_PAY"
        assert result["recommended_pct"] == 70

    def test_refund_below_50(self):
        result = make_payment_decision(30, 0.9, 0.8)
        assert result["action"] == "REFUND"
        assert result["recommended_pct"] == 0

    def test_hitl_low_confidence(self):
        result = make_payment_decision(90, 0.5, 0.9)
        assert result["action"] == "HITL"
        assert "confidence" in result["reason"].lower()

    def test_hitl_low_evidence(self):
        result = make_payment_decision(70, 0.85, 0.1)
        assert result["action"] == "HITL"
        assert "evidence" in result["reason"].lower()

    def test_high_score_low_evidence_still_passes(self):
        # Score ≥85 should still pass even with low evidence
        result = make_payment_decision(90, 0.9, 0.1)
        assert result["action"] == "FULL_PAY"

    def test_boundary_85_is_full_pay(self):
        result = make_payment_decision(85, 0.9, 0.8)
        assert result["action"] == "FULL_PAY"

    def test_boundary_50_is_partial(self):
        result = make_payment_decision(50, 0.9, 0.8)
        assert result["action"] == "PARTIAL_PAY"


# ── Schema Validation Tests ──────────────────────────────────────────────

class TestSchemaValidation:
    def test_decomposition_result_normalises_payments(self):
        from schemas.verification import DecompositionResult

        data = {
            "project_classification": {
                "primary_type": "code",
                "type_confidence": 0.9,
            },
            "milestones": [
                {
                    "id": "M1",
                    "title": "Setup",
                    "task_type": "code",
                    "estimated_days": 3,
                    "payment_percentage": 60,
                    "acceptance_criteria": [
                        {"id": "C1", "criterion": "Project setup complete"},
                    ],
                },
                {
                    "id": "M2",
                    "title": "Core",
                    "task_type": "code",
                    "estimated_days": 5,
                    "payment_percentage": 60,
                    "acceptance_criteria": [
                        {"id": "C1", "criterion": "Core logic works"},
                    ],
                },
            ],
        }
        result = DecompositionResult.model_validate(data)
        total = sum(m.payment_percentage for m in result.milestones)
        assert abs(total - 100) < 1.0  # Should be normalised

    def test_aqa_result_schema(self):
        from schemas.verification import AQAResult

        data = {
            "overallScore": 75,
            "completionStatus": "PARTIALLY_COMPLETED",
            "paymentRecommendation": "PRO_RATED",
            "proRatedPercentage": 75,
            "modality": "code",
            "confidence": 0.85,
            "evidenceCompleteness": 0.6,
        }
        result = AQAResult.model_validate(data)
        assert result.overallScore == 75
        assert result.modality == "code"
        assert result.confidence == 0.85


# ── Code Pipeline Score Tests ──────────────────────────────────────────

class TestCodePipelineScore:
    def test_weighted_scoring_all_layers(self):
        """All 4 layers contributing: static*0.15 + runtime*0.35 + sonar*0.20 + llm*0.30."""
        static = {"parse_check": 80, "structure_check": 90}
        runtime = {"test_execution": 70, "test_presence": 100}
        sonar = {"sonar_gate": 100}
        llm = {"criterion_0": 80, "criterion_1": 90}

        score, confidence = compute_code_pipeline_score(static, runtime, sonar, llm)
        # static_avg=85, runtime_avg=85, sonar_avg=100, llm_avg=85
        # = 85*0.15 + 85*0.35 + 100*0.20 + 85*0.30 = 12.75 + 29.75 + 20 + 25.5 = 88.0
        assert 85 <= score <= 92
        assert confidence > 0.7

    def test_sonarqube_fail_caps_at_70(self):
        """SonarQube ERROR status caps overall score at 70."""
        static = {"parse_check": 100}
        runtime = {"test_execution": 100}
        sonar = {"sonar_gate": 25}
        llm = {"criterion_0": 100}

        score, _ = compute_code_pipeline_score(
            static, runtime, sonar, llm, sonar_gate_status="ERROR"
        )
        assert score <= 70

    def test_llm_alone_cannot_produce_full_score(self):
        """When only LLM has data, score is capped below FULL_PAY threshold."""
        static = {}
        runtime = {}
        sonar = {}
        llm = {"criterion_0": 100, "criterion_1": 100}

        score, confidence = compute_code_pipeline_score(static, runtime, sonar, llm)
        # Score should be capped at 84 (below 85 full-pay threshold)
        assert score <= 84
        assert confidence <= 0.65

    def test_confidence_increases_with_layers(self):
        """More layers contributing → higher confidence."""
        llm_only_score, llm_only_conf = compute_code_pipeline_score(
            {}, {}, {}, {"c0": 80}
        )
        two_layers_score, two_layers_conf = compute_code_pipeline_score(
            {"parse": 80}, {}, {}, {"c0": 80}
        )
        all_layers_score, all_layers_conf = compute_code_pipeline_score(
            {"parse": 80}, {"test": 80}, {"sonar": 80}, {"c0": 80}
        )
        assert all_layers_conf > two_layers_conf
        assert two_layers_conf > llm_only_conf

    def test_deterministic_pass_allows_full_score(self):
        """When static/runtime pass, LLM doesn't cap the score."""
        static = {"parse_check": 90}
        runtime = {"test_execution": 95}
        sonar = {"sonar_gate": 100}
        llm = {"criterion_0": 95, "criterion_1": 90}

        score, _ = compute_code_pipeline_score(static, runtime, sonar, llm)
        assert score >= 85  # Should reach full-pay threshold
