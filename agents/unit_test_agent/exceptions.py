"""Custom exceptions for the Unit Testing Agent pipeline."""

from __future__ import annotations


class UnitTestAgentError(Exception):
    """Base exception for unit test agent failures."""


class TestGenerationError(UnitTestAgentError):
    """Raised when test generation fails after all parse attempts."""


class JudgeEvaluationError(UnitTestAgentError):
    """Raised when a judge fails to produce a valid verdict."""


class BudgetExhaustedError(UnitTestAgentError):
    """Raised when the pipeline exhausts its total iteration budget."""
