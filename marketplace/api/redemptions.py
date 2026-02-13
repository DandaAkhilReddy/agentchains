"""Withdrawal API endpoints — convert USD balance to real value."""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.services import redemption_service

router = APIRouter(prefix="/redemptions", tags=["redemptions"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RedemptionCreateRequest(BaseModel):
    redemption_type: str = Field(..., pattern="^(api_credits|gift_card|bank_withdrawal|upi)$")
    amount_usd: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=10)
    payout_details: Optional[dict] = None  # UPI ID, bank details, etc.


class AdminApproveRequest(BaseModel):
    admin_notes: str = ""


class AdminRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Creator endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_redemption(
    req: RedemptionCreateRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Create a new withdrawal request. USD is debited immediately."""
    creator_id = get_current_creator_id(authorization)
    try:
        return await redemption_service.create_redemption(
            db, creator_id, req.redemption_type, req.amount_usd, req.currency,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_my_redemptions(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """List my redemption requests."""
    creator_id = get_current_creator_id(authorization)
    return await redemption_service.list_redemptions(db, creator_id, status, page, page_size)


@router.get("/methods")
async def get_redemption_methods():
    """Get available redemption methods with minimum thresholds."""
    return await redemption_service.get_redemption_methods()


@router.get("/{redemption_id}")
async def get_redemption(
    redemption_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Get a specific redemption request status."""
    creator_id = get_current_creator_id(authorization)
    result = await redemption_service.list_redemptions(db, creator_id)
    for r in result["redemptions"]:
        if r["id"] == redemption_id:
            return r
    raise HTTPException(status_code=404, detail="Redemption not found")


@router.post("/{redemption_id}/cancel")
async def cancel_redemption(
    redemption_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Cancel a pending withdrawal. USD is refunded."""
    creator_id = get_current_creator_id(authorization)
    try:
        return await redemption_service.cancel_redemption(db, redemption_id, creator_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.post("/admin/{redemption_id}/approve")
async def admin_approve(
    redemption_id: str,
    req: AdminApproveRequest,
    db: AsyncSession = Depends(get_db),
    _agent_id: str = Depends(get_current_creator_id),
):
    """Admin: approve a pending redemption."""
    try:
        return await redemption_service.admin_approve_redemption(
            db, redemption_id, req.admin_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/{redemption_id}/reject")
async def admin_reject(
    redemption_id: str,
    req: AdminRejectRequest,
    db: AsyncSession = Depends(get_db),
    _agent_id: str = Depends(get_current_creator_id),
):
    """Admin: reject a redemption. USD is refunded to creator."""
    try:
        return await redemption_service.admin_reject_redemption(
            db, redemption_id, req.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
