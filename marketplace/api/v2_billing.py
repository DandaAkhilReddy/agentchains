"""USD-native billing endpoints (v2 canonical API)."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.schemas.billing import (
    CancelSubscriptionRequest,
    ChangePlanRequest,
    CreateSubscriptionRequest,
    InvoiceListResponse,
    InvoiceResponse,
    PlanResponse,
    RecommendationResponse,
    SubscriptionResponse,
    UsageForecastResponse,
    UsageMeterResponse,
)
from marketplace.services.billing_v2_service import (
    cancel_subscription,
    change_plan,
    check_limits,
    get_plan,
    get_plans,
    get_subscription,
    get_usage,
    list_invoices,
    list_plans,
    subscribe,
)
from marketplace.services.deposit_service import confirm_deposit, create_deposit
from marketplace.services.invoice_service import (
    generate_invoice_pdf,
    get_invoice,
    get_invoice_pdf_url,
)
from marketplace.services.plan_advisor_service import (
    forecast_usage,
    recommend_plan,
)
from marketplace.services.stripe_service import StripePaymentService
from marketplace.services.token_service import get_balance, get_history, transfer

router = APIRouter(prefix="/billing", tags=["billing-v2"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline schemas for wallet/ledger endpoints (kept here for backward compat)
# ---------------------------------------------------------------------------


class BillingAccountResponse(BaseModel):
    account_scope: str = "agent"
    currency: str = "USD"
    balance_usd: float
    total_earned_usd: float
    total_spent_usd: float
    total_deposited_usd: float
    total_fees_paid_usd: float


class BillingLedgerEntry(BaseModel):
    id: str
    direction: str
    tx_type: str
    amount_usd: float
    fee_usd: float = 0.0
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    memo: Optional[str] = None
    created_at: Optional[str] = None


class BillingLedgerResponse(BaseModel):
    entries: list[BillingLedgerEntry]
    total: int
    page: int
    page_size: int


class BillingDepositCreateRequest(BaseModel):
    amount_usd: float = Field(..., gt=0, le=100_000, description="USD amount to deposit")
    payment_method: str = Field(default="admin_credit", min_length=1, max_length=30)


class BillingTransferCreateRequest(BaseModel):
    to_agent_id: str = Field(..., min_length=1, max_length=255)
    amount_usd: float = Field(..., gt=0, le=100_000)
    memo: Optional[str] = Field(default=None, max_length=1000)
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan_to_response(plan: object) -> PlanResponse:
    """Convert a BillingPlan ORM model to a PlanResponse schema."""
    features: list[str] = []
    raw = getattr(plan, "features_json", "[]") or "[]"
    try:
        features = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    return PlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description or "",
        tier=plan.tier,
        price_monthly=float(plan.price_usd_monthly),
        price_yearly=float(plan.price_usd_yearly),
        api_calls_limit=plan.api_calls_limit,
        storage_gb_limit=plan.storage_gb_limit,
        agents_limit=plan.agents_limit,
        features=features,
    )


def _get_stripe_service() -> StripePaymentService:
    return StripePaymentService(
        secret_key=settings.stripe_secret_key,
        webhook_secret=settings.stripe_webhook_secret,
    )


# ---------------------------------------------------------------------------
# Wallet / Ledger endpoints (existing)
# ---------------------------------------------------------------------------


@router.get("/accounts/me", response_model=BillingAccountResponse)
async def billing_account_me(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> BillingAccountResponse:
    try:
        data = await get_balance(db, agent_id)
    except ValueError:
        data = {
            "balance": 0.0,
            "total_earned": 0.0,
            "total_spent": 0.0,
            "total_deposited": 0.0,
            "total_fees_paid": 0.0,
        }
    return BillingAccountResponse(
        balance_usd=data["balance"],
        total_earned_usd=data["total_earned"],
        total_spent_usd=data["total_spent"],
        total_deposited_usd=data["total_deposited"],
        total_fees_paid_usd=data["total_fees_paid"],
    )


@router.get("/ledger/me", response_model=BillingLedgerResponse)
async def billing_ledger_me(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> BillingLedgerResponse:
    entries, total = await get_history(db, agent_id, page, page_size)
    normalized = [
        BillingLedgerEntry(
            id=entry["id"],
            direction=entry["direction"],
            tx_type=entry["tx_type"],
            amount_usd=entry["amount"],
            fee_usd=entry.get("fee_amount", 0.0),
            reference_id=entry.get("reference_id"),
            reference_type=entry.get("reference_type"),
            memo=entry.get("memo"),
            created_at=entry.get("created_at"),
        )
        for entry in entries
    ]
    return BillingLedgerResponse(entries=normalized, total=total, page=page, page_size=page_size)


@router.post("/deposits")
async def billing_create_deposit(
    req: BillingDepositCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> dict:
    try:
        return await create_deposit(
            db,
            agent_id=agent_id,
            amount_usd=req.amount_usd,
            payment_method=req.payment_method,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/deposits/{deposit_id}/confirm")
async def billing_confirm_deposit(
    deposit_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> dict:
    try:
        return await confirm_deposit(db, deposit_id, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/transfers")
async def billing_transfer(
    req: BillingTransferCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> dict:
    if req.to_agent_id == agent_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to yourself")
    try:
        entry = await transfer(
            db,
            from_agent_id=agent_id,
            to_agent_id=req.to_agent_id,
            amount=req.amount_usd,
            tx_type="transfer",
            idempotency_key=req.idempotency_key,
            memo=req.memo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "id": entry.id,
        "tx_type": entry.tx_type,
        "amount_usd": float(entry.amount),
        "fee_usd": float(entry.fee_amount),
        "memo": entry.memo,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=list[PlanResponse])
async def billing_list_plans(
    tier: Literal["free", "starter", "pro", "enterprise"] | None = Query(
        None, description="Filter by tier"
    ),
    db: AsyncSession = Depends(get_db),
) -> list[PlanResponse]:
    """List all active billing plans. Public — no auth required."""
    plans = await get_plans(db, tier=tier)
    return [_plan_to_response(p) for p in plans]


@router.get("/plans/recommend", response_model=RecommendationResponse)
async def billing_recommend_plan(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> RecommendationResponse:
    """Get AI-powered plan recommendation based on current usage."""
    try:
        return await recommend_plan(db, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def billing_get_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Get a single plan by ID. Public — no auth required."""
    plan = await get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(plan)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@router.get("/subscriptions/me", response_model=SubscriptionResponse | None)
async def billing_my_subscription(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> SubscriptionResponse | None:
    """Get the current agent's active subscription."""
    sub = await get_subscription(db, agent_id)
    if not sub:
        return None
    plan = await get_plan(db, sub.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    return SubscriptionResponse(
        id=sub.id,
        plan=_plan_to_response(plan),
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


@router.post("/subscriptions", status_code=201)
async def billing_create_subscription(
    req: CreateSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> dict:
    """Create a subscription. Returns a Stripe Checkout URL for paid plans."""
    plan = await get_plan(db, req.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    price = (
        float(plan.price_usd_yearly)
        if req.billing_cycle == "yearly"
        else float(plan.price_usd_monthly)
    )

    # Free plans: subscribe directly without Stripe
    if price == 0:
        sub = await subscribe(db, agent_id, req.plan_id)
        return {"subscription_id": sub.id, "checkout_url": None}

    # Paid plans: create a pending subscription record, then redirect to Stripe
    from marketplace.models.billing import Subscription as SubscriptionModel
    from marketplace.core.utils import utcnow as _utcnow

    pending_sub = SubscriptionModel(
        agent_id=agent_id,
        plan_id=req.plan_id,
        status="pending",
        current_period_start=_utcnow(),
    )
    db.add(pending_sub)
    await db.commit()
    await db.refresh(pending_sub)

    stripe_svc = _get_stripe_service()
    interval = "year" if req.billing_cycle == "yearly" else "month"
    frontend_url = settings.stripe_frontend_url or "http://localhost:5173"
    session = await stripe_svc.create_subscription_checkout(
        plan_name=plan.name,
        price_usd=Decimal(str(price)),
        interval=interval,
        agent_id=agent_id,
        plan_id=req.plan_id,
        success_url=f"{frontend_url}/billing?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{frontend_url}/billing?cancelled=true",
    )

    return {
        "subscription_id": pending_sub.id,
        "checkout_url": session.get("url"),
        "checkout_session_id": session.get("id"),
    }


@router.post("/subscriptions/me/cancel")
async def billing_cancel_subscription(
    req: CancelSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> dict:
    """Cancel the current subscription."""
    sub = await get_subscription(db, agent_id)
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found")
    try:
        updated = await cancel_subscription(db, sub.id, immediate=req.immediate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": updated.id,
        "status": updated.status,
        "cancel_at_period_end": updated.cancel_at_period_end,
    }


@router.post("/subscriptions/me/change-plan")
async def billing_change_plan(
    req: ChangePlanRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> dict:
    """Change to a different plan. Returns a Stripe Checkout URL for paid plans."""
    new_plan = await get_plan(db, req.new_plan_id)
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    price = (
        float(new_plan.price_usd_yearly)
        if req.billing_cycle == "yearly"
        else float(new_plan.price_usd_monthly)
    )

    # Free plans: switch directly
    if price == 0:
        sub = await change_plan(db, agent_id, req.new_plan_id)
        return {"subscription_id": sub.id, "checkout_url": None}

    # Paid plans: Stripe Checkout for the new plan
    stripe_svc = _get_stripe_service()
    interval = "year" if req.billing_cycle == "yearly" else "month"
    frontend_url = settings.stripe_frontend_url or "http://localhost:5173"
    session = await stripe_svc.create_subscription_checkout(
        plan_name=new_plan.name,
        price_usd=Decimal(str(price)),
        interval=interval,
        agent_id=agent_id,
        plan_id=req.new_plan_id,
        success_url=f"{frontend_url}/billing?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{frontend_url}/billing?cancelled=true",
    )

    return {
        "subscription_id": None,
        "checkout_url": session.get("url"),
        "checkout_session_id": session.get("id"),
    }


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


@router.get("/usage/me", response_model=list[UsageMeterResponse])
async def billing_my_usage(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> list[UsageMeterResponse]:
    """Get the current agent's usage meters for this billing period."""
    metrics = ["api_calls", "storage", "bandwidth"]
    results: list[UsageMeterResponse] = []

    for metric in metrics:
        limits = await check_limits(db, agent_id, metric)
        current = limits["current"]
        limit = limits["limit"]
        percent = round((current / limit) * 100, 1) if limit > 0 else 0.0
        results.append(
            UsageMeterResponse(
                metric_name=metric,
                current=current,
                limit=limit,
                percent_used=percent,
            )
        )

    return results


@router.get("/usage/me/forecast", response_model=list[UsageForecastResponse])
async def billing_usage_forecast(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> list[UsageForecastResponse]:
    """Project usage to end of billing period and warn of limit breaches."""
    try:
        return await forecast_usage(db, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@router.get("/invoices/me", response_model=InvoiceListResponse)
async def billing_my_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> InvoiceListResponse:
    """List the current agent's invoices (paginated)."""
    all_invoices = await list_invoices(db, agent_id)
    total = len(all_invoices)
    start = (page - 1) * page_size
    page_items = all_invoices[start : start + page_size]

    items = [
        InvoiceResponse(
            id=inv.id,
            amount_usd=float(inv.amount_usd),
            tax_usd=float(inv.tax_usd),
            total_usd=float(inv.total_usd),
            status=inv.status,
            issued_at=inv.issued_at,
            due_at=inv.due_at,
            paid_at=inv.paid_at,
            pdf_url=inv.pdf_url or "",
        )
        for inv in page_items
    ]

    return InvoiceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/invoices/{invoice_id}/pdf")
async def billing_invoice_pdf(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
) -> dict:
    """Get or generate the PDF URL for an invoice."""
    invoice = await get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Not your invoice")

    # Check if PDF already exists
    pdf_url = await get_invoice_pdf_url(db, invoice_id)
    if not pdf_url:
        pdf_url = await generate_invoice_pdf(db, invoice_id)

    return {"invoice_id": invoice_id, "pdf_url": pdf_url}
