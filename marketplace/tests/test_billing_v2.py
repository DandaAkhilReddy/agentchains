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
