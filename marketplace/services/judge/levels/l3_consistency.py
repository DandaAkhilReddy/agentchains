"""L3 Consistency — cross-field business invariant validation."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict


def _parse_datetime(value: Any) -> datetime | None:
    """Attempt to parse a value as an ISO-8601 datetime string.

    Args:
        value: Candidate value.

    Returns:
        Parsed datetime or None if not parseable.
    """
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _run_consistency_checks(data: dict[str, Any]) -> tuple[int, int, list[str]]:
    """Run cross-field consistency checks on a dict.

    Args:
        data: Dict to evaluate.

    Returns:
        (passed, total, failure_messages)
    """
    failures: list[str] = []
    total = 0
    passed = 0

    # Rule 1: end_date must be after start_date.
    if "start_date" in data and "end_date" in data:
        total += 1
        start = _parse_datetime(data["start_date"])
        end = _parse_datetime(data["end_date"])
        if start is not None and end is not None:
            if end > start:
                passed += 1
            else:
                failures.append("end_date must be after start_date")
        else:
            # Cannot compare — treat as neutral.
            passed += 1

    # Rule 2: price and quantity must both be positive when present.
    for field in ("price", "quantity"):
        if field in data and data[field] is not None:
            total += 1
            val = data[field]
            if isinstance(val, (int, float)) and val > 0:
                passed += 1
            else:
                failures.append(f"{field!r} must be positive, got {val!r}")

    # Rule 3: if status is "completed", completed_at must exist.
    if data.get("status") == "completed":
        total += 1
        if data.get("completed_at") is not None:
            passed += 1
        else:
            failures.append("status is 'completed' but completed_at is missing")

    # Rule 4: if min and max exist (e.g. price_range), min <= max.
    for prefix in ("price", "score", "confidence", "value"):
        min_key = f"{prefix}_min"
        max_key = f"{prefix}_max"
        if min_key in data and max_key in data:
            total += 1
            lo = data[min_key]
            hi = data[max_key]
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
                if lo <= hi:
                    passed += 1
                else:
                    failures.append(f"{min_key}={lo} must be <= {max_key}={hi}")
            else:
                passed += 1  # Non-numeric: skip.

    return passed, total, failures


class L3Consistency(JudgeLevel):
    """Level 3: Consistency.

    Validates cross-field business invariants such as date ordering,
    positive numeric fields, and completion-state requirements.
    """

    @property
    def level(self) -> int:
        return 3

    @property
    def name(self) -> str:
        return "consistency"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Run cross-field consistency checks on input and output data.

        Args:
            ctx: Pipeline context.

        Returns:
            LevelVerdict — skipped if no applicable rules fire.
        """
        out_passed, out_total, out_failures = _run_consistency_checks(ctx.output_data)
        in_passed, in_total, in_failures = _run_consistency_checks(ctx.input_data)

        total = in_total + out_total
        passed = in_passed + out_passed
        all_failures = in_failures + out_failures

        if total == 0:
            return LevelVerdict(
                verdict="skip",
                score=1.0,
                confidence=1.0,
                details={"reason": "no consistency rules applicable"},
            )

        score = passed / total

        if score >= 1.0:
            verdict = "pass"
        elif score >= 0.7:
            verdict = "warn"
        else:
            verdict = "fail"

        return LevelVerdict(
            verdict=verdict,
            score=round(score, 4),
            confidence=0.95,
            details={
                "passed_checks": passed,
                "total_checks": total,
                "failures": all_failures,
            },
        )
