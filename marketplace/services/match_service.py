"""A2A Auto-match service: finds the best seller/listing for a buyer's described need."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.listing import DataListing
from marketplace.models.agent_stats import AgentStats


FRESH_COST_ESTIMATES = {
    "web_search": 0.01,
    "code_analysis": 0.02,
    "document_summary": 0.01,
    "api_response": 0.015,
    "computation": 0.025,
}


async def auto_match(
    db: AsyncSession,
    description: str,
    category: str | None = None,
    max_price: float | None = None,
    buyer_id: str | None = None,
) -> dict:
    """Find the best listing for a buyer's described need.

    Matching algorithm:
    - 0.5 weight: keyword overlap between description and listing text/tags
    - 0.3 weight: quality_score
    - 0.2 weight: freshness (decay over 24 hours)

    Returns top 5 matches with savings estimates.
    """
    keywords = set(description.lower().split())

    query = select(DataListing).where(DataListing.status == "active")
    if category:
        query = query.where(DataListing.category == category)
    if max_price is not None:
        query = query.where(DataListing.price_usdc <= max_price)

    result = await db.execute(query)
    listings = list(result.scalars().all())

    # Pre-fetch seller specializations for bonus scoring
    seller_ids = {l.seller_id for l in listings if l.seller_id}
    specializations: dict[str, str | None] = {}
    if seller_ids and category:
        spec_result = await db.execute(
            select(AgentStats.agent_id, AgentStats.primary_specialization)
            .where(AgentStats.agent_id.in_(seller_ids))
        )
        specializations = {row[0]: row[1] for row in spec_result.all()}

    scored = []
    for listing in listings:
        # Skip buyer's own listings
        if buyer_id and listing.seller_id == buyer_id:
            continue

        score = _compute_match_score(listing, keywords)

        # Specialization bonus: +0.1 if seller specializes in the query category
        if category and listing.seller_id:
            spec = specializations.get(listing.seller_id)
            if spec and spec.lower() == category.lower():
                score = min(score + 0.1, 1.0)

        estimated_fresh_cost = FRESH_COST_ESTIMATES.get(listing.category, 0.01)
        savings = max(0, estimated_fresh_cost - float(listing.price_usdc))

        scored.append({
            "listing_id": listing.id,
            "title": listing.title,
            "category": listing.category,
            "price_usdc": float(listing.price_usdc),
            "quality_score": float(listing.quality_score) if listing.quality_score else 0.5,
            "match_score": round(score, 3),
            "estimated_fresh_cost": estimated_fresh_cost,
            "savings_usdc": round(savings, 6),
            "savings_percent": round(savings / max(estimated_fresh_cost, 0.001) * 100, 1),
            "seller_id": listing.seller_id,
        })

    scored.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "query": description,
        "category_filter": category,
        "matches": scored[:5],
        "total_candidates": len(listings),
    }


def _compute_match_score(listing: DataListing, keywords: set[str]) -> float:
    """Score 0.0-1.0 based on keyword overlap, quality, and freshness."""
    # Text overlap (0.0-0.5)
    listing_words: set[str] = set()
    listing_words.update(listing.title.lower().split())
    listing_words.update(listing.description.lower().split())
    tags = listing.tags
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tags = []
    if tags:
        for tag in tags:
            listing_words.update(str(tag).lower().replace("-", " ").split())

    overlap = len(keywords & listing_words)
    text_score = min(overlap / max(len(keywords), 1), 1.0) * 0.5

    # Quality (0.0-0.3)
    quality = float(listing.quality_score) if listing.quality_score else 0.5
    quality_score = quality * 0.3

    # Freshness (0.0-0.2) — decay over 24 hours
    if listing.freshness_at:
        now = datetime.now(timezone.utc)
        freshness_at = listing.freshness_at
        if freshness_at.tzinfo is None:
            freshness_at = freshness_at.replace(tzinfo=timezone.utc)
        age_hours = (now - freshness_at).total_seconds() / 3600
        freshness_score = max(0, 1 - age_hours / 24) * 0.2
    else:
        freshness_score = 0.0

    return text_score + quality_score + freshness_score
