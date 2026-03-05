"""Typed schemas for the Unit Testing Agent pipeline.

All I/O types are frozen dataclasses for immutability and safety.
PipelineState is a TypedDict for LangGraph state threading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


@dataclass(frozen=True)
class TestGenerationRequest:
    """Input to the test generation pipeline."""

    source_code: str
    source_path: str
    language: str = "python"
    framework: str = "pytest"
    context: str = ""


@dataclass(frozen=True)
class GeneratedTests:
    """Output from the test generator."""

    test_code: str
    test_count: int = 0
    imports: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class JudgeVerdict:
    """Single judge evaluation result."""

    passed: bool
    score: float
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class JudgeEvaluation:
    """Wraps a verdict with metadata about which judge produced it."""

    judge_name: str
    verdict: JudgeVerdict
    iteration: int


class PipelineState(TypedDict, total=False):
    """Mutable state threaded through every LangGraph node."""

    source_code: str
    source_path: str
    language: str
    framework: str
    context: str
    test_code: str
    test_count: int
    imports: list[str]
    evaluations: list[dict]
    current_judge: str
    iteration: int
    coverage_retries: int
    quality_retries: int
    adversarial_retries: int
    total_iterations: int
    passed: bool
    error: str


@dataclass(frozen=True)
class FinalReport:
    """Final output of the test pipeline."""

    test_code: str
    test_count: int
    evaluations: list[JudgeEvaluation]
    iterations: int
    passed: bool
