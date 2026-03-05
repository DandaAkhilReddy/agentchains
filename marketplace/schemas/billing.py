"""Pydantic schemas for billing endpoints: plans, subscriptions, usage, invoices."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


class PlanFeatureItem(BaseModel):
    text: str
    included: bool = True


class PlanResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    tier: str
    price_monthly: float
    price_yearly: float
    api_calls_limit: int
    storage_gb_limit: int
    agents_limit: int
    features: list[str] = Field(default_factory=list)


class PlanScoredResponse(BaseModel):
    """Plan with a fit score for recommendation."""

    plan: PlanResponse
    score: float
    label: str  # "good_fit" | "overpaying" | "at_risk" | "exceeds_limits"


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


class SubscriptionResponse(BaseModel):
    id: str
    plan: PlanResponse
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class CreateSubscriptionRequest(BaseModel):
    plan_id: str = Field(..., min_length=1, max_length=36)
    billing_cycle: Literal["monthly", "yearly"] = "monthly"


class ChangePlanRequest(BaseModel):
    new_plan_id: str = Field(..., min_length=1, max_length=36)


class CancelSubscriptionRequest(BaseModel):
    immediate: bool = False


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class UsageMeterResponse(BaseModel):
    metric_name: str
    current: float
    limit: int
    percent_used: float


class UsageForecastResponse(BaseModel):
    metric_name: str
    current: float
    projected_end_of_period: float
    limit: int
    percent_projected: float
    exceeds_limit: bool


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


class InvoiceResponse(BaseModel):
    id: str
    amount_usd: float
    tax_usd: float = 0.0
    total_usd: float
    status: str
    issued_at: datetime | None = None
    due_at: datetime | None = None
    paid_at: datetime | None = None
    pdf_url: str = ""


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


class RecommendationResponse(BaseModel):
    recommended_plan: PlanResponse
    reasoning: str
    savings_estimate_monthly: float
    all_plans_scored: list[PlanScoredResponse]
