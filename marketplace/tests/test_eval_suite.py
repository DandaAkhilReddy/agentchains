"""Tests for marketplace.eval.suite — EvalSuite."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from marketplace.eval.base import BaseEvaluator
from marketplace.eval.suite import EvalSuite
from marketplace.eval.types import EvalResult, EvalVerdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_evaluator(name: str, verdict: EvalVerdict, score: float = 1.0) -> BaseEvaluator:
    """Create a mock evaluator that always returns the given verdict/score."""
    ev = MagicMock(spec=BaseEvaluator)
    ev.name = name
    ev.evaluate = AsyncMock(
        return_value=EvalResult(eval_name=name, verdict=verdict, score=score)
    )
    return ev


def _make_failing_evaluator(name: str) -> BaseEvaluator:
    """Create a mock evaluator that raises an exception."""
    ev = MagicMock(spec=BaseEvaluator)
    ev.name = name
    ev.evaluate = AsyncMock(side_effect=RuntimeError(f"{name} exploded"))
    return ev


# ---------------------------------------------------------------------------
# Basic run tests
# ---------------------------------------------------------------------------


async def test_suite_run_single_evaluator_single_case() -> None:
    ev = _make_evaluator("safety", EvalVerdict.PASS, score=1.0)
    suite = EvalSuite(name="basic", evaluators=[ev])
    result = await suite.run([{"input": {"q": "hello"}, "output": {"answer": "hi"}}])
    assert result.suite_name == "basic"
    assert len(result.results) == 1
    assert result.results[0].verdict == EvalVerdict.PASS


async def test_suite_run_multiple_evaluators() -> None:
    ev1 = _make_evaluator("safety", EvalVerdict.PASS, score=1.0)
    ev2 = _make_evaluator("regression", EvalVerdict.WARN, score=0.5)
    suite = EvalSuite(name="multi", evaluators=[ev1, ev2])
    result = await suite.run([{"input": {}, "output": {}}])
    assert len(result.results) == 2


async def test_suite_run_multiple_cases() -> None:
    ev = _make_evaluator("safety", EvalVerdict.PASS, score=1.0)
    suite = EvalSuite(name="multi_case", evaluators=[ev])
    cases = [
        {"input": {"q": "a"}, "output": {"r": "1"}},
        {"input": {"q": "b"}, "output": {"r": "2"}},
        {"input": {"q": "c"}, "output": {"r": "3"}},
    ]
    result = await suite.run(cases)
    # 3 cases × 1 evaluator = 3 results
    assert len(result.results) == 3


async def test_suite_evaluator_exception_gives_skip_verdict() -> None:
    ev = _make_failing_evaluator("boom")
    suite = EvalSuite(name="fail_test", evaluators=[ev])
    result = await suite.run([{"input": {}, "output": {}}])
    assert len(result.results) == 1
    assert result.results[0].verdict == EvalVerdict.SKIP
    assert "error" in result.results[0].details


async def test_suite_evaluator_exception_includes_case_index() -> None:
    ev = _make_failing_evaluator("boom")
    suite = EvalSuite(name="idx_test", evaluators=[ev])
    cases = [{"input": {}, "output": {}}, {"input": {}, "output": {}}]
    result = await suite.run(cases)
    assert len(result.results) == 2
    for r in result.results:
        assert "case_index" in r.details


# ---------------------------------------------------------------------------
# Overall verdict and score
# ---------------------------------------------------------------------------


async def test_suite_overall_verdict_computed() -> None:
    ev1 = _make_evaluator("safety", EvalVerdict.PASS, score=1.0)
    ev2 = _make_evaluator("regression", EvalVerdict.FAIL, score=0.0)
    suite = EvalSuite(name="verdict", evaluators=[ev1, ev2])
    result = await suite.run([{"input": {}, "output": {}}])
    assert result.overall_verdict == EvalVerdict.FAIL


async def test_suite_overall_score_averaged() -> None:
    ev1 = _make_evaluator("a", EvalVerdict.PASS, score=0.8)
    ev2 = _make_evaluator("b", EvalVerdict.PASS, score=0.6)
    suite = EvalSuite(name="score_avg", evaluators=[ev1, ev2])
    result = await suite.run([{"input": {}, "output": {}}])
    assert abs(result.overall_score - 0.7) < 1e-9


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_suite_empty_evaluators() -> None:
    suite = EvalSuite(name="empty_ev", evaluators=[])
    result = await suite.run([{"input": {}, "output": {}}])
    assert len(result.results) == 0
    # compute_overall on empty → SKIP
    assert result.overall_verdict == EvalVerdict.SKIP


async def test_suite_empty_test_cases() -> None:
    ev = _make_evaluator("safety", EvalVerdict.PASS)
    suite = EvalSuite(name="empty_cases", evaluators=[ev])
    result = await suite.run([])
    assert len(result.results) == 0
    assert result.overall_verdict == EvalVerdict.SKIP


async def test_suite_evaluator_not_called_on_empty_cases() -> None:
    ev = _make_evaluator("safety", EvalVerdict.PASS)
    suite = EvalSuite(name="empty_cases", evaluators=[ev])
    await suite.run([])
    ev.evaluate.assert_not_awaited()


# ---------------------------------------------------------------------------
# run_on_workflow_output
# ---------------------------------------------------------------------------


async def test_suite_run_on_workflow_output() -> None:
    ev = _make_evaluator("safety", EvalVerdict.PASS, score=0.9)
    suite = EvalSuite(name="workflow", evaluators=[ev])
    result = await suite.run_on_workflow_output(
        input_data={"prompt": "Hello"},
        output_data={"response": "Hi there"},
    )
    assert result.suite_name == "workflow"
    assert len(result.results) == 1
    assert result.results[0].verdict == EvalVerdict.PASS


async def test_suite_run_on_workflow_output_with_expected() -> None:
    ev = _make_evaluator("regression", EvalVerdict.WARN, score=0.5)
    suite = EvalSuite(name="workflow_expected", evaluators=[ev])
    result = await suite.run_on_workflow_output(
        input_data={"q": "capital of France"},
        output_data={"answer": "Lyon"},
        expected={"answer": "Paris"},
    )
    assert len(result.results) == 1


# ---------------------------------------------------------------------------
# Results metadata
# ---------------------------------------------------------------------------


async def test_suite_results_include_eval_name() -> None:
    ev = _make_evaluator("my_eval", EvalVerdict.PASS, score=1.0)
    suite = EvalSuite(name="meta", evaluators=[ev])
    result = await suite.run([{"input": {}, "output": {}}])
    assert result.results[0].eval_name == "my_eval"


async def test_suite_results_include_duration_ms() -> None:
    """EvalResult returned by evaluator is passed through including duration_ms."""
    ev = MagicMock(spec=BaseEvaluator)
    ev.name = "timed"
    ev.evaluate = AsyncMock(
        return_value=EvalResult(
            eval_name="timed",
            verdict=EvalVerdict.PASS,
            score=1.0,
            duration_ms=42.0,
        )
    )
    suite = EvalSuite(name="dur", evaluators=[ev])
    result = await suite.run([{"input": {}, "output": {}}])
    assert result.results[0].duration_ms == pytest.approx(42.0)


async def test_suite_preserves_evaluator_order() -> None:
    ev1 = _make_evaluator("first", EvalVerdict.PASS)
    ev2 = _make_evaluator("second", EvalVerdict.WARN)
    ev3 = _make_evaluator("third", EvalVerdict.FAIL)
    suite = EvalSuite(name="order", evaluators=[ev1, ev2, ev3])
    result = await suite.run([{"input": {}, "output": {}}])
    names = [r.eval_name for r in result.results]
    assert names == ["first", "second", "third"]


async def test_suite_multiple_cases_multiple_evaluators_count() -> None:
    ev1 = _make_evaluator("a", EvalVerdict.PASS)
    ev2 = _make_evaluator("b", EvalVerdict.PASS)
    suite = EvalSuite(name="count", evaluators=[ev1, ev2])
    cases = [{"input": {}, "output": {}} for _ in range(4)]
    result = await suite.run(cases)
    # 4 cases × 2 evaluators = 8 results
    assert len(result.results) == 8
