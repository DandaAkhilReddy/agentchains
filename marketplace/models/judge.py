"""Judge pipeline evaluation models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text

from marketplace.database import Base


def utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class JudgePipelineRun(Base):
    """Overall pipeline run result with final aggregated verdict."""

    __tablename__ = "judge_pipeline_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(36), nullable=False)
    final_verdict = Column(String(20), nullable=False, default="pending")
    final_score = Column(Numeric(5, 4), nullable=False, default=0)
    final_confidence = Column(Numeric(5, 4), nullable=False, default=0)
    levels_completed = Column(Integer, nullable=False, default=0)
    breakdown_json = Column(Text, default="{}")
    input_hash = Column(String(71), default="")
    output_hash = Column(String(71), default="")
    human_override = Column(String(20), nullable=True)
    human_override_by = Column(String(36), nullable=True)
    human_override_at = Column(DateTime(timezone=True), nullable=True)
    human_override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_judge_run_target", "target_type", "target_id"),
        Index("idx_judge_run_verdict", "final_verdict"),
    )


class JudgeEvaluation(Base):
    """Per-level evaluation result within a judge pipeline run."""

    __tablename__ = "judge_evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("judge_pipeline_runs.id"), nullable=False)
    level = Column(Integer, nullable=False)
    level_name = Column(String(50), nullable=False)
    verdict = Column(String(20), nullable=False)
    score = Column(Numeric(5, 4), nullable=False, default=0)
    confidence = Column(Numeric(5, 4), nullable=False, default=0)
    details_json = Column(Text, default="{}")
    duration_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_judge_eval_run", "run_id"),
        Index("idx_judge_eval_level", "level"),
    )
