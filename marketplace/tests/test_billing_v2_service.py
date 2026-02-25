"""Tests for marketplace.services.billing_v2_service — plan management,
subscriptions, usage metering, limit checks, and invoices.

Uses in-memory SQLite via conftest fixtures.  asyncio_mode = "auto".
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.billing import BillingPlan, Invoice, Subscription, UsageMeter
from marketplace.services import billing_v2_service as svc


# ---------------------------------------------------------------------------
# Plan management
# ---------------------------------------------------------------------------


async def test_create_plan_defaults(db: AsyncSession):
    """create_plan sets sensible defaults (tier, storage, api_calls)."""
    plan = await svc.create_plan(db, name="Starter", price_monthly=9.99)

    assert isinstance(plan, BillingPlan)
    assert plan.name == "Starter"
    assert float(plan.price_usd_monthly) == 9.99
    assert float(plan.price_usd_yearly) == 0
    assert plan.api_calls_limit == 1000
    assert plan.storage_gb_limit == 1
    assert plan.tier == "starter"
    assert plan.status == "active"
    assert plan.features_json == "[]"
    assert plan.description == ""


async def test_create_plan_custom_features(db: AsyncSession):
    """create_plan stores features_json and custom limits."""
    features = ["sso", "priority_support"]
    plan = await svc.create_plan(
        db,
        name="Enterprise",
        price_monthly=99.0,
        price_yearly=999.0,
        api_calls_limit=100_000,
        storage_limit_gb=500,
        features=features,
        description="For large teams",
        tier="enterprise",
    )

    assert plan.tier == "enterprise"
    assert plan.api_calls_limit == 100_000
    assert plan.storage_gb_limit == 500
    assert json.loads(plan.features_json) == features
    assert plan.description == "For large teams"
    assert float(plan.price_usd_yearly) == 999.0


async def test_list_plans_returns_active_only(db: AsyncSession):
    """list_plans only returns plans with status='active'."""
    await svc.create_plan(db, name="Active Plan", price_monthly=10)
    plans = await svc.list_plans(db)
    assert len(plans) == 1
    assert plans[0].name == "Active Plan"


async def test_list_plans_empty(db: AsyncSession):
    """list_plans returns empty list when no plans exist."""
    plans = await svc.list_plans(db)
    assert plans == []


async def test_get_plans_filter_by_tier(db: AsyncSession):
    """get_plans filters by tier when provided."""
    await svc.create_plan(db, name="Starter Plan", price_monthly=10, tier="starter")
    await svc.create_plan(db, name="Pro Plan", price_monthly=50, tier="pro")

    starter_plans = await svc.get_plans(db, tier="starter")
    assert len(starter_plans) == 1
    assert starter_plans[0].name == "Starter Plan"

    pro_plans = await svc.get_plans(db, tier="pro")
    assert len(pro_plans) == 1
    assert pro_plans[0].name == "Pro Plan"


async def test_get_plans_no_tier_returns_all_active(db: AsyncSession):
    """get_plans without tier returns all active plans."""
    await svc.create_plan(db, name="Plan A", price_monthly=5, tier="starter")
    await svc.create_plan(db, name="Plan B", price_monthly=15, tier="pro")

    all_plans = await svc.get_plans(db)
    assert len(all_plans) == 2


async def test_get_plans_nonexistent_tier(db: AsyncSession):
    """get_plans returns empty for a tier that has no plans."""
    await svc.create_plan(db, name="Plan A", price_monthly=5, tier="starter")
    plans = await svc.get_plans(db, tier="nonexistent")
    assert plans == []


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


async def test_subscribe_creates_active_subscription(db: AsyncSession, make_agent):
    """subscribe creates an active subscription with 30-day period."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Sub Plan", price_monthly=20)

    sub = await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)

    assert isinstance(sub, Subscription)
    assert sub.agent_id == agent.id
    assert sub.plan_id == plan.id
    assert sub.status == "active"
    assert sub.current_period_start is not None
    assert sub.current_period_end is not None
    # period should be ~30 days
    delta = sub.current_period_end - sub.current_period_start
    assert delta.days == 30


async def test_get_subscription_returns_active(db: AsyncSession, make_agent):
    """get_subscription returns the active subscription for an agent."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Get Sub", price_monthly=10)
    created = await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)

    fetched = await svc.get_subscription(db, agent.id)
    assert fetched is not None
    assert fetched.id == created.id


async def test_get_subscription_returns_none_when_absent(db: AsyncSession, make_agent):
    """get_subscription returns None for an agent with no subscription."""
    agent, _ = await make_agent()
    result = await svc.get_subscription(db, agent.id)
    assert result is None


async def test_cancel_subscription_at_period_end(db: AsyncSession, make_agent):
    """cancel_subscription(immediate=False) sets cancel_at_period_end flag."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Cancel Plan", price_monthly=10)
    sub = await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)

    cancelled = await svc.cancel_subscription(db, sub.id, immediate=False)

    assert cancelled.cancel_at_period_end is True
    assert cancelled.status == "active"  # still active until period end


async def test_cancel_subscription_immediate(db: AsyncSession, make_agent):
    """cancel_subscription(immediate=True) sets status='cancelled'."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Imm Cancel", price_monthly=10)
    sub = await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)

    cancelled = await svc.cancel_subscription(db, sub.id, immediate=True)

    assert cancelled.status == "cancelled"


async def test_cancel_subscription_not_found(db: AsyncSession):
    """cancel_subscription raises ValueError for non-existent subscription."""
    with pytest.raises(ValueError, match="not found"):
        await svc.cancel_subscription(db, "nonexistent-id")


# ---------------------------------------------------------------------------
# Usage metering
# ---------------------------------------------------------------------------


async def test_record_usage_creates_meter(db: AsyncSession, make_agent):
    """record_usage creates a UsageMeter with correct period boundaries."""
    agent, _ = await make_agent()

    meter = await svc.record_usage(db, agent_id=agent.id, meter_type="api_calls", value=42.0)

    assert isinstance(meter, UsageMeter)
    assert meter.agent_id == agent.id
    assert meter.metric_name == "api_calls"
    assert float(meter.value) == 42.0
    assert meter.period_start is not None
    assert meter.period_end is not None
    # period_start should be day=1 of current month
    assert meter.period_start.day == 1
    assert meter.period_start.hour == 0
    assert meter.period_start.minute == 0


async def test_record_multiple_usage_entries(db: AsyncSession, make_agent):
    """Multiple record_usage calls create separate rows."""
    agent, _ = await make_agent()

    await svc.record_usage(db, agent.id, "api_calls", 10)
    await svc.record_usage(db, agent.id, "api_calls", 20)
    await svc.record_usage(db, agent.id, "storage", 5)

    records = await svc.get_usage(db, agent.id)
    assert len(records) == 3


async def test_get_usage_filter_by_meter_type(db: AsyncSession, make_agent):
    """get_usage filters by meter_type when provided."""
    agent, _ = await make_agent()
    await svc.record_usage(db, agent.id, "api_calls", 10)
    await svc.record_usage(db, agent.id, "storage", 5)

    api_only = await svc.get_usage(db, agent.id, meter_type="api_calls")
    assert len(api_only) == 1
    assert float(api_only[0].value) == 10.0


async def test_get_usage_empty(db: AsyncSession, make_agent):
    """get_usage returns empty list for agent with no records."""
    agent, _ = await make_agent()
    records = await svc.get_usage(db, agent.id)
    assert records == []


# ---------------------------------------------------------------------------
# Limit checking
# ---------------------------------------------------------------------------


async def test_check_limits_no_subscription(db: AsyncSession, make_agent):
    """check_limits returns allowed=False when agent has no subscription."""
    agent, _ = await make_agent()
    result = await svc.check_limits(db, agent.id, "api_calls")

    assert result["allowed"] is False
    assert result["current"] == 0
    assert result["limit"] == 0


async def test_check_limits_within_limit(db: AsyncSession, make_agent):
    """check_limits returns allowed=True when usage is within plan limit."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Limits Plan", price_monthly=10, api_calls_limit=100)
    await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)
    await svc.record_usage(db, agent.id, "api_calls", 50)

    result = await svc.check_limits(db, agent.id, "api_calls")

    assert result["allowed"] is True
    assert result["current"] == 50.0
    assert result["limit"] == 100


async def test_check_limits_exceeded(db: AsyncSession, make_agent):
    """check_limits returns allowed=False when usage exceeds plan limit."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Small Plan", price_monthly=5, api_calls_limit=10)
    await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)
    await svc.record_usage(db, agent.id, "api_calls", 15)

    result = await svc.check_limits(db, agent.id, "api_calls")

    assert result["allowed"] is False
    assert result["current"] == 15.0
    assert result["limit"] == 10


async def test_check_limits_storage_meter(db: AsyncSession, make_agent):
    """check_limits uses storage_gb_limit for 'storage' meter type."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(
        db, name="Storage Plan", price_monthly=10, storage_limit_gb=50,
    )
    await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)
    await svc.record_usage(db, agent.id, "storage", 30)

    result = await svc.check_limits(db, agent.id, "storage")

    assert result["allowed"] is True
    assert result["limit"] == 50


async def test_check_limits_unknown_meter_type(db: AsyncSession, make_agent):
    """check_limits returns limit=0 for unknown meter types."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Unknown Meter", price_monthly=10)
    await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)

    result = await svc.check_limits(db, agent.id, "unknown_metric")

    assert result["limit"] == 0
    # current < 0 is False so allowed is False
    assert result["allowed"] is False


async def test_check_usage_limit_boolean(db: AsyncSession, make_agent):
    """check_usage_limit returns a simple boolean wrapper around check_limits."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Bool Check", price_monthly=10, api_calls_limit=100)
    await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)

    assert await svc.check_usage_limit(db, agent.id, "api_calls") is True

    await svc.record_usage(db, agent.id, "api_calls", 200)

    assert await svc.check_usage_limit(db, agent.id, "api_calls") is False


async def test_check_usage_limit_no_plan(db: AsyncSession, make_agent):
    """check_usage_limit returns False for agent with no subscription."""
    agent, _ = await make_agent()
    assert await svc.check_usage_limit(db, agent.id, "api_calls") is False


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


async def test_generate_invoice(db: AsyncSession, make_agent):
    """generate_invoice creates an open invoice with correct amounts."""
    agent, _ = await make_agent()

    invoice = await svc.generate_invoice(
        db, agent_id=agent.id, amount_usd=49.99, description="Monthly billing",
    )

    assert isinstance(invoice, Invoice)
    assert invoice.agent_id == agent.id
    assert float(invoice.amount_usd) == 49.99
    assert float(invoice.total_usd) == 49.99
    assert invoice.status == "open"
    assert invoice.issued_at is not None
    assert invoice.due_at is not None
    # Due in ~30 days
    delta = invoice.due_at - invoice.issued_at
    assert delta.days == 30


async def test_generate_invoice_with_subscription(db: AsyncSession, make_agent):
    """generate_invoice can be linked to a subscription."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Inv Plan", price_monthly=20)
    sub = await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)

    invoice = await svc.generate_invoice(
        db, agent_id=agent.id, amount_usd=20.0,
        description="Subscription renewal", subscription_id=sub.id,
    )

    assert invoice.subscription_id == sub.id


async def test_generate_invoice_line_items_json(db: AsyncSession, make_agent):
    """generate_invoice stores line items as JSON."""
    agent, _ = await make_agent()
    invoice = await svc.generate_invoice(
        db, agent_id=agent.id, amount_usd=25.0, description="API usage",
    )

    items = json.loads(invoice.line_items_json)
    assert len(items) == 1
    assert items[0]["description"] == "API usage"
    assert items[0]["amount"] == 25.0


async def test_list_invoices_ordered_desc(db: AsyncSession, make_agent):
    """list_invoices returns invoices ordered by created_at descending."""
    agent, _ = await make_agent()
    inv1 = await svc.generate_invoice(db, agent.id, 10.0, "First")
    inv2 = await svc.generate_invoice(db, agent.id, 20.0, "Second")

    invoices = await svc.list_invoices(db, agent.id)
    assert len(invoices) == 2
    # Most recent first
    assert invoices[0].id == inv2.id
    assert invoices[1].id == inv1.id


async def test_list_invoices_empty(db: AsyncSession, make_agent):
    """list_invoices returns empty list for agent with no invoices."""
    agent, _ = await make_agent()
    invoices = await svc.list_invoices(db, agent.id)
    assert invoices == []


async def test_get_invoices_filter_by_status(db: AsyncSession, make_agent):
    """get_invoices filters by status when provided."""
    agent, _ = await make_agent()
    await svc.generate_invoice(db, agent.id, 10.0, "Open one")
    # Manually change one to paid
    inv2 = await svc.generate_invoice(db, agent.id, 20.0, "Paid one")
    inv2.status = "paid"
    await db.commit()

    open_invoices = await svc.get_invoices(db, agent.id, status="open")
    assert len(open_invoices) == 1

    paid_invoices = await svc.get_invoices(db, agent.id, status="paid")
    assert len(paid_invoices) == 1
    assert paid_invoices[0].id == inv2.id


async def test_get_invoices_no_filter(db: AsyncSession, make_agent):
    """get_invoices without status returns all invoices."""
    agent, _ = await make_agent()
    await svc.generate_invoice(db, agent.id, 10.0, "One")
    await svc.generate_invoice(db, agent.id, 20.0, "Two")

    invoices = await svc.get_invoices(db, agent.id)
    assert len(invoices) == 2


# ---------------------------------------------------------------------------
# BillingV2Service class wrapper
# ---------------------------------------------------------------------------


async def test_class_wrapper_create_plan(db: AsyncSession):
    """BillingV2Service.create_plan delegates to module-level function."""
    service = svc.BillingV2Service()
    plan = await service.create_plan(db, name="Wrapper Plan", price_monthly=15)
    assert plan.name == "Wrapper Plan"


async def test_class_wrapper_subscribe(db: AsyncSession, make_agent):
    """BillingV2Service.subscribe delegates to module-level function."""
    agent, _ = await make_agent()
    service = svc.BillingV2Service()
    plan = await service.create_plan(db, name="Wrap Sub", price_monthly=10)
    sub = await service.subscribe(db, agent_id=agent.id, plan_id=plan.id)
    assert sub.status == "active"


async def test_class_wrapper_record_usage(db: AsyncSession, make_agent):
    """BillingV2Service.record_usage delegates to module-level function."""
    agent, _ = await make_agent()
    service = svc.BillingV2Service()
    meter = await service.record_usage(db, agent_id=agent.id, meter_type="api_calls", value=7)
    assert float(meter.value) == 7.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_record_usage_zero_value(db: AsyncSession, make_agent):
    """Recording zero usage is valid."""
    agent, _ = await make_agent()
    meter = await svc.record_usage(db, agent.id, "api_calls", 0)
    assert float(meter.value) == 0.0


async def test_generate_invoice_zero_amount(db: AsyncSession, make_agent):
    """Generating a $0 invoice is valid."""
    agent, _ = await make_agent()
    invoice = await svc.generate_invoice(db, agent.id, 0.0, "Zero invoice")
    assert float(invoice.amount_usd) == 0.0


async def test_check_limits_boundary_exact(db: AsyncSession, make_agent):
    """Usage exactly at the limit should NOT be allowed (current < limit)."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Boundary", price_monthly=5, api_calls_limit=100)
    await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)
    await svc.record_usage(db, agent.id, "api_calls", 100)

    result = await svc.check_limits(db, agent.id, "api_calls")
    assert result["allowed"] is False  # 100 < 100 is False


async def test_check_limits_compute_uses_api_calls_limit(db: AsyncSession, make_agent):
    """'compute' meter type falls back to api_calls_limit."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="Compute", price_monthly=10, api_calls_limit=500)
    await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)
    await svc.record_usage(db, agent.id, "compute", 100)

    result = await svc.check_limits(db, agent.id, "compute")
    assert result["limit"] == 500
    assert result["allowed"] is True


async def test_check_limits_bandwidth_uses_storage_limit(db: AsyncSession, make_agent):
    """'bandwidth' meter type falls back to storage_gb_limit."""
    agent, _ = await make_agent()
    plan = await svc.create_plan(db, name="BW", price_monthly=10, storage_limit_gb=200)
    await svc.subscribe(db, agent_id=agent.id, plan_id=plan.id)

    result = await svc.check_limits(db, agent.id, "bandwidth")
    assert result["limit"] == 200
    assert result["allowed"] is True
