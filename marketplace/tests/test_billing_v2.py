"""Comprehensive tests for Billing V2: plans, subscriptions, usage metering, and invoicing."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.billing import BillingPlan, Invoice, Subscription, UsageMeter
from marketplace.services import billing_v2_service
from marketplace.services import invoice_service

pytestmark = pytest.mark.asyncio


def _uid() -> str:
    return str(uuid.uuid4())


async def _create_plan(db, **kw):
    defaults = dict(name=f"plan-{_uid()[:8]}", price_monthly=9.99, price_yearly=99.99, api_calls_limit=5000, storage_limit_gb=10, features=["basic_analytics"], description="Test plan", tier="starter")
    defaults.update(kw)
    return await billing_v2_service.create_plan(db, **defaults)


async def _subscribe(db, agent_id, plan_id):
    return await billing_v2_service.subscribe(db, agent_id, plan_id)


class TestBillingPlanModel:

    async def test_create_billing_plan_defaults(self, db):
        plan = BillingPlan(name="Free Tier")
        db.add(plan); await db.commit(); await db.refresh(plan)
        assert plan.id and len(plan.id) == 36
        assert plan.name == "Free Tier" and plan.tier == "starter"
        assert plan.status == "active" and plan.api_calls_limit == 1000

    async def test_plan_price_fields(self, db):
        plan = BillingPlan(name="Pro Plan", price_usd_monthly=Decimal("29.99"), price_usd_yearly=Decimal("299.99"))
        db.add(plan); await db.commit(); await db.refresh(plan)
        assert float(plan.price_usd_monthly) == pytest.approx(29.99)
        assert float(plan.price_usd_yearly) == pytest.approx(299.99)

    async def test_plan_unique_name_constraint(self, db):
        db.add(BillingPlan(name="Duplicate")); await db.commit()
        db.add(BillingPlan(name="Duplicate"))
        with pytest.raises(Exception): await db.commit()

    async def test_plan_features_json(self, db):
        features = ["analytics", "priority_support", "custom_branding"]
        plan = BillingPlan(name="Enterprise", features_json=json.dumps(features))
        db.add(plan); await db.commit(); await db.refresh(plan)
        assert json.loads(plan.features_json) == features

    async def test_plan_tiers(self, db):
        for tier in ("free", "starter", "pro", "enterprise"):
            db.add(BillingPlan(name=f"Plan-{tier}", tier=tier))
        await db.commit()
        result = await db.execute(select(BillingPlan))
        assert {p.tier for p in result.scalars().all()} == {"free", "starter", "pro", "enterprise"}

    async def test_plan_timestamps(self, db):
        plan = BillingPlan(name="TS"); db.add(plan); await db.commit(); await db.refresh(plan)
        assert plan.created_at is not None and plan.updated_at is not None

    async def test_plan_agents_limit_default(self, db):
        plan = BillingPlan(name="ALTest"); db.add(plan); await db.commit(); await db.refresh(plan)
        assert plan.agents_limit == 0

    async def test_plan_custom_agents_limit(self, db):
        plan = BillingPlan(name="CL", agents_limit=50); db.add(plan); await db.commit(); await db.refresh(plan)
        assert plan.agents_limit == 50

    async def test_plan_description_default_empty(self, db):
        plan = BillingPlan(name="ND"); db.add(plan); await db.commit(); await db.refresh(plan)
        assert plan.description == ""

    async def test_plan_large_limits(self, db):
        plan = BillingPlan(name="Big", api_calls_limit=10_000_000, storage_gb_limit=5000)
        db.add(plan); await db.commit(); await db.refresh(plan)
        assert plan.api_calls_limit == 10_000_000 and plan.storage_gb_limit == 5000


class TestSubscriptionModel:

    async def test_create_subscription(self, db):
        plan = await _create_plan(db)
        sub = Subscription(agent_id=_uid(), plan_id=plan.id)
        db.add(sub); await db.commit(); await db.refresh(sub)
        assert sub.id and sub.status == "active" and sub.cancel_at_period_end is False

    async def test_subscription_period_dates(self, db):
        plan = await _create_plan(db); now = datetime.now(timezone.utc)
        sub = Subscription(agent_id=_uid(), plan_id=plan.id, current_period_start=now, current_period_end=now + timedelta(days=30))
        db.add(sub); await db.commit(); await db.refresh(sub)
        assert (sub.current_period_end - sub.current_period_start).days == 30

    async def test_subscription_cancel_flag(self, db):
        plan = await _create_plan(db)
        sub = Subscription(agent_id=_uid(), plan_id=plan.id, cancel_at_period_end=True)
        db.add(sub); await db.commit(); await db.refresh(sub)
        assert sub.cancel_at_period_end is True

    async def test_subscription_stripe_id(self, db):
        plan = await _create_plan(db)
        sub = Subscription(agent_id=_uid(), plan_id=plan.id, stripe_subscription_id="sub_123")
        db.add(sub); await db.commit(); await db.refresh(sub)
        assert sub.stripe_subscription_id == "sub_123"

    async def test_subscription_statuses(self, db):
        plan = await _create_plan(db)
        for s in ("active", "cancelled", "past_due", "trialing"):
            db.add(Subscription(agent_id=_uid(), plan_id=plan.id, status=s))
        await db.commit()
        result = await db.execute(select(Subscription))
        assert {s.status for s in result.scalars().all()} == {"active", "cancelled", "past_due", "trialing"}


class TestSubscriptionModelExtended:

    async def test_subscription_plan_relationship(self, db):
        plan = await _create_plan(db, name="RelPlan")
        sub = Subscription(agent_id=_uid(), plan_id=plan.id)
        db.add(sub); await db.commit(); await db.refresh(sub)
        assert sub.plan is not None and sub.plan.name == "RelPlan"

    async def test_subscription_multiple_per_agent(self, db):
        plan = await _create_plan(db); aid = _uid()
        for _ in range(3): db.add(Subscription(agent_id=aid, plan_id=plan.id, status="cancelled"))
        await db.commit()
        result = await db.execute(select(Subscription).where(Subscription.agent_id == aid))
        assert len(list(result.scalars().all())) == 3

    async def test_subscription_timestamps(self, db):
        plan = await _create_plan(db)
        sub = Subscription(agent_id=_uid(), plan_id=plan.id)
        db.add(sub); await db.commit(); await db.refresh(sub)
        assert sub.created_at is not None and sub.updated_at is not None


class TestUsageMeterModel:
    async def test_create_usage_meter(self, db):
        m = UsageMeter(agent_id=_uid(), metric_name="api_calls", value=42)
        db.add(m); await db.commit(); await db.refresh(m)
        assert m.id and m.metric_name == "api_calls" and float(m.value) == 42
    async def test_usage_meter_period(self, db):
        now = datetime.now(timezone.utc)
        m = UsageMeter(agent_id=_uid(), metric_name="storage", value=5.5, period_start=now, period_end=now + timedelta(days=30))
        db.add(m); await db.commit(); await db.refresh(m)
        assert m.period_start is not None and m.period_end is not None
    async def test_usage_meter_multiple(self, db):
        aid = _uid()
        for metric in ("api_calls", "storage", "bandwidth", "compute"):
            db.add(UsageMeter(agent_id=aid, metric_name=metric, value=10))
        await db.commit()
        result = await db.execute(select(UsageMeter).where(UsageMeter.agent_id == aid))
        assert len(list(result.scalars().all())) == 4
    async def test_usage_meter_decimal(self, db):
        m = UsageMeter(agent_id=_uid(), metric_name="bw", value=Decimal("123.4567"))
        db.add(m); await db.commit(); await db.refresh(m)
        assert float(m.value) == pytest.approx(123.4567)
    async def test_usage_meter_created_at(self, db):
        m = UsageMeter(agent_id=_uid(), metric_name="api_calls", value=1)
        db.add(m); await db.commit(); await db.refresh(m)
        assert m.created_at is not None


class TestInvoiceModel:
    async def test_create_invoice_defaults(self, db):
        inv = Invoice(agent_id=_uid(), amount_usd=100, total_usd=100)
        db.add(inv); await db.commit(); await db.refresh(inv)
        assert inv.id and inv.status == "draft" and float(inv.tax_usd) == 0
    async def test_invoice_statuses(self, db):
        for s in ("draft", "open", "paid", "void", "uncollectible"):
            db.add(Invoice(agent_id=_uid(), amount_usd=10, total_usd=10, status=s))
        await db.commit()
        result = await db.execute(select(Invoice))
        assert {i.status for i in result.scalars().all()} == {"draft", "open", "paid", "void", "uncollectible"}
    async def test_invoice_dates(self, db):
        now = datetime.now(timezone.utc)
        inv = Invoice(agent_id=_uid(), amount_usd=50, total_usd=50, issued_at=now, due_at=now + timedelta(days=30), paid_at=now + timedelta(days=5))
        db.add(inv); await db.commit(); await db.refresh(inv)
        assert inv.issued_at and inv.due_at and inv.paid_at
    async def test_invoice_subscription_link(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = Invoice(agent_id=aid, subscription_id=sub.id, amount_usd=9.99, total_usd=9.99)
        db.add(inv); await db.commit(); await db.refresh(inv)
        assert inv.subscription_id == sub.id
    async def test_invoice_line_items(self, db):
        items = [{"description": "Pro", "amount": 29.99}]
        inv = Invoice(agent_id=_uid(), amount_usd=29.99, total_usd=29.99, line_items_json=json.dumps(items))
        db.add(inv); await db.commit(); await db.refresh(inv)
        assert len(json.loads(inv.line_items_json)) == 1


class TestBillingV2ServicePlans:
    async def test_create_plan(self, db):
        plan = await billing_v2_service.create_plan(db, name="TP", price_monthly=19.99, tier="pro")
        assert plan.name == "TP" and float(plan.price_usd_monthly) == pytest.approx(19.99)
    async def test_create_plan_features(self, db):
        plan = await billing_v2_service.create_plan(db, name="FP", price_monthly=49.99, features=["sso"])
        assert json.loads(plan.features_json) == ["sso"]
    async def test_create_plan_yearly(self, db):
        plan = await billing_v2_service.create_plan(db, name="YP", price_monthly=10, price_yearly=100)
        assert float(plan.price_usd_yearly) == pytest.approx(100)
    async def test_list_plans_active(self, db):
        await _create_plan(db, name="P1"); await _create_plan(db, name="P2")
        plans = await billing_v2_service.list_plans(db)
        assert len(plans) >= 2 and all(p.status == "active" for p in plans)
    async def test_list_plans_excludes_inactive(self, db):
        plan = await _create_plan(db, name="IP"); plan.status = "archived"; await db.commit()
        assert plan.id not in [p.id for p in await billing_v2_service.list_plans(db)]
    async def test_get_plans_by_tier(self, db):
        await _create_plan(db, name="S1", tier="starter"); await _create_plan(db, name="P1x", tier="pro")
        assert all(p.tier == "starter" for p in await billing_v2_service.get_plans(db, tier="starter"))
    async def test_get_plans_all(self, db):
        await _create_plan(db, name="A1"); await _create_plan(db, name="A2")
        assert len(await billing_v2_service.get_plans(db)) >= 2


class TestBillingV2ServiceSubs:
    async def test_subscribe(self, db):
        plan = await _create_plan(db); aid = _uid()
        sub = await billing_v2_service.subscribe(db, aid, plan.id)
        assert sub.status == "active" and sub.agent_id == aid
    async def test_subscribe_period(self, db):
        plan = await _create_plan(db)
        sub = await billing_v2_service.subscribe(db, _uid(), plan.id)
        assert (sub.current_period_end - sub.current_period_start).days == 30
    async def test_cancel_immediate(self, db):
        plan = await _create_plan(db); sub = await billing_v2_service.subscribe(db, _uid(), plan.id)
        assert (await billing_v2_service.cancel_subscription(db, sub.id, immediate=True)).status == "cancelled"
    async def test_cancel_at_end(self, db):
        plan = await _create_plan(db); sub = await billing_v2_service.subscribe(db, _uid(), plan.id)
        c = await billing_v2_service.cancel_subscription(db, sub.id, immediate=False)
        assert c.cancel_at_period_end is True and c.status == "active"
    async def test_cancel_nonexistent(self, db):
        with pytest.raises(ValueError, match="not found"):
            await billing_v2_service.cancel_subscription(db, _uid())
    async def test_get_sub_active(self, db):
        plan = await _create_plan(db); aid = _uid()
        await billing_v2_service.subscribe(db, aid, plan.id)
        assert (await billing_v2_service.get_subscription(db, aid)) is not None
    async def test_get_sub_none(self, db):
        assert await billing_v2_service.get_subscription(db, _uid()) is None


class TestBillingV2ServiceUsage:
    async def test_record(self, db):
        m = await billing_v2_service.record_usage(db, _uid(), "api_calls", 100)
        assert m.metric_name == "api_calls" and float(m.value) == 100
    async def test_record_period(self, db):
        m = await billing_v2_service.record_usage(db, _uid(), "storage", 5.5)
        assert m.period_start and m.period_start.day == 1
    async def test_get_all(self, db):
        aid = _uid()
        await billing_v2_service.record_usage(db, aid, "api_calls", 50)
        await billing_v2_service.record_usage(db, aid, "storage", 2)
        assert len(await billing_v2_service.get_usage(db, aid)) == 2
    async def test_get_by_type(self, db):
        aid = _uid()
        await billing_v2_service.record_usage(db, aid, "api_calls", 50)
        await billing_v2_service.record_usage(db, aid, "storage", 2)
        u = await billing_v2_service.get_usage(db, aid, meter_type="api_calls")
        assert len(u) == 1 and u[0].metric_name == "api_calls"
    async def test_limits_within(self, db):
        plan = await _create_plan(db, api_calls_limit=1000); aid = _uid()
        await billing_v2_service.subscribe(db, aid, plan.id)
        await billing_v2_service.record_usage(db, aid, "api_calls", 500)
        r = await billing_v2_service.check_limits(db, aid, "api_calls")
        assert r["allowed"] is True and r["current"] == 500
    async def test_limits_exceeded(self, db):
        plan = await _create_plan(db, api_calls_limit=100); aid = _uid()
        await billing_v2_service.subscribe(db, aid, plan.id)
        await billing_v2_service.record_usage(db, aid, "api_calls", 150)
        assert (await billing_v2_service.check_limits(db, aid, "api_calls"))["allowed"] is False
    async def test_limits_no_sub(self, db):
        r = await billing_v2_service.check_limits(db, _uid(), "api_calls")
        assert r["allowed"] is False and r["limit"] == 0
    async def test_usage_limit_true(self, db):
        plan = await _create_plan(db, api_calls_limit=500); aid = _uid()
        await billing_v2_service.subscribe(db, aid, plan.id)
        await billing_v2_service.record_usage(db, aid, "api_calls", 100)
        assert await billing_v2_service.check_usage_limit(db, aid, "api_calls") is True
    async def test_usage_limit_false(self, db):
        plan = await _create_plan(db, api_calls_limit=50); aid = _uid()
        await billing_v2_service.subscribe(db, aid, plan.id)
        await billing_v2_service.record_usage(db, aid, "api_calls", 100)
        assert await billing_v2_service.check_usage_limit(db, aid, "api_calls") is False
    async def test_limits_storage(self, db):
        plan = await _create_plan(db, storage_limit_gb=10); aid = _uid()
        await billing_v2_service.subscribe(db, aid, plan.id)
        await billing_v2_service.record_usage(db, aid, "storage", 5)
        assert (await billing_v2_service.check_limits(db, aid, "storage"))["allowed"] is True
    async def test_limits_boundary(self, db):
        plan = await _create_plan(db, api_calls_limit=100); aid = _uid()
        await billing_v2_service.subscribe(db, aid, plan.id)
        await billing_v2_service.record_usage(db, aid, "api_calls", 100)
        assert (await billing_v2_service.check_limits(db, aid, "api_calls"))["allowed"] is False
    async def test_cumulative(self, db):
        plan = await _create_plan(db, api_calls_limit=500); aid = _uid()
        await billing_v2_service.subscribe(db, aid, plan.id)
        await billing_v2_service.record_usage(db, aid, "api_calls", 200)
        await billing_v2_service.record_usage(db, aid, "api_calls", 200)
        r = await billing_v2_service.check_limits(db, aid, "api_calls")
        assert r["current"] == 400 and r["allowed"] is True


class TestBillingV2ServiceInvoices:
    async def test_gen_invoice(self, db):
        inv = await billing_v2_service.generate_invoice(db, _uid(), amount_usd=29.99, description="M")
        assert inv.status == "open" and float(inv.amount_usd) == pytest.approx(29.99)
    async def test_gen_invoice_sub(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await billing_v2_service.generate_invoice(db, aid, amount_usd=9.99, subscription_id=sub.id)
        assert inv.subscription_id == sub.id
    async def test_gen_invoice_items(self, db):
        inv = await billing_v2_service.generate_invoice(db, _uid(), amount_usd=50, description="Overage")
        assert json.loads(inv.line_items_json)[0]["description"] == "Overage"
    async def test_gen_invoice_due(self, db):
        inv = await billing_v2_service.generate_invoice(db, _uid(), amount_usd=10)
        assert inv.due_at is not None
    async def test_list_invoices(self, db):
        aid = _uid()
        await billing_v2_service.generate_invoice(db, aid, amount_usd=10)
        await billing_v2_service.generate_invoice(db, aid, amount_usd=20)
        assert len(await billing_v2_service.list_invoices(db, aid)) == 2
    async def test_get_invoices_status(self, db):
        aid = _uid()
        await billing_v2_service.generate_invoice(db, aid, amount_usd=10)
        assert len(await billing_v2_service.get_invoices(db, aid, status="open")) == 1


class TestInvoiceServiceFull:
    async def test_gen_line_items(self, db):
        items = [{"description": "Plan", "amount": 29.99, "quantity": 1}, {"description": "Over", "amount": 0.01, "quantity": 200}]
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=items)
        assert float(inv.amount_usd) == pytest.approx(29.99 + 2.0)
    async def test_custom_due(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        due = datetime.now(timezone.utc) + timedelta(days=60)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "T", "amount": 10}], due_date=due)
        assert inv.due_at is not None
    async def test_mark_paid(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "F", "amount": 25}])
        paid = await invoice_service.mark_invoice_paid(db, inv.id)
        assert paid.status == "paid" and paid.paid_at is not None
    async def test_mark_paid_stripe(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "F", "amount": 10}])
        assert (await invoice_service.mark_invoice_paid(db, inv.id, stripe_invoice_id="in_1")).stripe_invoice_id == "in_1"
    async def test_mark_nonexistent(self, db):
        with pytest.raises(ValueError): await invoice_service.mark_invoice_paid(db, _uid())
    async def test_void(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "F", "amount": 15}])
        assert (await invoice_service.void_invoice(db, inv.id)).status == "void"
    async def test_void_paid(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "F", "amount": 10}])
        await invoice_service.mark_invoice_paid(db, inv.id)
        with pytest.raises(ValueError, match="Cannot void"): await invoice_service.void_invoice(db, inv.id)
    async def test_void_missing(self, db):
        with pytest.raises(ValueError): await invoice_service.void_invoice(db, _uid())
    async def test_get_invoice(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "F", "amount": 20}])
        assert (await invoice_service.get_invoice(db, inv.id)).id == inv.id
    async def test_get_not_found(self, db):
        assert await invoice_service.get_invoice(db, _uid()) is None
    async def test_gen_pdf(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "M", "amount": 29.99, "quantity": 1}])
        fp = await invoice_service.generate_invoice_pdf(db, inv.id)
        assert fp.endswith(".txt")
    async def test_pdf_url_none(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "F", "amount": 5}])
        assert await invoice_service.get_invoice_pdf_url(db, inv.id) is None
    async def test_pdf_url_after(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "F", "amount": 5}])
        await invoice_service.generate_invoice_pdf(db, inv.id)
        assert "invoice_" in (await invoice_service.get_invoice_pdf_url(db, inv.id))
    async def test_pdf_missing(self, db):
        with pytest.raises(ValueError): await invoice_service.generate_invoice_pdf(db, _uid())
    async def test_render_text(self, db):
        plan = await _create_plan(db); aid = _uid(); sub = await _subscribe(db, aid, plan.id)
        inv = await invoice_service.generate_invoice(db, aid, sub.id, line_items=[{"description": "Pro", "amount": 49.99, "quantity": 1}])
        text = invoice_service._render_invoice_text(inv)
        assert "INVOICE" in text and "Pro" in text
    async def test_pdf_url_unknown(self, db):
        assert await invoice_service.get_invoice_pdf_url(db, _uid()) is None
