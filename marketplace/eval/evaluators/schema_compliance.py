"""Schema compliance evaluator — validates output matches expected JSON schema."""

from __future__ import annotations

import time
from typing import Any

import structlog

from marketplace.eval.base import BaseEvaluator
from marketplace.eval.types import EvalResult, EvalVerdict

logger = structlog.get_logger(__name__)


def _validate_schema(data: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    """Simple JSON schema validator (subset of JSON Schema Draft 7).

    Returns list of validation errors.
    """
    errors: list[str] = []
    schema_type = schema.get("type")

    if schema_type == "object":
        if not isinstance(data, dict):
            errors.append(f"{path}: expected object, got {type(data).__name__}")
            return errors

        # Check required fields
        for field in schema.get("required", []):
            if field not in data:
                errors.append(f"{path}.{field}: required field missing")

        # Validate properties
        properties = schema.get("properties", {})
        for key, prop_schema in properties.items():
            if key in data:
                errors.extend(_validate_schema(data[key], prop_schema, f"{path}.{key}"))

    elif schema_type == "array":
        if not isinstance(data, list):
            errors.append(f"{path}: expected array, got {type(data).__name__}")
            return errors
        items_schema = schema.get("items", {})
        if items_schema:
            for i, item in enumerate(data):
                errors.extend(_validate_schema(item, items_schema, f"{path}[{i}]"))

    elif schema_type == "string":
        if not isinstance(data, str):
            errors.append(f"{path}: expected string, got {type(data).__name__}")

    elif schema_type == "number":
        if not isinstance(data, (int, float)):
            errors.append(f"{path}: expected number, got {type(data).__name__}")

    elif schema_type == "integer":
        if not isinstance(data, int):
            errors.append(f"{path}: expected integer, got {type(data).__name__}")

    elif schema_type == "boolean":
        if not isinstance(data, bool):
            errors.append(f"{path}: expected boolean, got {type(data).__name__}")

    return errors


class SchemaComplianceEvaluator(BaseEvaluator):
    """Validates that output conforms to an expected JSON schema."""

    name = "schema_compliance"

    def __init__(self, schema: dict[str, Any] | None = None) -> None:
        self._schema = schema

    async def evaluate(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        expected: dict[str, Any] | None = None,
    ) -> EvalResult:
        start = time.perf_counter()

        # Use schema from expected or constructor
        schema = self._schema
        if expected and "schema" in expected:
            schema = expected["schema"]

        if schema is None:
            return EvalResult(
                eval_name=self.name,
                verdict=EvalVerdict.SKIP,
                score=0.0,
                details={"reason": "no_schema_provided"},
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        errors = _validate_schema(output_data, schema)
        duration_ms = (time.perf_counter() - start) * 1000

        if not errors:
            return EvalResult(
                eval_name=self.name,
                verdict=EvalVerdict.PASS,
                score=1.0,
                details={"validated_fields": len(schema.get("properties", {}))},
                duration_ms=duration_ms,
            )

        return EvalResult(
            eval_name=self.name,
            verdict=EvalVerdict.FAIL,
            score=max(0.0, 1.0 - len(errors) * 0.2),
            details={"errors": errors, "error_count": len(errors)},
            duration_ms=duration_ms,
        )
