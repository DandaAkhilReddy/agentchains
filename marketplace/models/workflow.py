import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class WorkflowDefinition(Base):
    __tablename__ = "workflows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    graph_json = Column(Text, nullable=False)
    owner_id = Column(String(36), nullable=False)
    version = Column(Integer, default=1)
    status = Column(String(20), default="draft")
    max_budget_usd = Column(Numeric(12, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=False)
    initiated_by = Column(String(36), nullable=False)
    status = Column(String(20), default="pending")
    input_json = Column(Text, default="{}")
    output_json = Column(Text, default="{}")
    total_cost_usd = Column(Numeric(12, 6), default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class WorkflowNodeExecution(Base):
    __tablename__ = "workflow_node_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), ForeignKey("workflow_executions.id"), nullable=False)
    node_id = Column(String(100), nullable=False)
    node_type = Column(String(30), nullable=False)
    status = Column(String(20), default="pending")
    input_json = Column(Text, default="{}")
    output_json = Column(Text, default="{}")
    cost_usd = Column(Numeric(12, 6), default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    attempt = Column(Integer, default=1)

    __table_args__ = (
        Index("idx_node_exec_execution", "execution_id"),
        Index("idx_node_exec_status", "status"),
    )
