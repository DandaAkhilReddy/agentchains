"""L9 Aggregator — weighted combination of L1-L8 scores."""
from __future__ import annotations

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict

# Level weights must sum to 1.0. Skipped levels are excluded from aggregation.
_LEVEL_WEIGHTS: dict[int, float] = {
    1: 0.15,  # Schema Validation
    2: 0.15,  # Data Quality
    3: 0.10,  # Consistency
    4: 0.10,  # Performance
    5: 0.10,  # Statistical
    6: 0.15,  # Semantic Quality
    7: 0.15,  # Safety
    8: 0.10,  # Consensus
}


class L9Aggregator(JudgeLevel):
    """Level 9: Aggregator.

    Computes a weighted average of L1-L8 scores, ignoring skipped levels.
    The final confidence is the average of non-skipped level confidences.

    When all preceding levels were skipped, the verdict defaults to ``warn``
    with a score of 0.5.
    """

    @property
    def level(self) -> int:
        return 9

    @property
    def name(self) -> str:
        return "aggregator"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Compute weighted score across previous non-skipped verdicts.

        Args:
            ctx: Pipeline context containing previous level verdicts.

        Returns:
            LevelVerdict with the aggregated score and confidence.
        """
        # previous_verdicts are in level order (L1 is index 0, …, L8 is index 7).
        non_skip_entries: list[tuple[int, LevelVerdict]] = []
        for idx, verdict in enumerate(ctx.previous_verdicts):
            level_num = idx + 1  # L1=1, …, L8=8
            if verdict.verdict != "skip" and level_num in _LEVEL_WEIGHTS:
                non_skip_entries.append((level_num, verdict))

        if not non_skip_entries:
            return LevelVerdict(
                verdict="warn",
                score=0.5,
                confidence=0.5,
                details={"reason": "all preceding levels were skipped"},
            )

        # Normalise weights to only non-skipped levels.
        total_weight = sum(_LEVEL_WEIGHTS[lvl] for lvl, _ in non_skip_entries)
        weighted_score = sum(
            (_LEVEL_WEIGHTS[lvl] / total_weight) * v.score
            for lvl, v in non_skip_entries
        )
        avg_confidence = sum(v.confidence for _, v in non_skip_entries) / len(non_skip_entries)

        # Aggregate per-level breakdown for transparency.
        breakdown: dict[str, float] = {
            f"l{lvl}": round(v.score, 4) for lvl, v in non_skip_entries
        }
        breakdown["weights_normalized"] = True

        if weighted_score >= 0.7:
            verdict_str = "pass"
        elif weighted_score >= 0.4:
            verdict_str = "warn"
        else:
            verdict_str = "fail"

        return LevelVerdict(
            verdict=verdict_str,
            score=round(weighted_score, 4),
            confidence=round(avg_confidence, 4),
            details={
                "aggregated_score": round(weighted_score, 4),
                "levels_included": [lvl for lvl, _ in non_skip_entries],
                "breakdown": breakdown,
            },
        )
