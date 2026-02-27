"""Integration tests for the full judge pipeline (run_judge_pipeline).

Tests verify:
- A full pipeline run creates JudgePipelineRun + JudgeEvaluation rows in the DB.
- skip_levels causes those levels to receive a 'skip' verdict.
- Bad data triggers early-level failures (or skips) without crashing.
- Results are correctly persisted and can be queried back.
- JudgePipelineResult dataclass has all expected fields.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.judge import JudgeEvaluation, JudgePipelineRun
from marketplace.services.judge_pipeline import JudgePipelineResult, run_judge_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_INPUT: dict[str, Any] = {"query": "What is the capital of France?"}
_VALID_OUTPUT: dict[str, Any] = {"result": "Paris", "status": "ok"}


async def _run_pipeline(
    db: AsyncSession,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    skip_levels: set[int] | None = None,
    target_id: str = "target-001",
) -> JudgePipelineResult:
    """Convenience wrapper around run_judge_pipeline with sensible defaults."""
    return await run_judge_pipeline(
        db,
        target_type="agent_output",
        target_id=target_id,
        input_data=input_data if input_data is not None else _VALID_INPUT,
        output_data=output_data if output_data is not None else _VALID_OUTPUT,
        metadata=metadata,
        skip_levels=skip_levels,
    )


# ===========================================================================
# JudgePipelineResult dataclass shape
# ===========================================================================

class TestJudgePipelineResultDataclass:
    """Verify the dataclass fields and types returned by run_judge_pipeline."""

    @pytest.mark.asyncio
    async def test_result_has_all_required_fields(self, db: AsyncSession) -> None:
        """run_judge_pipeline returns a JudgePipelineResult with all documented fields."""
        result = await _run_pipeline(db)

        assert isinstance(result, JudgePipelineResult)
        assert isinstance(result.run_id, str)
        assert isinstance(result.final_verdict, str)
        assert isinstance(result.final_score, float)
        assert isinstance(result.final_confidence, float)
        assert isinstance(result.levels_completed, int)
        assert isinstance(result.verdicts, list)

    @pytest.mark.asyncio
    async def test_run_id_is_non_empty_string(self, db: AsyncSession) -> None:
        """run_id must be a non-empty string (UUID from JudgePipelineRun)."""
        result = await _run_pipeline(db)
        assert len(result.run_id) > 0

    @pytest.mark.asyncio
    async def test_final_verdict_is_valid_string(self, db: AsyncSession) -> None:
        """final_verdict is one of: pass, fail, warn, skip, pending."""
        result = await _run_pipeline(db)
        assert result.final_verdict in {"pass", "fail", "warn", "skip", "pending"}

    @pytest.mark.asyncio
    async def test_scores_in_unit_range(self, db: AsyncSession) -> None:
        """final_score and final_confidence are in [0.0, 1.0]."""
        result = await _run_pipeline(db)
        assert 0.0 <= result.final_score <= 1.0
        assert 0.0 <= result.final_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_verdicts_list_contains_level_entries(self, db: AsyncSession) -> None:
        """verdicts list contains dicts with level, name, verdict, score, confidence, details."""
        result = await _run_pipeline(db)
        assert len(result.verdicts) > 0

        first = result.verdicts[0]
        assert "level" in first
        assert "name" in first
        assert "verdict" in first
        assert "score" in first
        assert "confidence" in first
        assert "details" in first
        assert "duration_ms" in first

    @pytest.mark.asyncio
    async def test_levels_completed_matches_verdict_count(self, db: AsyncSession) -> None:
        """levels_completed equals the length of the verdicts list."""
        result = await _run_pipeline(db)
        assert result.levels_completed == len(result.verdicts)


# ===========================================================================
# Database persistence
# ===========================================================================

class TestPipelinePersistence:
    """Verify pipeline results are persisted in JudgePipelineRun and JudgeEvaluation."""

    @pytest.mark.asyncio
    async def test_creates_pipeline_run_row(self, db: AsyncSession) -> None:
        """run_judge_pipeline creates one JudgePipelineRun row."""
        result = await _run_pipeline(db)

        run = await db.get(JudgePipelineRun, result.run_id)
        assert run is not None
        assert run.id == result.run_id

    @pytest.mark.asyncio
    async def test_pipeline_run_fields_persisted(self, db: AsyncSession) -> None:
        """JudgePipelineRun row has correct target_type, target_id, final_verdict."""
        result = await _run_pipeline(db, target_id="persist-target-01")

        run = await db.get(JudgePipelineRun, result.run_id)
        assert run is not None
        assert run.target_type == "agent_output"
        assert run.target_id == "persist-target-01"
        assert run.final_verdict == result.final_verdict
        assert float(run.final_score) == result.final_score
        assert run.levels_completed == result.levels_completed
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_creates_evaluation_rows_per_level(self, db: AsyncSession) -> None:
        """One JudgeEvaluation row is created for each level that runs."""
        result = await _run_pipeline(db)

        rows = await db.execute(
            select(JudgeEvaluation).where(JudgeEvaluation.run_id == result.run_id)
        )
        evals = list(rows.scalars().all())
        assert len(evals) == result.levels_completed

    @pytest.mark.asyncio
    async def test_evaluation_rows_have_correct_level_numbers(self, db: AsyncSession) -> None:
        """JudgeEvaluation rows have sequential level numbers starting at 1."""
        result = await _run_pipeline(db)

        rows = await db.execute(
            select(JudgeEvaluation)
            .where(JudgeEvaluation.run_id == result.run_id)
            .order_by(JudgeEvaluation.level)
        )
        evals = list(rows.scalars().all())
        levels = [e.level for e in evals]
        assert levels == list(range(1, result.levels_completed + 1))

    @pytest.mark.asyncio
    async def test_evaluation_verdicts_match_result_verdicts(self, db: AsyncSession) -> None:
        """JudgeEvaluation.verdict matches the corresponding entry in result.verdicts."""
        result = await _run_pipeline(db)

        rows = await db.execute(
            select(JudgeEvaluation)
            .where(JudgeEvaluation.run_id == result.run_id)
            .order_by(JudgeEvaluation.level)
        )
        evals = list(rows.scalars().all())

        for eval_row, result_verdict in zip(evals, result.verdicts):
            assert eval_row.verdict == result_verdict["verdict"]
            assert eval_row.level == result_verdict["level"]

    @pytest.mark.asyncio
    async def test_evaluation_details_json_valid(self, db: AsyncSession) -> None:
        """JudgeEvaluation.details_json can be parsed as JSON."""
        result = await _run_pipeline(db)

        rows = await db.execute(
            select(JudgeEvaluation).where(JudgeEvaluation.run_id == result.run_id)
        )
        evals = list(rows.scalars().all())

        for eval_row in evals:
            parsed = json.loads(eval_row.details_json)
            assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_breakdown_json_parseable(self, db: AsyncSession) -> None:
        """JudgePipelineRun.breakdown_json can be parsed as a list of dicts."""
        result = await _run_pipeline(db)

        run = await db.get(JudgePipelineRun, result.run_id)
        assert run is not None
        breakdown = json.loads(run.breakdown_json or "[]")
        assert isinstance(breakdown, list)
        assert len(breakdown) == result.levels_completed

    @pytest.mark.asyncio
    async def test_multiple_runs_create_separate_rows(self, db: AsyncSession) -> None:
        """Two successive pipeline runs create two independent JudgePipelineRun rows."""
        result1 = await _run_pipeline(db, target_id="multi-target-01")
        result2 = await _run_pipeline(db, target_id="multi-target-02")

        assert result1.run_id != result2.run_id

        run1 = await db.get(JudgePipelineRun, result1.run_id)
        run2 = await db.get(JudgePipelineRun, result2.run_id)
        assert run1 is not None
        assert run2 is not None
        assert run1.target_id == "multi-target-01"
        assert run2.target_id == "multi-target-02"


# ===========================================================================
# skip_levels behaviour
# ===========================================================================

class TestSkipLevels:
    """Verify that skip_levels causes automatic 'skip' verdicts."""

    @pytest.mark.asyncio
    async def test_skip_single_level(self, db: AsyncSession) -> None:
        """Skipping L1 → first verdict in result has verdict='skip'."""
        result = await _run_pipeline(db, skip_levels={1})

        assert result.verdicts[0]["level"] == 1
        assert result.verdicts[0]["verdict"] == "skip"
        assert result.verdicts[0]["details"]["reason"] == "skipped_by_request"

    @pytest.mark.asyncio
    async def test_skip_multiple_levels(self, db: AsyncSession) -> None:
        """Skipping {1, 2, 3} → first three verdicts are all 'skip'."""
        result = await _run_pipeline(db, skip_levels={1, 2, 3})

        for i in range(3):
            assert result.verdicts[i]["verdict"] == "skip"
            assert result.verdicts[i]["details"]["reason"] == "skipped_by_request"

    @pytest.mark.asyncio
    async def test_skipped_level_has_zero_score_and_confidence(self, db: AsyncSession) -> None:
        """Skipped levels get score=0.0 and confidence=0.0."""
        result = await _run_pipeline(db, skip_levels={2})

        l2_entry = next(v for v in result.verdicts if v["level"] == 2)
        assert l2_entry["score"] == 0.0
        assert l2_entry["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_skip_all_levels_except_l10(self, db: AsyncSession) -> None:
        """Skipping L1-L9 → L10 sees 9 skip verdicts with score=0.0.

        L10 reads the last previous_verdict (L9 skip, score=0.0 < 0.5 fail threshold)
        and returns fail with should_short_circuit=True.
        """
        result = await _run_pipeline(db, skip_levels={1, 2, 3, 4, 5, 6, 7, 8, 9})

        # All first 9 verdicts should be skip
        for i in range(9):
            assert result.verdicts[i]["verdict"] == "skip"

        # L10 runs; L9 skip had score=0.0 → L10 returns fail (below 0.5 threshold)
        l10_entry = next(v for v in result.verdicts if v["level"] == 10)
        assert l10_entry["verdict"] == "fail"
        assert result.final_verdict == "fail"

    @pytest.mark.asyncio
    async def test_skip_non_existent_level_no_effect(self, db: AsyncSession) -> None:
        """Skipping a level number not in 1-10 has no effect on results."""
        result_without_skip = await _run_pipeline(db)
        result_with_fake_skip = await _run_pipeline(db, skip_levels={99})

        # Both should run all 10 levels
        assert result_without_skip.levels_completed == result_with_fake_skip.levels_completed

    @pytest.mark.asyncio
    async def test_db_rows_for_skipped_levels_have_skip_verdict(self, db: AsyncSession) -> None:
        """JudgeEvaluation rows for skipped levels have verdict='skip' in DB."""
        result = await _run_pipeline(db, skip_levels={1, 3})

        rows = await db.execute(
            select(JudgeEvaluation)
            .where(JudgeEvaluation.run_id == result.run_id)
            .where(JudgeEvaluation.level.in_([1, 3]))
        )
        evals = list(rows.scalars().all())
        assert len(evals) == 2
        for e in evals:
            assert e.verdict == "skip"


# ===========================================================================
# Bad data / error paths
# ===========================================================================

class TestBadDataHandling:
    """Verify the pipeline handles malformed or incomplete data gracefully."""

    @pytest.mark.asyncio
    async def test_empty_input_output_completes_without_crash(self, db: AsyncSession) -> None:
        """Empty input/output dicts → pipeline runs to completion without raising."""
        result = await _run_pipeline(db, input_data={}, output_data={})

        assert isinstance(result, JudgePipelineResult)
        assert result.levels_completed >= 1

    @pytest.mark.asyncio
    async def test_missing_required_fields_causes_schema_failure(self, db: AsyncSession) -> None:
        """Missing required fields in output → L1 schema verdict is warn or fail."""
        result = await _run_pipeline(db, output_data={"extra": "value"})

        l1_entry = next((v for v in result.verdicts if v["level"] == 1), None)
        assert l1_entry is not None
        assert l1_entry["verdict"] in {"warn", "fail"}

    @pytest.mark.asyncio
    async def test_null_fields_cause_data_quality_failure(self, db: AsyncSession) -> None:
        """Null required fields → L2 data quality verdict is warn or fail."""
        result = await _run_pipeline(
            db,
            input_data={"query": "q"},
            output_data={"result": None, "status": None},
        )

        l2_entry = next((v for v in result.verdicts if v["level"] == 2), None)
        assert l2_entry is not None
        assert l2_entry["verdict"] in {"warn", "fail"}

    @pytest.mark.asyncio
    async def test_exception_in_level_recorded_as_skip(self, db: AsyncSession) -> None:
        """If a level raises an exception, it is recorded as skip with error detail."""
        from marketplace.services.judge.base import JudgeContext, LevelVerdict
        from marketplace.services.judge_pipeline import ALL_LEVELS

        # Patch L3 to raise
        original_evaluate = ALL_LEVELS[2].evaluate

        async def bad_evaluate(ctx: JudgeContext) -> LevelVerdict:
            raise RuntimeError("simulated level crash")

        ALL_LEVELS[2].evaluate = bad_evaluate
        try:
            result = await _run_pipeline(db)
        finally:
            ALL_LEVELS[2].evaluate = original_evaluate

        l3_entry = next((v for v in result.verdicts if v["level"] == 3), None)
        assert l3_entry is not None
        assert l3_entry["verdict"] == "skip"
        assert "error" in l3_entry["details"]

    @pytest.mark.asyncio
    async def test_safety_fail_short_circuits_pipeline(self, db: AsyncSession) -> None:
        """A should_short_circuit=True verdict stops the pipeline at that level."""
        from marketplace.services.judge.base import JudgeContext, LevelVerdict
        from marketplace.services.judge_pipeline import ALL_LEVELS

        # Force L7 (index 6) to return a short-circuit fail
        original_evaluate = ALL_LEVELS[6].evaluate

        async def short_circuit_evaluate(ctx: JudgeContext) -> LevelVerdict:
            return LevelVerdict(
                verdict="fail",
                score=0.0,
                confidence=0.9,
                details={"reason": "forced short-circuit"},
                should_short_circuit=True,
            )

        ALL_LEVELS[6].evaluate = short_circuit_evaluate
        try:
            result = await _run_pipeline(db)
        finally:
            ALL_LEVELS[6].evaluate = original_evaluate

        # Pipeline should have stopped at L7 (level 7 is index 6, level number 7)
        assert result.levels_completed == 7
        assert result.final_verdict == "fail"

    @pytest.mark.asyncio
    async def test_no_metadata_runs_full_pipeline(self, db: AsyncSession) -> None:
        """None metadata falls back to empty dict, pipeline still runs all levels."""
        result = await _run_pipeline(db, metadata=None)
        # L4/L5/L8 skip because no relevant metadata, but pipeline completes
        assert result.levels_completed == 10

    @pytest.mark.asyncio
    async def test_none_skip_levels_runs_all_levels(self, db: AsyncSession) -> None:
        """skip_levels=None defaults to no skips → all 10 levels run."""
        result = await _run_pipeline(db, skip_levels=None)
        assert result.levels_completed == 10

    @pytest.mark.asyncio
    async def test_large_metadata_does_not_crash(self, db: AsyncSession) -> None:
        """Very large metadata dict is handled without error."""
        big_metadata: dict[str, Any] = {f"key_{i}": f"value_{i}" for i in range(1000)}
        result = await _run_pipeline(db, metadata=big_metadata)
        assert isinstance(result, JudgePipelineResult)


# ===========================================================================
# Verdict ordering and pipeline integrity
# ===========================================================================

class TestPipelineOrdering:
    """Verify levels run in correct order and context propagation works."""

    @pytest.mark.asyncio
    async def test_verdicts_ordered_l1_to_l10(self, db: AsyncSession) -> None:
        """Verdicts in result are ordered L1 → L10 (no gaps, ascending)."""
        result = await _run_pipeline(db)

        levels = [v["level"] for v in result.verdicts]
        assert levels == list(range(1, result.levels_completed + 1))

    @pytest.mark.asyncio
    async def test_each_verdict_has_level_name(self, db: AsyncSession) -> None:
        """Each verdict entry contains a non-empty 'name' string."""
        result = await _run_pipeline(db)

        for v in result.verdicts:
            assert isinstance(v["name"], str)
            assert len(v["name"]) > 0

    @pytest.mark.asyncio
    async def test_duration_ms_non_negative(self, db: AsyncSession) -> None:
        """duration_ms for each level is >= 0."""
        result = await _run_pipeline(db)

        for v in result.verdicts:
            assert v["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_final_verdict_matches_last_run_level(self, db: AsyncSession) -> None:
        """final_verdict in result equals the verdict of the last completed level."""
        result = await _run_pipeline(db)
        last_level_verdict = result.verdicts[-1]["verdict"]
        assert result.final_verdict == last_level_verdict

    @pytest.mark.asyncio
    async def test_final_score_matches_last_run_level_score(self, db: AsyncSession) -> None:
        """final_score equals the score of the last completed level."""
        result = await _run_pipeline(db)
        last_level_score = result.verdicts[-1]["score"]
        assert abs(result.final_score - last_level_score) < 0.001
