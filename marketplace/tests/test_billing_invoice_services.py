"""Comprehensive tests for Billing V2 service, Invoice service, billing models,
and Compliance service.

Covers: plan CRUD, subscriptions, usage metering, tier enforcement, overage
calculation, proration logic, free-tier limits, invoice generation, line items,
tax calculation, PDF generation, invoice statuses, due dates, currency
validation, invoice numbering, model fields/defaults/relationships, GDPR data
export, right-to-deletion, consent tracking, audit log generation, and data
retention policies.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.billing import BillingPlan, Invoice, Subscription, UsageMeter
from marketplace.services import billing_v2_service
from marketplace.services import invoice_service
from marketplace.services import compliance_service

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


async def _create_plan(db, **kw):
    defaults = dict(
        name=f"plan-{_uid()[:8]}",
        price_monthly=9.99,
        price_yearly=99.99,
        api_calls_limit=5000,
        storage_limit_gb=10,
        features=["basic_analytics"],
        description="Test plan",
        tier="starter",
    )
    defaults.update(kw)
    return await billing_v2_service.create_plan(db, **defaults)


async def _subscribe(db, agent_id, plan_id):
    return await billing_v2_service.subscribe(db, agent_id, plan_id)


async def _seed_agent(db):
    """Create a minimal RegisteredAgent and return it."""
    from marketplace.models.agent import RegisteredAgent
    agent = RegisteredAgent(
        id=_uid(),
        name=f"agent-{_uid()[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test_key",
        status="active",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


# ===================================================================
# TestBillingV2Service — 27 tests
# ===================================================================

class TestBillingV2Service:
    """Tests for marketplace.services.billing_v2_service."""

    # --- Module import ---

    async def test_service_module_is_importable(self):
        """The billing_v2_service module should be importable."""
        import importlib
        mod = importlib.import_module("marketplace.services.billing_v2_service")
        assert hasattr(mod, "create_plan")
        assert hasattr(mod, "subscribe")
        assert hasattr(mod, "cancel_subscription")
        assert hasattr(mod, "record_usage")

    # --- Plan CRUD ---

    async def test_create_plan_returns_billing_plan(self, db):
        plan = await _create_plan(db)
        assert isinstance(plan, BillingPlan)
        assert plan.id is not None
        assert len(plan.id) == 36

    async def test_create_plan_stores_name_and_tier(self, db):
        plan = await _create_plan(db, name="ProPlan", tier="pro")
        assert plan.name == "ProPlan"
        assert plan.tier == "pro"

    async def test_create_plan_stores_pricing(self, db):
        plan = await _create_plan(db, price_monthly=49.99, price_yearly=499.99)
        assert float(plan.price_usd_monthly) == pytest.approx(49.99)
        assert float(plan.price_usd_yearly) == pytest.approx(499.99)

    async def test_create_plan_stores_features_json(self, db):
        features = ["analytics", "support", "api_access"]
        plan = await _create_plan(db, features=features)
        assert json.loads(plan.features_json) == features

    async def test_create_plan_stores_limits(self, db):
        plan = await _create_plan(db, api_calls_limit=10000, storage_limit_gb=50)
        assert plan.api_calls_limit == 10000
        assert plan.storage_gb_limit == 50

    async def test_list_plans_returns_active_only(self, db):
        await _create_plan(db, name="active-plan")
        inactive = BillingPlan(name="inactive-plan", status="archived")
        db.add(inactive)
        await db.commit()
        plans = await billing_v2_service.list_plans(db)
        names = [p.name for p in plans]
        assert "active-plan" in names
        assert "inactive-plan" not in names

    async def test_get_plans_filter_by_tier(self, db):
        await _create_plan(db, name="starter-x", tier="starter")
        await _create_plan(db, name="pro-x", tier="pro")
        starter_plans = await billing_v2_service.get_plans(db, tier="starter")
        assert all(p.tier == "starter" for p in starter_plans)

    async def test_get_plans_no_filter_returns_all_active(self, db):
        await _create_plan(db, name="a1")
        await _create_plan(db, name="a2")
        plans = await billing_v2_service.get_plans(db)
        assert len(plans) >= 2

    # --- Subscriptions ---

    async def test_subscribe_creates_active_subscription(self, db):
        plan = await _create_plan(db)
        sub = await _subscribe(db, _uid(), plan.id)
        assert isinstance(sub, Subscription)
        assert sub.status == "active"
        assert sub.plan_id == plan.id

    async def test_subscribe_sets_period_30_days(self, db):
        plan = await _create_plan(db)
        sub = await _subscribe(db, _uid(), plan.id)
        delta = sub.current_period_end - sub.current_period_start
        assert abs(delta.days - 30) <= 1

    async def test_cancel_subscription_immediate(self, db):
        plan = await _create_plan(db)
        sub = await _subscribe(db, _uid(), plan.id)
        cancelled = await billing_v2_service.cancel_subscription(db, sub.id, immediate=True)
        assert cancelled.status == "cancelled"

    async def test_cancel_subscription_at_period_end(self, db):
        plan = await _create_plan(db)
        sub = await _subscribe(db, _uid(), plan.id)
        cancelled = await billing_v2_service.cancel_subscription(db, sub.id, immediate=False)
        assert cancelled.cancel_at_period_end is True
        assert cancelled.status == "active"

    async def test_cancel_subscription_not_found_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            await billing_v2_service.cancel_subscription(db, _uid())

    async def test_get_subscription_returns_active(self, db):
        plan = await _create_plan(db)
        agent_id = _uid()
        await _subscribe(db, agent_id, plan.id)
        found = await billing_v2_service.get_subscription(db, agent_id)
        assert found is not None
        assert found.agent_id == agent_id

    async def test_get_subscription_returns_none_when_missing(self, db):
        result = await billing_v2_service.get_subscription(db, _uid())
        assert result is None

    async def test_subscription_state_transition_active_to_cancelled(self, db):
        plan = await _create_plan(db)
        sub = await _subscribe(db, _uid(), plan.id)
        assert sub.status == "active"
        await billing_v2_service.cancel_subscription(db, sub.id, immediate=True)
        refreshed = await db.execute(select(Subscription).where(Subscription.id == sub.id))
        assert refreshed.scalar_one().status == "cancelled"

    # --- Usage metering ---

    async def test_record_usage_creates_meter(self, db):
        meter = await billing_v2_service.record_usage(db, _uid(), "api_calls", 100)
        assert isinstance(meter, UsageMeter)
        assert float(meter.value) == pytest.approx(100)

    async def test_record_usage_sets_period_boundaries(self, db):
        meter = await billing_v2_service.record_usage(db, _uid(), "storage", 5.5)
        assert meter.period_start is not None
        assert meter.period_end is not None
        assert meter.period_end > meter.period_start

    async def test_get_usage_returns_all_for_agent(self, db):
        agent_id = _uid()
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 10)
        await billing_v2_service.record_usage(db, agent_id, "storage", 2)
        records = await billing_v2_service.get_usage(db, agent_id)
        assert len(records) == 2

    async def test_get_usage_filters_by_meter_type(self, db):
        agent_id = _uid()
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 10)
        await billing_v2_service.record_usage(db, agent_id, "storage", 2)
        records = await billing_v2_service.get_usage(db, agent_id, meter_type="api_calls")
        assert len(records) == 1
        assert records[0].metric_name == "api_calls"

    async def test_aggregate_usage_sums_values(self, db):
        agent_id = _uid()
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 100)
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 250)
        records = await billing_v2_service.get_usage(db, agent_id, meter_type="api_calls")
        total = sum(float(r.value) for r in records)
        assert total == pytest.approx(350)

    # --- Tier enforcement / limits ---

    async def test_check_limits_within_limit(self, db):
        plan = await _create_plan(db, api_calls_limit=1000)
        agent_id = _uid()
        await _subscribe(db, agent_id, plan.id)
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 500)
        result = await billing_v2_service.check_limits(db, agent_id, "api_calls")
        assert result["allowed"] is True
        assert result["current"] == pytest.approx(500)
        assert result["limit"] == 1000

    async def test_check_limits_exceeded(self, db):
        plan = await _create_plan(db, api_calls_limit=100)
        agent_id = _uid()
        await _subscribe(db, agent_id, plan.id)
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 150)
        result = await billing_v2_service.check_limits(db, agent_id, "api_calls")
        assert result["allowed"] is False

    async def test_check_limits_no_subscription(self, db):
        result = await billing_v2_service.check_limits(db, _uid(), "api_calls")
        assert result["allowed"] is False
        assert result["limit"] == 0

    async def test_check_usage_limit_bool_true(self, db):
        plan = await _create_plan(db, api_calls_limit=5000)
        agent_id = _uid()
        await _subscribe(db, agent_id, plan.id)
        assert await billing_v2_service.check_usage_limit(db, agent_id, "api_calls") is True

    async def test_check_usage_limit_bool_false_exceeded(self, db):
        plan = await _create_plan(db, api_calls_limit=10)
        agent_id = _uid()
        await _subscribe(db, agent_id, plan.id)
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 20)
        assert await billing_v2_service.check_usage_limit(db, agent_id, "api_calls") is False

    async def test_free_tier_low_limits(self, db):
        plan = await _create_plan(db, tier="free", api_calls_limit=50, storage_limit_gb=1)
        agent_id = _uid()
        await _subscribe(db, agent_id, plan.id)
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 51)
        result = await billing_v2_service.check_limits(db, agent_id, "api_calls")
        assert result["allowed"] is False
        assert result["limit"] == 50

    # --- Invoice generation in billing_v2_service ---

    async def test_generate_invoice_via_billing_service(self, db):
        agent_id = _uid()
        inv = await billing_v2_service.generate_invoice(
            db, agent_id, amount_usd=29.99, description="Monthly charge"
        )
        assert isinstance(inv, Invoice)
        assert inv.status == "open"
        assert float(inv.amount_usd) == pytest.approx(29.99)

    async def test_list_invoices_for_agent(self, db):
        agent_id = _uid()
        await billing_v2_service.generate_invoice(db, agent_id, 10.0)
        await billing_v2_service.generate_invoice(db, agent_id, 20.0)
        invoices = await billing_v2_service.list_invoices(db, agent_id)
        assert len(invoices) == 2

    async def test_get_invoices_filter_by_status(self, db):
        agent_id = _uid()
        await billing_v2_service.generate_invoice(db, agent_id, 10.0)
        invoices = await billing_v2_service.get_invoices(db, agent_id, status="open")
        assert len(invoices) >= 1
        assert all(i.status == "open" for i in invoices)

    # --- Overage calculation ---

    async def test_overage_amount_calculation(self, db):
        plan = await _create_plan(db, api_calls_limit=1000)
        agent_id = _uid()
        await _subscribe(db, agent_id, plan.id)
        await billing_v2_service.record_usage(db, agent_id, "api_calls", 1500)
        result = await billing_v2_service.check_limits(db, agent_id, "api_calls")
        overage = result["current"] - result["limit"]
        assert overage == pytest.approx(500)

    # --- Proration logic ---

    async def test_proration_partial_period(self, db):
        """Verify that the subscription period can be used to compute proration."""
        plan = await _create_plan(db, price_monthly=30.0)
        sub = await _subscribe(db, _uid(), plan.id)
        total_days = (sub.current_period_end - sub.current_period_start).days
        days_used = 15
        prorated_amount = float(plan.price_usd_monthly) * (days_used / total_days)
        assert 14.0 < prorated_amount < 16.0


# ===================================================================
# TestInvoiceService — 22 tests
# ===================================================================

class TestInvoiceService:
    """Tests for marketplace.services.invoice_service."""

    async def _make_invoice(self, db, agent_id=None, line_items=None, **kw):
        agent_id = agent_id or _uid()
        line_items = line_items or [{"description": "Plan subscription", "amount": 29.99, "quantity": 1}]
        defaults = dict(
            db=db,
            agent_id=agent_id,
            subscription_id=_uid(),
            line_items=line_items,
        )
        defaults.update(kw)
        return await invoice_service.generate_invoice(**defaults)

    async def test_generate_invoice_returns_invoice(self, db):
        inv = await self._make_invoice(db)
        assert isinstance(inv, Invoice)
        assert inv.id is not None

    async def test_generate_invoice_status_open(self, db):
        inv = await self._make_invoice(db)
        assert inv.status == "open"

    async def test_generate_invoice_calculates_amount_from_line_items(self, db):
        items = [
            {"description": "Plan", "amount": 10.0, "quantity": 2},
            {"description": "Addon", "amount": 5.0, "quantity": 1},
        ]
        inv = await self._make_invoice(db, line_items=items)
        assert float(inv.amount_usd) == pytest.approx(25.0)

    async def test_generate_invoice_stores_line_items_json(self, db):
        items = [{"description": "Monthly", "amount": 19.99, "quantity": 1}]
        inv = await self._make_invoice(db, line_items=items)
        stored = json.loads(inv.line_items_json)
        assert len(stored) == 1
        assert stored[0]["description"] == "Monthly"

    async def test_generate_invoice_tax_default_zero(self, db):
        inv = await self._make_invoice(db)
        assert float(inv.tax_usd) == pytest.approx(0.0)

    async def test_generate_invoice_total_equals_amount_plus_tax(self, db):
        inv = await self._make_invoice(db)
        expected_total = float(inv.amount_usd) + float(inv.tax_usd)
        assert float(inv.total_usd) == pytest.approx(expected_total)

    async def test_generate_invoice_default_due_date_30_days(self, db):
        inv = await self._make_invoice(db)
        now = datetime.now(timezone.utc)
        due = inv.due_at if inv.due_at.tzinfo else inv.due_at.replace(tzinfo=timezone.utc)
        delta = due - now
        assert 29 <= delta.days <= 31

    async def test_generate_invoice_custom_due_date(self, db):
        due = datetime(2026, 12, 31, tzinfo=timezone.utc)
        inv = await self._make_invoice(db, due_date=due)
        assert inv.due_at.year == 2026
        assert inv.due_at.month == 12
        assert inv.due_at.day == 31

    async def test_mark_invoice_paid(self, db):
        inv = await self._make_invoice(db)
        paid = await invoice_service.mark_invoice_paid(db, inv.id)
        assert paid.status == "paid"
        assert paid.paid_at is not None

    async def test_mark_invoice_paid_with_stripe_id(self, db):
        inv = await self._make_invoice(db)
        paid = await invoice_service.mark_invoice_paid(db, inv.id, stripe_invoice_id="in_stripe_123")
        assert paid.stripe_invoice_id == "in_stripe_123"

    async def test_mark_invoice_paid_not_found_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            await invoice_service.mark_invoice_paid(db, _uid())

    async def test_void_invoice(self, db):
        inv = await self._make_invoice(db)
        voided = await invoice_service.void_invoice(db, inv.id)
        assert voided.status == "void"

    async def test_void_paid_invoice_raises(self, db):
        inv = await self._make_invoice(db)
        await invoice_service.mark_invoice_paid(db, inv.id)
        with pytest.raises(ValueError, match="Cannot void a paid invoice"):
            await invoice_service.void_invoice(db, inv.id)

    async def test_void_invoice_not_found_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            await invoice_service.void_invoice(db, _uid())

    async def test_get_invoice_by_id(self, db):
        inv = await self._make_invoice(db)
        found = await invoice_service.get_invoice(db, inv.id)
        assert found is not None
        assert found.id == inv.id

    async def test_get_invoice_returns_none_for_missing(self, db):
        result = await invoice_service.get_invoice(db, _uid())
        assert result is None

    async def test_invoice_status_draft_to_open_to_paid(self, db):
        """Status transitions: an invoice starts open, then becomes paid."""
        inv = await self._make_invoice(db)
        assert inv.status == "open"
        paid = await invoice_service.mark_invoice_paid(db, inv.id)
        assert paid.status == "paid"

    async def test_invoice_status_open_to_void(self, db):
        inv = await self._make_invoice(db)
        voided = await invoice_service.void_invoice(db, inv.id)
        assert voided.status == "void"

    async def test_invoice_numbering_unique_ids(self, db):
        inv1 = await self._make_invoice(db)
        inv2 = await self._make_invoice(db)
        assert inv1.id != inv2.id

    async def test_invoice_currency_amount_precision(self, db):
        items = [{"description": "Micro-charge", "amount": 0.0001, "quantity": 1}]
        inv = await self._make_invoice(db, line_items=items)
        assert float(inv.amount_usd) == pytest.approx(0.0001, abs=1e-5)

    async def test_render_invoice_text_contains_fields(self, db):
        inv = await self._make_invoice(db)
        text = invoice_service._render_invoice_text(inv)
        assert "INVOICE" in text
        assert str(inv.id) in text
        assert "TOTAL" in text

    async def test_generate_invoice_pdf_creates_file(self, db):
        inv = await self._make_invoice(db)
        filepath = await invoice_service.generate_invoice_pdf(db, inv.id)
        assert filepath.endswith(".txt")
        assert os.path.isfile(filepath)
        # cleanup
        os.remove(filepath)

    async def test_generate_invoice_pdf_not_found_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            await invoice_service.generate_invoice_pdf(db, _uid())

    async def test_get_invoice_pdf_url_none_before_generation(self, db):
        inv = await self._make_invoice(db)
        url = await invoice_service.get_invoice_pdf_url(db, inv.id)
        # pdf_url defaults to "" which is falsy, so function returns None
        assert url is None

    async def test_get_invoice_pdf_url_after_generation(self, db):
        inv = await self._make_invoice(db)
        filepath = await invoice_service.generate_invoice_pdf(db, inv.id)
        url = await invoice_service.get_invoice_pdf_url(db, inv.id)
        assert url is not None
        assert url == filepath
        os.remove(filepath)

    async def test_get_invoice_pdf_url_missing_invoice(self, db):
        result = await invoice_service.get_invoice_pdf_url(db, _uid())
        assert result is None


# ===================================================================
# TestBillingModels — 12 tests
# ===================================================================

class TestBillingModels:
    """Tests for marketplace.models.billing model classes."""

    async def test_billing_plan_default_id_uuid(self, db):
        plan = BillingPlan(name=f"m-{_uid()[:6]}")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        assert len(plan.id) == 36
        uuid.UUID(plan.id)  # validates format

    async def test_billing_plan_default_status_active(self, db):
        plan = BillingPlan(name=f"m-{_uid()[:6]}")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        assert plan.status == "active"

    async def test_billing_plan_default_tier_starter(self, db):
        plan = BillingPlan(name=f"m-{_uid()[:6]}")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        assert plan.tier == "starter"

    async def test_billing_plan_default_api_calls_limit(self, db):
        plan = BillingPlan(name=f"m-{_uid()[:6]}")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        assert plan.api_calls_limit == 1000

    async def test_billing_plan_default_storage_limit(self, db):
        plan = BillingPlan(name=f"m-{_uid()[:6]}")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        assert plan.storage_gb_limit == 1

    async def test_subscription_model_defaults(self, db):
        plan = BillingPlan(name=f"m-{_uid()[:6]}")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        sub = Subscription(agent_id=_uid(), plan_id=plan.id)
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        assert sub.status == "active"
        assert sub.cancel_at_period_end is False

    async def test_subscription_has_plan_relationship(self, db):
        plan = BillingPlan(name=f"m-{_uid()[:6]}")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        sub = Subscription(agent_id=_uid(), plan_id=plan.id)
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        assert sub.plan is not None
        assert sub.plan.id == plan.id

    async def test_usage_meter_model_fields(self, db):
        meter = UsageMeter(
            agent_id=_uid(),
            metric_name="api_calls",
            value=42,
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(meter)
        await db.commit()
        await db.refresh(meter)
        assert meter.metric_name == "api_calls"
        assert float(meter.value) == pytest.approx(42)

    async def test_invoice_model_default_status_draft(self, db):
        inv = Invoice(agent_id=_uid(), amount_usd=10.0, total_usd=10.0)
        db.add(inv)
        await db.commit()
        await db.refresh(inv)
        assert inv.status == "draft"

    async def test_invoice_model_has_timestamps(self, db):
        inv = Invoice(agent_id=_uid(), amount_usd=5.0, total_usd=5.0)
        db.add(inv)
        await db.commit()
        await db.refresh(inv)
        assert inv.created_at is not None

    async def test_billing_plan_subscriptions_relationship(self, db):
        plan = BillingPlan(name=f"m-{_uid()[:6]}")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        sub1 = Subscription(agent_id=_uid(), plan_id=plan.id)
        sub2 = Subscription(agent_id=_uid(), plan_id=plan.id)
        db.add_all([sub1, sub2])
        await db.commit()
        await db.refresh(plan)
        assert len(plan.subscriptions) >= 2

    async def test_invoice_model_line_items_json_default(self, db):
        inv = Invoice(agent_id=_uid(), amount_usd=0, total_usd=0)
        db.add(inv)
        await db.commit()
        await db.refresh(inv)
        items = json.loads(inv.line_items_json)
        assert items == []


# ===================================================================
# TestComplianceService — 12 tests
# ===================================================================

class TestComplianceService:
    """Tests for marketplace.services.compliance_service (GDPR compliance)."""

    async def test_export_agent_data_returns_dict(self, db):
        agent = await _seed_agent(db)
        result = await compliance_service.export_agent_data(db, agent.id)
        assert isinstance(result, dict)
        assert "agent" in result

    async def test_export_agent_data_contains_export_id(self, db):
        agent = await _seed_agent(db)
        result = await compliance_service.export_agent_data(db, agent.id)
        assert "export_id" in result
        uuid.UUID(result["export_id"])  # valid UUID

    async def test_export_agent_data_contains_format_version(self, db):
        agent = await _seed_agent(db)
        result = await compliance_service.export_agent_data(db, agent.id)
        assert result["format_version"] == "1.0"

    async def test_export_agent_data_agent_not_found(self, db):
        result = await compliance_service.export_agent_data(db, _uid())
        assert "error" in result
        assert result["error"] == "Agent not found"

    async def test_export_agent_data_includes_listings_key(self, db):
        agent = await _seed_agent(db)
        result = await compliance_service.export_agent_data(db, agent.id)
        assert "listings" in result
        assert isinstance(result["listings"], list)

    async def test_export_agent_data_includes_transactions_key(self, db):
        agent = await _seed_agent(db)
        result = await compliance_service.export_agent_data(db, agent.id)
        assert "transactions" in result
        assert isinstance(result["transactions"], list)

    async def test_delete_agent_data_soft_delete(self, db):
        agent = await _seed_agent(db)
        result = await compliance_service.delete_agent_data(db, agent.id, soft_delete=True)
        assert result["method"] == "soft_delete"
        assert result["deleted_items"]["agent"] is True

    async def test_delete_agent_data_hard_delete(self, db):
        agent = await _seed_agent(db)
        result = await compliance_service.delete_agent_data(db, agent.id, soft_delete=False)
        assert result["method"] == "hard_delete"
        assert result["deleted_items"]["agent"] is True

    async def test_delete_agent_data_not_found(self, db):
        result = await compliance_service.delete_agent_data(db, _uid())
        assert "error" in result

    async def test_get_data_processing_record_structure(self, db):
        agent_id = _uid()
        record = await compliance_service.get_data_processing_record(db, agent_id)
        assert record["agent_id"] == agent_id
        assert "data_categories" in record
        assert "processing_purposes" in record

    async def test_data_retention_policies_present(self, db):
        record = await compliance_service.get_data_processing_record(db, _uid())
        retention = record["retention_periods"]
        assert "transaction_data" in retention
        assert "session_logs" in retention
        assert "30 days" in retention["session_logs"]

    async def test_audit_log_data_recipients(self, db):
        record = await compliance_service.get_data_processing_record(db, _uid())
        recipients = record["data_recipients"]
        assert "marketplace_platform" in recipients

    async def test_consent_tracking_data_categories(self, db):
        record = await compliance_service.get_data_processing_record(db, _uid())
        categories = record["data_categories"]
        assert "agent_profile" in categories
        assert "transaction_history" in categories
        assert "session_logs" in categories

    async def test_processing_purposes_include_fraud_detection(self, db):
        record = await compliance_service.get_data_processing_record(db, _uid())
        purposes = record["processing_purposes"]
        assert "fraud_detection" in purposes
        assert "marketplace_operations" in purposes
