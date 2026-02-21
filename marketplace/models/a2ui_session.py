"""SQLAlchemy models for A2UI session logging and consent tracking.

Pattern follows marketplace/models/agent.py.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class A2UISessionLog(Base):
    __tablename__ = "a2ui_session_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=True)
    session_started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    session_ended_at = Column(DateTime(timezone=True), nullable=True)
    message_count = Column(Integer, nullable=False, default=0)
    components_rendered = Column(Integer, nullable=False, default=0)
    inputs_requested = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_a2ui_sessions_agent", "agent_id"),
        Index("idx_a2ui_sessions_user", "user_id"),
    )


class A2UIConsentRecord(Base):
    __tablename__ = "a2ui_consent_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("a2ui_session_logs.id"),
        nullable=False,
    )
    consent_type = Column(String(50), nullable=False)
    granted = Column(Boolean, nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_a2ui_consent_session", "session_id"),
    )
