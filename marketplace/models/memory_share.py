"""Memory sharing policy models for cross-agent memory federation."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class MemorySharePolicy(Base):
    """Defines how an agent's memory can be shared with other agents."""

    __tablename__ = "memory_share_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_agent_id = Column(String(36), nullable=False)
    target_agent_id = Column(String(36), nullable=True)  # None = public
    memory_namespace = Column(String(100), nullable=False)
    access_level = Column(String(20), nullable=False, default="read")  # read | write | admin
    allow_derivative = Column(Boolean, nullable=False, default=False)
    max_reads_per_day = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active | revoked | expired
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_memory_share_owner", "owner_agent_id"),
        Index("idx_memory_share_target", "target_agent_id"),
        Index("idx_memory_share_namespace", "memory_namespace"),
    )


class MemoryAccessLog(Base):
    """Tracks cross-agent memory access for auditing."""

    __tablename__ = "memory_access_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id = Column(String(36), nullable=False)
    accessor_agent_id = Column(String(36), nullable=False)
    memory_namespace = Column(String(100), nullable=False)
    action = Column(String(20), nullable=False)  # read | write | delete
    resource_key = Column(String(500), nullable=True)
    accessed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_memory_access_accessor", "accessor_agent_id"),
        Index("idx_memory_access_time", "accessed_at"),
    )
