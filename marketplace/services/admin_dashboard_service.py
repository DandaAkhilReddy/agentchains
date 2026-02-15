"""Admin dashboard aggregation helpers."""

from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.agent import RegisteredAgent
from marketplace.models.agent_trust import AgentTrustProfile
from marketplace.models.audit_log import AuditLog
from marketplace.models.dual_layer import ConsumerOrder, PlatformFee
from marketplace.models.listing import DataListing
from marketplace.models.redemption import RedemptionRequest
from marketplace.models.transaction import Transaction
from marketplace.services import dashboard_service


_TRUST_WEIGHT = {
    "verified_secure_data": 1.0,
    "pending_verification": 0.7,
    "verification_failed": 0.0,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_admin_overview(db: AsyncSession) -> dict:
    total_agents = int((await db.execute(select(func.count(RegisteredAgent.id)))).scalar() or 0)
    active_agents = int(
        (await db.execute(select(func.count(RegisteredAgent.id)).where(RegisteredAgent.status == "active"))).scalar() or 0
    )
    total_listings = int((await db.execute(select(func.count(DataListing.id)))).scalar() or 0)
    active_listings = int(
        (await db.execute(select(func.count(DataListing.id)).where(DataListing.status == "active"))).scalar() or 0
    )

    tx_result = await db.execute(select(Transaction).where(Transaction.status == "completed"))
    completed_tx = list(tx_result.scalars().all())
    platform_volume = sum(float(tx.amount_usdc or 0) for tx in completed_tx)

    listing_ids = {
        listing_id
        for tx in completed_tx
        if (listing_id := dashboard_service._as_non_empty_str(tx.listing_id))  # noqa: SLF001
    }
    listing_map: dict[str, DataListing] = {}
    if listing_ids:
        try:
            listing_result = await db.execute(
                select(DataListing).where(DataListing.id.in_(listing_ids))
            )
            listing_map = {row.id: row for row in listing_result.scalars().all()}
        except Exception:
            listing_map = {}

    trust_weighted = 0.0
    for tx in completed_tx:
        listing = listing_map.get(tx.listing_id)
        trust_status = listing.trust_status if listing else "pending_verification"
        weight = _TRUST_WEIGHT.get(trust_status, 0.7)
        trust_weighted += float(tx.amount_usdc or 0) * weight

    return {
        "environment": settings.environment,
        "total_agents": total_agents,
        "active_agents": active_agents,
        "total_listings": total_listings,
        "active_listings": active_listings,
        "total_transactions": int((await db.execute(select(func.count(Transaction.id)))).scalar() or 0),
        "completed_transactions": len(completed_tx),
        "platform_volume_usd": round(platform_volume, 6),
        "trust_weighted_revenue_usd": round(trust_weighted, 6),
        "updated_at": _utcnow(),
    }


async def get_admin_finance(db: AsyncSession) -> dict:
    tx_result = await db.execute(select(Transaction).where(Transaction.status == "completed"))
    completed_tx = list(tx_result.scalars().all())
    platform_volume = sum(float(tx.amount_usdc or 0) for tx in completed_tx)
    consumer_orders_count = int((await db.execute(select(func.count(ConsumerOrder.id)))).scalar() or 0)
    fee_result = await db.execute(select(func.sum(PlatformFee.fee_usd)))
    platform_fee_volume_usd = float(fee_result.scalar() or 0)

    pending_payouts = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.status == "pending")
    )
    processing_payouts = await db.execute(
        select(RedemptionRequest).where(RedemptionRequest.status == "processing")
    )
    pending_rows = list(pending_payouts.scalars().all())
    processing_rows = list(processing_payouts.scalars().all())

    by_seller: dict[str, float] = {}
    for tx in completed_tx:
        seller_id = dashboard_service._as_non_empty_str(tx.seller_id) or "unknown"  # noqa: SLF001
        by_seller[seller_id] = by_seller.get(seller_id, 0.0) + float(tx.amount_usdc or 0)

    names_result = await db.execute(select(RegisteredAgent.id, RegisteredAgent.name))
    names = {row[0]: row[1] for row in names_result.all()}

    top_sellers = [
        {
            "agent_id": seller_id,
            "agent_name": names.get(seller_id, "Unknown"),
            "money_received_usd": round(amount, 6),
        }
        for seller_id, amount in sorted(by_seller.items(), key=lambda item: item[1], reverse=True)[:20]
    ]

    return {
        "platform_volume_usd": round(platform_volume, 6),
        "completed_transaction_count": len(completed_tx),
        "consumer_orders_count": consumer_orders_count,
        "platform_fee_volume_usd": round(platform_fee_volume_usd, 6),
        "payout_pending_count": len(pending_rows),
        "payout_pending_usd": round(sum(float(r.amount_usd or 0) for r in pending_rows), 6),
        "payout_processing_count": len(processing_rows),
        "payout_processing_usd": round(sum(float(r.amount_usd or 0) for r in processing_rows), 6),
        "top_sellers_by_revenue": top_sellers,
        "updated_at": _utcnow(),
    }


async def get_admin_usage(db: AsyncSession) -> dict:
    tx_result = await db.execute(select(Transaction).where(Transaction.status == "completed"))
    completed = list(tx_result.scalars().all())
    listing_ids = {
        listing_id
        for tx in completed
        if (listing_id := dashboard_service._as_non_empty_str(tx.listing_id))  # noqa: SLF001
    }

    listing_map: dict[str, DataListing] = {}
    if listing_ids:
        try:
            listing_result = await db.execute(
                select(DataListing).where(DataListing.id.in_(listing_ids))
            )
            listing_map = {row.id: row for row in listing_result.scalars().all()}
        except Exception:
            listing_map = {}

    info_used_count = len(completed)
    data_served_bytes = 0
    money_saved = 0.0
    category: dict[str, dict] = {}

    for tx in completed:
        listing = listing_map.get(tx.listing_id)
        if listing is None:
            continue
        amount = float(tx.amount_usdc or 0)
        fresh_cost = dashboard_service._fresh_cost_estimate_usd(listing)  # noqa: SLF001
        saved = max(fresh_cost - amount, 0.0)
        data_served_bytes += int(listing.content_size or 0)
        money_saved += saved
        bucket = category.setdefault(
            listing.category,
            {"category": listing.category, "usage_count": 0, "volume_usd": 0.0, "money_saved_usd": 0.0},
        )
        bucket["usage_count"] += 1
        bucket["volume_usd"] += amount
        bucket["money_saved_usd"] += saved

    return {
        "info_used_count": info_used_count,
        "data_served_bytes": data_served_bytes,
        "unique_buyers_count": len({tx.buyer_id for tx in completed if tx.buyer_id}),
        "unique_sellers_count": len({tx.seller_id for tx in completed if tx.seller_id}),
        "money_saved_for_others_usd": round(money_saved, 6),
        "category_breakdown": sorted(
            (
                {
                    "category": row["category"],
                    "usage_count": row["usage_count"],
                    "volume_usd": round(float(row["volume_usd"]), 6),
                    "money_saved_usd": round(float(row["money_saved_usd"]), 6),
                }
                for row in category.values()
            ),
            key=lambda row: row["usage_count"],
            reverse=True,
        ),
        "updated_at": _utcnow(),
    }


async def list_admin_agents(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> dict:
    stmt = select(RegisteredAgent)
    count_stmt = select(func.count(RegisteredAgent.id))
    if status:
        stmt = stmt.where(RegisteredAgent.status == status)
        count_stmt = count_stmt.where(RegisteredAgent.status == status)

    stmt = stmt.order_by(RegisteredAgent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    total = int((await db.execute(count_stmt)).scalar() or 0)
    agents = list((await db.execute(stmt)).scalars().all())

    trust_rows = await db.execute(select(AgentTrustProfile))
    trust_map = {row.agent_id: row for row in trust_rows.scalars().all()}

    entries = []
    for agent in agents:
        metrics = await dashboard_service.get_agent_dashboard(db, agent.id)
        trust = trust_map.get(agent.id)
        entries.append(
            {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "status": agent.status,
                "trust_status": trust.trust_status if trust else metrics["trust_status"],
                "trust_tier": trust.trust_tier if trust else metrics["trust_tier"],
                "trust_score": int(trust.trust_score) if trust else metrics["trust_score"],
                "money_received_usd": metrics["money_received_usd"],
                "info_used_count": metrics["info_used_count"],
                "other_agents_served_count": metrics["other_agents_served_count"],
                "data_served_bytes": metrics["data_served_bytes"],
            }
        )

    return {"total": total, "page": page, "page_size": page_size, "entries": entries}


async def list_security_events(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    severity: str | None = None,
    event_type: str | None = None,
) -> dict:
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))
    if severity:
        stmt = stmt.where(AuditLog.severity == severity)
        count_stmt = count_stmt.where(AuditLog.severity == severity)
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
        count_stmt = count_stmt.where(AuditLog.event_type == event_type)

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(stmt)).scalars().all())
    total = int((await db.execute(count_stmt)).scalar() or 0)

    events = []
    for row in rows:
        try:
            details = row.details if isinstance(row.details, dict) else {}
            if isinstance(row.details, str):
                import json

                details = json.loads(row.details)
        except Exception:
            details = {}
        events.append(
            {
                "id": row.id,
                "event_type": row.event_type,
                "severity": row.severity,
                "agent_id": row.agent_id,
                "creator_id": row.creator_id,
                "ip_address": row.ip_address,
                "details": details,
                "created_at": row.created_at,
            }
        )
    return {"total": total, "page": page, "page_size": page_size, "events": events}


async def list_pending_payouts(db: AsyncSession, *, limit: int = 100) -> dict:
    pending = await db.execute(
        select(RedemptionRequest)
        .where(RedemptionRequest.status == "pending")
        .order_by(RedemptionRequest.created_at.asc())
        .limit(max(1, min(limit, 500)))
    )
    rows = list(pending.scalars().all())
    return {
        "count": len(rows),
        "total_pending_usd": round(sum(float(row.amount_usd or 0) for row in rows), 6),
        "requests": [
            {
                "id": row.id,
                "creator_id": row.creator_id,
                "redemption_type": row.redemption_type,
                "amount_usd": float(row.amount_usd or 0),
                "currency": row.currency,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }
