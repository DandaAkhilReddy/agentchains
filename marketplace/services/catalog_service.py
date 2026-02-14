"""Data Catalog: agents declare capabilities, buyers discover sellers."""

import fnmatch
import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.async_tasks import fire_and_forget
from marketplace.models.catalog import CatalogSubscription, DataCatalogEntry
from marketplace.models.listing import DataListing


async def register_catalog_entry(
    db: AsyncSession,
    agent_id: str,
    namespace: str,
    topic: str,
    description: str = "",
    schema_json: dict | None = None,
    price_range_min: float = 0.001,
    price_range_max: float = 0.01,
) -> DataCatalogEntry:
    """Seller declares: 'I can produce this type of data.'"""
    entry = DataCatalogEntry(
        agent_id=agent_id,
        namespace=namespace,
        topic=topic,
        description=description,
        schema_json=json.dumps(schema_json or {}),
        price_range_min=price_range_min,
        price_range_max=price_range_max,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    # Notify subscribers
    await notify_subscribers(db, entry)

    return entry


async def search_catalog(
    db: AsyncSession,
    q: str | None = None,
    namespace: str | None = None,
    agent_id: str | None = None,
    min_quality: float | None = None,
    max_price: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DataCatalogEntry], int]:
    """Buyer discovers capabilities: 'who sells Python data?'"""
    query = select(DataCatalogEntry).where(DataCatalogEntry.status == "active")
    count_query = select(func.count(DataCatalogEntry.id)).where(DataCatalogEntry.status == "active")

    if q:
        pattern = f"%{q}%"
        cond = (
            DataCatalogEntry.topic.ilike(pattern)
            | DataCatalogEntry.description.ilike(pattern)
            | DataCatalogEntry.namespace.ilike(pattern)
        )
        query = query.where(cond)
        count_query = count_query.where(cond)

    if namespace:
        query = query.where(DataCatalogEntry.namespace == namespace)
        count_query = count_query.where(DataCatalogEntry.namespace == namespace)

    if agent_id:
        query = query.where(DataCatalogEntry.agent_id == agent_id)
        count_query = count_query.where(DataCatalogEntry.agent_id == agent_id)

    if min_quality is not None:
        query = query.where(DataCatalogEntry.quality_avg >= min_quality)
        count_query = count_query.where(DataCatalogEntry.quality_avg >= min_quality)

    if max_price is not None:
        query = query.where(DataCatalogEntry.price_range_min <= max_price)
        count_query = count_query.where(DataCatalogEntry.price_range_min <= max_price)

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(DataCatalogEntry.active_listings_count.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    entries = list(result.scalars().all())

    return entries, total


async def get_catalog_entry(db: AsyncSession, entry_id: str) -> DataCatalogEntry | None:
    result = await db.execute(
        select(DataCatalogEntry).where(DataCatalogEntry.id == entry_id)
    )
    return result.scalar_one_or_none()


async def update_catalog_entry(
    db: AsyncSession,
    entry_id: str,
    agent_id: str,
    **kwargs,
) -> DataCatalogEntry | None:
    entry = await get_catalog_entry(db, entry_id)
    if not entry or entry.agent_id != agent_id:
        return None
    for k, v in kwargs.items():
        if hasattr(entry, k) and v is not None:
            setattr(entry, k, v)
    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_catalog_entry(db: AsyncSession, entry_id: str, agent_id: str) -> bool:
    entry = await get_catalog_entry(db, entry_id)
    if not entry or entry.agent_id != agent_id:
        return False
    entry.status = "retired"
    await db.commit()
    return True


async def get_agent_catalog(db: AsyncSession, agent_id: str) -> list[DataCatalogEntry]:
    result = await db.execute(
        select(DataCatalogEntry)
        .where(DataCatalogEntry.agent_id == agent_id, DataCatalogEntry.status == "active")
    )
    return list(result.scalars().all())


# ── Subscriptions ────────────────────────────────────────────

async def subscribe(
    db: AsyncSession,
    subscriber_id: str,
    namespace_pattern: str,
    topic_pattern: str = "*",
    category_filter: str | None = None,
    max_price: float | None = None,
    min_quality: float | None = None,
    notify_via: str = "websocket",
    webhook_url: str | None = None,
) -> CatalogSubscription:
    sub = CatalogSubscription(
        subscriber_id=subscriber_id,
        namespace_pattern=namespace_pattern,
        topic_pattern=topic_pattern,
        category_filter=category_filter,
        max_price=max_price,
        min_quality=min_quality,
        notify_via=notify_via,
        webhook_url=webhook_url,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def unsubscribe(db: AsyncSession, sub_id: str, subscriber_id: str) -> bool:
    result = await db.execute(
        select(CatalogSubscription).where(CatalogSubscription.id == sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub or sub.subscriber_id != subscriber_id:
        return False
    sub.status = "paused"
    await db.commit()
    return True


async def get_subscriptions(db: AsyncSession, subscriber_id: str) -> list[CatalogSubscription]:
    result = await db.execute(
        select(CatalogSubscription)
        .where(CatalogSubscription.subscriber_id == subscriber_id, CatalogSubscription.status == "active")
    )
    return list(result.scalars().all())


async def notify_subscribers(db: AsyncSession, entry: DataCatalogEntry):
    """Notify subscribers whose patterns match the new catalog entry."""
    result = await db.execute(
        select(CatalogSubscription).where(CatalogSubscription.status == "active")
    )
    subs = list(result.scalars().all())

    for sub in subs:
        # Skip self-notifications
        if sub.subscriber_id == entry.agent_id:
            continue

        # Check namespace pattern match
        if not fnmatch.fnmatch(entry.namespace, sub.namespace_pattern):
            continue

        # Check topic pattern match
        if sub.topic_pattern != "*" and not fnmatch.fnmatch(entry.topic.lower(), sub.topic_pattern.lower()):
            continue

        # Check price filter
        if sub.max_price is not None and float(entry.price_range_min) > float(sub.max_price):
            continue

        # Check quality filter
        if sub.min_quality is not None and float(entry.quality_avg) < float(sub.min_quality):
            continue

        # Push notification via WebSocket
        if sub.notify_via == "websocket":
            try:
                from marketplace.main import broadcast_event
                fire_and_forget(
                    broadcast_event("catalog_update", {
                        "entry_id": entry.id,
                        "namespace": entry.namespace,
                        "topic": entry.topic,
                        "agent_id": entry.agent_id,
                        "price_range": [float(entry.price_range_min), float(entry.price_range_max)],
                        "subscriber_id": sub.subscriber_id,
                    }),
                    task_name="broadcast_catalog_update",
                )
            except Exception:
                pass


async def auto_populate_catalog(db: AsyncSession, agent_id: str) -> list[DataCatalogEntry]:
    """Scan agent's existing listings and auto-create catalog entries by grouping category+tags."""
    result = await db.execute(
        select(DataListing)
        .where(DataListing.seller_id == agent_id, DataListing.status == "active")
    )
    listings = list(result.scalars().all())

    # Group by category
    groups: dict[str, list[DataListing]] = {}
    for listing in listings:
        groups.setdefault(listing.category, []).append(listing)

    created = []
    for category, group_listings in groups.items():
        # Check if catalog entry already exists
        existing = await db.execute(
            select(DataCatalogEntry)
            .where(
                DataCatalogEntry.agent_id == agent_id,
                DataCatalogEntry.namespace == category,
                DataCatalogEntry.status == "active",
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Compute stats
        prices = [float(listing.price_usdc) for listing in group_listings]
        qualities = [
            float(listing.quality_score) if listing.quality_score else 0.5
            for listing in group_listings
        ]

        entry = DataCatalogEntry(
            agent_id=agent_id,
            namespace=category,
            topic=f"Auto-populated {category} data",
            description=f"Agent has {len(group_listings)} active {category} listings",
            price_range_min=min(prices),
            price_range_max=max(prices),
            quality_avg=sum(qualities) / len(qualities),
            active_listings_count=len(group_listings),
        )
        db.add(entry)
        created.append(entry)

    if created:
        await db.commit()
        for e in created:
            await db.refresh(e)

    return created
