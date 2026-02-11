"""Immutable, append-only security audit trail with SHA-256 hash chain."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String, Text

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False)
    agent_id = Column(String(36), nullable=True)
    creator_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), default="")
    details = Column(Text, default="{}")
    severity = Column(String(10), nullable=False, default="info")
    prev_hash = Column(String(64), nullable=True)
    entry_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_audit_event", "event_type"),
        Index("idx_audit_agent", "agent_id"),
        Index("idx_audit_severity", "severity"),
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_hash", "entry_hash"),
    )
