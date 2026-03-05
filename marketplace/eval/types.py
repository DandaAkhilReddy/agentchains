"""Eval Layer type definitions — verdicts, results, and suite results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvalVerdict(str, Enum):
    """Evaluation outcome."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass
class EvalResult:
    """Result of a single evaluation."""

    eval_name: str
    verdict: EvalVerdict
    score: float = 0.0  # 0.0 - 1.0
    confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class EvalSuiteResult:
    """Aggregated result of running an eval suite."""

    suite_name: str
    results: list[EvalResult] = field(default_factory=list)
    overall_verdict: EvalVerdict = EvalVerdict.PASS
    overall_score: float = 0.0

    def compute_overall(self) -> None:
        """Compute overall verdict and score from individual results."""
        if not self.results:
            self.overall_verdict = EvalVerdict.SKIP
            self.overall_score = 0.0
            return

        scores = [r.score for r in self.results]
        self.overall_score = sum(scores) / len(scores) if scores else 0.0

        verdicts = [r.verdict for r in self.results]
        if EvalVerdict.FAIL in verdicts:
            self.overall_verdict = EvalVerdict.FAIL
        elif EvalVerdict.WARN in verdicts:
            self.overall_verdict = EvalVerdict.WARN
        else:
            self.overall_verdict = EvalVerdict.PASS
