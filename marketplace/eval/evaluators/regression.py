"""Regression evaluator — compares output against golden reference via semantic similarity."""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from marketplace.eval.base import BaseEvaluator
from marketplace.eval.types import EvalResult, EvalVerdict

logger = structlog.get_logger(__name__)


def _jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two strings (word-level)."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


class RegressionEvaluator(BaseEvaluator):
    """Compares output against golden reference and flags regressions."""

    name = "regression"

    def __init__(self, threshold: float = 0.7) -> None:
        self._threshold = threshold

    async def evaluate(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        expected: dict[str, Any] | None = None,
    ) -> EvalResult:
        start = time.perf_counter()

        if expected is None:
            return EvalResult(
                eval_name=self.name,
                verdict=EvalVerdict.SKIP,
                score=0.0,
                details={"reason": "no_golden_reference"},
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        output_text = json.dumps(output_data, sort_keys=True, default=str)
        expected_text = json.dumps(expected, sort_keys=True, default=str)

        # Exact match check
        if output_text == expected_text:
            return EvalResult(
                eval_name=self.name,
                verdict=EvalVerdict.PASS,
                score=1.0,
                details={"match_type": "exact"},
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        # Semantic similarity (Jaccard as baseline — can be upgraded to embeddings)
        similarity = _jaccard_similarity(output_text, expected_text)
        duration_ms = (time.perf_counter() - start) * 1000

        if similarity >= self._threshold:
            verdict = EvalVerdict.PASS
        elif similarity >= self._threshold * 0.7:
            verdict = EvalVerdict.WARN
        else:
            verdict = EvalVerdict.FAIL

        return EvalResult(
            eval_name=self.name,
            verdict=verdict,
            score=similarity,
            details={
                "similarity": round(similarity, 4),
                "threshold": self._threshold,
                "match_type": "semantic",
            },
            duration_ms=duration_ms,
        )
