"""Tests for marketplace.core.utils — shared utility functions.

Covers:
- utcnow: returns timezone-aware UTC datetime
- to_decimal: coercion from float/int/str/Decimal, quantization to 6 places
- load_json: valid JSON, invalid JSON, empty/None input, custom fallback
- safe_float: normal conversion, NaN/Inf rejection, non-numeric types
- safe_int: normal conversion, non-numeric types
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from marketplace.core.utils import (
    load_json,
    safe_float,
    safe_int,
    to_decimal,
    utcnow,
)


# ---------------------------------------------------------------------------
# utcnow
# ---------------------------------------------------------------------------


class TestUtcnow:
    """UTC datetime generation."""

    def test_returns_datetime(self) -> None:
        result = utcnow()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self) -> None:
        result = utcnow()
        assert result.tzinfo is not None

    def test_is_utc(self) -> None:
        result = utcnow()
        assert result.tzinfo == timezone.utc

    def test_is_close_to_now(self) -> None:
        before = datetime.now(timezone.utc)
        result = utcnow()
        after = datetime.now(timezone.utc)
        assert before <= result <= after


# ---------------------------------------------------------------------------
# to_decimal
# ---------------------------------------------------------------------------


class TestToDecimal:
    """Decimal coercion with 6-place quantization."""

    def test_from_int(self) -> None:
        result = to_decimal(42)
        assert result == Decimal("42.000000")
        assert isinstance(result, Decimal)

    def test_from_float(self) -> None:
        result = to_decimal(3.14)
        assert result == Decimal("3.140000")

    def test_from_string(self) -> None:
        result = to_decimal("99.123456789")
        assert result == Decimal("99.123457")  # rounded

    def test_from_decimal(self) -> None:
        original = Decimal("1.23456789")
        result = to_decimal(original)
        assert result == Decimal("1.234568")

    def test_already_quantized_decimal_unchanged(self) -> None:
        original = Decimal("5.500000")
        result = to_decimal(original)
        assert result == original

    def test_zero(self) -> None:
        result = to_decimal(0)
        assert result == Decimal("0.000000")

    def test_negative_value(self) -> None:
        result = to_decimal(-1.5)
        assert result == Decimal("-1.500000")

    def test_very_small_value(self) -> None:
        result = to_decimal(0.0000001)
        assert result == Decimal("0.000000")  # rounds to 0 at 6 places

    def test_large_value(self) -> None:
        result = to_decimal(999999999.999999)
        assert isinstance(result, Decimal)
        assert result > Decimal("999999999")


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------


class TestLoadJson:
    """JSON parsing with fallback."""

    def test_valid_json_object(self) -> None:
        result = load_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_array(self) -> None:
        result = load_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_valid_json_string(self) -> None:
        result = load_json('"hello"')
        assert result == "hello"

    def test_valid_json_number(self) -> None:
        result = load_json("42")
        assert result == 42

    def test_valid_json_boolean(self) -> None:
        result = load_json("true")
        assert result is True

    def test_valid_json_null(self) -> None:
        result = load_json("null")
        assert result is None

    def test_invalid_json_returns_default_dict(self) -> None:
        result = load_json("{not valid json}")
        assert result == {}

    def test_empty_string_returns_default_dict(self) -> None:
        result = load_json("")
        assert result == {}

    def test_none_input_returns_default_dict(self) -> None:
        result = load_json(None)
        assert result == {}

    def test_custom_fallback_on_invalid_json(self) -> None:
        result = load_json("bad json", fallback=[])
        assert result == []

    def test_custom_fallback_on_none(self) -> None:
        result = load_json(None, fallback="default")
        assert result == "default"

    def test_custom_fallback_on_empty_string(self) -> None:
        result = load_json("", fallback=42)
        assert result == 42

    def test_none_fallback_becomes_empty_dict(self) -> None:
        """When fallback is explicitly None, the function defaults to {}."""
        result = load_json("", fallback=None)
        assert result == {}

    def test_nested_json(self) -> None:
        result = load_json('{"a": {"b": [1, 2]}}')
        assert result == {"a": {"b": [1, 2]}}


# ---------------------------------------------------------------------------
# safe_float
# ---------------------------------------------------------------------------


class TestSafeFloat:
    """Safe float conversion."""

    def test_from_int(self) -> None:
        assert safe_float(42) == 42.0

    def test_from_float(self) -> None:
        assert safe_float(3.14) == 3.14

    def test_from_string(self) -> None:
        assert safe_float("2.718") == 2.718

    def test_from_decimal(self) -> None:
        assert safe_float(Decimal("9.99")) == 9.99

    def test_nan_returns_default(self) -> None:
        assert safe_float(float("nan")) == 0.0

    def test_inf_returns_default(self) -> None:
        assert safe_float(float("inf")) == 0.0

    def test_negative_inf_returns_default(self) -> None:
        assert safe_float(float("-inf")) == 0.0

    def test_none_returns_default(self) -> None:
        assert safe_float(None) == 0.0

    def test_non_numeric_string_returns_default(self) -> None:
        assert safe_float("not-a-number") == 0.0

    def test_empty_string_returns_default(self) -> None:
        assert safe_float("") == 0.0

    def test_custom_default(self) -> None:
        assert safe_float("bad", default=-1.0) == -1.0

    def test_object_returns_default(self) -> None:
        assert safe_float(object()) == 0.0

    def test_list_returns_default(self) -> None:
        assert safe_float([1, 2, 3]) == 0.0

    def test_zero_string(self) -> None:
        assert safe_float("0") == 0.0

    def test_negative_string(self) -> None:
        assert safe_float("-3.5") == -3.5

    def test_nan_with_custom_default(self) -> None:
        assert safe_float(float("nan"), default=99.0) == 99.0

    def test_bool_true_converts_to_float(self) -> None:
        """Python: float(True) == 1.0."""
        assert safe_float(True) == 1.0

    def test_bool_false_converts_to_float(self) -> None:
        assert safe_float(False) == 0.0


# ---------------------------------------------------------------------------
# safe_int
# ---------------------------------------------------------------------------


class TestSafeInt:
    """Safe int conversion."""

    def test_from_int(self) -> None:
        assert safe_int(42) == 42

    def test_from_float(self) -> None:
        assert safe_int(3.9) == 3  # truncates

    def test_from_string(self) -> None:
        assert safe_int("100") == 100

    def test_from_decimal(self) -> None:
        assert safe_int(Decimal("7")) == 7

    def test_none_returns_default(self) -> None:
        assert safe_int(None) == 0

    def test_non_numeric_string_returns_default(self) -> None:
        assert safe_int("abc") == 0

    def test_empty_string_returns_default(self) -> None:
        assert safe_int("") == 0

    def test_custom_default(self) -> None:
        assert safe_int("bad", default=-1) == -1

    def test_float_string_returns_default(self) -> None:
        """int("3.14") raises ValueError — safe_int should return default."""
        assert safe_int("3.14") == 0

    def test_object_returns_default(self) -> None:
        assert safe_int(object()) == 0

    def test_negative_int_string(self) -> None:
        assert safe_int("-5") == -5

    def test_zero(self) -> None:
        assert safe_int(0) == 0

    def test_bool_true(self) -> None:
        assert safe_int(True) == 1

    def test_bool_false(self) -> None:
        assert safe_int(False) == 0
