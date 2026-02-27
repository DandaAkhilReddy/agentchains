"""L2 Data Quality — null checks, empty strings, bounds validation."""
from __future__ import annotations

from typing import Any

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict

# Fields that must be non-null and non-empty-string in output_data.
_NON_EMPTY_OUTPUT_FIELDS: tuple[str, ...] = ("result", "status")

# Numeric fields in output_data with (min, max) bounds.
_BOUNDED_OUTPUT_FIELDS: dict[str, tuple[float, float]] = {
    "score": (0.0, 1.0),
    "confidence": (0.0, 1.0),
    "price": (0.0, float("inf")),
    "quantity": (0.0, float("inf")),
}


def _run_quality_checks(data: dict[str, Any]) -> tuple[int, int, list[str]]:
    """Run data quality checks over a dict.

    Args:
        data: Dict to evaluate.

    Returns:
        (passed, total, failure_messages)
    """
    failures: list[str] = []
    total = 0
    passed = 0

    # Non-null / non-empty checks for known required output fields.
    for field in _NON_EMPTY_OUTPUT_FIELDS:
        if field not in data:
            continue
        total += 1
        value = data[field]
        if value is None:
            failures.append(f"field {field!r} is null")
        elif isinstance(value, str) and value.strip() == "":
            failures.append(f"field {field!r} is an empty string")
        else:
            passed += 1

    # Null check for all keys present in the dict.
    for key, value in data.items():
        if key in _NON_EMPTY_OUTPUT_FIELDS:
            continue  # Already checked above.
        total += 1
        if value is None:
            failures.append(f"field {key!r} is null")
        else:
            passed += 1

    # Bounds checks for known numeric fields.
    for field, (lo, hi) in _BOUNDED_OUTPUT_FIELDS.items():
        if field not in data or data[field] is None:
            continue
        value = data[field]
        if not isinstance(value, (int, float)):
            total += 1
            failures.append(f"field {field!r} expected numeric, got {type(value).__name__}")
            continue
        total += 1
        if lo <= value <= hi:
            passed += 1
        else:
            failures.append(f"field {field!r} = {value} out of bounds [{lo}, {hi}]")

    return passed, total, failures


class L2DataQuality(JudgeLevel):
    """Level 2: Data Quality.

    Checks for null values in required fields, empty strings, type correctness,
    and values within reasonable bounds.
    """

    @property
    def level(self) -> int:
        return 2

    @property
    def name(self) -> str:
        return "data_quality"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Evaluate data quality of input and output dicts.

        Args:
            ctx: Pipeline context.

        Returns:
            LevelVerdict with score proportional to passing checks.
        """
        out_passed, out_total, out_failures = _run_quality_checks(ctx.output_data)
        in_passed, in_total, in_failures = _run_quality_checks(ctx.input_data)

        total = in_total + out_total
        passed = in_passed + out_passed
        score = passed / total if total > 0 else 1.0

        all_failures = in_failures + out_failures

        if score >= 0.9:
            verdict = "pass"
        elif score >= 0.6:
            verdict = "warn"
        else:
            verdict = "fail"

        return LevelVerdict(
            verdict=verdict,
            score=round(score, 4),
            confidence=0.90,
            details={
                "passed_checks": passed,
                "total_checks": total,
                "failures": all_failures,
            },
        )
