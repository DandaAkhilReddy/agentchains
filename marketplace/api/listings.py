import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.schemas.listing import (
    ListingCreateRequest,
    ListingListResponse,
    ListingResponse,
    ListingUpdateRequest,
    SellerSummary,
)
from marketplace.services import listing_service

router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("", response_model=ListingResponse, status_code=201)
async def create_listing(
    req: ListingCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    listing = await listing_service.create_listing(db, current_agent, req)
    return _listing_to_response(listing)


@router.get("", response_model=ListingListResponse)
async def list_listings(
    category: str | None = Query(None),
    status: str = Query("active"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    listings, total = await listing_service.list_listings(db, category, status, page, page_size)
    return ListingListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=[_listing_to_response(l) for l in listings],
    )


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
):
    listing = await listing_service.get_listing(db, listing_id)
    return _listing_to_response(listing)


@router.put("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: str,
    req: ListingUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    listing = await listing_service.update_listing(db, listing_id, current_agent, req)
    return _listing_to_response(listing)


@router.delete("/{listing_id}")
async def delist(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: str = Depends(get_current_agent_id),
):
    await listing_service.delist(db, listing_id, current_agent)
    return {"status": "delisted"}


def _listing_to_response(listing) -> ListingResponse:
    metadata = listing.metadata_json
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    tags = listing.tags
    if isinstance(tags, str):
        tags = json.loads(tags)

    seller_summary = None
    if listing.seller:
        seller_summary = SellerSummary(
            id=listing.seller.id,
            name=listing.seller.name,
        )

    return ListingResponse(
        id=listing.id,
        seller_id=listing.seller_id,
        seller=seller_summary,
        title=listing.title,
        description=listing.description,
        category=listing.category,
        content_hash=listing.content_hash,
        content_size=listing.content_size,
        content_type=listing.content_type,
        price_usdc=float(listing.price_usdc),
        currency=listing.currency,
        metadata=metadata,
        tags=tags,
        quality_score=float(listing.quality_score) if listing.quality_score else 0.5,
        freshness_at=listing.freshness_at,
        expires_at=listing.expires_at,
        status=listing.status,
        access_count=listing.access_count,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )
