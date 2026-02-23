import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ChainTemplate(Base):
    __tablename__ = "chain_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    category = Column(String(50), default="general")
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=True)
    graph_json = Column(Text, nullable=False)
    author_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=True)
    forked_from_id = Column(String(36), ForeignKey("chain_templates.id"), nullable=True)
    version = Column(Integer, default=1)
    status = Column(String(20), default="draft")  # draft | active | archived
    tags_json = Column(Text, default="[]")
    required_capabilities_json = Column(Text, default="[]")
    execution_count = Column(Integer, default=0)
    avg_cost_usd = Column(Numeric(12, 6), default=0)
    avg_duration_ms = Column(Integer, default=0)
    trust_score = Column(Integer, default=0)  # 0-100
    max_budget_usd = Column(Numeric(12, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_chain_templates_category", "category"),
        Index("idx_chain_templates_author", "author_id"),
        Index("idx_chain_templates_status", "status"),
    )


class ChainExecution(Base):
    __tablename__ = "chain_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chain_template_id = Column(String(36), ForeignKey("chain_templates.id"), nullable=False)
    workflow_execution_id = Column(String(36), ForeignKey("workflow_executions.id"), nullable=True)
    initiated_by = Column(String(36), nullable=False)
    status = Column(String(20), default="pending")
    input_json = Column(Text, default="{}")
    output_json = Column(Text, default="{}")
    total_cost_usd = Column(Numeric(12, 6), default=0)
    participant_agents_json = Column(Text, default="[]")
    provenance_hash = Column(String(64), nullable=True)
    idempotency_key = Column(String(64), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_chain_executions_template", "chain_template_id"),
        Index("idx_chain_executions_status", "status"),
        Index("idx_chain_executions_idempotency", "idempotency_key"),
    )
