"""Withdrawal API endpoints — convert USD balance to real value."""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.api.deprecations import apply_legacy_v1_deprecation_headers
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
    response: Response,
    req: RedemptionCreateRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Create a new withdrawal request. USD is debited immediately."""
    apply_legacy_v1_deprecation_headers(response)
    creator_id = get_current_creator_id(authorization)
    try:
        return await redemption_service.create_redemption(
            db, creator_id, req.redemption_type, req.amount_usd, req.currency,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_my_redemptions(
    response: Response,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """List my redemption requests."""
    apply_legacy_v1_deprecation_headers(response)
    creator_id = get_current_creator_id(authorization)
    return await redemption_service.list_redemptions(db, creator_id, status, page, page_size)


@router.get("/methods")
async def get_redemption_methods(response: Response):
    """Get available redemption methods with minimum thresholds."""
    apply_legacy_v1_deprecation_headers(response)
    return await redemption_service.get_redemption_methods()


@router.get("/{redemption_id}")
async def get_redemption(
    response: Response,
    redemption_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Get a specific redemption request status."""
    apply_legacy_v1_deprecation_headers(response)
    creator_id = get_current_creator_id(authorization)
    result = await redemption_service.list_redemptions(db, creator_id)
    for r in result["redemptions"]:
        if r["id"] == redemption_id:
            return r
    raise HTTPException(status_code=404, detail="Redemption not found")


@router.post("/{redemption_id}/cancel")
async def cancel_redemption(
    response: Response,
    redemption_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Cancel a pending withdrawal. USD is refunded."""
    apply_legacy_v1_deprecation_headers(response)
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
    response: Response,
    redemption_id: str,
    req: AdminApproveRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Admin: approve a pending redemption. Requires platform admin privileges."""
    apply_legacy_v1_deprecation_headers(response)
    from marketplace.config import settings
    creator_id = get_current_creator_id(authorization)
    admin_ids = [a.strip() for a in getattr(settings, "admin_creator_ids", "").split(",") if a.strip()]
    if admin_ids and creator_id not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    try:
        return await redemption_service.admin_approve_redemption(
            db, redemption_id, req.admin_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/{redemption_id}/reject")
async def admin_reject(
    response: Response,
    redemption_id: str,
    req: AdminRejectRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Admin: reject a redemption. Requires platform admin privileges. USD is refunded."""
    apply_legacy_v1_deprecation_headers(response)
    from marketplace.config import settings
    creator_id = get_current_creator_id(authorization)
    admin_ids = [a.strip() for a in getattr(settings, "admin_creator_ids", "").split(",") if a.strip()]
    if admin_ids and creator_id not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    try:
        return await redemption_service.admin_reject_redemption(
            db, redemption_id, req.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
