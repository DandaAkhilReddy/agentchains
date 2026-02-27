"""L5 Statistical — outlier detection via manual z-score computation."""
from __future__ import annotations

import math
from typing import Any

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict

# Z-score threshold for flagging an outlier.
_ZSCORE_THRESHOLD = 3.0
# Minimum number of values required to compute meaningful statistics.
_MIN_SAMPLE_SIZE = 3


def _collect_numeric_values(data: dict[str, Any]) -> list[float]:
    """Recursively collect all numeric (int/float) leaf values from a dict.

    Args:
        data: Dict to traverse.

    Returns:
        Flat list of numeric values found at any depth.
    """
    result: list[float] = []
    for value in data.values():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result.append(float(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    result.append(float(item))
        elif isinstance(value, dict):
            result.extend(_collect_numeric_values(value))
    return result


def _compute_mean(values: list[float]) -> float:
    """Compute arithmetic mean.

    Args:
        values: Non-empty list of floats.

    Returns:
        Mean value.
    """
    return sum(values) / len(values)


def _compute_stddev(values: list[float], mean: float) -> float:
    """Compute population standard deviation.

    Args:
        values: Non-empty list of floats.
        mean: Pre-computed mean.

    Returns:
        Standard deviation (0.0 if constant).
    """
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _detect_outliers(values: list[float]) -> tuple[list[float], float]:
    """Detect outliers using z-scores.

    Args:
        values: Numeric values to analyse.

    Returns:
        (outlier_values, outlier_ratio) where outlier_ratio is in [0, 1].
    """
    if len(values) < _MIN_SAMPLE_SIZE:
        return [], 0.0

    mean = _compute_mean(values)
    stddev = _compute_stddev(values, mean)

    if stddev == 0.0:
        return [], 0.0

    outliers = [v for v in values if abs((v - mean) / stddev) > _ZSCORE_THRESHOLD]
    return outliers, len(outliers) / len(values)


class L5Statistical(JudgeLevel):
    """Level 5: Statistical Analysis.

    Collects all numeric values from ``output_data`` and flags statistical
    outliers (|z-score| > 3).  Skipped when no numeric data is found or the
    sample is too small for meaningful analysis.
    """

    @property
    def level(self) -> int:
        return 5

    @property
    def name(self) -> str:
        return "statistical"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Run outlier detection on numeric values in output_data.

        Args:
            ctx: Pipeline context.

        Returns:
            LevelVerdict — skipped when no numeric data is available.
        """
        numeric_values = _collect_numeric_values(ctx.output_data)

        if len(numeric_values) < _MIN_SAMPLE_SIZE:
            return LevelVerdict(
                verdict="skip",
                score=1.0,
                confidence=1.0,
                details={
                    "reason": "insufficient numeric data for statistical analysis",
                    "numeric_count": len(numeric_values),
                },
            )

        outliers, outlier_ratio = _detect_outliers(numeric_values)
        mean = _compute_mean(numeric_values)
        stddev = _compute_stddev(numeric_values, mean)

        # Score: penalise proportionally to outlier ratio.
        score = max(0.0, 1.0 - outlier_ratio * 2)

        if outlier_ratio == 0.0:
            verdict = "pass"
        elif outlier_ratio < 0.1:
            verdict = "warn"
        else:
            verdict = "fail"

        return LevelVerdict(
            verdict=verdict,
            score=round(score, 4),
            confidence=0.80,
            details={
                "numeric_count": len(numeric_values),
                "outlier_count": len(outliers),
                "outlier_ratio": round(outlier_ratio, 4),
                "mean": round(mean, 6),
                "stddev": round(stddev, 6),
                "outlier_values": outliers[:10],  # cap logged outliers
            },
        )
