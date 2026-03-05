"""Tests for TestPipelineOrchestrator — happy path, retries, budget, fallback."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.orchestrator import TestPipelineOrchestrator
from agents.unit_test_agent.schemas import TestGenerationRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SOURCE_CODE = "def add(a: int, b: int) -> int:\n    return a + b"


def _make_request() -> TestGenerationRequest:
    return TestGenerationRequest(
        source_code=SOURCE_CODE,
        source_path="math_utils.py",
    )


def _judge_response(passed: bool, score: float) -> str:
    return json.dumps({
        "passed": passed,
        "score": score,
        "issues": [] if passed else ["issue"],
        "suggestions": [] if passed else ["fix it"],
    })


def _gen_response(test_code: str = "def test_add(): assert add(1,2)==3") -> str:
    return json.dumps({
        "test_code": test_code,
        "test_count": 1,
        "imports": ["pytest"],
    })


def _make_model_sequence(responses: list[str]) -> MagicMock:
    """Create a mock ModelAgent that returns responses in sequence."""
    model = MagicMock()
    side_effects = []
    for content in responses:
        resp = MagicMock()
        resp.content = content
        resp.completion_tokens = 50
        side_effects.append(resp)
    model.complete = AsyncMock(side_effect=side_effects)
    return model


# ---------------------------------------------------------------------------
# Happy path — all judges pass on first try
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Tests for the happy path where all judges pass."""

    @pytest.mark.asyncio
    async def test_all_pass_first_try(self) -> None:
        """Generate once, all 3 judges pass -> FinalReport.passed=True."""
        model = _make_model_sequence([
            _gen_response(),                      # generate
            _judge_response(True, 90.0),          # coverage
            _judge_response(True, 85.0),          # quality
            _judge_response(True, 80.0),          # adversarial
        ])
        config = UnitTestAgentConfig(
            coverage_threshold=80.0,
            quality_threshold=70.0,
            adversarial_threshold=70.0,
        )

        # Force sequential fallback to avoid LangGraph dependency
        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model, config)
            report = await orch.run(_make_request())

        assert report.passed is True
        assert report.test_count == 1
        assert report.iterations == 1
        assert len(report.evaluations) == 3

    @pytest.mark.asyncio
    async def test_report_contains_all_judge_names(self) -> None:
        model = _make_model_sequence([
            _gen_response(),
            _judge_response(True, 90.0),
            _judge_response(True, 85.0),
            _judge_response(True, 80.0),
        ])

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model)
            report = await orch.run(_make_request())

        judge_names = [e.judge_name for e in report.evaluations]
        assert judge_names == ["coverage", "quality", "adversarial"]


# ---------------------------------------------------------------------------
# Retry path — judge fails, tests improve, then pass
# ---------------------------------------------------------------------------


class TestRetryPath:
    """Tests for retry behavior when judges fail."""

    @pytest.mark.asyncio
    async def test_coverage_retry_then_pass(self) -> None:
        """Coverage fails once, improve, then passes."""
        model = _make_model_sequence([
            _gen_response("def test_v1(): pass"),     # initial generate
            _judge_response(False, 50.0),             # coverage FAIL
            _gen_response("def test_v2(): pass"),     # improve
            _judge_response(True, 85.0),              # coverage PASS
            _judge_response(True, 80.0),              # quality PASS
            _judge_response(True, 75.0),              # adversarial PASS
        ])
        config = UnitTestAgentConfig(coverage_max_retries=3)

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model, config)
            report = await orch.run(_make_request())

        assert report.passed is True
        assert report.iterations == 2  # initial + 1 improvement

    @pytest.mark.asyncio
    async def test_quality_retry_then_pass(self) -> None:
        """Coverage passes, quality fails once, improves, then passes."""
        model = _make_model_sequence([
            _gen_response(),                          # generate
            _judge_response(True, 90.0),              # coverage PASS
            _judge_response(False, 40.0),             # quality FAIL
            _gen_response("def test_improved(): pass"),  # improve
            _judge_response(True, 80.0),              # quality PASS
            _judge_response(True, 75.0),              # adversarial PASS
        ])
        config = UnitTestAgentConfig(quality_max_retries=3)

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model, config)
            report = await orch.run(_make_request())

        assert report.passed is True

    @pytest.mark.asyncio
    async def test_adversarial_retry_then_pass(self) -> None:
        """Coverage and quality pass, adversarial fails once, improves, passes."""
        model = _make_model_sequence([
            _gen_response(),                          # generate
            _judge_response(True, 90.0),              # coverage PASS
            _judge_response(True, 80.0),              # quality PASS
            _judge_response(False, 40.0),             # adversarial FAIL
            _gen_response("def test_better(): pass"), # improve
            _judge_response(True, 75.0),              # adversarial PASS
        ])
        config = UnitTestAgentConfig(adversarial_max_retries=2)

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model, config)
            report = await orch.run(_make_request())

        assert report.passed is True


# ---------------------------------------------------------------------------
# Exhaustion — retries exceed limits
# ---------------------------------------------------------------------------


class TestExhaustion:
    """Tests for retry exhaustion and budget limits."""

    @pytest.mark.asyncio
    async def test_coverage_retries_exhausted(self) -> None:
        """Coverage fails 4 times (3 retries + initial) -> pipeline stops."""
        model = _make_model_sequence([
            _gen_response(),                    # generate (iter 1)
            _judge_response(False, 30.0),       # coverage FAIL
            _gen_response(),                    # improve (iter 2)
            _judge_response(False, 35.0),       # coverage FAIL
            _gen_response(),                    # improve (iter 3)
            _judge_response(False, 40.0),       # coverage FAIL
            _gen_response(),                    # improve (iter 4)
            _judge_response(False, 45.0),       # coverage FAIL — exhausted
        ])
        config = UnitTestAgentConfig(coverage_max_retries=3)

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model, config)
            report = await orch.run(_make_request())

        assert report.passed is False
        # All evaluations should be coverage
        assert all(e.judge_name == "coverage" for e in report.evaluations)

    @pytest.mark.asyncio
    async def test_total_budget_exhaustion(self) -> None:
        """Pipeline stops when total_max_iterations is reached.

        With total_max_iterations=2:
          - generate (iter=1)
          - coverage FAIL
          - improve (iter=2)
          - budget check: 2 >= 2 -> stop before next evaluation
        """
        model = _make_model_sequence([
            _gen_response(),                    # generate (iter 1)
            _judge_response(False, 30.0),       # coverage FAIL
            _gen_response(),                    # improve (iter 2 = budget)
        ])
        config = UnitTestAgentConfig(
            total_max_iterations=2,
            coverage_max_retries=5,
        )

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model, config)
            report = await orch.run(_make_request())

        assert report.passed is False
        assert report.iterations == 2

    @pytest.mark.asyncio
    async def test_pipeline_stops_after_judge_failure(self) -> None:
        """If a judge exhausts retries, later judges are skipped."""
        model = _make_model_sequence([
            _gen_response(),                    # generate
            _judge_response(True, 90.0),        # coverage PASS
            _judge_response(False, 20.0),       # quality FAIL
            _gen_response(),                    # improve
            _judge_response(False, 25.0),       # quality FAIL
            _gen_response(),                    # improve
            _judge_response(False, 30.0),       # quality FAIL
            _gen_response(),                    # improve
            _judge_response(False, 35.0),       # quality FAIL — exhausted
        ])
        config = UnitTestAgentConfig(quality_max_retries=3)

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model, config)
            report = await orch.run(_make_request())

        assert report.passed is False
        judge_names = {e.judge_name for e in report.evaluations}
        assert "adversarial" not in judge_names


# ---------------------------------------------------------------------------
# LangGraph fallback
# ---------------------------------------------------------------------------


class TestLangGraphFallback:
    """Tests that the orchestrator works without LangGraph."""

    @pytest.mark.asyncio
    async def test_sequential_fallback_used(self) -> None:
        """When _build_graph returns None, sequential path runs."""
        model = _make_model_sequence([
            _gen_response(),
            _judge_response(True, 90.0),
            _judge_response(True, 85.0),
            _judge_response(True, 80.0),
        ])

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model)
            assert orch._graph is None
            report = await orch.run(_make_request())

        assert report.passed is True

    @pytest.mark.asyncio
    async def test_no_langgraph_import(self) -> None:
        """Orchestrator constructs without LangGraph installed."""
        model = _make_model_sequence([
            _gen_response(),
            _judge_response(True, 90.0),
            _judge_response(True, 85.0),
            _judge_response(True, 80.0),
        ])

        with patch(
            "agents.unit_test_agent.orchestrator.LANGGRAPH_AVAILABLE", False
        ):
            orch = TestPipelineOrchestrator(model)
            assert orch._graph is None
            report = await orch.run(_make_request())

        assert report.passed is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for the orchestrator."""

    @pytest.mark.asyncio
    async def test_default_config_used(self) -> None:
        """When no config provided, defaults are used."""
        model = _make_model_sequence([
            _gen_response(),
            _judge_response(True, 90.0),
            _judge_response(True, 85.0),
            _judge_response(True, 80.0),
        ])

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model)
            assert orch._config.coverage_threshold == 80.0
            report = await orch.run(_make_request())

        assert report.passed is True

    @pytest.mark.asyncio
    async def test_single_iteration_budget(self) -> None:
        """With budget=1, only one generation occurs."""
        model = _make_model_sequence([
            _gen_response(),
            _judge_response(False, 50.0),  # coverage FAIL — budget prevents retry
        ])
        config = UnitTestAgentConfig(total_max_iterations=1, coverage_max_retries=5)

        with patch.object(TestPipelineOrchestrator, '_build_graph', return_value=None):
            orch = TestPipelineOrchestrator(model, config)
            report = await orch.run(_make_request())

        assert report.passed is False
        assert report.iterations == 1
