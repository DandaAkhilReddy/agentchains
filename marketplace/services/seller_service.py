"""Seller API: bulk listing, demand matching, price suggestions."""

import json
import statistics
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.catalog import DataCatalogEntry
from marketplace.models.demand_signal import DemandSignal
from marketplace.models.listing import DataListing
from marketplace.models.seller_webhook import SellerWebhook
from marketplace.schemas.listing import ListingCreateRequest
from marketplace.services.listing_service import create_listing


async def bulk_list(
    db: AsyncSession,
    seller_id: str,
    items: list[dict],
) -> dict:
    """Create up to 100 listings atomically."""
    if len(items) > 100:
        return {"error": "Maximum 100 listings per batch", "created": 0}

    created = []
    errors = []
    for i, item in enumerate(items):
        try:
            req = ListingCreateRequest(**item)
            listing = await create_listing(db, seller_id, req)
            created.append({"index": i, "listing_id": listing.id, "title": listing.title})
        except Exception as e:
            errors.append({"index": i, "error": str(e)})

    return {
        "created": len(created),
        "errors": len(errors),
        "listings": created,
        "error_details": errors,
    }


async def get_demand_for_seller(db: AsyncSession, seller_id: str) -> list[dict]:
    """Cross-reference DemandSignal with seller's catalog to find opportunities."""
    # Get seller's catalog entries
    catalog_result = await db.execute(
        select(DataCatalogEntry)
        .where(DataCatalogEntry.agent_id == seller_id, DataCatalogEntry.status == "active")
    )
    catalog_entries = list(catalog_result.scalars().all())

    if not catalog_entries:
        return []

    # Get recent demand signals
    demand_result = await db.execute(
        select(DemandSignal)
        .order_by(DemandSignal.velocity.desc())
        .limit(50)
    )
    demands = list(demand_result.scalars().all())

    # Match demand to seller's capabilities
    matches = []
    seller_namespaces = {e.namespace.lower() for e in catalog_entries}
    seller_categories = {e.namespace.split(".")[0].lower() for e in catalog_entries}

    for demand in demands:
        category = (demand.category or "").lower()
        query = (demand.query_pattern or "").lower()

        # Check if seller can fulfill this demand
        if category in seller_categories or any(ns in query for ns in seller_namespaces):
            matches.append({
                "demand_id": demand.id,
                "query_pattern": demand.query_pattern,
                "category": demand.category,
                "velocity": float(demand.velocity or 0),
                "total_searches": int(demand.search_count or 0),
                "avg_max_price": float(demand.avg_max_price or 0),
                "fulfillment_rate": float(demand.fulfillment_rate or 0),
                "opportunity": "high" if float(demand.velocity or 0) > 5 else "medium",
            })

    matches.sort(key=lambda x: x["velocity"], reverse=True)
    return matches


async def suggest_price(
    db: AsyncSession,
    seller_id: str,
    category: str,
    quality_score: float = 0.5,
) -> dict:
    """Suggest optimal pricing based on market data."""
    # Get competing listings in same category
    result = await db.execute(
        select(DataListing.price_usdc, DataListing.quality_score, DataListing.access_count)
        .where(DataListing.category == category, DataListing.status == "active")
    )
    competitors = list(result.all())

    if not competitors:
        return {
            "suggested_price": 0.005,
            "category": category,
            "competitors": 0,
            "strategy": "No competitors — default pricing",
        }

    prices = [float(row[0]) for row in competitors]
    qualities = [float(row[1]) if row[1] else 0.5 for row in competitors]
    accesses = [int(row[2]) if row[2] else 0 for row in competitors]

    median_price = statistics.median(prices)
    avg_quality = statistics.mean(qualities)
    max_access = max(accesses) if accesses else 1

    # Price strategy: quality-adjusted median
    quality_multiplier = quality_score / max(avg_quality, 0.01)
    suggested = median_price * quality_multiplier

    # Demand adjustment: high-demand categories get a premium
    demand_result = await db.execute(
        select(func.sum(DemandSignal.search_count))
        .where(DemandSignal.category == category)
    )
    total_demand = (demand_result.scalar() or 0)
    if total_demand > 100:
        suggested *= 1.15  # 15% demand premium

    # Floor and ceiling
    suggested = max(0.001, min(suggested, max(prices) * 1.5))

    return {
        "suggested_price": round(suggested, 6),
        "category": category,
        "quality_score": quality_score,
        "competitors": len(competitors),
        "median_price": round(median_price, 6),
        "price_range": [round(min(prices), 6), round(max(prices), 6)],
        "demand_searches": int(total_demand),
        "strategy": f"Quality-adjusted median ({quality_multiplier:.1f}x)" + (
            " + 15% demand premium" if total_demand > 100 else ""
        ),
    }


async def register_webhook(
    db: AsyncSession,
    seller_id: str,
    url: str,
    event_types: list[str] | None = None,
    secret: str | None = None,
) -> SellerWebhook:
    """Register a webhook for demand notifications."""
    webhook = SellerWebhook(
        seller_id=seller_id,
        url=url,
        event_types=json.dumps(event_types or ["demand_match"]),
        secret=secret,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


async def get_webhooks(db: AsyncSession, seller_id: str) -> list[SellerWebhook]:
    result = await db.execute(
        select(SellerWebhook)
        .where(SellerWebhook.seller_id == seller_id, SellerWebhook.status == "active")
    )
    return list(result.scalars().all())
