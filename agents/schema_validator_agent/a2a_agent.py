"""Schema Validator A2A Agent — JSON Schema validation via the A2A protocol.

Runs on port 9014 and exposes a ``validate-schema`` skill. Implements a recursive
JSON Schema validator supporting a practical subset: type, required, properties,
items, minimum, maximum, minLength, maxLength, pattern, and enum keywords.
All validation errors are collected and returned together rather than failing fast.
"""

from __future__ import annotations

import re
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "validate-schema",
        "name": "Validate Schema",
        "description": (
            "Validate a data payload against a JSON Schema. Supports type, required, "
            "properties, items, minimum, maximum, minLength, maxLength, pattern, and "
            "enum keywords. Returns all errors, not just the first one."
        ),
        "tags": ["validation", "schema", "json-schema", "compliance", "data-quality"],
        "examples": [
            '{"data": {"name": "Alice", "age": 30}, "schema": {"type": "object", "required": ["name"]}}',
            '{"data": [1, 2, "three"], "schema": {"type": "array", "items": {"type": "integer"}}}',
        ],
    }
]

_JSON_SCHEMA_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _type_name(value: Any) -> str:
    """Return a JSON Schema type label for a Python value.

    Args:
        value: Any Python object.

    Returns:
        One of the JSON Schema type strings: ``string``, ``integer``, ``number``,
        ``boolean``, ``array``, ``object``, or ``null``.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _validate_node(
    data: Any,
    schema: dict[str, Any],
    path: str,
    errors: list[dict[str, Any]],
    checked: list[str],
) -> None:
    """Recursively validate a data node against a schema node.

    Collects all constraint violations into ``errors`` without raising. Appends
    each checked field path to ``checked``.

    Args:
        data: The data value to validate at this node.
        schema: The JSON Schema dict applicable to this node.
        path: Dot-path string identifying this node for error messages.
        errors: Mutable list to append error dicts into.
        checked: Mutable list to append checked field paths into.
    """
    checked.append(path or "(root)")

    # ── type ────────────────────────────────────────────────────────────────
    expected_type: str | None = schema.get("type")
    if expected_type is not None:
        py_type = _JSON_SCHEMA_TYPES.get(expected_type)
        if py_type is not None:
            # booleans are ints in Python — reject bool when type == "integer"
            if expected_type == "integer" and isinstance(data, bool):
                errors.append({
                    "path": path or "(root)",
                    "message": f"Expected type '{expected_type}' but got 'boolean'",
                    "expected": expected_type,
                    "actual": _type_name(data),
                })
                return
            if not isinstance(data, py_type):
                errors.append({
                    "path": path or "(root)",
                    "message": f"Expected type '{expected_type}' but got '{_type_name(data)}'",
                    "expected": expected_type,
                    "actual": _type_name(data),
                })
                # Do not recurse into properties/items when root type is wrong
                return

    # ── enum ────────────────────────────────────────────────────────────────
    enum_values: list[Any] | None = schema.get("enum")
    if enum_values is not None and data not in enum_values:
        errors.append({
            "path": path or "(root)",
            "message": f"Value {data!r} is not one of {enum_values!r}",
            "expected": f"one of {enum_values!r}",
            "actual": repr(data),
        })

    # ── string constraints ───────────────────────────────────────────────────
    if isinstance(data, str):
        min_len: int | None = schema.get("minLength")
        if min_len is not None and len(data) < min_len:
            errors.append({
                "path": path or "(root)",
                "message": f"String length {len(data)} is less than minLength {min_len}",
                "expected": f"minLength {min_len}",
                "actual": str(len(data)),
            })

        max_len: int | None = schema.get("maxLength")
        if max_len is not None and len(data) > max_len:
            errors.append({
                "path": path or "(root)",
                "message": f"String length {len(data)} exceeds maxLength {max_len}",
                "expected": f"maxLength {max_len}",
                "actual": str(len(data)),
            })

        pattern: str | None = schema.get("pattern")
        if pattern is not None and not re.search(pattern, data):
            errors.append({
                "path": path or "(root)",
                "message": f"String {data!r} does not match pattern {pattern!r}",
                "expected": f"matches pattern {pattern!r}",
                "actual": repr(data),
            })

    # ── numeric constraints ──────────────────────────────────────────────────
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        minimum: int | float | None = schema.get("minimum")
        if minimum is not None and data < minimum:
            errors.append({
                "path": path or "(root)",
                "message": f"Value {data} is less than minimum {minimum}",
                "expected": f">= {minimum}",
                "actual": str(data),
            })

        maximum: int | float | None = schema.get("maximum")
        if maximum is not None and data > maximum:
            errors.append({
                "path": path or "(root)",
                "message": f"Value {data} exceeds maximum {maximum}",
                "expected": f"<= {maximum}",
                "actual": str(data),
            })

    # ── object constraints ───────────────────────────────────────────────────
    if isinstance(data, dict):
        required_fields: list[str] = schema.get("required", [])
        for field in required_fields:
            field_path = f"{path}.{field}" if path else field
            checked.append(field_path)
            if field not in data:
                errors.append({
                    "path": field_path,
                    "message": f"Required field '{field}' is missing",
                    "expected": "present",
                    "actual": "missing",
                })

        properties: dict[str, Any] = schema.get("properties", {})
        for prop, prop_schema in properties.items():
            if prop in data:
                child_path = f"{path}.{prop}" if path else prop
                _validate_node(data[prop], prop_schema, child_path, errors, checked)

    # ── array constraints ────────────────────────────────────────────────────
    if isinstance(data, list):
        items_schema: dict[str, Any] | None = schema.get("items")
        if items_schema is not None:
            for idx, item in enumerate(data):
                child_path = f"{path}[{idx}]" if path else f"[{idx}]"
                _validate_node(item, items_schema, child_path, errors, checked)


def _validate(data: Any, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate data against a JSON Schema and return a structured result.

    Args:
        data: The data value to validate (any JSON-compatible type).
        schema: A JSON Schema dict using the supported subset of keywords.

    Returns:
        Dict with ``valid`` (bool), ``errors`` (list of error dicts with
        ``path``, ``message``, ``expected``, ``actual`` keys), and
        ``checked_fields`` (list of paths that were inspected).
    """
    errors: list[dict[str, Any]] = []
    checked: list[str] = []
    _validate_node(data, schema, "", errors, checked)
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "checked_fields": list(dict.fromkeys(checked)),  # deduplicate, preserve order
    }


class SchemaValidatorA2AAgent(BaseA2AAgent):
    """A2A agent that validates data payloads against JSON Schema definitions.

    Accepts a ``data`` value and a ``schema`` dict via the ``validate-schema``
    skill. Implements a recursive validator for a practical JSON Schema subset
    without relying on the ``jsonschema`` library. All errors are collected
    before returning so callers receive a complete picture of violations.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Schema Validator Agent",
            description=(
                "Validates data payloads against a JSON Schema (simplified subset). "
                "Supports type, required, properties, items, minimum, maximum, "
                "minLength, maxLength, pattern, and enum. Returns all errors at once."
            ),
            port=9014,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming schema validation request.

        Args:
            skill_id: Must be ``validate-schema``.
            input_data: Dict with ``data`` (any JSON value) and ``schema`` (dict).

        Returns:
            Dict with ``valid`` (bool), ``errors`` (list of error dicts), and
            ``checked_fields`` (list of inspected field paths).
        """
        data: Any = input_data.get("data")
        schema: dict[str, Any] = input_data.get("schema", {})

        if not isinstance(schema, dict):
            return {
                "valid": False,
                "errors": [
                    {
                        "path": "(root)",
                        "message": "Schema must be a JSON object (dict)",
                        "expected": "object",
                        "actual": _type_name(schema),
                    }
                ],
                "checked_fields": [],
            }

        return _validate(data, schema)


agent = SchemaValidatorA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9014)
