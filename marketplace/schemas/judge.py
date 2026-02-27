"""Pydantic schemas for the judge pipeline API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JudgeRequest(BaseModel):
    """Request body for triggering a judge pipeline evaluation.

    Attributes:
        target_type: Category of artifact being judged (e.g. "agent_output").
        target_id: Identifier of the artifact being judged.
        input_data: Input that was provided to the process under evaluation.
        output_data: Output produced by the process under evaluation.
        metadata: Optional extra context (latency_ms, alternative_outputs, etc.).
        skip_levels: Level numbers (1-10) to skip in this run.
    """

    target_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Category: agent_output, listing, transaction",
    )
    target_id: str = Field(..., min_length=1, max_length=36)
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    skip_levels: list[int] = Field(default_factory=list)


class LevelVerdictResponse(BaseModel):
    """Per-level verdict returned in a pipeline response.

    Attributes:
        level: Level number (1-10).
        name: Human-readable level name.
        verdict: "pass", "fail", "warn", or "skip".
        score: Quality score in [0.0, 1.0].
        confidence: Confidence in the verdict in [0.0, 1.0].
        details: Arbitrary key-value explanation of the verdict.
        duration_ms: Wall-clock time the level took in milliseconds.
    """

    level: int
    name: str
    verdict: str
    score: float
    confidence: float
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int


class JudgePipelineResponse(BaseModel):
    """Full pipeline result returned after evaluation.

    Attributes:
        run_id: UUID of the persisted pipeline run row.
        final_verdict: Aggregated verdict: "pass", "fail", "warn", or "pending".
        final_score: Aggregated quality score in [0.0, 1.0].
        final_confidence: Aggregated confidence in [0.0, 1.0].
        levels_completed: Number of levels that ran.
        verdicts: Ordered list of per-level verdict objects.
    """

    run_id: str
    final_verdict: str
    final_score: float
    final_confidence: float
    levels_completed: int
    verdicts: list[LevelVerdictResponse] = Field(default_factory=list)


class HumanOverrideRequest(BaseModel):
    """Request body for applying a human override to a pipeline run.

    Attributes:
        decision: Either "approved" or "rejected".
        reason: Explanation for the override decision.
    """

    decision: str = Field(..., pattern="^(approved|rejected)$")
    reason: str = Field(..., min_length=1, max_length=2000)


class JudgeRunSummary(BaseModel):
    """Summary of a single pipeline run for list responses.

    Attributes:
        run_id: UUID of the pipeline run row.
        target_type: Category of artifact judged.
        target_id: Identifier of artifact judged.
        final_verdict: Aggregated verdict.
        final_score: Aggregated quality score.
        final_confidence: Aggregated confidence.
        levels_completed: Number of levels that ran.
        human_override: Applied human override ("approved", "rejected", or None).
        created_at: ISO-8601 timestamp of run creation.
        completed_at: ISO-8601 timestamp of run completion (None if pending).
    """

    run_id: str
    target_type: str
    target_id: str
    final_verdict: str
    final_score: float
    final_confidence: float
    levels_completed: int
    human_override: str | None = None
    created_at: str
    completed_at: str | None = None


class JudgeRunListResponse(BaseModel):
    """Paginated list of judge pipeline runs.

    Attributes:
        items: List of run summaries for the current page.
        total: Total number of runs matching the query.
        page: Current page number (1-indexed).
        page_size: Number of items per page.
    """

    items: list[JudgeRunSummary]
    total: int
    page: int
    page_size: int
