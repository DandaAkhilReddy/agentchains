"""Demand Intelligence Service: tracks searches, aggregates demand, detects gaps and opportunities."""

import uuid
import json
import math
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.search_log import SearchLog
from marketplace.models.demand_signal import DemandSignal
from marketplace.models.opportunity import OpportunitySignal
from marketplace.models.listing import DataListing


def normalize_query(text: str) -> str:
    """Normalize a search query for deduplication: lowercase, sorted unique words."""
    words = sorted(set(text.lower().strip().split()))
    return " ".join(words)


async def log_search(
    db: AsyncSession,
    query_text: str,
    category: str | None = None,
    source: str = "discover",
    requester_id: str | None = None,
    matched_count: int = 0,
    led_to_purchase: int = 0,
    max_price: float | None = None,
) -> SearchLog:
    """Insert a SearchLog row. Called from discover, auto_match, and express routes."""
    log = SearchLog(
        query_text=query_text,
        category=category,
        source=source,
        requester_id=requester_id,
        matched_count=matched_count,
        led_to_purchase=led_to_purchase,
        max_price=max_price,
    )
    db.add(log)
    await db.commit()
    return log


async def aggregate_demand(db: AsyncSession, time_window_hours: int = 24) -> list[DemandSignal]:
    """Aggregate SearchLogs into DemandSignals within a time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

    result = await db.execute(
        select(SearchLog).where(SearchLog.created_at >= cutoff)
    )
    logs = list(result.scalars().all())

    if not logs:
        return []

    # Group by normalized query
    groups: dict[str, list[SearchLog]] = defaultdict(list)
    for log in logs:
        pattern = normalize_query(log.query_text)
        if pattern:
            groups[pattern].append(log)

    signals = []
    for pattern, group_logs in groups.items():
        search_count = len(group_logs)
        requesters = set(l.requester_id for l in group_logs if l.requester_id)
        unique_requesters = len(requesters) if requesters else 1
        prices = [float(l.max_price) for l in group_logs if l.max_price is not None]
        avg_max_price = sum(prices) / len(prices) if prices else None
        matched = sum(1 for l in group_logs if l.matched_count > 0)
        fulfillment_rate = round(matched / search_count, 3)
        purchased = sum(1 for l in group_logs if l.led_to_purchase)
        conversion_rate = round(purchased / search_count, 3)

        # Velocity: searches per hour
        span_hours = max(time_window_hours, 1)
        velocity = round(search_count / span_hours, 2)

        is_gap = 1 if fulfillment_rate < 0.2 else 0

        # Most common category in this group
        cats = [l.category for l in group_logs if l.category]
        category = max(set(cats), key=cats.count) if cats else None

        timestamps = [l.created_at for l in group_logs if l.created_at]
        first = min(timestamps) if timestamps else datetime.now(timezone.utc)
        last = max(timestamps) if timestamps else datetime.now(timezone.utc)

        # Upsert
        existing = await db.execute(
            select(DemandSignal).where(DemandSignal.query_pattern == pattern)
        )
        signal = existing.scalar_one_or_none()

        if signal:
            signal.search_count = search_count
            signal.unique_requesters = unique_requesters
            signal.avg_max_price = avg_max_price
            signal.fulfillment_rate = fulfillment_rate
            signal.conversion_rate = conversion_rate
            signal.velocity = velocity
            signal.is_gap = is_gap
            signal.category = category
            signal.last_searched_at = last
        else:
            signal = DemandSignal(
                query_pattern=pattern,
                category=category,
                search_count=search_count,
                unique_requesters=unique_requesters,
                avg_max_price=avg_max_price,
                fulfillment_rate=fulfillment_rate,
                conversion_rate=conversion_rate,
                velocity=velocity,
                is_gap=is_gap,
                first_searched_at=first,
                last_searched_at=last,
            )
            db.add(signal)

        signals.append(signal)

    await db.commit()
    return signals


async def get_trending(
    db: AsyncSession, limit: int = 20, hours: int = 6
) -> list[DemandSignal]:
    """Return top demand signals by velocity within a time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(DemandSignal)
        .where(DemandSignal.last_searched_at >= cutoff)
        .order_by(DemandSignal.velocity.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_demand_gaps(
    db: AsyncSession, limit: int = 20, category: str | None = None
) -> list[DemandSignal]:
    """Return unmet demand: queries searched but rarely fulfilled."""
    query = select(DemandSignal).where(DemandSignal.is_gap == 1)
    if category:
        query = query.where(DemandSignal.category == category)
    query = query.order_by(DemandSignal.search_count.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def generate_opportunities(db: AsyncSession) -> list[OpportunitySignal]:
    """Create OpportunitySignals from top demand gaps."""
    gaps = await get_demand_gaps(db, limit=50)
    if not gaps:
        return []

    # Count competing listings for each gap
    opportunities = []
    max_velocity = max(float(g.velocity or 0) for g in gaps) if gaps else 1
    max_requesters = max(g.unique_requesters for g in gaps) if gaps else 1

    for gap in gaps:
        # Count active listings that match this query pattern
        keywords = gap.query_pattern.split()
        count_query = select(func.count(DataListing.id)).where(DataListing.status == "active")
        if gap.category:
            count_query = count_query.where(DataListing.category == gap.category)
        competing = (await db.execute(count_query)).scalar() or 0

        velocity = float(gap.velocity or 0)
        avg_price = float(gap.avg_max_price) if gap.avg_max_price else 0.005
        estimated_revenue = round(velocity * avg_price, 6)

        # Urgency: 0.4 * normalized_velocity + 0.3 * (1 - fulfillment_rate) + 0.3 * normalized_requesters
        norm_velocity = velocity / max(max_velocity, 0.01)
        fulfillment = float(gap.fulfillment_rate or 0)
        norm_requesters = gap.unique_requesters / max(max_requesters, 1)
        urgency = round(0.4 * norm_velocity + 0.3 * (1 - fulfillment) + 0.3 * norm_requesters, 3)

        # Upsert by demand_signal_id
        existing = await db.execute(
            select(OpportunitySignal).where(
                OpportunitySignal.demand_signal_id == gap.id,
                OpportunitySignal.status == "active",
            )
        )
        opp = existing.scalar_one_or_none()

        if opp:
            opp.estimated_revenue_usdc = estimated_revenue
            opp.search_velocity = velocity
            opp.competing_listings = competing
            opp.urgency_score = urgency
        else:
            opp = OpportunitySignal(
                demand_signal_id=gap.id,
                query_pattern=gap.query_pattern,
                category=gap.category,
                estimated_revenue_usdc=estimated_revenue,
                search_velocity=velocity,
                competing_listings=competing,
                urgency_score=urgency,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            db.add(opp)

        opportunities.append(opp)

    await db.commit()
    return opportunities


async def get_opportunities(
    db: AsyncSession, category: str | None = None, limit: int = 20
) -> list[OpportunitySignal]:
    """Return active opportunities ordered by urgency."""
    query = select(OpportunitySignal).where(OpportunitySignal.status == "active")
    if category:
        query = query.where(OpportunitySignal.category == category)
    query = query.order_by(OpportunitySignal.urgency_score.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())
