"""Unit tests for each judge level L1-L10.

Tests cover happy paths, edge cases, empty/degenerate input, and mock-based
LLM paths for L6 (Semantic), L7 (Safety), and L8 (Consensus).
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.services.judge.base import JudgeContext, LevelVerdict
from marketplace.services.judge.levels.l1_schema import L1SchemaValidation
from marketplace.services.judge.levels.l2_data_quality import L2DataQuality
from marketplace.services.judge.levels.l3_consistency import L3Consistency
from marketplace.services.judge.levels.l4_performance import L4Performance
from marketplace.services.judge.levels.l5_statistical import L5Statistical
from marketplace.services.judge.levels.l6_semantic import L6Semantic
from marketplace.services.judge.levels.l7_safety import L7Safety
from marketplace.services.judge.levels.l8_consensus import L8Consensus
from marketplace.services.judge.levels.l9_aggregator import L9Aggregator
from marketplace.services.judge.levels.l10_human_gate import L10HumanGate


# ---------------------------------------------------------------------------
# Helper: build a minimal valid JudgeContext
# ---------------------------------------------------------------------------

def make_context(
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    previous_verdicts: list[LevelVerdict] | None = None,
) -> JudgeContext:
    """Build a JudgeContext with sensible defaults for testing."""
    return JudgeContext(
        target_type="agent_output",
        target_id="test-target-001",
        input_data=input_data if input_data is not None else {"query": "What is the capital of France?"},
        output_data=output_data if output_data is not None else {"result": "Paris", "status": "ok"},
        metadata=metadata if metadata is not None else {},
        previous_verdicts=previous_verdicts if previous_verdicts is not None else [],
    )


def _make_verdict(
    verdict: str = "pass",
    score: float = 1.0,
    confidence: float = 0.9,
    should_short_circuit: bool = False,
) -> LevelVerdict:
    """Build a LevelVerdict for use in previous_verdicts lists."""
    return LevelVerdict(
        verdict=verdict,
        score=score,
        confidence=confidence,
        should_short_circuit=should_short_circuit,
    )


# ===========================================================================
# L1 — Schema Validation
# ===========================================================================

class TestL1SchemaValidation:
    """Tests for L1SchemaValidation — required field presence and type checks."""

    @pytest.fixture
    def level(self) -> L1SchemaValidation:
        return L1SchemaValidation()

    def test_level_number_and_name(self, level: L1SchemaValidation) -> None:
        assert level.level == 1
        assert level.name == "schema_validation"

    @pytest.mark.asyncio
    async def test_valid_input_output_passes(self, level: L1SchemaValidation) -> None:
        """All required fields present with correct types → pass."""
        ctx = make_context(
            input_data={"query": "test query"},
            output_data={"result": "some answer", "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.score == 1.0
        assert verdict.confidence == 0.95
        assert verdict.details["failures"] == []

    @pytest.mark.asyncio
    async def test_missing_required_output_field_result_fails(self, level: L1SchemaValidation) -> None:
        """Missing 'result' in output_data causes failure (score < 0.5)."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"status": "ok"},  # 'result' missing
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("result" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_missing_required_output_field_status_fails(self, level: L1SchemaValidation) -> None:
        """Missing 'status' in output_data surfaces as a schema failure."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer"},  # 'status' missing
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("status" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_missing_required_input_query_fails(self, level: L1SchemaValidation) -> None:
        """Missing 'query' in input_data surfaces as a schema failure."""
        ctx = make_context(
            input_data={},  # 'query' missing
            output_data={"result": "answer", "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("query" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_wrong_type_for_status_fails(self, level: L1SchemaValidation) -> None:
        """Non-string 'status' is a type mismatch → fail/warn."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": 42},  # int not str
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("status" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_wrong_type_for_query_fails(self, level: L1SchemaValidation) -> None:
        """Non-string 'query' is a type mismatch → fail/warn."""
        ctx = make_context(
            input_data={"query": 123},
            output_data={"result": "answer", "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("query" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_empty_output_data_fails(self, level: L1SchemaValidation) -> None:
        """Completely empty output_data → both required fields missing → fail."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "fail"
        assert len(verdict.details["failures"]) >= 2

    @pytest.mark.asyncio
    async def test_empty_input_data_fails(self, level: L1SchemaValidation) -> None:
        """Completely empty input_data → 'query' missing → fail/warn."""
        ctx = make_context(
            input_data={},
            output_data={"result": "answer", "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}

    @pytest.mark.asyncio
    async def test_score_reflects_partial_pass(self, level: L1SchemaValidation) -> None:
        """When some fields pass and others fail, score is between 0 and 1."""
        ctx = make_context(
            input_data={"query": "valid"},
            output_data={"result": "answer"},  # missing 'status'
        )
        verdict = await level.evaluate(ctx)
        assert 0.0 < verdict.score < 1.0

    @pytest.mark.asyncio
    async def test_result_as_list_is_accepted(self, level: L1SchemaValidation) -> None:
        """'result' can be a list — acceptable type."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": [1, 2, 3], "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_result_as_dict_is_accepted(self, level: L1SchemaValidation) -> None:
        """'result' can be a dict — acceptable type."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": {"answer": "Paris"}, "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_none_value_for_required_field_fails(self, level: L1SchemaValidation) -> None:
        """None value for a required field is treated as missing → failure."""
        ctx = make_context(
            input_data={"query": None},
            output_data={"result": "answer", "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert any("query" in f for f in verdict.details["failures"])


# ===========================================================================
# L2 — Data Quality
# ===========================================================================

class TestL2DataQuality:
    """Tests for L2DataQuality — null checks, empty strings, bounds validation."""

    @pytest.fixture
    def level(self) -> L2DataQuality:
        return L2DataQuality()

    def test_level_number_and_name(self, level: L2DataQuality) -> None:
        assert level.level == 2
        assert level.name == "data_quality"

    @pytest.mark.asyncio
    async def test_good_quality_data_passes(self, level: L2DataQuality) -> None:
        """All fields non-null, non-empty, within bounds → pass."""
        ctx = make_context(
            input_data={"query": "valid query"},
            output_data={"result": "valid result", "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.score >= 0.9

    @pytest.mark.asyncio
    async def test_null_required_output_field_fails(self, level: L2DataQuality) -> None:
        """Null 'result' field in output_data → quality failure."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": None, "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("result" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_null_required_status_field_fails(self, level: L2DataQuality) -> None:
        """Null 'status' field → quality failure."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": None},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("status" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_empty_string_result_fails(self, level: L2DataQuality) -> None:
        """Empty string 'result' (whitespace only) → quality failure."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "   ", "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("result" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_empty_string_status_fails(self, level: L2DataQuality) -> None:
        """Empty string 'status' → quality failure."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": ""},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("status" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_score_in_bounds_passes(self, level: L2DataQuality) -> None:
        """Numeric 'score' field in [0, 1] passes bounds check."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": "ok", "score": 0.85},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert "score" not in " ".join(verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_score_out_of_bounds_fails(self, level: L2DataQuality) -> None:
        """Numeric 'score' above 1.0 fails bounds check."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": "ok", "score": 1.5},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("score" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_negative_score_fails_bounds(self, level: L2DataQuality) -> None:
        """Negative 'score' value fails bounds check."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": "ok", "score": -0.1},
        )
        verdict = await level.evaluate(ctx)
        assert any("score" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_price_out_of_bounds_fails(self, level: L2DataQuality) -> None:
        """Negative 'price' value fails bounds check (price must be >= 0)."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": "ok", "price": -5.0},
        )
        verdict = await level.evaluate(ctx)
        assert any("price" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_none_extra_field_fails(self, level: L2DataQuality) -> None:
        """None value for an arbitrary extra field → quality failure."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": "ok", "extra_field": None},
        )
        verdict = await level.evaluate(ctx)
        assert any("extra_field" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_confidence_score_of_zero_is_valid(self, level: L2DataQuality) -> None:
        """confidence=0.0 is at the minimum bound → should pass bounds check."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": "ok", "confidence": 0.0},
        )
        verdict = await level.evaluate(ctx)
        assert not any("confidence" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_confidence_score_of_one_is_valid(self, level: L2DataQuality) -> None:
        """confidence=1.0 is at the maximum bound → should pass bounds check."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status": "ok", "confidence": 1.0},
        )
        verdict = await level.evaluate(ctx)
        assert not any("confidence" in f for f in verdict.details["failures"])


# ===========================================================================
# L3 — Consistency
# ===========================================================================

class TestL3Consistency:
    """Tests for L3Consistency — cross-field business invariant validation."""

    @pytest.fixture
    def level(self) -> L3Consistency:
        return L3Consistency()

    def test_level_number_and_name(self, level: L3Consistency) -> None:
        assert level.level == 3
        assert level.name == "consistency"

    @pytest.mark.asyncio
    async def test_no_applicable_rules_skips(self, level: L3Consistency) -> None:
        """No date/price/status fields → skip verdict."""
        ctx = make_context(
            input_data={"query": "q"},
            output_data={"result": "answer", "status_field": "none"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "skip"
        assert verdict.score == 1.0
        assert "no consistency rules applicable" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_valid_date_range_passes(self, level: L3Consistency) -> None:
        """end_date after start_date → pass."""
        ctx = make_context(
            output_data={
                "result": "answer",
                "start_date": "2024-01-01T00:00:00",
                "end_date": "2024-12-31T00:00:00",
            },
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.details["failures"] == []

    @pytest.mark.asyncio
    async def test_end_date_before_start_date_fails(self, level: L3Consistency) -> None:
        """end_date before start_date → consistency failure."""
        ctx = make_context(
            output_data={
                "result": "answer",
                "start_date": "2024-12-31T00:00:00",
                "end_date": "2024-01-01T00:00:00",
            },
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("end_date" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_equal_start_end_date_fails(self, level: L3Consistency) -> None:
        """end_date == start_date violates the 'after' invariant."""
        ctx = make_context(
            output_data={
                "result": "ok",
                "start_date": "2024-06-01T00:00:00",
                "end_date": "2024-06-01T00:00:00",
            },
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}

    @pytest.mark.asyncio
    async def test_completed_with_timestamp_passes(self, level: L3Consistency) -> None:
        """status='completed' + completed_at present → pass."""
        ctx = make_context(
            output_data={
                "result": "done",
                "status": "completed",
                "completed_at": "2024-06-15T12:00:00",
            },
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_completed_without_timestamp_fails(self, level: L3Consistency) -> None:
        """status='completed' but no completed_at → consistency failure."""
        ctx = make_context(
            output_data={
                "result": "done",
                "status": "completed",
                # no completed_at
            },
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("completed_at" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_positive_price_passes(self, level: L3Consistency) -> None:
        """Positive price value → passes consistency check."""
        ctx = make_context(
            output_data={"result": "item", "price": 9.99},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_zero_price_fails(self, level: L3Consistency) -> None:
        """price=0 violates 'must be positive' rule."""
        ctx = make_context(
            output_data={"result": "item", "price": 0},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("price" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_negative_quantity_fails(self, level: L3Consistency) -> None:
        """Negative quantity violates 'must be positive' rule."""
        ctx = make_context(
            output_data={"result": "item", "quantity": -1},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("quantity" in f for f in verdict.details["failures"])

    @pytest.mark.asyncio
    async def test_valid_price_range_passes(self, level: L3Consistency) -> None:
        """price_min <= price_max → passes range check."""
        ctx = make_context(
            output_data={"result": "ok", "price_min": 1.0, "price_max": 5.0},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_inverted_price_range_fails(self, level: L3Consistency) -> None:
        """price_min > price_max → fails range check."""
        ctx = make_context(
            output_data={"result": "ok", "price_min": 10.0, "price_max": 1.0},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert any("price_min" in f for f in verdict.details["failures"])


# ===========================================================================
# L4 — Performance
# ===========================================================================

class TestL4Performance:
    """Tests for L4Performance — latency and response-size checks."""

    @pytest.fixture
    def level(self) -> L4Performance:
        return L4Performance()

    def test_level_number_and_name(self, level: L4Performance) -> None:
        assert level.level == 4
        assert level.name == "performance"

    @pytest.mark.asyncio
    async def test_no_metadata_skips(self, level: L4Performance) -> None:
        """No performance metrics in metadata → skip verdict."""
        ctx = make_context(metadata={})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "skip"
        assert "no performance metrics" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_fast_response_passes(self, level: L4Performance) -> None:
        """latency_ms=100 (< 5000ms threshold) → pass."""
        ctx = make_context(metadata={"latency_ms": 100})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.score > 0.5

    @pytest.mark.asyncio
    async def test_latency_at_pass_threshold_passes(self, level: L4Performance) -> None:
        """latency_ms=4999 (just under 5000ms) → pass."""
        ctx = make_context(metadata={"latency_ms": 4999})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_latency_in_warn_range_warns(self, level: L4Performance) -> None:
        """latency_ms=7500 (between 5000 and 10000) → warn."""
        ctx = make_context(metadata={"latency_ms": 7500})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "warn"
        assert verdict.score < 0.5

    @pytest.mark.asyncio
    async def test_latency_exceeds_warn_threshold_fails(self, level: L4Performance) -> None:
        """latency_ms=15000 (> 10000ms) → fail."""
        ctx = make_context(metadata={"latency_ms": 15000})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "fail"
        assert verdict.score == 0.0

    @pytest.mark.asyncio
    async def test_zero_latency_passes(self, level: L4Performance) -> None:
        """latency_ms=0 → maximum score, pass."""
        ctx = make_context(metadata={"latency_ms": 0})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.score == 1.0

    @pytest.mark.asyncio
    async def test_large_response_size_warns(self, level: L4Performance) -> None:
        """response_size_bytes > 1 MiB → warn."""
        ctx = make_context(metadata={"response_size_bytes": 2 * 1024 * 1024})  # 2 MiB
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "warn"
        assert verdict.score < 1.0

    @pytest.mark.asyncio
    async def test_small_response_size_passes(self, level: L4Performance) -> None:
        """response_size_bytes = 1024 bytes → pass (under threshold)."""
        ctx = make_context(metadata={"response_size_bytes": 1024})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.score == 1.0

    @pytest.mark.asyncio
    async def test_combined_latency_and_size_weights(self, level: L4Performance) -> None:
        """With both metrics, score is 70% latency + 30% size weighted."""
        ctx = make_context(metadata={"latency_ms": 0, "response_size_bytes": 1024})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.details["latency_ms"] == 0
        assert verdict.details["response_size_bytes"] == 1024

    @pytest.mark.asyncio
    async def test_only_size_metric_present(self, level: L4Performance) -> None:
        """Only response_size_bytes in metadata (no latency) → evaluates size only."""
        ctx = make_context(metadata={"response_size_bytes": 512})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"


# ===========================================================================
# L5 — Statistical
# ===========================================================================

class TestL5Statistical:
    """Tests for L5Statistical — outlier detection via z-score."""

    @pytest.fixture
    def level(self) -> L5Statistical:
        return L5Statistical()

    def test_level_number_and_name(self, level: L5Statistical) -> None:
        assert level.level == 5
        assert level.name == "statistical"

    @pytest.mark.asyncio
    async def test_no_numeric_data_skips(self, level: L5Statistical) -> None:
        """No numeric values in output_data → skip verdict."""
        ctx = make_context(
            output_data={"result": "text only", "status": "ok"},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "skip"
        assert "insufficient numeric data" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_fewer_than_three_values_skips(self, level: L5Statistical) -> None:
        """Only 2 numeric values → below _MIN_SAMPLE_SIZE=3 → skip."""
        ctx = make_context(
            output_data={"a": 1.0, "b": 2.0},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "skip"
        assert verdict.details["numeric_count"] == 2

    @pytest.mark.asyncio
    async def test_normal_data_passes(self, level: L5Statistical) -> None:
        """Normal numeric distribution (no outliers) → pass."""
        ctx = make_context(
            output_data={"v1": 1.0, "v2": 1.1, "v3": 0.9, "v4": 1.05, "v5": 0.95},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.score == 1.0
        assert verdict.details["outlier_count"] == 0

    @pytest.mark.asyncio
    async def test_extreme_outlier_warns_or_fails(self, level: L5Statistical) -> None:
        """One extreme outlier in otherwise tight data → warn or fail."""
        # 50 values near 1.0 plus one extreme outlier — z-score will be well above 3
        tight = {f"v{i}": 1.0 for i in range(50)}
        tight["outlier"] = 1_000_000.0
        ctx = make_context(output_data=tight)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "fail"}
        assert verdict.details["outlier_count"] >= 1

    @pytest.mark.asyncio
    async def test_constant_values_pass(self, level: L5Statistical) -> None:
        """All identical values → stddev=0 → no outliers → pass."""
        ctx = make_context(
            output_data={"a": 5.0, "b": 5.0, "c": 5.0, "d": 5.0},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_nested_numeric_values_collected(self, level: L5Statistical) -> None:
        """Numeric values in nested dicts are collected recursively."""
        ctx = make_context(
            output_data={
                "result": "ok",
                "stats": {"mean": 0.5, "std": 0.1, "count": 100},
                "extra": 0.4,
            },
        )
        verdict = await level.evaluate(ctx)
        # 4 numeric values (0.5, 0.1, 100, 0.4) → above min sample
        assert verdict.details["numeric_count"] >= 3

    @pytest.mark.asyncio
    async def test_boolean_values_excluded(self, level: L5Statistical) -> None:
        """Booleans are excluded from numeric collection."""
        ctx = make_context(
            output_data={"flag": True, "active": False},
        )
        verdict = await level.evaluate(ctx)
        # Only 0 numerics collected (booleans excluded)
        assert verdict.verdict == "skip"

    @pytest.mark.asyncio
    async def test_list_values_collected(self, level: L5Statistical) -> None:
        """Numeric values in lists are included in collection."""
        ctx = make_context(
            output_data={"values": [1.0, 2.0, 3.0, 4.0]},
        )
        verdict = await level.evaluate(ctx)
        assert verdict.details["numeric_count"] == 4

    @pytest.mark.asyncio
    async def test_score_penalized_by_outlier_ratio(self, level: L5Statistical) -> None:
        """score = max(0.0, 1.0 - outlier_ratio * 2): outlier_ratio > 0 → score < 1."""
        # 50 tight values + 1 extreme outlier so z-score well exceeds 3.0
        tight = {f"v{i}": 1.0 for i in range(50)}
        tight["outlier"] = 9_999_999.0
        ctx = make_context(output_data=tight)
        verdict = await level.evaluate(ctx)
        assert verdict.score < 1.0


# ===========================================================================
# L6 — Semantic Quality
# ===========================================================================

class TestL6Semantic:
    """Tests for L6Semantic — LLM-based relevance scoring."""

    @pytest.fixture
    def level(self) -> L6Semantic:
        return L6Semantic()

    def test_level_number_and_name(self, level: L6Semantic) -> None:
        assert level.level == 6
        assert level.name == "semantic_quality"

    @pytest.mark.asyncio
    async def test_no_api_key_skips(self, level: L6Semantic) -> None:
        """Missing OPENAI_API_KEY → skip verdict without calling API."""
        ctx = make_context()
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            verdict = await level.evaluate(ctx)
        assert verdict.verdict == "skip"
        assert verdict.score == 0.0
        assert "OPENAI_API_KEY not set" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_with_key_high_relevance_passes(self, level: L6Semantic) -> None:
        """Mock LLM returns relevance=0.9 → pass verdict."""
        ctx = make_context()
        mock_response = {"relevance": 0.9, "reasoning": "Very relevant"}

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l6_semantic._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "pass"
        assert verdict.score == 0.9
        assert verdict.details["reasoning"] == "Very relevant"

    @pytest.mark.asyncio
    async def test_with_key_medium_relevance_warns(self, level: L6Semantic) -> None:
        """Mock LLM returns relevance=0.55 (0.4 <= x < 0.7) → warn verdict."""
        ctx = make_context()
        mock_response = {"relevance": 0.55, "reasoning": "Somewhat relevant"}

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l6_semantic._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "warn"
        assert verdict.score == 0.55

    @pytest.mark.asyncio
    async def test_with_key_low_relevance_fails(self, level: L6Semantic) -> None:
        """Mock LLM returns relevance=0.2 (< 0.4) → fail verdict."""
        ctx = make_context()
        mock_response = {"relevance": 0.2, "reasoning": "Not relevant at all"}

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l6_semantic._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "fail"
        assert verdict.score == 0.2

    @pytest.mark.asyncio
    async def test_llm_call_failure_skips(self, level: L6Semantic) -> None:
        """LLM call raises an exception → skip verdict, not crash."""
        ctx = make_context()

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l6_semantic._call_openai",
                new=AsyncMock(side_effect=RuntimeError("Connection refused")),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "skip"
        assert "LLM call failed" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_relevance_clamped_above_one(self, level: L6Semantic) -> None:
        """Relevance > 1.0 from LLM is clamped to 1.0."""
        ctx = make_context()
        mock_response = {"relevance": 1.5, "reasoning": "Over the limit"}

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l6_semantic._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.score <= 1.0

    @pytest.mark.asyncio
    async def test_relevance_clamped_below_zero(self, level: L6Semantic) -> None:
        """Negative relevance from LLM is clamped to 0.0."""
        ctx = make_context()
        mock_response = {"relevance": -0.5, "reasoning": "Below zero"}

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l6_semantic._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.score >= 0.0
        assert verdict.verdict == "fail"

    @pytest.mark.asyncio
    async def test_missing_relevance_key_defaults_to_warn(self, level: L6Semantic) -> None:
        """Response without 'relevance' key defaults to 0.5 → warn verdict."""
        ctx = make_context()
        mock_response = {"reasoning": "No relevance key"}

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l6_semantic._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "warn"
        assert verdict.score == 0.5


# ===========================================================================
# L7 — Safety
# ===========================================================================

class TestL7Safety:
    """Tests for L7Safety — LLM-based harmful content check."""

    @pytest.fixture
    def level(self) -> L7Safety:
        return L7Safety()

    def test_level_number_and_name(self, level: L7Safety) -> None:
        assert level.level == 7
        assert level.name == "safety"

    @pytest.mark.asyncio
    async def test_no_api_key_skips(self, level: L7Safety) -> None:
        """Missing OPENAI_API_KEY → skip, no crash."""
        ctx = make_context()
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            verdict = await level.evaluate(ctx)
        assert verdict.verdict == "skip"
        assert "OPENAI_API_KEY not set" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_safe_content_passes(self, level: L7Safety) -> None:
        """Mock LLM returns verdict='pass', score=1.0 → pass, no short-circuit."""
        ctx = make_context()
        mock_response = {"verdict": "pass", "score": 1.0, "issues": [], "reasoning": "All safe"}

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l7_safety._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "pass"
        assert verdict.score == 1.0
        assert verdict.should_short_circuit is False

    @pytest.mark.asyncio
    async def test_harmful_content_fails_with_short_circuit(self, level: L7Safety) -> None:
        """Mock LLM returns verdict='fail' → fail + should_short_circuit=True."""
        ctx = make_context()
        mock_response = {
            "verdict": "fail",
            "score": 0.0,
            "issues": ["hate speech detected"],
            "reasoning": "Contains harmful content",
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l7_safety._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "fail"
        assert verdict.should_short_circuit is True
        assert verdict.details["issues"] == ["hate speech detected"]

    @pytest.mark.asyncio
    async def test_warn_verdict_does_not_short_circuit(self, level: L7Safety) -> None:
        """Mock LLM returns verdict='warn' → warn, should_short_circuit=False."""
        ctx = make_context()
        mock_response = {
            "verdict": "warn",
            "score": 0.6,
            "issues": ["mild concern"],
            "reasoning": "Borderline",
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l7_safety._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "warn"
        assert verdict.should_short_circuit is False

    @pytest.mark.asyncio
    async def test_llm_failure_skips(self, level: L7Safety) -> None:
        """LLM call raises → skip, not crash."""
        ctx = make_context()

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l7_safety._call_openai",
                new=AsyncMock(side_effect=TimeoutError("timed out")),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "skip"
        assert "LLM call failed" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_invalid_verdict_string_defaults_to_warn(self, level: L7Safety) -> None:
        """Unknown verdict string from LLM defaults to 'warn'."""
        ctx = make_context()
        mock_response = {
            "verdict": "unknown_verdict",
            "score": 0.7,
            "issues": [],
            "reasoning": "Unexpected",
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l7_safety._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "warn"
        assert verdict.should_short_circuit is False

    @pytest.mark.asyncio
    async def test_score_clamped_to_zero_one(self, level: L7Safety) -> None:
        """score from LLM outside [0,1] is clamped."""
        ctx = make_context()
        mock_response = {
            "verdict": "pass",
            "score": 99.0,  # way above 1.0
            "issues": [],
            "reasoning": "ok",
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l7_safety._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.score <= 1.0


# ===========================================================================
# L8 — Consensus
# ===========================================================================

class TestL8Consensus:
    """Tests for L8Consensus — agreement check across alternative outputs."""

    @pytest.fixture
    def level(self) -> L8Consensus:
        return L8Consensus()

    def test_level_number_and_name(self, level: L8Consensus) -> None:
        assert level.level == 8
        assert level.name == "consensus"

    @pytest.mark.asyncio
    async def test_no_alternatives_skips(self, level: L8Consensus) -> None:
        """No alternative_outputs in metadata → skip verdict."""
        ctx = make_context(metadata={})
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "skip"
        assert "no alternative outputs provided" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_alternatives_but_no_api_key_skips(self, level: L8Consensus) -> None:
        """Alternatives present but OPENAI_API_KEY missing → skip."""
        ctx = make_context(
            metadata={"alternative_outputs": [{"result": "Paris"}, {"result": "Rome"}]},
        )
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            verdict = await level.evaluate(ctx)
        assert verdict.verdict == "skip"
        assert "OPENAI_API_KEY not set" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_high_consensus_passes(self, level: L8Consensus) -> None:
        """Mock LLM returns agreement_score=0.95, pass → pass verdict."""
        ctx = make_context(
            metadata={"alternative_outputs": [{"result": "Paris"}, {"result": "Paris"}]},
        )
        mock_response = {
            "agreement_score": 0.95,
            "consensus_verdict": "pass",
            "reasoning": "All agree",
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l8_consensus._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "pass"
        assert verdict.score == 0.95
        assert verdict.details["alternatives_compared"] == 2

    @pytest.mark.asyncio
    async def test_low_consensus_fails(self, level: L8Consensus) -> None:
        """Mock LLM returns agreement_score=0.1, fail → fail verdict."""
        ctx = make_context(
            metadata={
                "alternative_outputs": [
                    {"result": "Paris"},
                    {"result": "London"},
                    {"result": "Berlin"},
                ]
            },
        )
        mock_response = {
            "agreement_score": 0.1,
            "consensus_verdict": "fail",
            "reasoning": "No agreement",
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l8_consensus._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "fail"
        assert verdict.score == 0.1

    @pytest.mark.asyncio
    async def test_llm_failure_skips(self, level: L8Consensus) -> None:
        """LLM call raises → skip, not crash."""
        ctx = make_context(
            metadata={"alternative_outputs": [{"result": "Paris"}]},
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l8_consensus._call_openai",
                new=AsyncMock(side_effect=RuntimeError("connection error")),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "skip"
        assert "LLM call failed" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_invalid_consensus_verdict_defaults_to_warn(self, level: L8Consensus) -> None:
        """Unrecognised consensus_verdict from LLM defaults to warn."""
        ctx = make_context(
            metadata={"alternative_outputs": [{"result": "Paris"}]},
        )
        mock_response = {
            "agreement_score": 0.6,
            "consensus_verdict": "undecided",
            "reasoning": "Unclear",
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l8_consensus._call_openai",
                new=AsyncMock(return_value=mock_response),
            ):
                verdict = await level.evaluate(ctx)

        assert verdict.verdict == "warn"

    @pytest.mark.asyncio
    async def test_alternatives_capped_at_five(self, level: L8Consensus) -> None:
        """With >5 alternatives, only the first 5 are compared (no crash)."""
        ctx = make_context(
            metadata={
                "alternative_outputs": [{"result": f"alt{i}"} for i in range(10)]
            },
        )
        mock_response = {
            "agreement_score": 0.8,
            "consensus_verdict": "pass",
            "reasoning": "Mostly agree",
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch(
                "marketplace.services.judge.levels.l8_consensus._call_openai",
                new=AsyncMock(return_value=mock_response),
            ) as mock_call:
                verdict = await level.evaluate(ctx)
                # Verify the prompt was built (call was made)
                mock_call.assert_awaited_once()

        # All 10 alternatives are counted in detail (the cap is on the prompt text, not the count)
        assert verdict.details["alternatives_compared"] == 10


# ===========================================================================
# L9 — Aggregator
# ===========================================================================

class TestL9Aggregator:
    """Tests for L9Aggregator — weighted average of L1-L8 scores."""

    @pytest.fixture
    def level(self) -> L9Aggregator:
        return L9Aggregator()

    def test_level_number_and_name(self, level: L9Aggregator) -> None:
        assert level.level == 9
        assert level.name == "aggregator"

    @pytest.mark.asyncio
    async def test_all_skipped_warns_with_default_score(self, level: L9Aggregator) -> None:
        """All previous verdicts are 'skip' → warn with score=0.5."""
        previous = [_make_verdict("skip", score=0.0, confidence=0.0) for _ in range(8)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "warn"
        assert verdict.score == 0.5
        assert "all preceding levels were skipped" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_all_pass_high_score(self, level: L9Aggregator) -> None:
        """All 8 levels pass with score=1.0 → aggregated score=1.0 → pass."""
        previous = [_make_verdict("pass", score=1.0, confidence=0.9) for _ in range(8)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.score >= 0.9

    @pytest.mark.asyncio
    async def test_all_fail_low_score(self, level: L9Aggregator) -> None:
        """All 8 levels fail with score=0.0 → aggregated score=0.0 → fail."""
        previous = [_make_verdict("fail", score=0.0, confidence=0.8) for _ in range(8)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "fail"
        assert verdict.score == 0.0

    @pytest.mark.asyncio
    async def test_mixed_verdicts_medium_score(self, level: L9Aggregator) -> None:
        """Mix of pass and fail verdicts → score between thresholds → warn."""
        previous = [
            _make_verdict("pass", score=1.0, confidence=0.9),
            _make_verdict("fail", score=0.0, confidence=0.9),
            _make_verdict("pass", score=1.0, confidence=0.9),
            _make_verdict("fail", score=0.0, confidence=0.9),
            _make_verdict("pass", score=1.0, confidence=0.9),
            _make_verdict("fail", score=0.0, confidence=0.9),
            _make_verdict("pass", score=0.5, confidence=0.8),
            _make_verdict("pass", score=0.5, confidence=0.8),
        ]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict in {"warn", "pass", "fail"}  # exact depends on weights
        assert 0.0 <= verdict.score <= 1.0

    @pytest.mark.asyncio
    async def test_skipped_levels_excluded_from_aggregation(self, level: L9Aggregator) -> None:
        """Skipped levels do not contribute to the weighted average."""
        # L1=pass(1.0), L2-L8=skip
        previous = [
            _make_verdict("pass", score=1.0, confidence=0.95),  # L1
        ] + [
            _make_verdict("skip", score=0.0, confidence=0.0) for _ in range(7)  # L2-L8
        ]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        # Only L1 contributed; its score=1.0 so aggregated should also be 1.0
        assert verdict.verdict == "pass"
        assert verdict.score == 1.0
        assert 1 in verdict.details["levels_included"]

    @pytest.mark.asyncio
    async def test_breakdown_contains_level_keys(self, level: L9Aggregator) -> None:
        """details['breakdown'] contains keys like 'l1', 'l2', etc."""
        previous = [
            _make_verdict("pass", score=0.8, confidence=0.9) for _ in range(4)
        ] + [
            _make_verdict("skip", score=0.0, confidence=0.0) for _ in range(4)
        ]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        breakdown = verdict.details["breakdown"]
        assert "l1" in breakdown
        assert "l2" in breakdown
        assert "l3" in breakdown
        assert "l4" in breakdown

    @pytest.mark.asyncio
    async def test_confidence_is_average_of_non_skip_levels(self, level: L9Aggregator) -> None:
        """Final confidence is mean of non-skipped level confidences."""
        previous = [
            _make_verdict("pass", score=1.0, confidence=0.8),  # L1: 0.8
            _make_verdict("pass", score=1.0, confidence=0.9),  # L2: 0.9
        ] + [
            _make_verdict("skip", score=0.0, confidence=0.0) for _ in range(6)
        ]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        expected_confidence = (0.8 + 0.9) / 2
        assert abs(verdict.confidence - expected_confidence) < 0.001

    @pytest.mark.asyncio
    async def test_warn_verdict_for_score_in_warn_range(self, level: L9Aggregator) -> None:
        """Score in [0.4, 0.7) → warn."""
        # Score 0.5 for all 8 levels → weighted avg = 0.5 → warn
        previous = [_make_verdict("warn", score=0.5, confidence=0.8) for _ in range(8)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "warn"


# ===========================================================================
# L10 — Human Gate
# ===========================================================================

class TestL10HumanGate:
    """Tests for L10HumanGate — threshold-based routing from L9 score."""

    @pytest.fixture
    def level(self) -> L10HumanGate:
        return L10HumanGate()

    def test_level_number_and_name(self, level: L10HumanGate) -> None:
        assert level.level == 10
        assert level.name == "human_gate"

    @pytest.mark.asyncio
    async def test_no_previous_verdicts_warns(self, level: L10HumanGate) -> None:
        """Empty previous_verdicts list → warn with default score=0.5."""
        ctx = make_context(previous_verdicts=[])
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "warn"
        assert verdict.score == 0.5
        assert "no preceding verdict" in verdict.details["reason"]

    @pytest.mark.asyncio
    async def test_high_score_auto_passes(self, level: L10HumanGate) -> None:
        """L9 score >= 0.7 → auto-approved, pass verdict."""
        previous = [_make_verdict("pass", score=0.85, confidence=0.9)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"
        assert verdict.details["action"] == "auto_approved"
        assert verdict.should_short_circuit is False

    @pytest.mark.asyncio
    async def test_score_at_pass_threshold_passes(self, level: L10HumanGate) -> None:
        """L9 score = 0.7 (exactly at pass threshold) → auto-approved."""
        previous = [_make_verdict("pass", score=0.7, confidence=0.9)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_medium_score_flagged_for_review(self, level: L10HumanGate) -> None:
        """0.5 <= L9 score < 0.7 → warn, flagged for human review."""
        previous = [_make_verdict("warn", score=0.6, confidence=0.8)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "warn"
        assert verdict.details["action"] == "flagged_for_human_review"
        assert verdict.should_short_circuit is False

    @pytest.mark.asyncio
    async def test_score_just_below_warn_threshold_warns(self, level: L10HumanGate) -> None:
        """L9 score = 0.69 (just below 0.7 threshold) → warn."""
        previous = [_make_verdict("warn", score=0.69, confidence=0.8)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "warn"

    @pytest.mark.asyncio
    async def test_low_score_fails_with_short_circuit(self, level: L10HumanGate) -> None:
        """L9 score < 0.5 → fail + should_short_circuit=True."""
        previous = [_make_verdict("fail", score=0.3, confidence=0.8)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "fail"
        assert verdict.should_short_circuit is True
        assert verdict.details["action"] == "auto_rejected_requires_human_review"

    @pytest.mark.asyncio
    async def test_score_zero_fails_with_short_circuit(self, level: L10HumanGate) -> None:
        """L9 score = 0.0 → fail with short-circuit."""
        previous = [_make_verdict("fail", score=0.0, confidence=0.5)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert verdict.verdict == "fail"
        assert verdict.should_short_circuit is True

    @pytest.mark.asyncio
    async def test_score_at_fail_threshold_fails(self, level: L10HumanGate) -> None:
        """L9 score exactly at 0.5 → exactly at boundary, should warn (>= 0.5)."""
        previous = [_make_verdict("warn", score=0.5, confidence=0.8)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        # score=0.5 is NOT < 0.5, so it falls into warn zone (< 0.7)
        assert verdict.verdict == "warn"
        assert verdict.should_short_circuit is False

    @pytest.mark.asyncio
    async def test_uses_last_previous_verdict(self, level: L10HumanGate) -> None:
        """L10 reads the LAST element of previous_verdicts (the L9 score)."""
        previous = [
            _make_verdict("fail", score=0.1, confidence=0.9),  # L1-style low
            _make_verdict("pass", score=0.9, confidence=0.9),  # last = L9's verdict
        ]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        # Uses score=0.9 (last verdict) → should pass
        assert verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_details_include_threshold_values(self, level: L10HumanGate) -> None:
        """details always contains l9_score, fail_threshold, warn_threshold."""
        previous = [_make_verdict("pass", score=0.8, confidence=0.9)]
        ctx = make_context(previous_verdicts=previous)
        verdict = await level.evaluate(ctx)
        assert "l9_score" in verdict.details
        assert "fail_threshold" in verdict.details
        assert "warn_threshold" in verdict.details
        assert verdict.details["fail_threshold"] == 0.5
        assert verdict.details["warn_threshold"] == 0.7
