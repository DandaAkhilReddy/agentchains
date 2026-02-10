"""Optimizer routes — multi-loan strategy comparison."""

from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User
from app.db.repositories.loan_repo import LoanRepository
from app.db.repositories.plan_repo import RepaymentPlanRepository
from app.schemas.optimizer import (
    OptimizerRequest, OptimizationResponse, StrategyResultResponse, LoanResultResponse,
    QuickCompareRequest, QuickCompareResponse,
    WhatIfRequest, WhatIfResponse,
    SavePlanRequest, TaxImpactRequest, TaxImpactResponse,
    SensitivityRequest, SensitivityResponse, SensitivityPointResponse,
)
from app.core.strategies import LoanSnapshot
from app.core.optimization import MultiLoanOptimizer
from app.core.financial_math import calculate_total_interest, calculate_interest_saved
from app.core.indian_rules import compare_tax_regimes, LoanTaxInfo
from app.core.usa_rules import compare_standard_vs_itemized, USLoanTaxInfo
from app.core.country_rules import get_tax_bracket

router = APIRouter(prefix="/api/optimizer", tags=["optimizer"])


def _loan_to_snapshot(loan, country: str = "IN") -> LoanSnapshot:
    """Convert DB loan to LoanSnapshot for optimizer."""
    snapshot = LoanSnapshot(
        loan_id=str(loan.id),
        bank_name=loan.bank_name,
        loan_type=loan.loan_type,
        outstanding_principal=Decimal(str(loan.outstanding_principal)),
        interest_rate=Decimal(str(loan.interest_rate)),
        emi_amount=Decimal(str(loan.emi_amount)),
        remaining_tenure_months=loan.remaining_tenure_months,
        prepayment_penalty_pct=Decimal(str(loan.prepayment_penalty_pct)),
        foreclosure_charges_pct=Decimal(str(loan.foreclosure_charges_pct)),
        eligible_80c=loan.eligible_80c,
        eligible_24b=loan.eligible_24b,
        eligible_80e=loan.eligible_80e,
        eligible_80eea=loan.eligible_80eea,
        eligible_mortgage_deduction=loan.eligible_mortgage_deduction,
        eligible_student_loan_deduction=loan.eligible_student_loan_deduction,
    )
    return snapshot


@router.post("/analyze", response_model=OptimizationResponse)
async def analyze(
    req: OptimizerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full multi-loan optimization with all strategies."""
    repo = LoanRepository(db)
    loans = await repo.list_by_user(user.id, status="active")

    selected = [l for l in loans if l.id in [UUID(str(lid)) for lid in req.loan_ids]]
    if not selected:
        raise HTTPException(status_code=400, detail="No matching active loans found")

    country = user.country or "IN"
    snapshots = [_loan_to_snapshot(l, country) for l in selected]
    lump_dict = {ls.month: ls.amount for ls in req.lump_sums}

    optimizer = MultiLoanOptimizer(
        loans=snapshots,
        monthly_extra=req.monthly_extra,
        lump_sums=lump_dict,
        annual_growth_pct=req.annual_growth_pct,
    )
    result = optimizer.optimize(strategies=req.strategies, tax_bracket=req.tax_bracket, country=country)

    return OptimizationResponse(
        baseline_total_interest=result.baseline_total_interest,
        baseline_total_months=result.baseline_total_months,
        strategies=[
            StrategyResultResponse(
                strategy_name=s.strategy_name,
                strategy_description=s.strategy_description,
                total_interest_paid=s.total_interest_paid,
                total_months=s.total_months,
                interest_saved_vs_baseline=s.interest_saved_vs_baseline,
                months_saved_vs_baseline=s.months_saved_vs_baseline,
                payoff_order=s.payoff_order,
                loan_results=[
                    LoanResultResponse(
                        loan_id=lr.loan_id,
                        bank_name=lr.bank_name,
                        loan_type=lr.loan_type,
                        original_balance=lr.original_balance,
                        payoff_month=lr.payoff_month,
                        months_saved=lr.months_saved,
                    ) for lr in s.loan_results
                ],
                debt_free_date_months=s.debt_free_date_months,
            ) for s in result.strategies
        ],
        recommended_strategy=result.recommended_strategy,
    )


@router.get("/dashboard-summary")
async def dashboard_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-run optimization summary for dashboard."""
    repo = LoanRepository(db)
    loans = await repo.list_by_user(user.id, status="active")

    if not loans:
        return {"has_loans": False}

    total_emi = sum(float(l.emi_amount) for l in loans)
    default_extra = Decimal(str(round(total_emi * 0.1, 2)))

    country = user.country or "IN"
    snapshots = [_loan_to_snapshot(l, country) for l in loans]

    optimizer = MultiLoanOptimizer(loans=snapshots, monthly_extra=default_extra)
    result = optimizer.optimize(strategies=["avalanche", "snowball", "smart_hybrid"], country=country)

    best = next((s for s in result.strategies if s.strategy_name == result.recommended_strategy), None)

    return {
        "has_loans": True,
        "loan_count": len(loans),
        "total_debt": float(sum(Decimal(str(l.outstanding_principal)) for l in loans)),
        "total_emi": total_emi,
        "suggested_extra": float(default_extra),
        "recommended_strategy": result.recommended_strategy,
        "interest_saved": float(best.interest_saved_vs_baseline) if best else 0,
        "months_saved": best.months_saved_vs_baseline if best else 0,
        "debt_free_months": best.total_months if best else 0,
        "baseline_months": result.baseline_total_months,
        "strategies_preview": [
            {
                "name": s.strategy_name,
                "interest_saved": float(s.interest_saved_vs_baseline),
                "months_saved": s.months_saved_vs_baseline,
            }
            for s in result.strategies
        ],
    }


@router.post("/quick-compare", response_model=QuickCompareResponse)
async def quick_compare(
    req: QuickCompareRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight savings preview."""
    repo = LoanRepository(db)
    loans = await repo.list_by_user(user.id, status="active")
    selected = [l for l in loans if l.id in [UUID(str(lid)) for lid in req.loan_ids]]

    if not selected:
        raise HTTPException(status_code=400, detail="No matching loans")

    snapshots = [_loan_to_snapshot(l) for l in selected]
    optimizer = MultiLoanOptimizer(loans=snapshots, monthly_extra=req.monthly_extra)
    result = optimizer.optimize(strategies=["avalanche"])

    best = result.strategies[0] if result.strategies else None
    return QuickCompareResponse(
        interest_saved=best.interest_saved_vs_baseline if best else Decimal("0"),
        months_saved=best.months_saved_vs_baseline if best else 0,
        debt_free_months=best.total_months if best else 0,
    )


@router.post("/what-if", response_model=WhatIfResponse)
async def what_if(
    req: WhatIfRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Single loan what-if scenario."""
    repo = LoanRepository(db)
    loan = await repo.get_by_id(req.loan_id, user.id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    principal = Decimal(str(loan.outstanding_principal))
    rate = Decimal(str(loan.interest_rate))
    tenure = loan.remaining_tenure_months

    original_interest = calculate_total_interest(principal, rate, tenure)
    lump_sums = {req.lump_sum_month: req.lump_sum} if req.lump_sum > 0 else None

    interest_saved, months_saved = calculate_interest_saved(
        principal, rate, tenure, req.monthly_extra, lump_sums
    )

    return WhatIfResponse(
        original_interest=original_interest,
        new_interest=original_interest - interest_saved,
        interest_saved=interest_saved,
        original_months=tenure,
        new_months=tenure - months_saved,
        months_saved=months_saved,
    )


@router.post("/save-plan")
async def save_plan(
    req: SavePlanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a repayment plan."""
    repo = RepaymentPlanRepository(db)
    plan = await repo.create(
        user_id=user.id,
        name=req.name,
        strategy=req.strategy,
        config=req.config,
        results=req.results,
    )
    return {"plan_id": str(plan.id), "message": "Plan saved"}


@router.get("/plans")
async def list_plans(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List saved repayment plans."""
    repo = RepaymentPlanRepository(db)
    plans = await repo.list_by_user(user.id)
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "strategy": p.strategy,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat(),
        }
        for p in plans
    ]


@router.post("/sensitivity", response_model=SensitivityResponse)
async def sensitivity(
    req: SensitivityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rate sensitivity analysis — how interest rate changes affect payoff."""
    repo = LoanRepository(db)
    loans = await repo.list_by_user(user.id, status="active")

    selected = [l for l in loans if l.id in [UUID(str(lid)) for lid in req.loan_ids]]
    if not selected:
        raise HTTPException(status_code=400, detail="No matching active loans found")

    country = user.country or "IN"
    snapshots = [_loan_to_snapshot(l, country) for l in selected]
    lump_dict = {ls.month: ls.amount for ls in req.lump_sums}

    optimizer = MultiLoanOptimizer(
        loans=snapshots,
        monthly_extra=req.monthly_extra,
        lump_sums=lump_dict,
        annual_growth_pct=req.annual_growth_pct,
    )
    result = optimizer.sensitivity_analysis(
        strategy_name=req.strategy,
        rate_deltas=req.rate_deltas,
        tax_bracket=req.tax_bracket,
        country=country,
    )

    return SensitivityResponse(
        strategy_name=result.strategy_name,
        points=[
            SensitivityPointResponse(
                rate_delta_pct=p.rate_delta_pct,
                total_interest_paid=p.total_interest_paid,
                total_months=p.total_months,
                interest_saved_vs_baseline=p.interest_saved_vs_baseline,
            ) for p in result.points
        ],
    )


@router.post("/tax-impact", response_model=TaxImpactResponse)
async def tax_impact(
    req: TaxImpactRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare tax regimes/deductions considering loan deductions."""
    repo = LoanRepository(db)
    loans = await repo.list_by_user(user.id, status="active")
    country = user.country or "IN"

    if country == "US":
        us_loans = [
            USLoanTaxInfo(
                loan_type=l.loan_type,
                annual_interest_paid=Decimal(str(l.emi_amount)) * 12 * Decimal("0.5"),
                annual_principal_paid=Decimal(str(l.emi_amount)) * 12 * Decimal("0.5"),
                eligible_mortgage_deduction=l.eligible_mortgage_deduction,
                eligible_student_loan_deduction=l.eligible_student_loan_deduction,
                outstanding_principal=Decimal(str(l.outstanding_principal)),
            )
            for l in loans
        ]
        filing_status = user.filing_status or "single"
        result = compare_standard_vs_itemized(req.annual_income, us_loans, filing_status)
        return TaxImpactResponse(
            old_regime_tax=result["standard"]["tax"],
            new_regime_tax=result["itemized"]["tax"],
            recommended=result["recommended"],
            savings=result["savings"],
            explanation=result["explanation"],
            deductions={},
        )

    # India: Old vs New regime
    tax_loans = [
        LoanTaxInfo(
            loan_type=l.loan_type,
            annual_interest_paid=Decimal(str(l.emi_amount)) * 12 * Decimal("0.5"),
            annual_principal_paid=Decimal(str(l.emi_amount)) * 12 * Decimal("0.5"),
            eligible_80c=l.eligible_80c,
            eligible_24b=l.eligible_24b,
            eligible_80e=l.eligible_80e,
            eligible_80eea=l.eligible_80eea,
        )
        for l in loans
    ]

    result = compare_tax_regimes(req.annual_income, tax_loans)

    return TaxImpactResponse(
        old_regime_tax=result["old_regime"]["tax"],
        new_regime_tax=result["new_regime"]["tax"],
        recommended=result["recommended"],
        savings=result["savings"],
        explanation=result["explanation"],
        deductions=result["old_regime"]["deductions"],
    )
