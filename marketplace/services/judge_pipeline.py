"""Judge pipeline orchestrator — runs L1 through L10 sequentially."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.judge import JudgeEvaluation, JudgePipelineRun
from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict
from marketplace.services.judge.levels.l10_human_gate import L10HumanGate
from marketplace.services.judge.levels.l1_schema import L1SchemaValidation
from marketplace.services.judge.levels.l2_data_quality import L2DataQuality
from marketplace.services.judge.levels.l3_consistency import L3Consistency
from marketplace.services.judge.levels.l4_performance import L4Performance
from marketplace.services.judge.levels.l5_statistical import L5Statistical
from marketplace.services.judge.levels.l6_semantic import L6Semantic
from marketplace.services.judge.levels.l7_safety import L7Safety
from marketplace.services.judge.levels.l8_consensus import L8Consensus
from marketplace.services.judge.levels.l9_aggregator import L9Aggregator

logger = logging.getLogger(__name__)

# Ordered pipeline — must remain L1 → L10 for ctx.previous_verdicts indexing to work.
ALL_LEVELS: list[JudgeLevel] = [
    L1SchemaValidation(),
    L2DataQuality(),
    L3Consistency(),
    L4Performance(),
    L5Statistical(),
    L6Semantic(),
    L7Safety(),
    L8Consensus(),
    L9Aggregator(),
    L10HumanGate(),
]


@dataclass
class JudgePipelineResult:
    """Aggregated result returned by :func:`run_judge_pipeline`.

    Attributes:
        run_id: UUID of the persisted :class:`JudgePipelineRun` row.
        final_verdict: "pass", "fail", "warn", or "pending".
        final_score: Aggregated quality score in [0.0, 1.0].
        final_confidence: Aggregated confidence in [0.0, 1.0].
        levels_completed: Number of levels that ran (excluding short-circuit stop).
        verdicts: Per-level verdict dicts with score, confidence, details, duration_ms.
    """

    run_id: str
    final_verdict: str
    final_score: float
    final_confidence: float
    levels_completed: int
    verdicts: list[dict[str, Any]] = field(default_factory=list)


async def run_judge_pipeline(
    db: AsyncSession,
    target_type: str,
    target_id: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    skip_levels: set[int] | None = None,
) -> JudgePipelineResult:
    """Run the full 10-level judge pipeline and persist results.

    Levels run sequentially from L1 to L10.  If a level sets
    ``should_short_circuit=True`` on its :class:`~marketplace.services.judge.base.LevelVerdict`,
    the pipeline halts after recording that level.  Any level whose number is
    in ``skip_levels`` is automatically given a ``skip`` verdict without calling
    ``evaluate``.

    Args:
        db: Active async SQLAlchemy session.
        target_type: Category of artifact being judged (e.g. "agent_output").
        target_id: Identifier of the artifact being judged.
        input_data: Input that was sent to the process under evaluation.
        output_data: Output produced by the process under evaluation.
        metadata: Optional extra context (latency_ms, alternative_outputs, etc.).
        skip_levels: Set of level numbers (1–10) to skip automatically.

    Returns:
        :class:`JudgePipelineResult` with the aggregated verdict and per-level breakdown.
    """
    run = JudgePipelineRun(target_type=target_type, target_id=target_id)
    db.add(run)
    await db.flush()  # Obtain run.id before creating evaluations.

    ctx = JudgeContext(
        target_type=target_type,
        target_id=target_id,
        input_data=input_data,
        output_data=output_data,
        metadata=metadata or {},
    )

    skip: set[int] = skip_levels or set()
    verdicts: list[dict[str, Any]] = []
    duration_ms = 0

    for judge_level in ALL_LEVELS:
        if judge_level.level in skip:
            verdict = LevelVerdict(
                verdict="skip",
                score=0.0,
                confidence=0.0,
                details={"reason": "skipped_by_request"},
            )
            duration_ms = 0
        else:
            start = time.monotonic()
            try:
                verdict = await judge_level.evaluate(ctx)
            except Exception as exc:
                logger.error(
                    "Judge L%d (%s) raised an exception: %s",
                    judge_level.level,
                    judge_level.name,
                    exc,
                )
                verdict = LevelVerdict(
                    verdict="skip",
                    score=0.0,
                    confidence=0.0,
                    details={"error": str(exc)},
                )
            duration_ms = int((time.monotonic() - start) * 1000)

        evaluation = JudgeEvaluation(
            run_id=run.id,
            level=judge_level.level,
            level_name=judge_level.name,
            verdict=verdict.verdict,
            score=verdict.score,
            confidence=verdict.confidence,
            details_json=json.dumps(verdict.details),
            duration_ms=duration_ms,
        )
        db.add(evaluation)

        ctx.previous_verdicts.append(verdict)
        verdicts.append(
            {
                "level": judge_level.level,
                "name": judge_level.name,
                "verdict": verdict.verdict,
                "score": verdict.score,
                "confidence": verdict.confidence,
                "details": verdict.details,
                "duration_ms": duration_ms,
            }
        )

        if verdict.should_short_circuit:
            logger.info(
                "Judge pipeline short-circuited at L%d (%s) with verdict=%s",
                judge_level.level,
                judge_level.name,
                verdict.verdict,
            )
            break

    # Update the pipeline run row with aggregated results.
    last = verdicts[-1] if verdicts else {}
    run.final_verdict = last.get("verdict", "pending")
    run.final_score = last.get("score", 0.0)
    run.final_confidence = last.get("confidence", 0.0)
    run.levels_completed = len(verdicts)
    run.breakdown_json = json.dumps(verdicts)
    run.completed_at = datetime.now(timezone.utc)

    await db.commit()

    return JudgePipelineResult(
        run_id=run.id,
        final_verdict=run.final_verdict,
        final_score=float(run.final_score),
        final_confidence=float(run.final_confidence),
        levels_completed=run.levels_completed,
        verdicts=verdicts,
    )
