"""Trust verification endpoints (v2 canonical API)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.models.listing import DataListing
from marketplace.services import trust_verification_service

router = APIRouter(prefix="/verification", tags=["verification-v2"])


class SourceReceiptCreateRequest(BaseModel):
    provider: str = Field(..., min_length=2, max_length=64)
    source_query: str = Field(..., min_length=1)
    seller_signature: str = Field(..., min_length=8)
    response_hash: str | None = None
    request_payload: dict = {}
    headers: dict = {}


@router.get("/listings/{listing_id}")
async def get_listing_trust_state(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DataListing).where(DataListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    payload = trust_verification_service.build_trust_payload(listing)
    payload["listing_id"] = listing_id
    return payload


@router.post("/listings/{listing_id}/run")
async def run_listing_verification(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    result = await db.execute(select(DataListing).where(DataListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.seller_id != current_agent:
        raise HTTPException(status_code=403, detail="Only the listing seller can run verification")
    return await trust_verification_service.run_strict_verification(
        db,
        listing,
        requested_by=current_agent,
        trigger_source="manual",
    )


@router.post("/listings/{listing_id}/receipts")
async def add_listing_source_receipt(
    listing_id: str,
    req: SourceReceiptCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    result = await db.execute(select(DataListing).where(DataListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.seller_id != current_agent:
        raise HTTPException(status_code=403, detail="Only the listing seller can add receipts")

    try:
        receipt = await trust_verification_service.add_source_receipt(
            db,
            listing_id=listing_id,
            provider=req.provider,
            source_query=req.source_query,
            seller_signature=req.seller_signature,
            response_hash=req.response_hash,
            request_payload=req.request_payload,
            headers=req.headers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    verification = await trust_verification_service.run_strict_verification(
        db,
        listing,
        requested_by=current_agent,
        trigger_source="receipt_submit",
    )
    return {
        "receipt_id": receipt.id,
        "verification": verification,
    }

