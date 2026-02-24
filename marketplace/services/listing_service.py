import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from marketplace.core.events import broadcast_event
from marketplace.core.exceptions import AuthorizationError, ListingNotFoundError
from marketplace.models.listing import DataListing
from marketplace.schemas.listing import ListingCreateRequest, ListingUpdateRequest
from marketplace.services.cache_service import listing_cache
from marketplace.services.storage_service import get_storage
from marketplace.services import trust_verification_service


async def create_listing(
    db: AsyncSession, seller_id: str, req: ListingCreateRequest
) -> DataListing:
    """Create a new data listing. Stores content in HashFS and computes hash."""
    storage = get_storage()
    content_bytes = req.content.encode("utf-8")
    content_hash = storage.put(content_bytes)
    price_usd = req.price_usd if req.price_usd is not None else req.price_usdc

    listing = DataListing(
        seller_id=seller_id,
        title=req.title,
        description=req.description,
        category=req.category,
        content_hash=content_hash,
        content_size=len(content_bytes),
        price_usdc=price_usd,
        metadata_json=json.dumps(req.metadata),
        tags=json.dumps(req.tags),
        quality_score=req.quality_score,
        freshness_at=datetime.now(timezone.utc),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    # Generate zero-knowledge proofs for pre-purchase verification
    try:
        from marketplace.services.zkp_service import generate_proofs
        await generate_proofs(
            db, listing.id, content_bytes, req.category,
            len(content_bytes), listing.freshness_at,
            float(req.quality_score) if req.quality_score else 0.5,
        )
        await db.commit()
    except Exception:
        logger.warning("ZKP generation failed for listing %s", listing.id, exc_info=True)

    # Strict trust verification baseline (non-blocking for listing publish)
    try:
        await trust_verification_service.bootstrap_listing_trust_artifacts(
            db,
            listing,
            req.metadata,
        )
        await trust_verification_service.run_strict_verification(
            db,
            listing,
            requested_by=seller_id,
            trigger_source="listing_create",
        )
    except Exception:
        logger.warning("Trust verification bootstrap failed for listing %s", listing.id, exc_info=True)

    # Cache the new listing
    listing_cache.put(f"listing:{listing.id}", listing)

    # Broadcast event
    broadcast_event("listing_created", {
        "listing_id": listing.id,
        "title": listing.title,
        "category": listing.category,
        "price_usd": float(listing.price_usdc),
        "price_usdc": float(listing.price_usdc),
        "seller_id": seller_id,
    })

    return listing


async def get_listing(db: AsyncSession, listing_id: str) -> DataListing:
    """Get a listing by ID or raise 404. Uses cache for hot listings."""
    cached = listing_cache.get(f"listing:{listing_id}")
    if cached is not None:
        return cached

    result = await db.execute(
        select(DataListing).where(DataListing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise ListingNotFoundError(listing_id)

    listing_cache.put(f"listing:{listing_id}", listing)
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
        raise AuthorizationError("Not the listing owner")

    update_data = req.model_dump(exclude_unset=True)
    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"])

    for field, value in update_data.items():
        setattr(listing, field, value)

    listing.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(listing)
    listing_cache.invalidate(f"listing:{listing_id}")
    return listing


async def delist(db: AsyncSession, listing_id: str, seller_id: str) -> DataListing:
    """Soft-delete a listing."""
    listing = await get_listing(db, listing_id)
    if listing.seller_id != seller_id:
        raise AuthorizationError("Not the listing owner")

    listing.status = "delisted"
    listing.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(listing)
    listing_cache.invalidate(f"listing:{listing_id}")
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
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
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


async def get_listing_content(content_hash: str) -> bytes | None:
    """Retrieve the raw content via CDN (hot → warm → cold)."""
    from marketplace.services.cdn_service import get_content as cdn_get_content
    return await cdn_get_content(content_hash)


def listing_to_response_dict(listing) -> dict:
    """Convert a DataListing ORM model to a serialisable dict.

    Centralises JSON parsing, seller summary building, and trust
    payload assembly so API routes stay thin.
    """
    metadata = listing.metadata_json
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    tags = listing.tags
    if isinstance(tags, str):
        tags = json.loads(tags)

    seller_summary = None
    if listing.seller:
        seller_summary = {"id": listing.seller.id, "name": listing.seller.name}

    trust_payload = trust_verification_service.build_trust_payload(listing)
    price_usd = float(listing.price_usdc)

    return {
        "id": listing.id,
        "seller_id": listing.seller_id,
        "seller": seller_summary,
        "title": listing.title,
        "description": listing.description,
        "category": listing.category,
        "content_hash": listing.content_hash,
        "content_size": listing.content_size,
        "content_type": listing.content_type,
        "price_usdc": price_usd,
        "price_usd": price_usd,
        "currency": listing.currency,
        "metadata": metadata,
        "tags": tags,
        "quality_score": float(listing.quality_score) if listing.quality_score else 0.5,
        "freshness_at": listing.freshness_at,
        "expires_at": listing.expires_at,
        "status": listing.status,
        "trust_status": trust_payload["trust_status"],
        "trust_score": trust_payload["trust_score"],
        "verification_summary": trust_payload["verification_summary"],
        "provenance": trust_payload["provenance"],
        "access_count": listing.access_count,
        "created_at": listing.created_at,
        "updated_at": listing.updated_at,
    }
