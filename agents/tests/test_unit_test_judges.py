"""Tests for judge classes — CoverageJudge, QualityJudge, AdversarialJudge."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.exceptions import JudgeEvaluationError
from agents.unit_test_agent.judges import (
    AdversarialJudge,
    CoverageJudge,
    QualityJudge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(content: str) -> MagicMock:
    """Create a mock ModelAgent returning the given content."""
    resp = MagicMock()
    resp.content = content
    model = MagicMock()
    model.complete = AsyncMock(return_value=resp)
    return model


SOURCE_CODE = "def add(a, b): return a + b"
TEST_CODE = "def test_add(): assert add(1, 2) == 3"


# ---------------------------------------------------------------------------
# CoverageJudge
# ---------------------------------------------------------------------------


class TestCoverageJudge:
    """Tests for the CoverageJudge (Layer 1)."""

    @pytest.mark.asyncio
    async def test_passing_verdict(self) -> None:
        config = UnitTestAgentConfig(coverage_threshold=80.0)
        payload = json.dumps({
            "passed": True,
            "score": 90.0,
            "issues": [],
            "suggestions": [],
        })
        model = _make_model(payload)
        judge = CoverageJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.passed is True
        assert verdict.score == 90.0
        assert verdict.issues == []

    @pytest.mark.asyncio
    async def test_failing_verdict(self) -> None:
        config = UnitTestAgentConfig(coverage_threshold=80.0)
        payload = json.dumps({
            "passed": False,
            "score": 50.0,
            "issues": ["No test for negative inputs"],
            "suggestions": ["Add test_add_negatives"],
        })
        model = _make_model(payload)
        judge = CoverageJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.passed is False
        assert verdict.score == 50.0
        assert len(verdict.issues) == 1

    @pytest.mark.asyncio
    async def test_threshold_boundary(self) -> None:
        config = UnitTestAgentConfig(coverage_threshold=80.0)
        payload = json.dumps({
            "passed": True,
            "score": 80.0,
            "issues": [],
            "suggestions": [],
        })
        model = _make_model(payload)
        judge = CoverageJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.passed is True
        assert verdict.score == 80.0

    @pytest.mark.asyncio
    async def test_below_threshold_overrides_llm_passed(self) -> None:
        """Even if LLM says passed=True, score below threshold means fail."""
        config = UnitTestAgentConfig(coverage_threshold=80.0)
        payload = json.dumps({
            "passed": True,
            "score": 60.0,
            "issues": [],
            "suggestions": [],
        })
        model = _make_model(payload)
        judge = CoverageJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        # The judge uses score >= threshold, not the LLM's "passed" field
        assert verdict.passed is False

    @pytest.mark.asyncio
    async def test_malformed_json_raises(self) -> None:
        config = UnitTestAgentConfig()
        model = _make_model("not valid json at all")
        judge = CoverageJudge(model, config)

        with pytest.raises(JudgeEvaluationError):
            await judge.evaluate(SOURCE_CODE, TEST_CODE)

    @pytest.mark.asyncio
    async def test_markdown_fences_stripped(self) -> None:
        config = UnitTestAgentConfig(coverage_threshold=80.0)
        payload = '```json\n' + json.dumps({
            "passed": True,
            "score": 85.0,
            "issues": [],
            "suggestions": [],
        }) + '\n```'
        model = _make_model(payload)
        judge = CoverageJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.score == 85.0

    def test_judge_name(self) -> None:
        config = UnitTestAgentConfig()
        model = MagicMock()
        judge = CoverageJudge(model, config)
        assert judge.judge_name == "coverage"

    def test_threshold_value(self) -> None:
        config = UnitTestAgentConfig(coverage_threshold=90.0)
        model = MagicMock()
        judge = CoverageJudge(model, config)
        assert judge.threshold == 90.0


# ---------------------------------------------------------------------------
# QualityJudge
# ---------------------------------------------------------------------------


class TestQualityJudge:
    """Tests for the QualityJudge (Layer 2)."""

    @pytest.mark.asyncio
    async def test_passing_verdict(self) -> None:
        config = UnitTestAgentConfig(quality_threshold=70.0)
        payload = json.dumps({
            "passed": True,
            "score": 85.0,
            "issues": [],
            "suggestions": [],
        })
        model = _make_model(payload)
        judge = QualityJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.passed is True
        assert verdict.score == 85.0

    @pytest.mark.asyncio
    async def test_failing_verdict_with_feedback(self) -> None:
        config = UnitTestAgentConfig(quality_threshold=70.0)
        payload = json.dumps({
            "passed": False,
            "score": 45.0,
            "issues": ["Test names not descriptive", "No assertions on type"],
            "suggestions": ["Use test_add_returns_sum_of_two_integers pattern"],
        })
        model = _make_model(payload)
        judge = QualityJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.passed is False
        assert len(verdict.issues) == 2
        assert len(verdict.suggestions) == 1

    def test_judge_name(self) -> None:
        config = UnitTestAgentConfig()
        model = MagicMock()
        judge = QualityJudge(model, config)
        assert judge.judge_name == "quality"

    def test_threshold_value(self) -> None:
        config = UnitTestAgentConfig(quality_threshold=75.0)
        model = MagicMock()
        judge = QualityJudge(model, config)
        assert judge.threshold == 75.0


# ---------------------------------------------------------------------------
# AdversarialJudge
# ---------------------------------------------------------------------------


class TestAdversarialJudge:
    """Tests for the AdversarialJudge (Layer 3)."""

    @pytest.mark.asyncio
    async def test_passing_verdict(self) -> None:
        config = UnitTestAgentConfig(adversarial_threshold=70.0)
        payload = json.dumps({
            "passed": True,
            "score": 80.0,
            "issues": [],
            "suggestions": [],
        })
        model = _make_model(payload)
        judge = AdversarialJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.passed is True

    @pytest.mark.asyncio
    async def test_mutation_detection_failure(self) -> None:
        config = UnitTestAgentConfig(adversarial_threshold=70.0)
        payload = json.dumps({
            "passed": False,
            "score": 30.0,
            "issues": [
                "Changing + to - in add() would not be caught",
                "Swapping a,b arguments would not be caught",
            ],
            "suggestions": [
                "Add test_add_noncommutative with different a,b",
                "Add test_add_subtraction_different to distinguish + from -",
            ],
        })
        model = _make_model(payload)
        judge = AdversarialJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.passed is False
        assert len(verdict.issues) == 2
        assert len(verdict.suggestions) == 2

    def test_judge_name(self) -> None:
        config = UnitTestAgentConfig()
        model = MagicMock()
        judge = AdversarialJudge(model, config)
        assert judge.judge_name == "adversarial"

    def test_threshold_value(self) -> None:
        config = UnitTestAgentConfig(adversarial_threshold=60.0)
        model = MagicMock()
        judge = AdversarialJudge(model, config)
        assert judge.threshold == 60.0

    @pytest.mark.asyncio
    async def test_non_dict_response_raises(self) -> None:
        config = UnitTestAgentConfig()
        model = _make_model("[1, 2, 3]")
        judge = AdversarialJudge(model, config)

        with pytest.raises(JudgeEvaluationError):
            await judge.evaluate(SOURCE_CODE, TEST_CODE)

    @pytest.mark.asyncio
    async def test_missing_score_defaults_to_zero(self) -> None:
        config = UnitTestAgentConfig(adversarial_threshold=70.0)
        payload = json.dumps({
            "passed": False,
            "issues": ["test"],
            "suggestions": [],
        })
        model = _make_model(payload)
        judge = AdversarialJudge(model, config)

        verdict = await judge.evaluate(SOURCE_CODE, TEST_CODE)
        assert verdict.score == 0.0
        assert verdict.passed is False
