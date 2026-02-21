"""Memory sharing models for cross-agent memory federation."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Index, String, Text, DateTime, Boolean, Integer

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class MemorySharePolicy(Base):
    """Defines sharing rules for agent memory."""

    __tablename__ = "memory_share_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_agent_id = Column(String(36), nullable=False)
    memory_namespace = Column(String(200), nullable=False)
    access_level = Column(String(20), nullable=False, default="read")  # read | write | admin
    allowed_agent_ids = Column(Text, default="[]")  # JSON array of agent IDs, or ["*"] for all
    allowed_namespaces = Column(Text, default="[]")  # JSON array of allowed source namespaces
    max_reads_per_hour = Column(Integer, default=100)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_memory_share_owner", "owner_agent_id"),
        Index("idx_memory_share_namespace", "memory_namespace"),
    )


class MemoryAccessLog(Base):
    """Tracks cross-agent memory access for auditing."""

    __tablename__ = "memory_access_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id = Column(String(36), nullable=False)
    requester_agent_id = Column(String(36), nullable=False)
    owner_agent_id = Column(String(36), nullable=False)
    memory_namespace = Column(String(200), nullable=False)
    operation = Column(String(20), nullable=False)  # read | write | list
    success = Column(Boolean, nullable=False, default=True)
    denial_reason = Column(String(200), default="")
    accessed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_memory_access_requester", "requester_agent_id"),
        Index("idx_memory_access_time", "accessed_at"),
    )
