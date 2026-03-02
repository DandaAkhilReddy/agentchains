"""JSON Normalizer A2A Agent — nested JSON flattening via the A2A protocol.

Runs on port 9008 and exposes a ``normalize-json`` skill. Accepts an arbitrary
JSON dict or list, flattens it to dot-notation keys, optionally filters to a
requested set of fields, and returns structural metadata alongside the result.
"""

from __future__ import annotations

from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "normalize-json",
        "name": "Normalize JSON",
        "description": (
            "Flatten nested JSON objects/arrays to dot-notation keys "
            "(e.g. ``a.b.c``), with optional field extraction. Returns the "
            "normalized dict alongside field count and depth statistics."
        ),
        "tags": ["json", "normalization", "flattening", "data-transformation"],
        "examples": [
            '{"data": {"user": {"name": "Alice", "address": {"city": "NYC"}}}}',
            '{"data": [{"id": 1, "tags": ["a", "b"]}], "extract_fields": ["items.0.id"]}',
        ],
    }
]


def _depth(value: Any, current: int = 0) -> int:
    """Recursively compute the maximum nesting depth of a JSON value.

    Args:
        value: Any JSON-compatible value (dict, list, scalar).
        current: Depth of the current node (internal recursion counter).

    Returns:
        Integer depth of the deepest nested node.
    """
    if isinstance(value, dict):
        if not value:
            return current + 1
        return max(_depth(v, current + 1) for v in value.values())
    if isinstance(value, list):
        if not value:
            return current + 1
        return max(_depth(item, current + 1) for item in value)
    return current


def _flatten(
    value: Any,
    prefix: str = "",
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recursively flatten a nested JSON structure to dot-notation keys.

    Dicts are traversed with ``parent.child`` key paths. List elements are
    indexed as ``parent.0``, ``parent.1``, etc.

    Args:
        value: The JSON value to flatten (dict, list, or scalar).
        prefix: Key prefix accumulated during recursion.
        result: Accumulator dict (created on first call).

    Returns:
        Flat dict where every key is a dot-separated path string and every
        value is a scalar (str, int, float, bool, or None).
    """
    if result is None:
        result = {}

    if isinstance(value, dict):
        for key, child in value.items():
            new_key = f"{prefix}.{key}" if prefix else key
            _flatten(child, new_key, result)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            new_key = f"{prefix}.{idx}" if prefix else str(idx)
            _flatten(item, new_key, result)
    else:
        result[prefix] = value

    return result


def _extract_fields(
    flat: dict[str, Any], fields: list[str]
) -> dict[str, Any]:
    """Filter a flat dict to only the requested dot-notation field paths.

    Performs prefix matching so requesting ``"user"`` will include
    ``"user.name"`` and ``"user.age"`` etc.

    Args:
        flat: A fully flattened dot-notation dict.
        fields: List of field paths or prefixes to retain.

    Returns:
        Filtered dict containing only keys that match a requested field
        or that start with a requested field prefix.
    """
    kept: dict[str, Any] = {}
    for field in fields:
        exact_prefix = field + "."
        for key, val in flat.items():
            if key == field or key.startswith(exact_prefix):
                kept[key] = val
    return kept


class JsonNormalizerA2AAgent(BaseA2AAgent):
    """A2A agent that flattens nested JSON to dot-notation keys.

    The ``normalize-json`` skill accepts a ``data`` payload (dict or list),
    an optional ``flatten`` flag (default ``True``), and an optional
    ``extract_fields`` list to project specific paths from the result.
    """

    def __init__(self) -> None:
        super().__init__(
            name="JSON Normalizer Agent",
            description=(
                "Flattens nested JSON objects and arrays to dot-notation keys, "
                "with optional field extraction. Returns the normalized dict "
                "alongside field count, original depth, and flattened depth "
                "metadata. Useful as a pre-processing step in data pipelines."
            ),
            port=9008,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming JSON normalization request.

        Args:
            skill_id: Must be ``normalize-json``.
            input_data: Dict with:
                - ``data`` (dict | list): The JSON value to normalize. Required.
                - ``flatten`` (bool, default ``True``): Whether to flatten nesting.
                - ``extract_fields`` (list[str], optional): Dot-notation field
                  paths to retain after flattening.

        Returns:
            Dict with ``normalized`` (flattened/filtered dict), ``field_count``
            (int), ``original_depth`` (int), and ``flattened_depth`` (int, always 1
            after full flattening).
        """
        data: Any = input_data.get("data")
        if data is None:
            return {
                "normalized": {},
                "field_count": 0,
                "original_depth": 0,
                "flattened_depth": 0,
            }

        should_flatten: bool = bool(input_data.get("flatten", True))
        extract_fields: list[str] = input_data.get("extract_fields") or []

        original_depth = _depth(data)

        if should_flatten:
            normalized = _flatten(data)
        else:
            # No flattening: wrap scalars or return the dict as-is
            if isinstance(data, dict):
                normalized = dict(data)
            elif isinstance(data, list):
                normalized = {str(i): v for i, v in enumerate(data)}
            else:
                normalized = {"value": data}

        if extract_fields:
            normalized = _extract_fields(normalized, extract_fields)

        flattened_depth = _depth(normalized) if not should_flatten else 1

        return {
            "normalized": normalized,
            "field_count": len(normalized),
            "original_depth": original_depth,
            "flattened_depth": flattened_depth,
        }


agent = JsonNormalizerA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9008)
