"""L1 Schema Validation — checks required fields and basic type correctness."""
from __future__ import annotations

from typing import Any

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict

# Required top-level keys expected in output_data for any evaluation target.
_REQUIRED_OUTPUT_KEYS: frozenset[str] = frozenset({"result", "status"})
# Required top-level keys expected in input_data.
_REQUIRED_INPUT_KEYS: frozenset[str] = frozenset({"query"})

# Expected types for known output fields. None means any non-None value is OK.
_OUTPUT_FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "result": (str, dict, list),
    "status": str,
}
_INPUT_FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "query": str,
}


def _check_fields(
    data: dict[str, Any],
    required_keys: frozenset[str],
    field_types: dict[str, type | tuple[type, ...]],
) -> tuple[int, int, list[str]]:
    """Check presence and type correctness for a set of fields.

    Args:
        data: The dict to validate.
        required_keys: Keys that must be present (non-None).
        field_types: Mapping of field name to expected type(s).

    Returns:
        Tuple of (passed_checks, total_checks, list_of_failure_reasons).
    """
    failures: list[str] = []
    total = len(required_keys) + len(field_types)
    passed = 0

    for key in required_keys:
        if key in data and data[key] is not None:
            passed += 1
        else:
            failures.append(f"missing required field: {key!r}")

    for key, expected_type in field_types.items():
        if key not in data:
            # Already counted as missing above if in required_keys.
            if key not in required_keys:
                failures.append(f"missing field: {key!r}")
        elif not isinstance(data[key], expected_type):
            failures.append(
                f"field {key!r} has wrong type: expected {expected_type}, "
                f"got {type(data[key]).__name__}"
            )
        else:
            passed += 1

    return passed, total, failures


class L1SchemaValidation(JudgeLevel):
    """Level 1: Schema Validation.

    Validates that ``input_data`` and ``output_data`` contain the required
    fields with the correct types.  Score reflects the proportion of checks
    that passed.
    """

    @property
    def level(self) -> int:
        return 1

    @property
    def name(self) -> str:
        return "schema_validation"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Check required fields and types in input/output data.

        Args:
            ctx: Pipeline context.

        Returns:
            LevelVerdict with score proportional to passing checks.
        """
        in_passed, in_total, in_failures = _check_fields(
            ctx.input_data, _REQUIRED_INPUT_KEYS, _INPUT_FIELD_TYPES
        )
        out_passed, out_total, out_failures = _check_fields(
            ctx.output_data, _REQUIRED_OUTPUT_KEYS, _OUTPUT_FIELD_TYPES
        )

        total = in_total + out_total
        passed = in_passed + out_passed
        score = passed / total if total > 0 else 1.0

        all_failures = in_failures + out_failures

        if score >= 1.0:
            verdict = "pass"
        elif score >= 0.5:
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
