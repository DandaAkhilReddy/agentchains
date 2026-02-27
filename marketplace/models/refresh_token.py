"""Refresh token model for JWT token rotation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, String

from marketplace.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash = Column(String(128), unique=True, nullable=False)
    actor_id = Column(String(36), nullable=False)
    actor_type = Column(String(20), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_refresh_token_actor", "actor_id"),
        Index("idx_refresh_token_expires", "expires_at"),
        Index("idx_refresh_token_hash", "token_hash"),
    )
