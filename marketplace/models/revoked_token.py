"""Revoked JWT token tracking for token blacklist/revocation support."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String

from marketplace.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String(36), primary_key=True)
    actor_id = Column(String(36), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_revoked_token_actor", "actor_id"),
        Index("idx_revoked_token_expires", "expires_at"),
    )
