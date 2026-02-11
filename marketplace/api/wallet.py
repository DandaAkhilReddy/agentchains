from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.models.token_account import TokenLedger
from marketplace.services.token_service import (
    create_account,
    get_balance,
    get_history,
    get_supply,
    recalculate_tier,
    transfer,
)
from marketplace.services.deposit_service import (
    confirm_deposit,
    create_deposit,
    get_deposits,
    get_supported_currencies,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class BalanceResponse(BaseModel):
    balance: float
    tier: str
    total_earned: float
    total_spent: float
    total_deposited: float
    total_fees_paid: float
    usd_equivalent: float
    token_name: str


class HistoryEntry(BaseModel):
    id: str
    direction: str
    tx_type: str
    amount: float
    fee_amount: float = 0.0
    burn_amount: float = 0.0
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    memo: Optional[str] = None
    created_at: Optional[str] = None


class HistoryResponse(BaseModel):
    entries: list[HistoryEntry]
    total: int
    page: int
    page_size: int


class DepositRequest(BaseModel):
    amount_fiat: float = Field(..., gt=0, description="Fiat amount to deposit")
    currency: str = Field(default="USD", description="ISO currency code")


class TransferRequest(BaseModel):
    to_agent_id: str
    amount: float = Field(..., gt=0)
    memo: Optional[str] = None


class TierInfo(BaseModel):
    name: str
    min_axn: int
    max_axn: Optional[int] = None
    discount_pct: int


class TiersResponse(BaseModel):
    tiers: list[TierInfo]


class SupplyResponse(BaseModel):
    total_minted: float
    total_burned: float
    circulating: float
    treasury: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/balance", response_model=BalanceResponse)
async def wallet_balance(
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Return the authenticated agent's ARD balance and tier info."""
    data = await get_balance(db, agent_id)
    return BalanceResponse(**data, token_name=settings.token_name)


@router.get("/history", response_model=HistoryResponse)
async def wallet_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Return paginated ledger history for the authenticated agent."""
    entries, total = await get_history(db, agent_id, page, page_size)
    return HistoryResponse(entries=entries, total=total, page=page, page_size=page_size)


@router.post("/deposit")
async def wallet_deposit(
    req: DepositRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Create a fiat deposit request that will be converted to ARD."""
    try:
        deposit = await create_deposit(db, agent_id, req.amount_fiat, req.currency)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return deposit


@router.post("/deposit/{deposit_id}/confirm")
async def wallet_confirm_deposit(
    deposit_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Confirm a pending deposit (MVP: any authenticated agent can confirm their own)."""
    deposit = await confirm_deposit(db, deposit_id)
    return deposit


@router.get("/supply", response_model=SupplyResponse)
async def wallet_supply(
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint: return ARD token supply statistics."""
    data = await get_supply(db)
    return SupplyResponse(
        total_minted=data["total_minted"],
        total_burned=data["total_burned"],
        circulating=data["circulating"],
        treasury=data.get("platform_balance", 0.0),
    )


@router.post("/transfer")
async def wallet_transfer(
    req: TransferRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Transfer ARD tokens to another agent."""
    try:
        entry = await transfer(
            db,
            from_agent_id=agent_id,
            to_agent_id=req.to_agent_id,
            amount=req.amount,
            tx_type="transfer",
            memo=req.memo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": entry.id,
        "amount": float(entry.amount),
        "fee_amount": float(entry.fee_amount),
        "burn_amount": float(entry.burn_amount),
        "tx_type": entry.tx_type,
        "memo": entry.memo,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.get("/tiers", response_model=TiersResponse)
async def wallet_tiers():
    """Public endpoint: return ARD tier definitions and discount rates."""
    return TiersResponse(tiers=[
        TierInfo(name="bronze", min_axn=0, max_axn=9_999, discount_pct=0),
        TierInfo(name="silver", min_axn=10_000, max_axn=99_999, discount_pct=10),
        TierInfo(name="gold", min_axn=100_000, max_axn=999_999, discount_pct=25),
        TierInfo(name="platinum", min_axn=1_000_000, max_axn=None, discount_pct=50),
    ])


@router.get("/currencies")
async def wallet_currencies():
    """Public endpoint: return supported fiat currencies with ARD exchange rates."""
    currencies = get_supported_currencies()
    return currencies


@router.get("/ledger/verify")
async def verify_ledger_chain(
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Verify integrity of the token ledger SHA-256 hash chain."""
    from marketplace.core.hashing import compute_ledger_hash

    entries = await db.execute(
        select(TokenLedger).order_by(TokenLedger.created_at.asc()).limit(limit)
    )
    entries = entries.scalars().all()

    prev_hash = None
    checked = 0
    for entry in entries:
        if entry.entry_hash is None:
            continue  # Skip pre-chain entries
        expected = compute_ledger_hash(
            prev_hash, entry.from_account_id, entry.to_account_id,
            entry.amount, entry.fee_amount, entry.burn_amount,
            entry.tx_type, entry.created_at.isoformat(),
        )
        if expected != entry.entry_hash:
            return {"valid": False, "broken_at": entry.id, "entry_number": checked + 1,
                    "expected": expected, "actual": entry.entry_hash}
        prev_hash = entry.entry_hash
        checked += 1

    return {"valid": True, "entries_checked": checked}
