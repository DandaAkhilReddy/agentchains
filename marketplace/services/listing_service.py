import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.exceptions import ListingNotFoundError
from marketplace.models.listing import DataListing
from marketplace.schemas.listing import ListingCreateRequest, ListingUpdateRequest
from marketplace.services.storage_service import get_storage


async def create_listing(
    db: AsyncSession, seller_id: str, req: ListingCreateRequest
) -> DataListing:
    """Create a new data listing. Stores content in HashFS and computes hash."""
    storage = get_storage()
    content_bytes = req.content.encode("utf-8")
    content_hash = storage.put(content_bytes)

    listing = DataListing(
        seller_id=seller_id,
        title=req.title,
        description=req.description,
        category=req.category,
        content_hash=content_hash,
        content_size=len(content_bytes),
        price_usdc=req.price_usdc,
        metadata_json=json.dumps(req.metadata),
        tags=json.dumps(req.tags),
        quality_score=req.quality_score,
        freshness_at=datetime.now(timezone.utc),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing


async def get_listing(db: AsyncSession, listing_id: str) -> DataListing:
    """Get a listing by ID or raise 404."""
    result = await db.execute(
        select(DataListing).where(DataListing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise ListingNotFoundError(listing_id)
    return listing


async def list_listings(
    db: AsyncSession,
    category: str | None = None,
    status: str = "active",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DataListing], int]:
    """List listings with optional filters."""
    query = select(DataListing).where(DataListing.status == status)
    count_query = select(func.count(DataListing.id)).where(DataListing.status == status)

    if category:
        query = query.where(DataListing.category == category)
        count_query = count_query.where(DataListing.category == category)

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(DataListing.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    listings = list(result.scalars().all())

    return listings, total


async def update_listing(
    db: AsyncSession, listing_id: str, seller_id: str, req: ListingUpdateRequest
) -> DataListing:
    """Update listing fields (only by the owner)."""
    listing = await get_listing(db, listing_id)
    if listing.seller_id != seller_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the listing owner")

    update_data = req.model_dump(exclude_unset=True)
    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"])

    for field, value in update_data.items():
        setattr(listing, field, value)

    listing.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(listing)
    return listing


async def delist(db: AsyncSession, listing_id: str, seller_id: str) -> DataListing:
    """Soft-delete a listing."""
    listing = await get_listing(db, listing_id)
    if listing.seller_id != seller_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the listing owner")

    listing.status = "delisted"
    listing.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(listing)
    return listing


async def discover(
    db: AsyncSession,
    q: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quality: float | None = None,
    max_age_hours: int | None = None,
    seller_id: str | None = None,
    sort_by: str = "freshness",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DataListing], int]:
    """Search and filter listings for the discovery API."""
    query = select(DataListing).where(DataListing.status == "active")
    count_query = select(func.count(DataListing.id)).where(DataListing.status == "active")

    if q:
        pattern = f"%{q}%"
        filter_cond = DataListing.title.ilike(pattern) | DataListing.description.ilike(pattern) | DataListing.tags.ilike(pattern)
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    if category:
        query = query.where(DataListing.category == category)
        count_query = count_query.where(DataListing.category == category)
    if min_price is not None:
        query = query.where(DataListing.price_usdc >= min_price)
        count_query = count_query.where(DataListing.price_usdc >= min_price)
    if max_price is not None:
        query = query.where(DataListing.price_usdc <= max_price)
        count_query = count_query.where(DataListing.price_usdc <= max_price)
    if min_quality is not None:
        query = query.where(DataListing.quality_score >= min_quality)
        count_query = count_query.where(DataListing.quality_score >= min_quality)
    if max_age_hours is not None:
        cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=max_age_hours)
        query = query.where(DataListing.freshness_at >= cutoff)
        count_query = count_query.where(DataListing.freshness_at >= cutoff)
    if seller_id:
        query = query.where(DataListing.seller_id == seller_id)
        count_query = count_query.where(DataListing.seller_id == seller_id)

    total = (await db.execute(count_query)).scalar() or 0

    # Sorting
    if sort_by == "price_asc":
        query = query.order_by(DataListing.price_usdc.asc())
    elif sort_by == "price_desc":
        query = query.order_by(DataListing.price_usdc.desc())
    elif sort_by == "quality":
        query = query.order_by(DataListing.quality_score.desc())
    else:  # freshness (default)
        query = query.order_by(DataListing.freshness_at.desc())

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    listings = list(result.scalars().all())

    return listings, total


def get_listing_content(content_hash: str) -> bytes | None:
    """Retrieve the raw content for a listing from HashFS."""
    storage = get_storage()
    return storage.get(content_hash)
