"""USD-native billing endpoints (v2 canonical API)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.services.deposit_service import confirm_deposit, create_deposit
from marketplace.services.token_service import get_balance, get_history, transfer

router = APIRouter(prefix="/billing", tags=["billing-v2"])


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
    amount_usd: float = Field(..., gt=0, description="USD amount to deposit")
    payment_method: str = Field(default="admin_credit", min_length=1, max_length=30)


class BillingTransferCreateRequest(BaseModel):
    to_agent_id: str
    amount_usd: float = Field(..., gt=0)
    memo: Optional[str] = None


@router.get("/accounts/me", response_model=BillingAccountResponse)
async def billing_account_me(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    data = await get_balance(db, agent_id)
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
):
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
):
    try:
        return await create_deposit(
            db,
            agent_id=agent_id,
            amount_usd=req.amount_usd,
            payment_method=req.payment_method,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/deposits/{deposit_id}/confirm")
async def billing_confirm_deposit(
    deposit_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    return await confirm_deposit(db, deposit_id, agent_id)


@router.post("/transfers")
async def billing_transfer(
    req: BillingTransferCreateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    try:
        entry = await transfer(
            db,
            from_agent_id=agent_id,
            to_agent_id=req.to_agent_id,
            amount=req.amount_usd,
            tx_type="transfer",
            memo=req.memo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "id": entry.id,
        "tx_type": entry.tx_type,
        "amount_usd": float(entry.amount),
        "fee_usd": float(entry.fee_amount),
        "memo": entry.memo,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }

