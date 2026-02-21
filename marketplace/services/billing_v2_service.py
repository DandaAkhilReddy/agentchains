"""Billing V2 service: plan management, subscriptions, usage metering, and invoices."""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.billing import BillingPlan, Invoice, Subscription, UsageMeter

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Plan management
# ---------------------------------------------------------------------------

async def create_plan(
    db: AsyncSession,
    name: str,
    price_monthly: float,
    price_yearly: float = 0,
    api_calls_limit: int = 1000,
    storage_limit_gb: int = 1,
    features: list[str] | None = None,
    description: str = "",
    tier: str = "starter",
) -> BillingPlan:
    """Create a new billing plan."""
    plan = BillingPlan(
        name=name,
        tier=tier,
        price_usd_monthly=price_monthly,
        price_usd_yearly=price_yearly,
        api_calls_limit=api_calls_limit,
        storage_gb_limit=storage_limit_gb,
        description=description,
        features_json=json.dumps(features or []),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    logger.info("Created billing plan '%s' (id=%s)", name, plan.id)
    return plan


async def list_plans(db: AsyncSession) -> list[BillingPlan]:
    """List all active billing plans."""
    stmt = select(BillingPlan).where(BillingPlan.status == "active")
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_plans(db: AsyncSession, tier: str | None = None) -> list[BillingPlan]:
    """List billing plans, optionally filtered by tier."""
    stmt = select(BillingPlan).where(BillingPlan.status == "active")
    if tier:
        stmt = stmt.where(BillingPlan.tier == tier)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

async def subscribe(db: AsyncSession, agent_id: str, plan_id: str) -> Subscription:
    """Create a new subscription for an agent."""
    now = _utcnow()
    sub = Subscription(
        agent_id=agent_id,
        plan_id=plan_id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def cancel_subscription(
    db: AsyncSession, subscription_id: str, immediate: bool = False
) -> Subscription:
    """Cancel a subscription, either immediately or at period end."""
    result = await db.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise ValueError(f"Subscription {subscription_id} not found")

    if immediate:
        sub.status = "cancelled"
        sub.current_period_end = _utcnow()
    else:
        sub.cancel_at_period_end = True

    sub.updated_at = _utcnow()
    await db.commit()
    await db.refresh(sub)
    return sub


async def get_subscription(db: AsyncSession, agent_id: str) -> Subscription | None:
    """Get the active subscription for an agent."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.agent_id == agent_id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Usage metering
# ---------------------------------------------------------------------------

async def record_usage(
    db: AsyncSession, agent_id: str, meter_type: str, value: float
) -> UsageMeter:
    """Record a usage data point for an agent."""
    now = _utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (period_start.month % 12) + 1
    year = period_start.year + (1 if next_month == 1 else 0)
    period_end = period_start.replace(year=year, month=next_month)

    meter = UsageMeter(
        agent_id=agent_id,
        metric_name=meter_type,
        value=value,
        period_start=period_start,
        period_end=period_end,
    )
    db.add(meter)
    await db.commit()
    await db.refresh(meter)
    return meter


async def get_usage(
    db: AsyncSession,
    agent_id: str,
    meter_type: str | None = None,
    period_start: datetime | None = None,
) -> list[UsageMeter]:
    """Get usage records for an agent, optionally filtered by type and period."""
    stmt = select(UsageMeter).where(UsageMeter.agent_id == agent_id)
    if meter_type:
        stmt = stmt.where(UsageMeter.metric_name == meter_type)
    if period_start:
        stmt = stmt.where(UsageMeter.period_start >= period_start)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def check_limits(
    db: AsyncSession, agent_id: str, meter_type: str
) -> dict:
    """Check if an agent has exceeded their plan limits for a meter type.

    Returns dict with keys: allowed (bool), current (float), limit (int).
    """
    sub = await get_subscription(db, agent_id)
    if not sub:
        return {"allowed": False, "current": 0, "limit": 0}

    # Load the plan
    plan_result = await db.execute(
        select(BillingPlan).where(BillingPlan.id == sub.plan_id)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        return {"allowed": False, "current": 0, "limit": 0}

    # Determine the limit based on meter type
    limit_map = {
        "api_calls": plan.api_calls_limit,
        "storage": plan.storage_gb_limit,
        "compute": plan.api_calls_limit,  # fallback to api_calls
        "bandwidth": plan.storage_gb_limit,  # fallback to storage
    }
    limit = limit_map.get(meter_type, 0)

    # Sum usage for the current period
    now = _utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage_records = await get_usage(db, agent_id, meter_type, period_start)
    current = sum(float(u.value) for u in usage_records)

    return {
        "allowed": current < limit,
        "current": current,
        "limit": limit,
    }


async def check_usage_limit(
    db: AsyncSession, agent_id: str, metric_name: str
) -> bool:
    """Check if an agent is within their plan usage limit for a given metric.

    Returns True if the agent is within their limit, False if exceeded or no plan.
    """
    result = await check_limits(db, agent_id, metric_name)
    return result["allowed"]


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

async def generate_invoice(
    db: AsyncSession,
    agent_id: str,
    amount_usd: float,
    description: str = "",
    subscription_id: str | None = None,
) -> Invoice:
    """Generate a new invoice for an agent."""
    now = _utcnow()
    invoice = Invoice(
        agent_id=agent_id,
        subscription_id=subscription_id,
        amount_usd=amount_usd,
        total_usd=amount_usd,
        status="open",
        line_items_json=json.dumps([{"description": description, "amount": amount_usd}]),
        issued_at=now,
        due_at=now + timedelta(days=30),
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    logger.info("Generated invoice '%s' for agent '%s' ($%.2f)", invoice.id, agent_id, amount_usd)
    return invoice


async def list_invoices(db: AsyncSession, agent_id: str) -> list[Invoice]:
    """List all invoices for an agent, ordered by most recent first."""
    stmt = (
        select(Invoice)
        .where(Invoice.agent_id == agent_id)
        .order_by(Invoice.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_invoices(
    db: AsyncSession, agent_id: str, status: str | None = None
) -> list[Invoice]:
    """Get invoices for an agent, optionally filtered by status."""
    stmt = select(Invoice).where(Invoice.agent_id == agent_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


class BillingV2Service:
    """Class wrapper for billing v2 functions."""

    async def create_plan(self, db, **kwargs):
        return await create_plan(db, **kwargs)

    async def subscribe(self, db, **kwargs):
        return await subscribe(db, **kwargs)

    async def record_usage(self, db, **kwargs):
        return await record_usage(db, **kwargs)
