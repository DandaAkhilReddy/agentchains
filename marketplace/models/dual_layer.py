"""Dual-layer marketplace models for developer builder and end-user buyer flows."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)

from marketplace.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EndUser(Base):
    """Non-technical buyer account backed by a managed buyer agent."""

    __tablename__ = "end_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    managed_agent_id = Column(
        String(36), ForeignKey("registered_agents.id"), unique=True, nullable=False
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_end_users_email", "email"),
        Index("idx_end_users_status", "status"),
    )


class ConsumerOrder(Base):
    """Buyer-facing order record mapped to an internal transaction."""

    __tablename__ = "consumer_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    end_user_id = Column(String(36), ForeignKey("end_users.id"), nullable=False)
    listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=False)
    tx_id = Column(String(36), ForeignKey("transactions.id"), nullable=False, unique=True)
    amount_usd = Column(Numeric(18, 6), nullable=False, default=0)
    fee_usd = Column(Numeric(18, 6), nullable=False, default=0)
    payout_usd = Column(Numeric(18, 6), nullable=False, default=0)
    status = Column(String(30), nullable=False, default="completed")
    trust_status = Column(String(32), nullable=False, default="pending_verification")
    warning_acknowledged = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_consumer_orders_user", "end_user_id"),
        Index("idx_consumer_orders_listing", "listing_id"),
        Index("idx_consumer_orders_status", "status"),
        Index("idx_consumer_orders_created", "created_at"),
    )


class DeveloperProfile(Base):
    """Public creator profile for discoverable developer identity."""

    __tablename__ = "developer_profiles"

    creator_id = Column(String(36), ForeignKey("creators.id"), primary_key=True)
    bio = Column(Text, nullable=False, default="")
    links_json = Column(Text, nullable=False, default="[]")
    specialties_json = Column(Text, nullable=False, default="[]")
    featured_flag = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class BuilderProject(Base):
    """Draft or published builder project owned by a creator."""

    __tablename__ = "builder_projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id = Column(String(36), ForeignKey("creators.id"), nullable=False)
    template_key = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    config_json = Column(Text, nullable=False, default="{}")
    status = Column(String(20), nullable=False, default="draft")
    published_listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_builder_projects_creator", "creator_id"),
        Index("idx_builder_projects_status", "status"),
        Index("idx_builder_projects_template", "template_key"),
    )


class PlatformFee(Base):
    """Explicit fee accounting row used by admin and payout reporting."""

    __tablename__ = "platform_fees"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tx_id = Column(String(36), ForeignKey("transactions.id"), nullable=True)
    order_id = Column(String(36), ForeignKey("consumer_orders.id"), nullable=True, unique=True)
    gross_usd = Column(Numeric(18, 6), nullable=False, default=0)
    fee_usd = Column(Numeric(18, 6), nullable=False, default=0)
    payout_usd = Column(Numeric(18, 6), nullable=False, default=0)
    policy_version = Column(String(40), nullable=False, default="dual-layer-fee-v1")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_platform_fees_tx", "tx_id"),
        Index("idx_platform_fees_order", "order_id"),
        Index("idx_platform_fees_created", "created_at"),
    )
