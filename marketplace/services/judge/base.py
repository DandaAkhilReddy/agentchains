"""Judge level protocol — base types for the 10-level cascade."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LevelVerdict:
    """Result from a single judge level evaluation.

    Attributes:
        verdict: Outcome string — "pass", "fail", "warn", or "skip".
        score: Continuous quality score in [0.0, 1.0].
        confidence: Confidence in the verdict in [0.0, 1.0].
        details: Arbitrary key-value pairs explaining the verdict.
        should_short_circuit: If True, the pipeline stops after this level.
    """

    verdict: str  # "pass" | "fail" | "warn" | "skip"
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    details: dict[str, Any] = field(default_factory=dict)
    should_short_circuit: bool = False


@dataclass
class JudgeContext:
    """Context passed to each judge level in the cascade.

    Attributes:
        target_type: Category of the artifact being judged.
        target_id: Identifier of the artifact being judged.
        input_data: Input data sent to the agent or process under evaluation.
        output_data: Output produced by the agent or process.
        metadata: Additional context (e.g., latency_ms, alternative_outputs).
        previous_verdicts: Verdicts from levels that have already run.
    """

    target_type: str  # "agent_output" | "listing" | "transaction"
    target_id: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    previous_verdicts: list[LevelVerdict] = field(default_factory=list)


class JudgeLevel(abc.ABC):
    """Abstract base class for a judge level in the cascade.

    Subclasses must implement :meth:`level`, :meth:`name`, and
    :meth:`evaluate`.  The pipeline orchestrator instantiates all levels once
    and calls ``evaluate`` with a shared :class:`JudgeContext`.
    """

    @property
    @abc.abstractmethod
    def level(self) -> int:
        """Level number (1–10)."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable level name."""

    @abc.abstractmethod
    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Run this level's evaluation and return a verdict.

        Args:
            ctx: Shared pipeline context including prior verdicts.

        Returns:
            A :class:`LevelVerdict` describing the outcome.
        """
