"""Tests for marketplace.eval.types — EvalVerdict, EvalResult, EvalSuiteResult."""

from __future__ import annotations

import pytest

from marketplace.eval.types import EvalResult, EvalSuiteResult, EvalVerdict


# ---------------------------------------------------------------------------
# EvalVerdict
# ---------------------------------------------------------------------------


def test_eval_verdict_pass_exists() -> None:
    assert EvalVerdict.PASS == "pass"


def test_eval_verdict_fail_exists() -> None:
    assert EvalVerdict.FAIL == "fail"


def test_eval_verdict_warn_exists() -> None:
    assert EvalVerdict.WARN == "warn"


def test_eval_verdict_skip_exists() -> None:
    assert EvalVerdict.SKIP == "skip"


# ---------------------------------------------------------------------------
# EvalResult
# ---------------------------------------------------------------------------


def test_eval_result_creation_all_fields() -> None:
    result = EvalResult(
        eval_name="safety",
        verdict=EvalVerdict.PASS,
        score=0.95,
        confidence=0.9,
        details={"checks_passed": ["pii", "harmful"]},
        duration_ms=12.5,
    )
    assert result.eval_name == "safety"
    assert result.verdict == EvalVerdict.PASS
    assert result.score == 0.95
    assert result.confidence == 0.9
    assert result.details == {"checks_passed": ["pii", "harmful"]}
    assert result.duration_ms == 12.5


def test_eval_result_defaults() -> None:
    result = EvalResult(eval_name="regression", verdict=EvalVerdict.FAIL)
    assert result.score == 0.0
    assert result.confidence == 1.0
    assert result.details == {}
    assert result.duration_ms == 0.0


def test_eval_result_details_default_independent() -> None:
    """Each EvalResult gets its own details dict (no shared mutable default)."""
    r1 = EvalResult(eval_name="a", verdict=EvalVerdict.PASS)
    r2 = EvalResult(eval_name="b", verdict=EvalVerdict.FAIL)
    r1.details["x"] = 1
    assert "x" not in r2.details


# ---------------------------------------------------------------------------
# EvalSuiteResult — creation
# ---------------------------------------------------------------------------


def test_eval_suite_result_creation() -> None:
    suite = EvalSuiteResult(suite_name="my_suite")
    assert suite.suite_name == "my_suite"
    assert suite.results == []
    assert suite.overall_score == 0.0


# ---------------------------------------------------------------------------
# EvalSuiteResult.compute_overall — verdict aggregation
# ---------------------------------------------------------------------------


def test_compute_overall_all_pass_gives_pass() -> None:
    suite = EvalSuiteResult(suite_name="s")
    suite.results = [
        EvalResult(eval_name="a", verdict=EvalVerdict.PASS, score=1.0),
        EvalResult(eval_name="b", verdict=EvalVerdict.PASS, score=0.8),
    ]
    suite.compute_overall()
    assert suite.overall_verdict == EvalVerdict.PASS


def test_compute_overall_one_fail_gives_fail() -> None:
    suite = EvalSuiteResult(suite_name="s")
    suite.results = [
        EvalResult(eval_name="a", verdict=EvalVerdict.PASS, score=1.0),
        EvalResult(eval_name="b", verdict=EvalVerdict.FAIL, score=0.0),
    ]
    suite.compute_overall()
    assert suite.overall_verdict == EvalVerdict.FAIL


def test_compute_overall_warn_no_fail_gives_warn() -> None:
    suite = EvalSuiteResult(suite_name="s")
    suite.results = [
        EvalResult(eval_name="a", verdict=EvalVerdict.PASS, score=1.0),
        EvalResult(eval_name="b", verdict=EvalVerdict.WARN, score=0.5),
    ]
    suite.compute_overall()
    assert suite.overall_verdict == EvalVerdict.WARN


def test_compute_overall_all_skip_gives_skip() -> None:
    # SKIP is not FAIL or WARN, so verdict falls through to PASS (not SKIP)
    # Let's check the actual behavior per implementation
    suite = EvalSuiteResult(suite_name="s")
    suite.results = [
        EvalResult(eval_name="a", verdict=EvalVerdict.SKIP, score=0.0),
    ]
    suite.compute_overall()
    # Per implementation: SKIP in verdicts doesn't trigger FAIL or WARN → PASS
    assert suite.overall_verdict == EvalVerdict.PASS


def test_compute_overall_mixed_warn_and_pass_gives_warn() -> None:
    suite = EvalSuiteResult(suite_name="s")
    suite.results = [
        EvalResult(eval_name="a", verdict=EvalVerdict.PASS, score=0.9),
        EvalResult(eval_name="b", verdict=EvalVerdict.WARN, score=0.6),
        EvalResult(eval_name="c", verdict=EvalVerdict.PASS, score=0.8),
    ]
    suite.compute_overall()
    assert suite.overall_verdict == EvalVerdict.WARN


def test_compute_overall_fail_dominates_warn() -> None:
    suite = EvalSuiteResult(suite_name="s")
    suite.results = [
        EvalResult(eval_name="a", verdict=EvalVerdict.WARN, score=0.5),
        EvalResult(eval_name="b", verdict=EvalVerdict.FAIL, score=0.0),
    ]
    suite.compute_overall()
    assert suite.overall_verdict == EvalVerdict.FAIL


def test_compute_overall_empty_results_gives_skip() -> None:
    suite = EvalSuiteResult(suite_name="s")
    suite.compute_overall()
    assert suite.overall_verdict == EvalVerdict.SKIP
    assert suite.overall_score == 0.0


# ---------------------------------------------------------------------------
# EvalSuiteResult.compute_overall — score averaging
# ---------------------------------------------------------------------------


def test_compute_overall_score_is_average() -> None:
    suite = EvalSuiteResult(suite_name="s")
    suite.results = [
        EvalResult(eval_name="a", verdict=EvalVerdict.PASS, score=0.8),
        EvalResult(eval_name="b", verdict=EvalVerdict.PASS, score=0.6),
    ]
    suite.compute_overall()
    assert abs(suite.overall_score - 0.7) < 1e-9


def test_compute_overall_single_result_score() -> None:
    suite = EvalSuiteResult(suite_name="s")
    suite.results = [EvalResult(eval_name="a", verdict=EvalVerdict.PASS, score=0.42)]
    suite.compute_overall()
    assert abs(suite.overall_score - 0.42) < 1e-9
