import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ChainProvenanceEntry(Base):
    __tablename__ = "chain_provenance_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chain_execution_id = Column(
        String(36), ForeignKey("chain_executions.id"), nullable=False
    )
    node_id = Column(String(100), nullable=False)
    event_type = Column(String(30), nullable=False)  # node_started | node_completed | node_failed
    event_timestamp = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    node_type = Column(String(30), nullable=True)  # agent_call, condition, loop, etc.
    agent_id = Column(String(36), nullable=True)
    input_hash_sha256 = Column(String(64), nullable=True)
    output_hash_sha256 = Column(String(64), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(12, 6), default=0)
    status = Column(String(20), nullable=True)  # running, completed, failed
    error_message = Column(Text, nullable=True)
    attempt_number = Column(Integer, default=1)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_provenance_execution", "chain_execution_id"),
        Index("idx_provenance_event_type", "event_type"),
        Index("idx_provenance_timestamp", "event_timestamp"),
    )
