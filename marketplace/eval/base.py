"""Base evaluator — abstract base class for all evaluators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from marketplace.eval.types import EvalResult


class BaseEvaluator(ABC):
    """Abstract base for all evaluation implementations."""

    name: str = "base"

    @abstractmethod
    async def evaluate(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        expected: dict[str, Any] | None = None,
    ) -> EvalResult:
        """Evaluate input/output pair against criteria.

        Args:
            input_data: The input given to the agent/workflow.
            output_data: The output produced by the agent/workflow.
            expected: Optional expected/golden output for comparison.
        """
