"""Billing V2 models: plans, subscriptions, usage meters, and invoices."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class BillingPlan(Base):
    __tablename__ = "billing_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, default="")
    tier = Column(String(20), nullable=False, default="starter")  # free / starter / pro / enterprise
    price_usd_monthly = Column(Numeric(10, 2), nullable=False, default=0)
    price_usd_yearly = Column(Numeric(10, 2), nullable=False, default=0)
    api_calls_limit = Column(Integer, nullable=False, default=1000)
    storage_gb_limit = Column(Integer, nullable=False, default=1)
    agents_limit = Column(Integer, nullable=False, default=0)
    features_json = Column(Text, default="[]")
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    subscriptions = relationship("Subscription", back_populates="plan", lazy="selectin")

    __table_args__ = (
        Index("idx_billing_plans_status", "status"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False)
    plan_id = Column(String(36), ForeignKey("billing_plans.id"), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # active / cancelled / past_due / trialing
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    stripe_subscription_id = Column(String(200), default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    plan = relationship("BillingPlan", back_populates="subscriptions", lazy="selectin",
                        foreign_keys=[plan_id],
                        primaryjoin="Subscription.plan_id == BillingPlan.id")

    __table_args__ = (
        Index("idx_subscriptions_agent", "agent_id"),
        Index("idx_subscriptions_plan", "plan_id"),
        Index("idx_subscriptions_status", "status"),
    )


class UsageMeter(Base):
    __tablename__ = "usage_meters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False)
    metric_name = Column(String(50), nullable=False)  # api_calls / storage / bandwidth
    value = Column(Numeric(14, 4), nullable=False, default=0)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_usage_agent_metric_period", "agent_id", "metric_name", "period_start"),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False)
    subscription_id = Column(String(36), ForeignKey("subscriptions.id"), nullable=True)
    amount_usd = Column(Numeric(12, 4), nullable=False, default=0)
    tax_usd = Column(Numeric(12, 4), nullable=False, default=0)
    total_usd = Column(Numeric(12, 4), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="draft")  # draft / open / paid / void / uncollectible
    stripe_invoice_id = Column(String(200), default="")
    pdf_url = Column(String(500), default="")
    line_items_json = Column(Text, default="[]")
    issued_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_invoices_agent", "agent_id"),
        Index("idx_invoices_subscription", "subscription_id"),
        Index("idx_invoices_status", "status"),
    )
