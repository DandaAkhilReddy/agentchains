"""RBAC models — Role definitions and actor-role assignments."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint

from marketplace.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(Base):
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), default="")
    permissions_json = Column(Text, default="[]")
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ActorRole(Base):
    __tablename__ = "actor_roles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(36), nullable=False)
    actor_type = Column(String(20), nullable=False)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False)
    granted_by = Column(String(36), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("actor_id", "role_id", name="uq_actor_role"),
        Index("idx_actor_role_actor", "actor_id"),
        Index("idx_actor_role_role", "role_id"),
    )
