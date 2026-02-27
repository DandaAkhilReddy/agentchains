"""L10 Human Gate — final routing decision based on L9 aggregated score."""
from __future__ import annotations

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict

# Score below which the pipeline immediately fails and requires human review.
_FAIL_THRESHOLD = 0.5
# Score below which the pipeline warns and flags for human review.
_WARN_THRESHOLD = 0.7


class L10HumanGate(JudgeLevel):
    """Level 10: Human Gate.

    Reads the L9 aggregated score from ``ctx.previous_verdicts[-1]`` and
    applies threshold-based routing:

    - score < 0.5  → ``fail`` with ``should_short_circuit=True``
    - score < 0.7  → ``warn`` (flagged for human review)
    - score >= 0.7 → ``pass`` (auto-approved)

    If the L9 verdict is missing or unavailable, defaults to ``warn``.
    """

    @property
    def level(self) -> int:
        return 10

    @property
    def name(self) -> str:
        return "human_gate"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Apply human-gate thresholds to the L9 aggregated score.

        Args:
            ctx: Pipeline context; reads the last entry in ``previous_verdicts``
                which should be the L9 aggregator verdict.

        Returns:
            LevelVerdict — fail (with short-circuit), warn, or pass.
        """
        # L9 is index 8 in previous_verdicts (levels 1-9 have run before us).
        if not ctx.previous_verdicts:
            return LevelVerdict(
                verdict="warn",
                score=0.5,
                confidence=0.5,
                details={"reason": "no preceding verdict available for L10 gate"},
            )

        l9_verdict = ctx.previous_verdicts[-1]
        l9_score = l9_verdict.score

        details: dict = {
            "l9_score": l9_score,
            "fail_threshold": _FAIL_THRESHOLD,
            "warn_threshold": _WARN_THRESHOLD,
        }

        if l9_score < _FAIL_THRESHOLD:
            details["action"] = "auto_rejected_requires_human_review"
            return LevelVerdict(
                verdict="fail",
                score=round(l9_score, 4),
                confidence=round(l9_verdict.confidence, 4),
                details=details,
                should_short_circuit=True,
            )

        if l9_score < _WARN_THRESHOLD:
            details["action"] = "flagged_for_human_review"
            return LevelVerdict(
                verdict="warn",
                score=round(l9_score, 4),
                confidence=round(l9_verdict.confidence, 4),
                details=details,
            )

        details["action"] = "auto_approved"
        return LevelVerdict(
            verdict="pass",
            score=round(l9_score, 4),
            confidence=round(l9_verdict.confidence, 4),
            details=details,
        )
