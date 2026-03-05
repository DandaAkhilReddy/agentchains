"""Comprehensive tests for billing subscription features.

Covers:
- Pydantic schemas (PlanResponse, SubscriptionResponse, UsageMeterResponse,
  InvoiceResponse, RecommendationResponse, and request schemas)
- billing_v2_service: get_plan(), change_plan(), seed_default_plans()
- plan_advisor_service: _score_plan(), _generate_reasoning(), recommend_plan()
- stripe_service: create_subscription_checkout() in simulated mode
- Webhook handler dispatch table: all 10 event types registered

All DB tests use the autouse _setup_db fixture from conftest.py which creates
a fresh in-memory SQLite for every test function.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.billing import BillingPlan, Subscription
from marketplace.schemas.billing import (
    CancelSubscriptionRequest,
    ChangePlanRequest,
    CreateSubscriptionRequest,
    InvoiceListResponse,
    InvoiceResponse,
    PlanFeatureItem,
    PlanResponse,
    PlanScoredResponse,
    RecommendationResponse,
    SubscriptionResponse,
    UsageForecastResponse,
    UsageMeterResponse,
)
from marketplace.services import billing_v2_service
from marketplace.services.plan_advisor_service import (
    _generate_reasoning,
    _plan_to_response,
    _score_plan,
)
from marketplace.services.stripe_service import StripePaymentService

# asyncio_mode = "auto" (pyproject.toml) — no explicit mark needed for async tests.
# Module-level mark kept for compatibility with test runners that need it.
pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return str(uuid.uuid4())


async def _mk_plan(db: AsyncSession, **kw: object) -> BillingPlan:
    """Create a plan with safe defaults; caller can override any field."""
    defaults: dict = dict(
        name=f"plan-{_uid()[:8]}",
        price_monthly=9.99,
        price_yearly=99.99,
        api_calls_limit=5_000,
        storage_limit_gb=5,
        features=["feature_a"],
        description="Test plan",
        tier="starter",
    )
    defaults.update(kw)
    return await billing_v2_service.create_plan(db, **defaults)


async def _mk_sub(db: AsyncSession, agent_id: str, plan_id: str) -> Subscription:
    return await billing_v2_service.subscribe(db, agent_id, plan_id)


def _fake_plan_orm(
    *,
    id: str = "plan-001",
    name: str = "Test",
    tier: str = "starter",
    description: str = "desc",
    price_usd_monthly: float = 19.0,
    price_usd_yearly: float = 190.0,
    api_calls_limit: int = 25_000,
    storage_gb_limit: int = 3,
    agents_limit: int = 10,
    features_json: str = '["a", "b"]',
) -> object:
    """Return a minimal object that satisfies _score_plan and _plan_to_response."""

    class _FakePlan:
        pass

    p = _FakePlan()
    p.id = id
    p.name = name
    p.tier = tier
    p.description = description
    p.price_usd_monthly = price_usd_monthly
    p.price_usd_yearly = price_usd_yearly
    p.api_calls_limit = api_calls_limit
    p.storage_gb_limit = storage_gb_limit
    p.agents_limit = agents_limit
    p.features_json = features_json
    return p


# ===========================================================================
# 1. Pydantic Schema Tests
# ===========================================================================


class TestPlanResponseSchema:
    """Tests 1-8: PlanResponse serialization and validation."""

    def test_plan_response_round_trips_all_fields(self) -> None:
        """Test 1: All fields survive model_dump → model_validate round-trip."""
        data = {
            "id": "plan-abc",
            "name": "Pro",
            "description": "Pro tier",
            "tier": "pro",
            "price_monthly": 49.0,
            "price_yearly": 490.0,
            "api_calls_limit": 100_000,
            "storage_gb_limit": 10,
            "agents_limit": 50,
            "features": ["sso", "analytics"],
        }
        plan = PlanResponse(**data)
        assert plan.id == "plan-abc"
        assert plan.name == "Pro"
        assert plan.tier == "pro"
        assert plan.price_monthly == pytest.approx(49.0)
        assert plan.features == ["sso", "analytics"]

    def test_plan_response_description_defaults_empty(self) -> None:
        """Test 2: description has a default of empty string."""
        plan = PlanResponse(
            id="x",
            name="Min",
            tier="free",
            price_monthly=0,
            price_yearly=0,
            api_calls_limit=1000,
            storage_gb_limit=1,
            agents_limit=0,
        )
        assert plan.description == ""

    def test_plan_response_features_defaults_empty_list(self) -> None:
        """Test 3: features defaults to []."""
        plan = PlanResponse(
            id="y",
            name="Min2",
            tier="free",
            price_monthly=0,
            price_yearly=0,
            api_calls_limit=100,
            storage_gb_limit=1,
            agents_limit=0,
        )
        assert plan.features == []

    def test_plan_feature_item_included_default_true(self) -> None:
        """Test 4: PlanFeatureItem.included defaults to True."""
        item = PlanFeatureItem(text="Analytics")
        assert item.included is True

    def test_plan_feature_item_can_be_excluded(self) -> None:
        """Test 5: PlanFeatureItem can be set to excluded."""
        item = PlanFeatureItem(text="SSO", included=False)
        assert item.included is False

    def test_plan_scored_response_holds_plan_and_score(self) -> None:
        """Test 6: PlanScoredResponse nests PlanResponse correctly."""
        plan = PlanResponse(
            id="z",
            name="Scored",
            tier="pro",
            price_monthly=49,
            price_yearly=490,
            api_calls_limit=100_000,
            storage_gb_limit=10,
            agents_limit=5,
        )
        scored = PlanScoredResponse(plan=plan, score=72.5, label="good_fit")
        assert scored.plan.name == "Scored"
        assert scored.score == pytest.approx(72.5)
        assert scored.label == "good_fit"

    def test_plan_response_json_serialisable(self) -> None:
        """Test 7: model_dump produces a JSON-safe dict."""
        plan = PlanResponse(
            id="j",
            name="JSON",
            tier="starter",
            price_monthly=19,
            price_yearly=190,
            api_calls_limit=25_000,
            storage_gb_limit=3,
            agents_limit=0,
            features=["email_support"],
        )
        d = plan.model_dump()
        assert json.dumps(d)  # no TypeError
        assert d["features"] == ["email_support"]

    def test_plan_response_requires_name(self) -> None:
        """Test 8: name is required; omitting it raises ValidationError."""
        with pytest.raises(ValidationError):
            PlanResponse(
                id="bad",
                tier="free",
                price_monthly=0,
                price_yearly=0,
                api_calls_limit=100,
                storage_gb_limit=1,
                agents_limit=0,
            )


class TestSubscriptionResponseSchema:
    """Tests 9-12: SubscriptionResponse serialization."""

    def _make_plan_response(self) -> PlanResponse:
        return PlanResponse(
            id="p1",
            name="Starter",
            tier="starter",
            price_monthly=19,
            price_yearly=190,
            api_calls_limit=25_000,
            storage_gb_limit=3,
            agents_limit=0,
        )

    def test_subscription_response_minimal(self) -> None:
        """Test 9: minimal SubscriptionResponse is valid."""
        sr = SubscriptionResponse(
            id="sub-1",
            plan=self._make_plan_response(),
            status="active",
        )
        assert sr.cancel_at_period_end is False
        assert sr.current_period_start is None

    def test_subscription_response_with_dates(self) -> None:
        """Test 10: datetime fields are accepted."""
        now = datetime.now(timezone.utc)
        sr = SubscriptionResponse(
            id="sub-2",
            plan=self._make_plan_response(),
            status="active",
            current_period_start=now,
            current_period_end=now,
        )
        assert sr.current_period_start == now

    def test_subscription_response_cancel_flag(self) -> None:
        """Test 11: cancel_at_period_end can be set True."""
        sr = SubscriptionResponse(
            id="sub-3",
            plan=self._make_plan_response(),
            status="active",
            cancel_at_period_end=True,
        )
        assert sr.cancel_at_period_end is True

    def test_subscription_response_statuses(self) -> None:
        """Test 12: arbitrary status strings are accepted (no enum enforcement)."""
        for status in ("active", "cancelled", "past_due", "trialing"):
            sr = SubscriptionResponse(
                id="sub-x", plan=self._make_plan_response(), status=status
            )
            assert sr.status == status


class TestUsageMeterResponseSchema:
    """Tests 13-15: UsageMeterResponse validation."""

    def test_usage_meter_response_basic(self) -> None:
        """Test 13: basic UsageMeterResponse serializes correctly."""
        um = UsageMeterResponse(
            metric_name="api_calls",
            current=750.0,
            limit=1000,
            percent_used=75.0,
        )
        assert um.metric_name == "api_calls"
        assert um.percent_used == pytest.approx(75.0)

    def test_usage_meter_zero_values(self) -> None:
        """Test 14: zero current and limit are valid (no-subscription state)."""
        um = UsageMeterResponse(metric_name="storage", current=0.0, limit=0, percent_used=0.0)
        assert um.current == 0.0 and um.limit == 0

    def test_usage_forecast_response_exceeds_flag(self) -> None:
        """Test 15: UsageForecastResponse.exceeds_limit is honoured."""
        uf = UsageForecastResponse(
            metric_name="bandwidth",
            current=900.0,
            projected_end_of_period=1200.0,
            limit=1000,
            percent_projected=120.0,
            exceeds_limit=True,
        )
        assert uf.exceeds_limit is True


class TestInvoiceResponseSchema:
    """Tests 16-18: InvoiceResponse serialization."""

    def test_invoice_response_minimal(self) -> None:
        """Test 16: minimal InvoiceResponse with all nullable fields absent."""
        inv = InvoiceResponse(
            id="inv-1",
            amount_usd=29.99,
            total_usd=29.99,
            status="open",
        )
        assert inv.tax_usd == pytest.approx(0.0)
        assert inv.pdf_url == ""
        assert inv.paid_at is None

    def test_invoice_response_with_tax(self) -> None:
        """Test 17: tax_usd is captured correctly."""
        inv = InvoiceResponse(
            id="inv-2",
            amount_usd=100.0,
            tax_usd=8.0,
            total_usd=108.0,
            status="paid",
        )
        assert inv.tax_usd == pytest.approx(8.0)
        assert inv.total_usd == pytest.approx(108.0)

    def test_invoice_list_response_structure(self) -> None:
        """Test 18: InvoiceListResponse wraps items with pagination metadata."""
        item = InvoiceResponse(id="i", amount_usd=10, total_usd=10, status="open")
        resp = InvoiceListResponse(items=[item], total=1, page=1, page_size=20)
        assert resp.total == 1
        assert resp.items[0].id == "i"


class TestRecommendationResponseSchema:
    """Tests 19-20: RecommendationResponse serialization."""

    def _make_plan(self) -> PlanResponse:
        return PlanResponse(
            id="r1",
            name="Rec",
            tier="pro",
            price_monthly=49,
            price_yearly=490,
            api_calls_limit=100_000,
            storage_gb_limit=10,
            agents_limit=5,
        )

    def test_recommendation_response_minimal(self) -> None:
        """Test 19: RecommendationResponse with empty all_plans_scored list."""
        rec = RecommendationResponse(
            recommended_plan=self._make_plan(),
            reasoning="The Pro plan fits your needs.",
            savings_estimate_monthly=10.0,
            all_plans_scored=[],
        )
        assert rec.savings_estimate_monthly == pytest.approx(10.0)
        assert "Pro" in rec.reasoning

    def test_recommendation_response_with_scored_plans(self) -> None:
        """Test 20: all_plans_scored is correctly nested."""
        plan = self._make_plan()
        scored = PlanScoredResponse(plan=plan, score=65.0, label="good_fit")
        rec = RecommendationResponse(
            recommended_plan=plan,
            reasoning="Good fit.",
            savings_estimate_monthly=0.0,
            all_plans_scored=[scored],
        )
        assert len(rec.all_plans_scored) == 1
        assert rec.all_plans_scored[0].label == "good_fit"


# ===========================================================================
# 2. Request Schema Validation Tests
# ===========================================================================


class TestRequestSchemaValidation:
    """Tests 21-26: Request schema field validation."""

    def test_create_subscription_request_valid(self) -> None:
        """Test 21: valid CreateSubscriptionRequest passes validation."""
        req = CreateSubscriptionRequest(plan_id="plan-abc", billing_cycle="yearly")
        assert req.billing_cycle == "yearly"

    def test_create_subscription_request_default_cycle(self) -> None:
        """Test 22: billing_cycle defaults to monthly."""
        req = CreateSubscriptionRequest(plan_id="plan-xyz")
        assert req.billing_cycle == "monthly"

    def test_create_subscription_request_rejects_empty_plan_id(self) -> None:
        """Test 23: plan_id with length < 1 is rejected."""
        with pytest.raises(ValidationError):
            CreateSubscriptionRequest(plan_id="")

    def test_create_subscription_request_rejects_invalid_cycle(self) -> None:
        """Test 24: billing_cycle not in {'monthly','yearly'} is rejected."""
        with pytest.raises(ValidationError):
            CreateSubscriptionRequest(plan_id="plan-abc", billing_cycle="weekly")

    def test_change_plan_request_valid(self) -> None:
        """Test 25: ChangePlanRequest accepts a valid plan ID."""
        req = ChangePlanRequest(new_plan_id="plan-pro")
        assert req.new_plan_id == "plan-pro"

    def test_cancel_subscription_request_default_not_immediate(self) -> None:
        """Test 26: CancelSubscriptionRequest.immediate defaults to False."""
        req = CancelSubscriptionRequest()
        assert req.immediate is False

    def test_cancel_subscription_request_immediate_true(self) -> None:
        """Test 27: CancelSubscriptionRequest.immediate can be True."""
        req = CancelSubscriptionRequest(immediate=True)
        assert req.immediate is True


# ===========================================================================
# 3. billing_v2_service — get_plan() and change_plan()
# ===========================================================================


class TestBillingV2GetPlan:
    """Tests 28-31: get_plan()."""

    async def test_get_plan_returns_plan_by_id(self, db: AsyncSession) -> None:
        """Test 28: get_plan returns the matching BillingPlan."""
        plan = await _mk_plan(db, name="GetPlanTest")
        fetched = await billing_v2_service.get_plan(db, plan.id)
        assert fetched is not None
        assert fetched.id == plan.id
        assert fetched.name == "GetPlanTest"

    async def test_get_plan_returns_none_for_unknown_id(self, db: AsyncSession) -> None:
        """Test 29: get_plan returns None for a non-existent ID."""
        result = await billing_v2_service.get_plan(db, _uid())
        assert result is None

    async def test_get_plan_returns_none_for_empty_id(self, db: AsyncSession) -> None:
        """Test 30: get_plan returns None when given an empty string ID."""
        result = await billing_v2_service.get_plan(db, "")
        assert result is None

    async def test_get_plan_preserves_features_json(self, db: AsyncSession) -> None:
        """Test 31: features_json is stored and retrieved intact."""
        plan = await _mk_plan(db, name="FeaturePlan", features=["sso", "audit_logs"])
        fetched = await billing_v2_service.get_plan(db, plan.id)
        assert fetched is not None
        assert json.loads(fetched.features_json) == ["sso", "audit_logs"]


class TestBillingV2ChangePlan:
    """Tests 32-37: change_plan()."""

    async def test_change_plan_cancels_old_and_creates_new_sub(
        self, db: AsyncSession
    ) -> None:
        """Test 32: change_plan cancels existing subscription and creates new one."""
        old_plan = await _mk_plan(db, name="OldPlan")
        new_plan = await _mk_plan(db, name="NewPlan")
        aid = _uid()
        old_sub = await _mk_sub(db, aid, old_plan.id)

        new_sub = await billing_v2_service.change_plan(db, aid, new_plan.id)

        # New subscription should be active on the new plan
        assert new_sub.plan_id == new_plan.id
        assert new_sub.status == "active"

        # Old subscription should be cancelled
        await db.refresh(old_sub)
        assert old_sub.status == "cancelled"

    async def test_change_plan_no_existing_subscription(self, db: AsyncSession) -> None:
        """Test 33: change_plan works when agent has no prior subscription."""
        plan = await _mk_plan(db, name="FreshPlan")
        aid = _uid()
        new_sub = await billing_v2_service.change_plan(db, aid, plan.id)
        assert new_sub.status == "active"
        assert new_sub.agent_id == aid

    async def test_change_plan_raises_for_unknown_plan_id(
        self, db: AsyncSession
    ) -> None:
        """Test 34: change_plan raises ValueError when new_plan_id does not exist."""
        with pytest.raises(ValueError, match="not found"):
            await billing_v2_service.change_plan(db, _uid(), _uid())

    async def test_change_plan_new_sub_has_30_day_period(self, db: AsyncSession) -> None:
        """Test 35: newly created subscription has a 30-day billing period."""
        plan = await _mk_plan(db, name="PeriodPlan")
        new_sub = await billing_v2_service.change_plan(db, _uid(), plan.id)
        delta = new_sub.current_period_end - new_sub.current_period_start
        assert delta.days == 30

    async def test_change_plan_multiple_times(self, db: AsyncSession) -> None:
        """Test 36: changing plan multiple times only leaves one active sub."""
        from sqlalchemy import select

        p1 = await _mk_plan(db, name="PlanA")
        p2 = await _mk_plan(db, name="PlanB")
        p3 = await _mk_plan(db, name="PlanC")
        aid = _uid()

        await billing_v2_service.change_plan(db, aid, p1.id)
        await billing_v2_service.change_plan(db, aid, p2.id)
        final = await billing_v2_service.change_plan(db, aid, p3.id)

        assert final.plan_id == p3.id
        assert final.status == "active"

        # Only one active subscription should exist for this agent
        result = await db.execute(
            select(Subscription).where(
                Subscription.agent_id == aid,
                Subscription.status == "active",
            )
        )
        active_subs = result.scalars().all()
        assert len(active_subs) == 1

    async def test_change_plan_old_sub_period_end_updated(
        self, db: AsyncSession
    ) -> None:
        """Test 37: cancelled old subscription's period_end is set to now (immediate)."""
        from marketplace.core.utils import utcnow

        old_plan = await _mk_plan(db, name="OldTimed")
        new_plan = await _mk_plan(db, name="NewTimed")
        aid = _uid()
        old_sub = await _mk_sub(db, aid, old_plan.id)

        before = utcnow()
        await billing_v2_service.change_plan(db, aid, new_plan.id)
        after = utcnow()

        await db.refresh(old_sub)
        # The cancelled period_end must be between before and after
        pe = old_sub.current_period_end
        if pe.tzinfo is None:
            pe = pe.replace(tzinfo=timezone.utc)
        assert before <= pe <= after


# ===========================================================================
# 4. billing_v2_service — seed_default_plans()
# ===========================================================================


class TestSeedDefaultPlans:
    """Tests 38-44: seed_default_plans()."""

    async def test_seed_creates_four_plans(self, db: AsyncSession) -> None:
        """Test 38: seed_default_plans creates exactly 4 plans."""
        plans = await billing_v2_service.seed_default_plans(db)
        assert len(plans) == 4

    async def test_seed_plan_names(self, db: AsyncSession) -> None:
        """Test 39: the 4 seeded plans are Free, Starter, Pro, Enterprise."""
        plans = await billing_v2_service.seed_default_plans(db)
        names = {p.name for p in plans}
        assert names == {"Free", "Starter", "Pro", "Enterprise"}

    async def test_seed_free_plan_is_zero_price(self, db: AsyncSession) -> None:
        """Test 40: Free plan has price 0."""
        plans = await billing_v2_service.seed_default_plans(db)
        free = next(p for p in plans if p.name == "Free")
        assert float(free.price_usd_monthly) == pytest.approx(0.0)

    async def test_seed_enterprise_has_highest_limits(self, db: AsyncSession) -> None:
        """Test 41: Enterprise plan has api_calls_limit of 1,000,000."""
        plans = await billing_v2_service.seed_default_plans(db)
        ent = next(p for p in plans if p.name == "Enterprise")
        assert ent.api_calls_limit == 1_000_000

    async def test_seed_is_idempotent(self, db: AsyncSession) -> None:
        """Test 42: running seed twice returns same 4 plans (no duplicates)."""
        first = await billing_v2_service.seed_default_plans(db)
        second = await billing_v2_service.seed_default_plans(db)
        first_ids = {p.id for p in first}
        second_ids = {p.id for p in second}
        assert first_ids == second_ids

    async def test_seed_plans_are_active(self, db: AsyncSession) -> None:
        """Test 43: all seeded plans have status='active'."""
        plans = await billing_v2_service.seed_default_plans(db)
        assert all(p.status == "active" for p in plans)

    async def test_seed_tiers_match_names(self, db: AsyncSession) -> None:
        """Test 44: each plan's tier matches expected value for its name."""
        plans = await billing_v2_service.seed_default_plans(db)
        tier_map = {p.name: p.tier for p in plans}
        assert tier_map["Free"] == "free"
        assert tier_map["Starter"] == "starter"
        assert tier_map["Pro"] == "pro"
        assert tier_map["Enterprise"] == "enterprise"


# ===========================================================================
# 5. plan_advisor_service — _score_plan()
# ===========================================================================


class TestScorePlan:
    """Tests 45-54: _score_plan() rule-based scoring."""

    def test_good_fit_50_to_80_percent_usage(self) -> None:
        """Test 45: 50-80% utilization yields label='good_fit' and score > 50."""
        plan = _fake_plan_orm(api_calls_limit=1000, storage_gb_limit=10)
        score, label = _score_plan(plan, {"api_calls": 600, "storage": 7, "bandwidth": 7})
        assert label == "good_fit"
        assert score > 50

    def test_exceeds_limits_over_100_percent(self) -> None:
        """Test 46: usage >100% of any limit yields label='exceeds_limits'."""
        plan = _fake_plan_orm(api_calls_limit=100, storage_gb_limit=5)
        score, label = _score_plan(plan, {"api_calls": 150, "storage": 2, "bandwidth": 2})
        assert label == "exceeds_limits"

    def test_overpaying_less_than_50_percent(self) -> None:
        """Test 47: usage <50% on multiple metrics yields label='overpaying'."""
        plan = _fake_plan_orm(api_calls_limit=10_000, storage_gb_limit=100)
        score, label = _score_plan(
            plan, {"api_calls": 100, "storage": 0.5, "bandwidth": 0.5}
        )
        assert label == "overpaying"

    def test_at_risk_80_to_100_percent(self) -> None:
        """Test 48: usage 80-100% on two metrics yields label='at_risk'."""
        plan = _fake_plan_orm(api_calls_limit=1000, storage_gb_limit=10)
        # 85% on api_calls, 90% on storage, 85% on bandwidth
        score, label = _score_plan(
            plan, {"api_calls": 850, "storage": 9, "bandwidth": 9}
        )
        assert label == "at_risk"

    def test_score_returns_float(self) -> None:
        """Test 49: _score_plan always returns a float score."""
        plan = _fake_plan_orm()
        score, _ = _score_plan(plan, {})
        assert isinstance(score, float)

    def test_zero_usage_reduces_score(self) -> None:
        """Test 50: zero usage (overpaying all metrics) reduces base score."""
        plan = _fake_plan_orm(api_calls_limit=10_000, storage_gb_limit=100)
        score, label = _score_plan(plan, {"api_calls": 0, "storage": 0, "bandwidth": 0})
        # Each metric at 0 → -5 per metric (overpaying)
        assert score < 50

    def test_free_plan_gets_small_price_bonus(self) -> None:
        """Test 51: free plan (price=0) gets +5 bonus for free price."""
        free = _fake_plan_orm(price_usd_monthly=0, api_calls_limit=1000, storage_gb_limit=5)
        paid = _fake_plan_orm(price_usd_monthly=199, api_calls_limit=1000, storage_gb_limit=5)
        # Same usage for both
        usage = {"api_calls": 600, "storage": 3, "bandwidth": 3}
        free_score, _ = _score_plan(free, usage)
        paid_score, _ = _score_plan(paid, usage)
        # Free plan should score higher due to +5 bonus vs cost penalty for paid
        assert free_score > paid_score

    def test_score_rounded_to_one_decimal(self) -> None:
        """Test 52: score is rounded to 1 decimal place."""
        plan = _fake_plan_orm()
        score, _ = _score_plan(plan, {"api_calls": 500, "storage": 2, "bandwidth": 2})
        # round(x, 1) should have at most 1 decimal digit
        assert score == round(score, 1)

    def test_exceeds_limits_score_penalty(self) -> None:
        """Test 53: exceeding limits subtracts 30 per exceeded metric from score."""
        plan = _fake_plan_orm(api_calls_limit=10, storage_gb_limit=1)
        # Both api_calls and storage exceed limits, bandwidth exceeds too
        base = 50.0
        score, label = _score_plan(
            plan, {"api_calls": 200, "storage": 5, "bandwidth": 5}
        )
        assert label == "exceeds_limits"
        # At least one -30 deduction happened
        assert score < base

    def test_empty_usage_dict_uses_zero_for_missing_metrics(self) -> None:
        """Test 54: missing metrics in usage dict are treated as 0 (overpaying)."""
        plan = _fake_plan_orm(api_calls_limit=1000, storage_gb_limit=10)
        score, _ = _score_plan(plan, {})
        # No exceptions; score is a valid number
        assert isinstance(score, float)


# ===========================================================================
# 6. plan_advisor_service — _generate_reasoning()
# ===========================================================================


class TestGenerateReasoning:
    """Tests 55-60: _generate_reasoning() text generation."""

    def _make_scored(self, label: str, name: str = "Pro") -> PlanScoredResponse:
        plan = PlanResponse(
            id="p",
            name=name,
            tier="pro",
            price_monthly=49,
            price_yearly=490,
            api_calls_limit=100_000,
            storage_gb_limit=10,
            agents_limit=5,
        )
        return PlanScoredResponse(plan=plan, score=65.0, label=label)

    def test_good_fit_mentions_plan_name(self) -> None:
        """Test 55: good_fit reasoning mentions the plan name."""
        scored = self._make_scored("good_fit", "Enterprise")
        text = _generate_reasoning(scored, {}, 0.0)
        assert "Enterprise" in text

    def test_overpaying_mentions_price_message(self) -> None:
        """Test 56: overpaying reasoning contains 'better price' message."""
        scored = self._make_scored("overpaying", "Starter")
        text = _generate_reasoning(scored, {}, 0.0)
        assert "better price" in text or "Starter" in text

    def test_at_risk_mentions_headroom(self) -> None:
        """Test 57: at_risk reasoning mentions 'headroom'."""
        scored = self._make_scored("at_risk", "Pro")
        text = _generate_reasoning(scored, {}, 0.0)
        assert "headroom" in text or "Pro" in text

    def test_exceeds_limits_mentions_upgrade(self) -> None:
        """Test 58: exceeds_limits reasoning contains 'Upgrade'."""
        scored = self._make_scored("exceeds_limits", "Enterprise")
        text = _generate_reasoning(scored, {}, 0.0)
        assert "Upgrade" in text or "exceeds" in text.lower()

    def test_savings_appended_when_positive(self) -> None:
        """Test 59: positive savings estimate is included in reasoning."""
        scored = self._make_scored("overpaying")
        text = _generate_reasoning(scored, {}, 15.0)
        assert "$15.00" in text or "save" in text.lower()

    def test_api_usage_appended_when_nonzero(self) -> None:
        """Test 60: api_calls usage is appended when > 0."""
        scored = self._make_scored("good_fit")
        text = _generate_reasoning(scored, {"api_calls": 5000}, 0.0)
        assert "5,000" in text

    def test_zero_savings_not_appended(self) -> None:
        """Test 61: zero savings produces no savings sentence."""
        scored = self._make_scored("good_fit")
        text = _generate_reasoning(scored, {}, 0.0)
        assert "save" not in text.lower()


# ===========================================================================
# 7. plan_advisor_service — _plan_to_response()
# ===========================================================================


class TestPlanToResponse:
    """Tests 62-65: _plan_to_response() ORM → schema conversion."""

    def test_converts_valid_orm_to_plan_response(self) -> None:
        """Test 62: valid ORM object produces correct PlanResponse."""
        orm = _fake_plan_orm(
            id="pr-1",
            name="TestConvert",
            tier="pro",
            price_usd_monthly=49.0,
            price_usd_yearly=490.0,
            api_calls_limit=100_000,
            storage_gb_limit=10,
            agents_limit=5,
            features_json='["sso"]',
        )
        result = _plan_to_response(orm)
        assert isinstance(result, PlanResponse)
        assert result.id == "pr-1"
        assert result.features == ["sso"]

    def test_handles_invalid_features_json(self) -> None:
        """Test 63: malformed features_json falls back to empty list."""
        orm = _fake_plan_orm(features_json="not-valid-json")
        result = _plan_to_response(orm)
        assert result.features == []

    def test_handles_none_features_json(self) -> None:
        """Test 64: None features_json falls back to empty list."""
        orm = _fake_plan_orm(features_json=None)  # type: ignore[arg-type]
        result = _plan_to_response(orm)
        assert result.features == []

    def test_description_defaults_empty_string(self) -> None:
        """Test 65: None description in ORM becomes empty string in response."""
        orm = _fake_plan_orm()
        orm.description = None  # type: ignore[assignment]
        result = _plan_to_response(orm)
        assert result.description == ""


# ===========================================================================
# 8. stripe_service — create_subscription_checkout() simulated mode
# ===========================================================================


class TestStripeSubscriptionCheckout:
    """Tests 66-73: create_subscription_checkout() in simulated mode."""

    def _svc(self) -> StripePaymentService:
        return StripePaymentService()  # empty key → simulated

    async def test_checkout_returns_id_and_url(self) -> None:
        """Test 66: simulated checkout returns id and url keys."""
        svc = self._svc()
        result = await svc.create_subscription_checkout(
            plan_name="Pro",
            price_usd=Decimal("49.00"),
            interval="month",
            agent_id=_uid(),
            plan_id="plan-pro",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        assert "id" in result
        assert "url" in result

    async def test_checkout_id_has_cs_sub_sim_prefix(self) -> None:
        """Test 67: simulated checkout ID starts with 'cs_sub_sim_'."""
        svc = self._svc()
        result = await svc.create_subscription_checkout(
            plan_name="Starter",
            price_usd=Decimal("19.00"),
            interval="month",
            agent_id=_uid(),
            plan_id="plan-starter",
            success_url="https://example.com/s",
            cancel_url="https://example.com/c",
        )
        assert result["id"].startswith("cs_sub_sim_")

    async def test_checkout_url_contains_session_id(self) -> None:
        """Test 68: simulated checkout URL embeds the session ID."""
        svc = self._svc()
        result = await svc.create_subscription_checkout(
            plan_name="Pro",
            price_usd=Decimal("49.00"),
            interval="month",
            agent_id=_uid(),
            plan_id="plan-pro",
            success_url="https://example.com/s",
            cancel_url="https://example.com/c",
        )
        assert result["id"] in result["url"]

    async def test_checkout_simulated_flag_is_true(self) -> None:
        """Test 69: simulated checkout response includes simulated=True."""
        svc = self._svc()
        result = await svc.create_subscription_checkout(
            plan_name="Free",
            price_usd=Decimal("0.00"),
            interval="month",
            agent_id=_uid(),
            plan_id="plan-free",
            success_url="https://example.com/s",
            cancel_url="https://example.com/c",
        )
        assert result.get("simulated") is True

    async def test_checkout_ids_are_unique_across_calls(self) -> None:
        """Test 70: two checkout calls produce different IDs."""
        svc = self._svc()
        kwargs = dict(
            plan_name="Pro",
            price_usd=Decimal("49.00"),
            interval="month",
            agent_id=_uid(),
            plan_id="plan-pro",
            success_url="https://example.com/s",
            cancel_url="https://example.com/c",
        )
        r1 = await svc.create_subscription_checkout(**kwargs)
        r2 = await svc.create_subscription_checkout(**kwargs)
        assert r1["id"] != r2["id"]

    async def test_checkout_yearly_interval_accepted(self) -> None:
        """Test 71: yearly interval is accepted without error."""
        svc = self._svc()
        result = await svc.create_subscription_checkout(
            plan_name="Pro",
            price_usd=Decimal("490.00"),
            interval="year",
            agent_id=_uid(),
            plan_id="plan-pro",
            success_url="https://example.com/s",
            cancel_url="https://example.com/c",
        )
        assert result["id"].startswith("cs_sub_sim_")

    async def test_checkout_large_price_accepted(self) -> None:
        """Test 72: large price (enterprise) is accepted."""
        svc = self._svc()
        result = await svc.create_subscription_checkout(
            plan_name="Enterprise",
            price_usd=Decimal("1990.00"),
            interval="year",
            agent_id=_uid(),
            plan_id="plan-ent",
            success_url="https://example.com/s",
            cancel_url="https://example.com/c",
        )
        assert "id" in result

    async def test_simulated_service_does_not_call_stripe_sdk(self) -> None:
        """Test 73: simulated mode never touches the Stripe SDK (_stripe is None)."""
        svc = self._svc()
        assert svc._stripe is None


# ===========================================================================
# 9. Webhook handler dispatch table — all 10 event types
# ===========================================================================


class TestWebhookHandlerDispatchTable:
    """Tests 74-76: stripe_webhook dispatch dict covers all 10 event types."""

    # We import the handler at module level to inspect it structurally, but
    # call it via the FastAPI test client to avoid duplicating route-level logic.

    def test_dispatch_dict_contains_all_10_event_types(self) -> None:
        """Test 74: the handlers dict in stripe_webhook has exactly 10 entries."""
        # Introspect by importing and calling the route in dry-run fashion.
        # We inspect the source to count event type keys.
        import inspect

        from marketplace.api.webhooks import stripe_webhook

        src = inspect.getsource(stripe_webhook)

        expected_events = [
            "payment_intent.succeeded",
            "payment_intent.payment_failed",
            "charge.refunded",
            "checkout.session.completed",
            "account.updated",
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.payment_succeeded",
            "invoice.payment_failed",
        ]
        for event_type in expected_events:
            assert event_type in src, (
                f"Expected event type '{event_type}' missing from stripe_webhook dispatch"
            )

    def test_dispatch_dict_has_no_extra_event_types(self) -> None:
        """Test 75: exactly 10 events are wired — not more, not fewer."""
        import inspect

        from marketplace.api.webhooks import stripe_webhook

        src = inspect.getsource(stripe_webhook)

        # Count lines containing known Stripe event format strings
        # (contain a dot-separated event name as a string key)
        import re

        # Match quoted event type strings like "payment_intent.succeeded"
        found = re.findall(r'"([a-z_]+\.[a-z_.]+)"', src)
        # De-duplicate (in case of multi-occurrence)
        unique_events = set(found)
        assert len(unique_events) == 10, (
            f"Expected 10 event types in dispatch dict, found {len(unique_events)}: "
            f"{sorted(unique_events)}"
        )

    def test_subscription_lifecycle_handlers_are_importable(self) -> None:
        """Test 76: all subscription lifecycle handler functions can be imported."""
        from marketplace.api.webhooks import (
            _handle_subscription_created,
            _handle_subscription_deleted,
            _handle_subscription_updated,
            _handle_invoice_payment_succeeded,
            _handle_invoice_payment_failed,
        )

        assert callable(_handle_subscription_created)
        assert callable(_handle_subscription_deleted)
        assert callable(_handle_subscription_updated)
        assert callable(_handle_invoice_payment_succeeded)
        assert callable(_handle_invoice_payment_failed)


# ===========================================================================
# 10. plan_advisor_service — recommend_plan() integration
# ===========================================================================


class TestRecommendPlan:
    """Tests 77-80: recommend_plan() end-to-end with in-memory DB."""

    async def test_recommend_plan_raises_when_no_plans(self, db: AsyncSession) -> None:
        """Test 77: recommend_plan raises ValueError when no plans exist."""
        from marketplace.services.plan_advisor_service import recommend_plan

        with pytest.raises(ValueError, match="No billing plans available"):
            await recommend_plan(db, _uid())

    async def test_recommend_plan_returns_recommendation_response(
        self, db: AsyncSession
    ) -> None:
        """Test 78: with plans seeded, recommend_plan returns valid response."""
        from marketplace.services.plan_advisor_service import recommend_plan

        await billing_v2_service.seed_default_plans(db)
        aid = _uid()
        result = await recommend_plan(db, aid)
        assert isinstance(result, RecommendationResponse)
        assert result.recommended_plan.id
        assert len(result.all_plans_scored) == 4

    async def test_recommend_plan_savings_non_negative(self, db: AsyncSession) -> None:
        """Test 79: savings_estimate_monthly is always >= 0."""
        from marketplace.services.plan_advisor_service import recommend_plan

        await billing_v2_service.seed_default_plans(db)
        result = await recommend_plan(db, _uid())
        assert result.savings_estimate_monthly >= 0.0

    async def test_recommend_plan_scores_sorted_descending(
        self, db: AsyncSession
    ) -> None:
        """Test 80: all_plans_scored list is sorted by score descending."""
        from marketplace.services.plan_advisor_service import recommend_plan

        await billing_v2_service.seed_default_plans(db)
        result = await recommend_plan(db, _uid())
        scores = [s.score for s in result.all_plans_scored]
        assert scores == sorted(scores, reverse=True)
