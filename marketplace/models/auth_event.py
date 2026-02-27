"""Auth event audit trail model for security event logging."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String, Text

from marketplace.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthEvent(Base):
    __tablename__ = "auth_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(36), nullable=True)
    actor_type = Column(String(20), nullable=True)
    event_type = Column(String(50), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    details_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_auth_event_actor", "actor_id"),
        Index("idx_auth_event_type", "event_type"),
        Index("idx_auth_event_created", "created_at"),
    )
