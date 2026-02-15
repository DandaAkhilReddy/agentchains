"""USD payout request endpoints (v2 canonical API)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.services import redemption_service

router = APIRouter(prefix="/payouts", tags=["payouts-v2"])


def _normalize_payout_method(method: str) -> str:
    mapping = {
        "bank_transfer": "bank_withdrawal",
        "bank_withdrawal": "bank_withdrawal",
        "upi": "upi",
        "gift_card": "gift_card",
        "api_credits": "api_credits",
    }
    normalized = mapping.get(method)
    if normalized is None:
        raise ValueError(f"Unsupported payout_method: {method}")
    return normalized


class PayoutRequestCreate(BaseModel):
    payout_method: str = Field(..., min_length=1, max_length=30)
    amount_usd: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=10)
    payout_details: Optional[dict] = None


class PayoutApproveRequest(BaseModel):
    admin_notes: str = ""


class PayoutRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


@router.post("/requests", status_code=201)
async def create_payout_request(
    req: PayoutRequestCreate,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    creator_id = get_current_creator_id(authorization)
    try:
        redemption_type = _normalize_payout_method(req.payout_method)
        return await redemption_service.create_redemption(
            db,
            creator_id,
            redemption_type,
            req.amount_usd,
            req.currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/requests")
async def list_payout_requests(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    creator_id = get_current_creator_id(authorization)
    return await redemption_service.list_redemptions(db, creator_id, status, page, page_size)


@router.post("/requests/{request_id}/cancel")
async def cancel_payout_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    creator_id = get_current_creator_id(authorization)
    try:
        return await redemption_service.cancel_redemption(db, request_id, creator_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/requests/{request_id}/approve")
async def admin_approve_payout_request(
    request_id: str,
    req: PayoutApproveRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    from marketplace.config import settings

    creator_id = get_current_creator_id(authorization)
    admin_ids = [a.strip() for a in getattr(settings, "admin_creator_ids", "").split(",") if a.strip()]
    if admin_ids and creator_id not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    try:
        return await redemption_service.admin_approve_redemption(db, request_id, req.admin_notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/requests/{request_id}/reject")
async def admin_reject_payout_request(
    request_id: str,
    req: PayoutRejectRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    from marketplace.config import settings

    creator_id = get_current_creator_id(authorization)
    admin_ids = [a.strip() for a in getattr(settings, "admin_creator_ids", "").split(",") if a.strip()]
    if admin_ids and creator_id not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    try:
        return await redemption_service.admin_reject_redemption(db, request_id, req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

