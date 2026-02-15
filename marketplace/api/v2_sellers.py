"""Seller-facing USD earnings endpoints (v2 canonical API)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.creator_auth import get_current_creator_id
from marketplace.database import get_db
from marketplace.services import creator_service, redemption_service

router = APIRouter(prefix="/sellers", tags=["sellers-v2"])


@router.get("/me/earnings")
async def seller_earnings_me(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """Return seller earnings and payout snapshot in USD terms."""
    creator_id = get_current_creator_id(authorization)

    wallet = await creator_service.get_creator_wallet(db, creator_id)
    pending = await redemption_service.list_redemptions(
        db,
        creator_id,
        status="pending",
        page=1,
        page_size=100,
    )
    processing = await redemption_service.list_redemptions(
        db,
        creator_id,
        status="processing",
        page=1,
        page_size=100,
    )

    return {
        "currency": "USD",
        "balance_usd": wallet.get("balance", 0.0),
        "total_earned_usd": wallet.get("total_earned", 0.0),
        "total_spent_usd": wallet.get("total_spent", 0.0),
        "total_deposited_usd": wallet.get("total_deposited", 0.0),
        "total_fees_paid_usd": wallet.get("total_fees_paid", 0.0),
        "pending_payout_count": pending.get("total", 0),
        "processing_payout_count": processing.get("total", 0),
    }

