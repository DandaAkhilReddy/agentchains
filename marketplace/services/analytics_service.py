"""Analytics service: earnings breakdown, agent stats, and multi-leaderboards."""

import json
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.agent_stats import AgentStats
from marketplace.models.listing import DataListing as Listing
from marketplace.models.transaction import Transaction


async def get_earnings_breakdown(db: AsyncSession, agent_id: str) -> dict:
    """Get the authenticated agent's earnings breakdown."""
    # Earnings as seller (completed transactions)
    seller_txns = await db.execute(
        select(Transaction).where(
            Transaction.seller_id == agent_id,
            Transaction.status == "completed",
        )
    )
    seller_list = list(seller_txns.scalars().all())

    # Spending as buyer
    buyer_txns = await db.execute(
        select(Transaction).where(
            Transaction.buyer_id == agent_id,
            Transaction.status == "completed",
        )
    )
    buyer_list = list(buyer_txns.scalars().all())

    total_earned = sum(float(t.amount_usdc) for t in seller_list)
    total_spent = sum(float(t.amount_usdc) for t in buyer_list)

    # Earnings by category — join with listing
    earnings_by_cat: dict[str, float] = defaultdict(float)
    for t in seller_list:
        listing_result = await db.execute(
            select(Listing.category).where(Listing.id == t.listing_id)
        )
        row = listing_result.first()
        cat = row[0] if row else "unknown"
        earnings_by_cat[cat] += float(t.amount_usdc)

    # Timeline (grouped by date)
    timeline: dict[str, dict] = {}
    for t in seller_list:
        day = t.initiated_at.strftime("%Y-%m-%d")
        if day not in timeline:
            timeline[day] = {"date": day, "earned": 0.0, "spent": 0.0}
        timeline[day]["earned"] += float(t.amount_usdc)
    for t in buyer_list:
        day = t.initiated_at.strftime("%Y-%m-%d")
        if day not in timeline:
            timeline[day] = {"date": day, "earned": 0.0, "spent": 0.0}
        timeline[day]["spent"] += float(t.amount_usdc)

    return {
        "agent_id": agent_id,
        "total_earned_usdc": total_earned,
        "total_spent_usdc": total_spent,
        "net_revenue_usdc": total_earned - total_spent,
        "earnings_by_category": dict(earnings_by_cat),
        "earnings_timeline": sorted(timeline.values(), key=lambda x: x["date"]),
    }


async def get_agent_stats(db: AsyncSession, agent_id: str) -> AgentStats:
    """Get or create agent stats, recalculating from live data."""
    result = await db.execute(
        select(AgentStats).where(AgentStats.agent_id == agent_id)
    )
    stats = result.scalar_one_or_none()
    if not stats:
        stats = AgentStats(agent_id=agent_id)
        db.add(stats)

    # Recalculate from live data
    # Listings
    listing_result = await db.execute(
        select(func.count(), func.sum(Listing.content_size), func.avg(Listing.quality_score))
        .where(Listing.seller_id == agent_id, Listing.status == "active")
    )
    row = listing_result.first()
    stats.total_listings_created = row[0] or 0
    stats.total_data_bytes_contributed = int(row[1] or 0)
    stats.avg_listing_quality = float(row[2] or 0.5)

    # Categories
    cat_result = await db.execute(
        select(Listing.category).where(
            Listing.seller_id == agent_id, Listing.status == "active"
        ).distinct()
    )
    categories = [r[0] for r in cat_result.all()]
    stats.categories_json = json.dumps(categories)
    stats.category_count = len(categories)
    stats.primary_specialization = categories[0] if categories else None
    stats.specialization_tags_json = json.dumps(categories)

    # Transaction metrics
    seller_txns = await db.execute(
        select(Transaction).where(
            Transaction.seller_id == agent_id, Transaction.status == "completed"
        )
    )
    seller_list = list(seller_txns.scalars().all())
    stats.total_earned_usdc = sum(float(t.amount_usdc) for t in seller_list)

    buyer_txns = await db.execute(
        select(Transaction).where(
            Transaction.buyer_id == agent_id, Transaction.status == "completed"
        )
    )
    buyer_list = list(buyer_txns.scalars().all())
    stats.total_spent_usdc = sum(float(t.amount_usdc) for t in buyer_list)

    # Unique buyers served
    unique_buyers = set(t.buyer_id for t in seller_list)
    stats.unique_buyers_served = len(unique_buyers)

    # Access counts (cache hits)
    access_result = await db.execute(
        select(func.sum(Listing.access_count)).where(Listing.seller_id == agent_id)
    )
    stats.total_cache_hits = int(access_result.scalar() or 0)

    # Helpfulness score: normalized metric
    stats.helpfulness_score = min(
        0.3 * min(stats.unique_buyers_served / 10, 1.0)
        + 0.3 * min(stats.total_listings_created / 20, 1.0)
        + 0.2 * float(stats.avg_listing_quality)
        + 0.2 * min(stats.total_cache_hits / 50, 1.0),
        1.0,
    )

    stats.last_calculated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(stats)
    return stats


async def get_multi_leaderboard(
    db: AsyncSession, board_type: str, limit: int = 20
) -> list[dict]:
    """Get multi-dimensional leaderboard entries."""
    if board_type == "helpfulness":
        stats_result = await db.execute(
            select(AgentStats)
            .order_by(AgentStats.helpfulness_score.desc())
            .limit(limit)
        )
        stats_list = list(stats_result.scalars().all())
        entries = []
        for rank, s in enumerate(stats_list, 1):
            agent_result = await db.execute(
                select(RegisteredAgent.name).where(RegisteredAgent.id == s.agent_id)
            )
            row = agent_result.first()
            entries.append({
                "rank": rank,
                "agent_id": s.agent_id,
                "agent_name": row[0] if row else "Unknown",
                "primary_score": float(s.helpfulness_score),
                "secondary_label": f"{s.unique_buyers_served} buyers served",
                "total_transactions": s.unique_buyers_served + s.total_cache_hits,
                "helpfulness_score": float(s.helpfulness_score),
                "total_earned_usdc": float(s.total_earned_usdc),
            })
        return entries

    elif board_type == "earnings":
        stats_result = await db.execute(
            select(AgentStats)
            .order_by(AgentStats.total_earned_usdc.desc())
            .limit(limit)
        )
        stats_list = list(stats_result.scalars().all())
        entries = []
        for rank, s in enumerate(stats_list, 1):
            agent_result = await db.execute(
                select(RegisteredAgent.name).where(RegisteredAgent.id == s.agent_id)
            )
            row = agent_result.first()
            entries.append({
                "rank": rank,
                "agent_id": s.agent_id,
                "agent_name": row[0] if row else "Unknown",
                "primary_score": float(s.total_earned_usdc),
                "secondary_label": f"${float(s.total_earned_usdc):.4f} earned",
                "total_transactions": s.total_listings_created,
                "helpfulness_score": float(s.helpfulness_score),
                "total_earned_usdc": float(s.total_earned_usdc),
            })
        return entries

    elif board_type == "contributors":
        stats_result = await db.execute(
            select(AgentStats)
            .order_by(AgentStats.total_data_bytes_contributed.desc())
            .limit(limit)
        )
        stats_list = list(stats_result.scalars().all())
        entries = []
        for rank, s in enumerate(stats_list, 1):
            agent_result = await db.execute(
                select(RegisteredAgent.name).where(RegisteredAgent.id == s.agent_id)
            )
            row = agent_result.first()
            entries.append({
                "rank": rank,
                "agent_id": s.agent_id,
                "agent_name": row[0] if row else "Unknown",
                "primary_score": s.total_data_bytes_contributed,
                "secondary_label": f"{s.total_data_bytes_contributed} bytes",
                "total_transactions": s.total_listings_created,
                "helpfulness_score": float(s.helpfulness_score),
                "total_earned_usdc": float(s.total_earned_usdc),
            })
        return entries

    else:
        # category:<name> or fallback
        return []
