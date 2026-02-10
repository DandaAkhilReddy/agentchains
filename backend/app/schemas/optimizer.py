"""Optimizer Pydantic v2 schemas."""

from decimal import Decimal
from pydantic import BaseModel, Field
from uuid import UUID


class LumpSum(BaseModel):
    month: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0)


class OptimizerRequest(BaseModel):
    loan_ids: list[UUID] = Field(..., min_length=1)
    monthly_extra: Decimal = Field(Decimal("0"), ge=0)
    lump_sums: list[LumpSum] = Field(default_factory=list)
    strategies: list[str] = Field(default_factory=lambda: ["avalanche", "snowball", "smart_hybrid", "proportional"])
    tax_bracket: Decimal = Field(Decimal("0.30"), ge=0, le=1)
    annual_growth_pct: Decimal = Field(Decimal("0"), ge=0, le=50)


class LoanResultResponse(BaseModel):
    loan_id: str
    bank_name: str
    loan_type: str
    original_balance: Decimal
    payoff_month: int
    months_saved: int


class StrategyResultResponse(BaseModel):
    strategy_name: str
    strategy_description: str
    total_interest_paid: Decimal
    total_months: int
    interest_saved_vs_baseline: Decimal
    months_saved_vs_baseline: int
    payoff_order: list[str]
    loan_results: list[LoanResultResponse]
    debt_free_date_months: int


class OptimizationResponse(BaseModel):
    baseline_total_interest: Decimal
    baseline_total_months: int
    strategies: list[StrategyResultResponse]
    recommended_strategy: str


class QuickCompareRequest(BaseModel):
    loan_ids: list[UUID] = Field(..., min_length=1)
    monthly_extra: Decimal = Field(..., gt=0)


class QuickCompareResponse(BaseModel):
    interest_saved: Decimal
    months_saved: int
    debt_free_months: int


class WhatIfRequest(BaseModel):
    loan_id: UUID
    monthly_extra: Decimal = Field(Decimal("0"), ge=0)
    lump_sum: Decimal = Field(Decimal("0"), ge=0)
    lump_sum_month: int = Field(1, gt=0)


class WhatIfResponse(BaseModel):
    original_interest: Decimal
    new_interest: Decimal
    interest_saved: Decimal
    original_months: int
    new_months: int
    months_saved: int


class SavePlanRequest(BaseModel):
    name: str = Field(..., max_length=100)
    strategy: str
    config: dict
    results: dict


class TaxImpactRequest(BaseModel):
    annual_income: Decimal = Field(..., gt=0)


class TaxImpactResponse(BaseModel):
    old_regime_tax: Decimal
    new_regime_tax: Decimal
    recommended: str
    savings: Decimal
    explanation: str
    deductions: dict


class SensitivityRequest(BaseModel):
    loan_ids: list[UUID] = Field(..., min_length=1)
    monthly_extra: Decimal = Field(Decimal("0"), ge=0)
    lump_sums: list[LumpSum] = Field(default_factory=list)
    strategy: str = Field("smart_hybrid")
    tax_bracket: Decimal = Field(Decimal("0.30"), ge=0, le=1)
    annual_growth_pct: Decimal = Field(Decimal("0"), ge=0, le=50)
    rate_deltas: list[float] = Field(default_factory=lambda: [-1.0, 0.0, 1.0, 2.0])


class SensitivityPointResponse(BaseModel):
    rate_delta_pct: float
    total_interest_paid: Decimal
    total_months: int
    interest_saved_vs_baseline: Decimal


class SensitivityResponse(BaseModel):
    strategy_name: str
    points: list[SensitivityPointResponse]
