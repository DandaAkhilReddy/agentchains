from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
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
    tx_type: str
    amount: float
    balance_after: float
    counterparty_id: Optional[str] = None
    memo: Optional[str] = None
    created_at: str


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
    """Return the authenticated agent's AXN balance and tier info."""
    data = await get_balance(db, agent_id)
    return BalanceResponse(**data)


@router.get("/history", response_model=HistoryResponse)
async def wallet_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Return paginated ledger history for the authenticated agent."""
    data = await get_history(db, agent_id, page, page_size)
    return HistoryResponse(**data)


@router.post("/deposit")
async def wallet_deposit(
    req: DepositRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Create a fiat deposit request that will be converted to AXN."""
    deposit = await create_deposit(db, agent_id, req.amount_fiat, req.currency)
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
    """Public endpoint: return AXN token supply statistics."""
    data = await get_supply(db)
    return SupplyResponse(**data)


@router.post("/transfer")
async def wallet_transfer(
    req: TransferRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Transfer AXN tokens to another agent."""
    entry = await transfer(
        db,
        from_agent_id=agent_id,
        to_agent_id=req.to_agent_id,
        amount=req.amount,
        tx_type="transfer",
        memo=req.memo,
    )
    return entry


@router.get("/tiers", response_model=TiersResponse)
async def wallet_tiers():
    """Public endpoint: return AXN tier definitions and discount rates."""
    return TiersResponse(tiers=[
        TierInfo(name="bronze", min_axn=0, max_axn=9_999, discount_pct=0),
        TierInfo(name="silver", min_axn=10_000, max_axn=99_999, discount_pct=10),
        TierInfo(name="gold", min_axn=100_000, max_axn=999_999, discount_pct=25),
        TierInfo(name="platinum", min_axn=1_000_000, max_axn=None, discount_pct=50),
    ])


@router.get("/currencies")
async def wallet_currencies():
    """Public endpoint: return supported fiat currencies with AXN exchange rates."""
    currencies = get_supported_currencies()
    return currencies
