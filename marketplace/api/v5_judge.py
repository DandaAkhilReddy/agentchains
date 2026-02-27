"""Judge pipeline API — evaluate, list, and override pipeline runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.models.judge import JudgePipelineRun
from marketplace.schemas.judge import (
    HumanOverrideRequest,
    JudgePipelineResponse,
    JudgeRequest,
    JudgeRunListResponse,
    JudgeRunSummary,
    LevelVerdictResponse,
)
from marketplace.services.judge_pipeline import run_judge_pipeline

router = APIRouter(prefix="/judge", tags=["judge"])


def _run_to_summary(run: JudgePipelineRun) -> JudgeRunSummary:
    """Serialise a :class:`JudgePipelineRun` ORM row to a summary schema.

    Args:
        run: SQLAlchemy ORM instance.

    Returns:
        :class:`JudgeRunSummary` ready to serialise.
    """
    return JudgeRunSummary(
        run_id=run.id,
        target_type=run.target_type,
        target_id=run.target_id,
        final_verdict=run.final_verdict,
        final_score=float(run.final_score),
        final_confidence=float(run.final_confidence),
        levels_completed=run.levels_completed,
        human_override=run.human_override,
        created_at=run.created_at.isoformat() if run.created_at else "",
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )


@router.post("/evaluate", status_code=201, response_model=JudgePipelineResponse)
async def evaluate(
    req: JudgeRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> JudgePipelineResponse:
    """Trigger a new judge pipeline evaluation.

    Runs all 10 judge levels in sequence (unless skip_levels is provided) and
    persists the result.  Requires agent authentication.

    Args:
        req: Evaluation request with input/output data and options.
        db: Database session (injected).
        agent_id: Authenticated agent identifier (injected).

    Returns:
        Full pipeline result including per-level verdicts.
    """
    result = await run_judge_pipeline(
        db,
        target_type=req.target_type,
        target_id=req.target_id,
        input_data=req.input_data,
        output_data=req.output_data,
        metadata=req.metadata,
        skip_levels=set(req.skip_levels) if req.skip_levels else None,
    )
    verdicts = [
        LevelVerdictResponse(
            level=v["level"],
            name=v["name"],
            verdict=v["verdict"],
            score=v["score"],
            confidence=v["confidence"],
            details=v.get("details", {}),
            duration_ms=v.get("duration_ms", 0),
        )
        for v in result.verdicts
    ]
    return JudgePipelineResponse(
        run_id=result.run_id,
        final_verdict=result.final_verdict,
        final_score=result.final_score,
        final_confidence=result.final_confidence,
        levels_completed=result.levels_completed,
        verdicts=verdicts,
    )


@router.get("/evaluations/{run_id}", response_model=JudgePipelineResponse)
async def get_evaluation(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> JudgePipelineResponse:
    """Retrieve a pipeline run result by its ID.

    Args:
        run_id: UUID of the pipeline run.
        db: Database session (injected).

    Returns:
        Full pipeline result including per-level verdicts.

    Raises:
        HTTPException: 404 if the run does not exist.
    """
    run: JudgePipelineRun | None = await db.get(JudgePipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Judge pipeline run not found")

    # Parse the stored breakdown JSON back into verdict dicts.
    breakdown: list[dict] = json.loads(run.breakdown_json or "[]")
    verdicts = [
        LevelVerdictResponse(
            level=v["level"],
            name=v["name"],
            verdict=v["verdict"],
            score=v["score"],
            confidence=v["confidence"],
            details=v.get("details", {}),
            duration_ms=v.get("duration_ms", 0),
        )
        for v in breakdown
    ]
    return JudgePipelineResponse(
        run_id=run.id,
        final_verdict=run.final_verdict,
        final_score=float(run.final_score),
        final_confidence=float(run.final_confidence),
        levels_completed=run.levels_completed,
        verdicts=verdicts,
    )


@router.get("/evaluations", response_model=JudgeRunListResponse)
async def list_evaluations(
    target_type: str | None = None,
    verdict: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> JudgeRunListResponse:
    """List pipeline runs with optional filters and pagination.

    Args:
        target_type: Filter by artifact category (e.g. "agent_output").
        verdict: Filter by final verdict (e.g. "pass", "fail", "warn").
        page: 1-indexed page number.
        page_size: Items per page (max 100).
        db: Database session (injected).

    Returns:
        Paginated list of pipeline run summaries.
    """
    base_q = select(JudgePipelineRun)
    if target_type:
        base_q = base_q.where(JudgePipelineRun.target_type == target_type)
    if verdict:
        base_q = base_q.where(JudgePipelineRun.final_verdict == verdict)

    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total: int = total_result.scalar() or 0

    offset = (page - 1) * page_size
    paged_q = (
        base_q.order_by(JudgePipelineRun.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = await db.execute(paged_q)
    runs: list[JudgePipelineRun] = list(rows.scalars().all())

    return JudgeRunListResponse(
        items=[_run_to_summary(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/evaluations/{run_id}/human-override", response_model=JudgeRunSummary)
async def apply_human_override(
    run_id: str,
    req: HumanOverrideRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> JudgeRunSummary:
    """Apply a human override (approve/reject) to an existing pipeline run.

    This endpoint implements the L10 human review workflow.  The override is
    recorded on the pipeline run row without re-running any judge levels.
    Requires agent authentication.

    Args:
        run_id: UUID of the pipeline run to override.
        req: Override decision and reason.
        db: Database session (injected).
        agent_id: Authenticated agent identifier acting as reviewer (injected).

    Returns:
        Updated pipeline run summary reflecting the override.

    Raises:
        HTTPException: 404 if the run does not exist.
        HTTPException: 409 if a human override has already been applied.
    """
    run: JudgePipelineRun | None = await db.get(JudgePipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Judge pipeline run not found")
    if run.human_override is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A human override ({run.human_override!r}) has already been applied to this run",
        )

    run.human_override = req.decision
    run.human_override_by = agent_id
    run.human_override_at = datetime.now(timezone.utc)
    run.human_override_reason = req.reason

    await db.commit()
    await db.refresh(run)

    return _run_to_summary(run)
