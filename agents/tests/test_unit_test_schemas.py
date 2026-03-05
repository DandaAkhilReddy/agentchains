"""Tests for Unit Testing Agent schemas, config, and exceptions."""

from __future__ import annotations

import pytest

from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.exceptions import (
    BudgetExhaustedError,
    JudgeEvaluationError,
    TestGenerationError,
    UnitTestAgentError,
)
from agents.unit_test_agent.schemas import (
    FinalReport,
    GeneratedTests,
    JudgeEvaluation,
    JudgeVerdict,
    TestGenerationRequest,
)


# ---------------------------------------------------------------------------
# TestGenerationRequest
# ---------------------------------------------------------------------------


class TestTestGenerationRequest:
    """Tests for the TestGenerationRequest dataclass."""

    def test_required_fields(self) -> None:
        req = TestGenerationRequest(
            source_code="def foo(): pass",
            source_path="foo.py",
        )
        assert req.source_code == "def foo(): pass"
        assert req.source_path == "foo.py"

    def test_defaults(self) -> None:
        req = TestGenerationRequest(source_code="x", source_path="x.py")
        assert req.language == "python"
        assert req.framework == "pytest"
        assert req.context == ""

    def test_frozen(self) -> None:
        req = TestGenerationRequest(source_code="x", source_path="x.py")
        with pytest.raises(AttributeError):
            req.source_code = "y"  # type: ignore[misc]

    def test_custom_fields(self) -> None:
        req = TestGenerationRequest(
            source_code="fn main() {}",
            source_path="main.rs",
            language="rust",
            framework="cargo test",
            context="Some context",
        )
        assert req.language == "rust"
        assert req.framework == "cargo test"
        assert req.context == "Some context"


# ---------------------------------------------------------------------------
# GeneratedTests
# ---------------------------------------------------------------------------


class TestGeneratedTests:
    """Tests for the GeneratedTests dataclass."""

    def test_defaults(self) -> None:
        gen = GeneratedTests(test_code="def test_a(): pass")
        assert gen.test_code == "def test_a(): pass"
        assert gen.test_count == 0
        assert gen.imports == []

    def test_with_imports(self) -> None:
        gen = GeneratedTests(
            test_code="...",
            test_count=3,
            imports=["pytest", "unittest.mock"],
        )
        assert gen.test_count == 3
        assert len(gen.imports) == 2

    def test_frozen(self) -> None:
        gen = GeneratedTests(test_code="x")
        with pytest.raises(AttributeError):
            gen.test_code = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JudgeVerdict
# ---------------------------------------------------------------------------


class TestJudgeVerdict:
    """Tests for the JudgeVerdict dataclass."""

    def test_passing_verdict(self) -> None:
        v = JudgeVerdict(passed=True, score=95.0)
        assert v.passed is True
        assert v.score == 95.0
        assert v.issues == []
        assert v.suggestions == []

    def test_failing_verdict(self) -> None:
        v = JudgeVerdict(
            passed=False,
            score=40.0,
            issues=["Missing edge case"],
            suggestions=["Add test for None input"],
        )
        assert v.passed is False
        assert len(v.issues) == 1
        assert len(v.suggestions) == 1

    def test_frozen(self) -> None:
        v = JudgeVerdict(passed=True, score=100.0)
        with pytest.raises(AttributeError):
            v.passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JudgeEvaluation
# ---------------------------------------------------------------------------


class TestJudgeEvaluation:
    """Tests for the JudgeEvaluation dataclass."""

    def test_construction(self) -> None:
        verdict = JudgeVerdict(passed=True, score=85.0)
        e = JudgeEvaluation(judge_name="coverage", verdict=verdict, iteration=1)
        assert e.judge_name == "coverage"
        assert e.verdict.passed is True
        assert e.iteration == 1


# ---------------------------------------------------------------------------
# FinalReport
# ---------------------------------------------------------------------------


class TestFinalReport:
    """Tests for the FinalReport dataclass."""

    def test_passing_report(self) -> None:
        verdict = JudgeVerdict(passed=True, score=90.0)
        evaluation = JudgeEvaluation(
            judge_name="coverage", verdict=verdict, iteration=1
        )
        report = FinalReport(
            test_code="def test_x(): pass",
            test_count=1,
            evaluations=[evaluation],
            iterations=1,
            passed=True,
        )
        assert report.passed is True
        assert report.iterations == 1
        assert len(report.evaluations) == 1

    def test_failing_report(self) -> None:
        report = FinalReport(
            test_code="",
            test_count=0,
            evaluations=[],
            iterations=8,
            passed=False,
        )
        assert report.passed is False
        assert report.iterations == 8


# ---------------------------------------------------------------------------
# UnitTestAgentConfig
# ---------------------------------------------------------------------------


class TestUnitTestAgentConfig:
    """Tests for the UnitTestAgentConfig dataclass."""

    def test_defaults(self) -> None:
        cfg = UnitTestAgentConfig()
        assert cfg.coverage_max_retries == 3
        assert cfg.quality_max_retries == 3
        assert cfg.adversarial_max_retries == 2
        assert cfg.total_max_iterations == 8
        assert cfg.coverage_threshold == 80.0
        assert cfg.quality_threshold == 70.0
        assert cfg.adversarial_threshold == 70.0

    def test_custom_values(self) -> None:
        cfg = UnitTestAgentConfig(
            coverage_max_retries=5,
            total_max_iterations=12,
            coverage_threshold=90.0,
        )
        assert cfg.coverage_max_retries == 5
        assert cfg.total_max_iterations == 12
        assert cfg.coverage_threshold == 90.0

    def test_frozen(self) -> None:
        cfg = UnitTestAgentConfig()
        with pytest.raises(AttributeError):
            cfg.coverage_max_retries = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    """Tests for custom exception hierarchy."""

    def test_hierarchy(self) -> None:
        assert issubclass(TestGenerationError, UnitTestAgentError)
        assert issubclass(JudgeEvaluationError, UnitTestAgentError)
        assert issubclass(BudgetExhaustedError, UnitTestAgentError)
        assert issubclass(UnitTestAgentError, Exception)

    def test_message(self) -> None:
        err = TestGenerationError("parse failed")
        assert str(err) == "parse failed"

    def test_chaining(self) -> None:
        original = ValueError("bad json")
        err = JudgeEvaluationError("judge failed")
        err.__cause__ = original
        assert err.__cause__ is original
