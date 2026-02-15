from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.api.deprecations import apply_legacy_v1_deprecation_headers
from marketplace.database import get_db
from marketplace.services.token_service import (
    get_balance,
    get_history,
    transfer,
)
from marketplace.services.deposit_service import (
    confirm_deposit,
    create_deposit,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class BalanceResponse(BaseModel):
    balance: float
    total_earned: float
    total_spent: float
    total_deposited: float
    total_fees_paid: float


class HistoryEntry(BaseModel):
    id: str
    direction: str
    tx_type: str
    amount: float
    fee_amount: float = 0.0
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
    amount_usd: float = Field(..., gt=0, description="USD amount to deposit")


class TransferRequest(BaseModel):
    to_agent_id: str
    amount: float = Field(..., gt=0)
    memo: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/balance", response_model=BalanceResponse)
async def wallet_balance(
    response: Response,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Return the authenticated agent's USD balance."""
    apply_legacy_v1_deprecation_headers(response)
    data = await get_balance(db, agent_id)
    return BalanceResponse(**data)


@router.get("/history", response_model=HistoryResponse)
async def wallet_history(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Return paginated ledger history for the authenticated agent."""
    apply_legacy_v1_deprecation_headers(response)
    entries, total = await get_history(db, agent_id, page, page_size)
    return HistoryResponse(entries=entries, total=total, page=page, page_size=page_size)


@router.post("/deposit")
async def wallet_deposit(
    response: Response,
    req: DepositRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Create a USD deposit request."""
    apply_legacy_v1_deprecation_headers(response)
    try:
        deposit = await create_deposit(db, agent_id, req.amount_usd)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return deposit


@router.post("/deposit/{deposit_id}/confirm")
async def wallet_confirm_deposit(
    response: Response,
    deposit_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Confirm a pending deposit. Only the deposit owner can confirm."""
    apply_legacy_v1_deprecation_headers(response)
    deposit = await confirm_deposit(db, deposit_id, agent_id)
    return deposit


@router.post("/transfer")
async def wallet_transfer(
    response: Response,
    req: TransferRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Transfer USD to another agent."""
    apply_legacy_v1_deprecation_headers(response)
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
        "tx_type": entry.tx_type,
        "memo": entry.memo,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }
