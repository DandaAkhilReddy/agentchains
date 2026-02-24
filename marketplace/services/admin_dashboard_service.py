"""Admin dashboard aggregation helpers."""

from __future__ import annotations
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.core.utils import utcnow as _utcnow
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


async def get_admin_overview(db: AsyncSession) -> dict:
    total_agents = int((await db.execute(select(func.count(RegisteredAgent.id)))).scalar() or 0)
    active_agents = int(
        (await db.execute(select(func.count(RegisteredAgent.id)).where(RegisteredAgent.status == "active"))).scalar() or 0
    )
    total_listings = int((await db.execute(select(func.count(DataListing.id)))).scalar() or 0)
    active_listings = int(
        (await db.execute(select(func.count(DataListing.id)).where(DataListing.status == "active"))).scalar() or 0
    )
    total_transactions = int((await db.execute(select(func.count(Transaction.id)))).scalar() or 0)

    # SQL aggregation for completed transaction totals
    tx_agg = await db.execute(
        select(
            func.count(Transaction.id),
            func.sum(Transaction.amount_usdc),
        ).where(Transaction.status == "completed")
    )
    tx_agg_row = tx_agg.first()
    completed_count = int(tx_agg_row[0] or 0)
    platform_volume = float(tx_agg_row[1] or 0)

    # Trust-weighted revenue still needs listing join, but use batch approach
    trust_weighted = 0.0
    if completed_count > 0:
        tx_result = await db.execute(select(Transaction).where(Transaction.status == "completed"))
        completed_tx = list(tx_result.scalars().all())
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
        "total_transactions": total_transactions,
        "completed_transactions": completed_count,
        "platform_volume_usd": round(platform_volume, 6),
        "trust_weighted_revenue_usd": round(trust_weighted, 6),
        "updated_at": _utcnow(),
    }


async def get_admin_finance(db: AsyncSession) -> dict:
    # SQL aggregation for transaction totals
    tx_agg = await db.execute(
        select(
            func.count(Transaction.id),
            func.sum(Transaction.amount_usdc),
        ).where(Transaction.status == "completed")
    )
    tx_agg_row = tx_agg.first()
    completed_count = int(tx_agg_row[0] or 0)
    platform_volume = float(tx_agg_row[1] or 0)

    consumer_orders_count = int((await db.execute(select(func.count(ConsumerOrder.id)))).scalar() or 0)
    fee_result = await db.execute(select(func.sum(PlatformFee.fee_usd)))
    platform_fee_volume_usd = float(fee_result.scalar() or 0)

    # SQL aggregation for payout stats
    payout_agg = await db.execute(
        select(
            RedemptionRequest.status,
            func.count(RedemptionRequest.id),
            func.sum(RedemptionRequest.amount_usd),
        )
        .where(RedemptionRequest.status.in_(["pending", "processing"]))
        .group_by(RedemptionRequest.status)
    )
    payout_stats: dict[str, dict] = {}
    for row in payout_agg.all():
        payout_stats[row[0]] = {"count": int(row[1] or 0), "usd": float(row[2] or 0)}

    # Top sellers by revenue — SQL aggregation
    seller_agg = await db.execute(
        select(
            Transaction.seller_id,
            func.sum(Transaction.amount_usdc).label("total"),
        )
        .where(Transaction.status == "completed")
        .group_by(Transaction.seller_id)
        .order_by(func.sum(Transaction.amount_usdc).desc())
        .limit(20)
    )
    seller_rows = seller_agg.all()
    seller_ids = {row[0] for row in seller_rows if row[0]}
    names: dict[str, str] = {}
    if seller_ids:
        names_result = await db.execute(
            select(RegisteredAgent.id, RegisteredAgent.name).where(
                RegisteredAgent.id.in_(seller_ids)
            )
        )
        names = {row[0]: row[1] for row in names_result.all()}

    top_sellers = [
        {
            "agent_id": row[0] or "unknown",
            "agent_name": names.get(row[0], "Unknown"),
            "money_received_usd": round(float(row[1] or 0), 6),
        }
        for row in seller_rows
    ]

    pending = payout_stats.get("pending", {"count": 0, "usd": 0})
    processing = payout_stats.get("processing", {"count": 0, "usd": 0})
    return {
        "platform_volume_usd": round(platform_volume, 6),
        "completed_transaction_count": completed_count,
        "consumer_orders_count": consumer_orders_count,
        "platform_fee_volume_usd": round(platform_fee_volume_usd, 6),
        "payout_pending_count": pending["count"],
        "payout_pending_usd": round(pending["usd"], 6),
        "payout_processing_count": processing["count"],
        "payout_processing_usd": round(processing["usd"], 6),
        "top_sellers_by_revenue": top_sellers,
        "updated_at": _utcnow(),
    }


async def get_admin_usage(db: AsyncSession) -> dict:
    # SQL aggregation: total completed count, unique buyers/sellers
    overview_agg = await db.execute(
        select(
            func.count(Transaction.id),
            func.count(Transaction.buyer_id.distinct()),
            func.count(Transaction.seller_id.distinct()),
        ).where(Transaction.status == "completed")
    )
    overview_row = overview_agg.first()
    info_used_count = int(overview_row[0] or 0)
    unique_buyers = int(overview_row[1] or 0)
    unique_sellers = int(overview_row[2] or 0)

    # SQL JOIN aggregation: category breakdown (count, volume, data bytes)
    cat_agg = await db.execute(
        select(
            DataListing.category,
            func.count(Transaction.id),
            func.sum(Transaction.amount_usdc),
            func.sum(DataListing.content_size),
        )
        .join(DataListing, Transaction.listing_id == DataListing.id)
        .where(Transaction.status == "completed")
        .group_by(DataListing.category)
    )
    cat_rows = cat_agg.all()

    data_served_bytes = sum(int(row[3] or 0) for row in cat_rows)
    category_breakdown: list[dict] = []
    category_volume: dict[str, float] = {}
    for row in cat_rows:
        cat_name = row[0] or "unknown"
        volume = float(row[2] or 0)
        category_volume[cat_name] = volume
        category_breakdown.append({
            "category": cat_name,
            "usage_count": int(row[1] or 0),
            "volume_usd": round(volume, 6),
            "money_saved_usd": 0.0,  # computed below from listing metadata
        })

    # money_saved requires _fresh_cost_estimate_usd which parses listing metadata JSON,
    # so we load only the distinct listings involved (not all transactions)
    money_saved = 0.0
    listing_ids_result = await db.execute(
        select(Transaction.listing_id).where(
            Transaction.status == "completed",
            Transaction.listing_id.isnot(None),
        ).distinct()
    )
    listing_ids = {row[0] for row in listing_ids_result.all() if row[0] and row[0].strip()}

    if listing_ids:
        listing_result = await db.execute(
            select(DataListing).where(DataListing.id.in_(listing_ids))
        )
        listings = list(listing_result.scalars().all())

        # Per-listing: get transaction volume from SQL
        vol_agg = await db.execute(
            select(
                Transaction.listing_id,
                func.count(Transaction.id),
                func.sum(Transaction.amount_usdc),
            )
            .where(
                Transaction.status == "completed",
                Transaction.listing_id.in_(listing_ids),
            )
            .group_by(Transaction.listing_id)
        )
        vol_map = {row[0]: (int(row[1] or 0), float(row[2] or 0)) for row in vol_agg.all()}

        cat_saved: dict[str, float] = {}
        for listing in listings:
            tx_count, tx_volume = vol_map.get(listing.id, (0, 0.0))
            if tx_count == 0:
                continue
            fresh_cost = dashboard_service._fresh_cost_estimate_usd(listing)  # noqa: SLF001
            avg_amount = tx_volume / tx_count if tx_count else 0.0
            saved_per_tx = max(fresh_cost - avg_amount, 0.0)
            total_saved = saved_per_tx * tx_count
            money_saved += total_saved
            cat_name = listing.category or "unknown"
            cat_saved[cat_name] = cat_saved.get(cat_name, 0.0) + total_saved

        # Merge money_saved into category_breakdown
        for entry in category_breakdown:
            entry["money_saved_usd"] = round(cat_saved.get(entry["category"], 0.0), 6)

    category_breakdown.sort(key=lambda row: row["usage_count"], reverse=True)

    return {
        "info_used_count": info_used_count,
        "data_served_bytes": data_served_bytes,
        "unique_buyers_count": unique_buyers,
        "unique_sellers_count": unique_sellers,
        "money_saved_for_others_usd": round(money_saved, 6),
        "category_breakdown": category_breakdown,
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

    # Batch-load transaction aggregates for all agents on this page
    agent_ids = [agent.id for agent in agents]

    # Seller metrics: money received, info used, unique buyers
    seller_agg = {}
    if agent_ids:
        seller_result = await db.execute(
            select(
                Transaction.seller_id,
                func.sum(Transaction.amount_usdc),
                func.count(Transaction.id),
                func.count(Transaction.buyer_id.distinct()),
            )
            .where(
                Transaction.seller_id.in_(agent_ids),
                Transaction.status == "completed",
            )
            .group_by(Transaction.seller_id)
        )
        for row in seller_result.all():
            seller_agg[row[0]] = {
                "money_received_usd": round(float(row[1] or 0), 6),
                "info_used_count": int(row[2] or 0),
                "other_agents_served_count": int(row[3] or 0),
            }

    # Data served bytes from listings
    data_bytes_agg: dict[str, int] = {}
    if agent_ids:
        bytes_result = await db.execute(
            select(
                DataListing.seller_id,
                func.sum(DataListing.content_size),
            )
            .where(DataListing.seller_id.in_(agent_ids))
            .group_by(DataListing.seller_id)
        )
        for row in bytes_result.all():
            data_bytes_agg[row[0]] = int(row[1] or 0)

    entries = []
    for agent in agents:
        trust = trust_map.get(agent.id)
        seller_metrics = seller_agg.get(agent.id, {
            "money_received_usd": 0.0,
            "info_used_count": 0,
            "other_agents_served_count": 0,
        })
        entries.append(
            {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "status": agent.status,
                "trust_status": trust.trust_status if trust else "unverified",
                "trust_tier": trust.trust_tier if trust else "T0",
                "trust_score": int(trust.trust_score) if trust else 0,
                "money_received_usd": seller_metrics["money_received_usd"],
                "info_used_count": seller_metrics["info_used_count"],
                "other_agents_served_count": seller_metrics["other_agents_served_count"],
                "data_served_bytes": data_bytes_agg.get(agent.id, 0),
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
