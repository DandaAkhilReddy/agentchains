import asyncio
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.database import async_session, get_db
from marketplace.schemas.listing import ListingListResponse, ListingResponse, SellerSummary
from marketplace.services import demand_service, listing_service

router = APIRouter(tags=["discovery"])


@router.get("/discover", response_model=ListingListResponse)
async def discover(
    q: str | None = Query(None, description="Full-text search on title, description, tags"),
    category: str | None = Query(None),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quality: float | None = Query(None, ge=0, le=1),
    max_age_hours: int | None = Query(None, ge=1),
    seller_id: str | None = Query(None),
    sort_by: str = Query("freshness", pattern="^(price_asc|price_desc|freshness|quality)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    listings, total = await listing_service.discover(
        db, q, category, min_price, max_price,
        min_quality, max_age_hours, seller_id,
        sort_by, page, page_size,
    )

    results = []
    for listing in listings:
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

        results.append(ListingResponse(
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
        ))

    # Fire-and-forget demand logging with its own session
    async def _log_demand():
        try:
            async with async_session() as bg_db:
                await demand_service.log_search(
                    bg_db, query_text=q or "", category=category, source="discover",
                    matched_count=total, max_price=max_price,
                )
        except Exception:
            pass

    asyncio.ensure_future(_log_demand())

    return ListingListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=results,
    )
