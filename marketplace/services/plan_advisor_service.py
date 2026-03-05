"""Plan advisor service: rule-based recommendation engine and usage forecasting."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.utils import utcnow as _utcnow
from marketplace.schemas.billing import (
    PlanScoredResponse,
    RecommendationResponse,
    UsageForecastResponse,
)
from marketplace.services.billing_v2_service import (
    METRICS,
    _current_period_start,
    _period_end_from_start,
    get_plan,
    get_plan_limits,
    get_subscription,
    get_subscription_with_plan,
    get_usage,
    list_plans,
    plan_to_response,
)

logger = logging.getLogger(__name__)


def _score_plan(
    plan: object,
    usage_by_metric: dict[str, float],
) -> tuple[float, str]:
    """Score a plan based on how well it fits current usage.

    Returns (score, label) where higher score = better fit.
    Labels: 'good_fit', 'overpaying', 'at_risk', 'exceeds_limits'.
    """
    score = 50.0  # Base score
    limits = get_plan_limits(plan)

    exceeded = False
    overpaying_count = 0
    at_risk_count = 0
    good_fit_count = 0

    for metric in METRICS:
        current = usage_by_metric.get(metric, 0.0)
        limit = limits.get(metric, 0)

        if limit <= 0:
            continue

        ratio = current / limit

        if ratio > 1.0:
            # Exceeds limits
            score -= 30
            exceeded = True
        elif ratio > 0.8:
            # At risk (80-100%)
            score -= 10
            at_risk_count += 1
        elif ratio >= 0.5:
            # Good fit (50-80%)
            score += 15
            good_fit_count += 1
        else:
            # Overpaying (< 50% utilization)
            score -= 5
            overpaying_count += 1

    # Factor in price efficiency — cheaper plans get a small bonus
    monthly_price = float(plan.price_usd_monthly)
    if monthly_price > 0:
        api_limit = plan.api_calls_limit or 1
        cost_per_1k_calls = (monthly_price / api_limit) * 1000
        # Lower cost per call = higher score (max +10)
        score += max(0, 10 - cost_per_1k_calls)
    else:
        score += 5  # Free plan small bonus

    if exceeded:
        label = "exceeds_limits"
    elif at_risk_count >= 2:
        label = "at_risk"
    elif overpaying_count >= 2:
        label = "overpaying"
    else:
        label = "good_fit"

    return round(score, 1), label


async def recommend_plan(
    db: AsyncSession, agent_id: str
) -> RecommendationResponse:
    """Recommend the best plan for an agent based on usage patterns.

    Rule-based scoring — no LLM dependency.
    """
    # Fetch subscription + plan once for usage gathering
    _, current_plan_obj = await get_subscription_with_plan(db, agent_id)
    current_plan_limits = get_plan_limits(current_plan_obj) if current_plan_obj else {}

    # Gather current usage across metrics (1 query per metric)
    period_start = _current_period_start()
    usage_by_metric: dict[str, float] = {}
    for metric in METRICS:
        usage_records = await get_usage(db, agent_id, metric, period_start)
        usage_by_metric[metric] = sum(float(u.value) for u in usage_records)

    # Score all plans
    plans = await list_plans(db)
    if not plans:
        raise ValueError("No billing plans available")

    scored: list[PlanScoredResponse] = []
    for plan in plans:
        plan_score, label = _score_plan(plan, usage_by_metric)
        scored.append(
            PlanScoredResponse(
                plan=plan_to_response(plan),
                score=plan_score,
                label=label,
            )
        )

    # Sort by score descending — best fit first
    scored.sort(key=lambda s: s.score, reverse=True)
    best = scored[0]

    # Calculate savings estimate vs current plan
    savings = 0.0
    if current_plan_obj:
        current_price = float(current_plan_obj.price_usd_monthly)
        best_price = best.plan.price_monthly
        savings = round(current_price - best_price, 2)

    # Generate reasoning
    reasoning = _generate_reasoning(best, usage_by_metric, savings)

    return RecommendationResponse(
        recommended_plan=best.plan,
        reasoning=reasoning,
        savings_estimate_monthly=max(savings, 0.0),
        all_plans_scored=scored,
    )


def _generate_reasoning(
    best: PlanScoredResponse,
    usage: dict[str, float],
    savings: float,
) -> str:
    """Generate human-readable reasoning for the recommendation."""
    parts: list[str] = []

    if best.label == "good_fit":
        parts.append(
            f"The {best.plan.name} plan is the best fit for your current usage patterns."
        )
    elif best.label == "overpaying":
        parts.append(
            f"You're using less than 50% of your current plan limits. "
            f"The {best.plan.name} plan provides sufficient capacity at a better price."
        )
    elif best.label == "at_risk":
        parts.append(
            f"You're approaching the limits of your current plan. "
            f"The {best.plan.name} plan gives you more headroom."
        )
    elif best.label == "exceeds_limits":
        parts.append(
            f"Your usage exceeds your current plan limits. "
            f"Upgrade to the {best.plan.name} plan to avoid service disruptions."
        )

    api_usage = usage.get("api_calls", 0)
    if api_usage > 0:
        parts.append(
            f"Your API usage is {int(api_usage):,} calls this period "
            f"(plan limit: {best.plan.api_calls_limit:,})."
        )

    if savings > 0:
        parts.append(f"Switching could save you ${savings:.2f}/month.")

    return " ".join(parts)


async def forecast_usage(
    db: AsyncSession, agent_id: str
) -> list[UsageForecastResponse]:
    """Project usage to end of billing period based on current rate.

    Uses linear extrapolation: (current_usage / days_elapsed) * days_in_period.
    """
    now = _utcnow()
    period_start = _current_period_start()
    period_end = _period_end_from_start(period_start)

    days_elapsed = max((now - period_start).days, 1)
    days_in_period = (period_end - period_start).days

    # Fetch subscription + plan once (avoids N+1 from calling check_limits per metric)
    _, plan = await get_subscription_with_plan(db, agent_id)
    limits = get_plan_limits(plan) if plan else {}

    forecasts: list[UsageForecastResponse] = []

    for metric in METRICS:
        usage_records = await get_usage(db, agent_id, metric, period_start)
        current = sum(float(u.value) for u in usage_records)
        limit = limits.get(metric, 0)

        # Linear projection
        daily_rate = current / days_elapsed
        projected = round(daily_rate * days_in_period, 1)
        percent_projected = round((projected / limit) * 100, 1) if limit > 0 else 0.0

        forecasts.append(
            UsageForecastResponse(
                metric_name=metric,
                current=current,
                projected_end_of_period=projected,
                limit=limit,
                percent_projected=percent_projected,
                exceeds_limit=projected > limit,
            )
        )

    return forecasts
