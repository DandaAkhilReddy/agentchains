"""API key model for machine-to-machine authentication."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, String, Text

from marketplace.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(36), nullable=False)
    actor_type = Column(String(20), nullable=False)
    key_prefix = Column(String(8), nullable=False)
    key_hash = Column(String(128), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    scopes_json = Column(Text, default='["*"]')
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_api_key_actor", "actor_id"),
        Index("idx_api_key_prefix", "key_prefix"),
        Index("idx_api_key_hash", "key_hash"),
    )
