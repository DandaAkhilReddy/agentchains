"""Shared utility functions for AgentChains marketplace services.

Extracted from 11+ service files where these were duplicated as private helpers.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


def utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def to_decimal(value: float | int | str | Decimal) -> Decimal:
    """Coerce a value to Decimal with 6 decimal places."""
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def load_json(value: str | None, fallback: object = None) -> object:
    """Parse a JSON string or return the fallback on failure."""
    if fallback is None:
        fallback = {}
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def safe_float(value: object, default: float = 0.0) -> float:
    """Convert a value to float, returning default on failure."""
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def safe_int(value: object, default: int = 0) -> int:
    """Convert a value to int, returning default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
