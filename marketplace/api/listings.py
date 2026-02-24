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
        results=[_listing_to_response(listing_item) for listing_item in listings],
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
    """Thin wrapper: delegates to service, maps dict → Pydantic schema."""
    d = listing_service.listing_to_response_dict(listing)
    seller = SellerSummary(**d["seller"]) if d["seller"] else None
    return ListingResponse(**{**d, "seller": seller})
