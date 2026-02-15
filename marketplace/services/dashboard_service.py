"""Role-specific dashboard metrics and open analytics helpers."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.agent_trust import AgentTrustProfile
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services import creator_service, dual_layer_service
from marketplace.services.match_service import FRESH_COST_ESTIMATES


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_non_empty_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _collect_listing_ids(transactions: list[Transaction]) -> set[str]:
    listing_ids: set[str] = set()
    for tx in transactions:
        listing_id = _as_non_empty_str(tx.listing_id)
        if listing_id:
            listing_ids.add(listing_id)
    return listing_ids


def _load_json(value: str | None, fallback: dict) -> dict:
    if not value:
        return fallback
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else fallback
    except Exception:
        return fallback


def _fresh_cost_estimate_usd(listing: DataListing) -> float:
    metadata = _load_json(listing.metadata_json, {})
    from_metadata = metadata.get("estimated_fresh_cost_usd")
    if isinstance(from_metadata, (int, float)):
        estimate_from_metadata = _safe_float(from_metadata, default=0.0)
        if estimate_from_metadata >= 0:
            return estimate_from_metadata
    category = _as_non_empty_str(getattr(listing, "category", None)) or "unknown"
    return _safe_float(FRESH_COST_ESTIMATES.get(category, 0.01), default=0.01)


async def _trust_summary(db: AsyncSession, agent_id: str) -> dict:
    result = await db.execute(
        select(AgentTrustProfile).where(AgentTrustProfile.agent_id == agent_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return {
            "trust_status": "unverified",
            "trust_tier": "T0",
            "trust_score": 0,
            "updated_at": None,
        }
    return {
        "trust_status": row.trust_status,
        "trust_tier": row.trust_tier,
        "trust_score": int(row.trust_score or 0),
        "updated_at": row.updated_at,
    }


async def get_agent_dashboard(db: AsyncSession, agent_id: str) -> dict:
    seller_tx_result = await db.execute(
        select(Transaction).where(
            Transaction.seller_id == agent_id,
            Transaction.status == "completed",
        )
    )
    seller_transactions = list(seller_tx_result.scalars().all())

    buyer_tx_result = await db.execute(
        select(Transaction).where(
            Transaction.buyer_id == agent_id,
            Transaction.status == "completed",
        )
    )
    buyer_transactions = list(buyer_tx_result.scalars().all())

    listing_ids = _collect_listing_ids(seller_transactions)
    listing_map: dict[str, DataListing] = {}
    if listing_ids:
        try:
            listing_result = await db.execute(
                select(DataListing).where(DataListing.id.in_(listing_ids))
            )
            listing_map = {row.id: row for row in listing_result.scalars().all()}
        except Exception:
            listing_map = {}

    money_received = sum(_safe_float(tx.amount_usdc, default=0.0) for tx in seller_transactions)
    money_spent = sum(_safe_float(tx.amount_usdc, default=0.0) for tx in buyer_transactions)
    info_used_count = len(seller_transactions)
    other_agents_served = len({tx.buyer_id for tx in seller_transactions if tx.buyer_id})

    data_served_bytes = 0
    money_saved = 0.0
    fresh_cost_total = 0.0
    for tx in seller_transactions:
        listing = listing_map.get(tx.listing_id)
        if listing is None:
            continue
        amount = _safe_float(tx.amount_usdc, default=0.0)
        fresh_cost = _fresh_cost_estimate_usd(listing)
        data_served_bytes += _safe_int(listing.content_size, default=0)
        fresh_cost_total += fresh_cost
        money_saved += max(fresh_cost - amount, 0.0)

    trust = await _trust_summary(db, agent_id)
    return {
        "agent_id": agent_id,
        "money_received_usd": round(money_received, 6),
        "money_spent_usd": round(money_spent, 6),
        "info_used_count": info_used_count,
        "other_agents_served_count": other_agents_served,
        "data_served_bytes": data_served_bytes,
        "savings": {
            "money_saved_for_others_usd": round(money_saved, 6),
            "fresh_cost_estimate_total_usd": round(fresh_cost_total, 6),
        },
        "trust_status": trust["trust_status"],
        "trust_tier": trust["trust_tier"],
        "trust_score": trust["trust_score"],
        "updated_at": trust["updated_at"] or _utcnow(),
    }


async def get_creator_dashboard_v2(db: AsyncSession, creator_id: str) -> dict:
    creator = await creator_service.get_creator_dashboard(db, creator_id)
    wallet = await creator_service.get_creator_wallet(db, creator_id)
    dual_layer = await dual_layer_service.get_creator_dual_layer_metrics(db, creator_id=creator_id)
    agents = creator.get("agents", [])

    active_agents = sum(1 for row in agents if row.get("status") == "active")
    total_saved = 0.0
    data_served_bytes = 0
    for row in agents:
        metrics = await get_agent_dashboard(db, row["agent_id"])
        total_saved += float(metrics["savings"]["money_saved_for_others_usd"])
        data_served_bytes += int(metrics["data_served_bytes"])

    return {
        "creator_id": creator_id,
        "creator_balance_usd": _safe_float(wallet.get("balance", 0.0), default=0.0),
        "creator_total_earned_usd": _safe_float(wallet.get("total_earned", 0.0), default=0.0),
        "total_agent_earnings_usd": _safe_float(creator.get("total_agent_earnings", 0.0), default=0.0),
        "total_agent_spent_usd": _safe_float(creator.get("total_agent_spent", 0.0), default=0.0),
        "creator_gross_revenue_usd": _safe_float(
            dual_layer.get("creator_gross_revenue_usd", 0.0), default=0.0
        ),
        "creator_platform_fees_usd": _safe_float(
            dual_layer.get("creator_platform_fees_usd", 0.0), default=0.0
        ),
        "creator_net_revenue_usd": _safe_float(
            dual_layer.get("creator_net_revenue_usd", 0.0), default=0.0
        ),
        "creator_pending_payout_usd": _safe_float(
            dual_layer.get("creator_pending_payout_usd", 0.0), default=0.0
        ),
        "total_agents": _safe_int(creator.get("agents_count", 0), default=0),
        "active_agents": active_agents,
        "money_saved_for_others_usd": round(total_saved, 6),
        "data_served_bytes": data_served_bytes,
        "updated_at": _utcnow(),
    }


async def get_agent_public_dashboard(db: AsyncSession, agent_id: str) -> dict:
    agent_result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise ValueError(f"Agent {agent_id} not found")

    metrics = await get_agent_dashboard(db, agent_id)
    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "money_received_usd": metrics["money_received_usd"],
        "info_used_count": metrics["info_used_count"],
        "other_agents_served_count": metrics["other_agents_served_count"],
        "data_served_bytes": metrics["data_served_bytes"],
        "money_saved_for_others_usd": metrics["savings"]["money_saved_for_others_usd"],
        "trust_status": metrics["trust_status"],
        "trust_tier": metrics["trust_tier"],
        "trust_score": metrics["trust_score"],
        "updated_at": metrics["updated_at"],
    }


async def get_open_market_analytics(db: AsyncSession, limit: int = 10) -> dict:
    total_agents = int((await db.execute(select(func.count(RegisteredAgent.id)))).scalar() or 0)
    total_listings = int((await db.execute(select(func.count(DataListing.id)))).scalar() or 0)

    tx_rows = await db.execute(
        select(Transaction).where(Transaction.status == "completed")
    )
    completed_transactions = list(tx_rows.scalars().all())
    total_completed = len(completed_transactions)
    platform_volume = sum(_safe_float(tx.amount_usdc, default=0.0) for tx in completed_transactions)

    by_seller: dict[str, float] = {}
    by_usage: dict[str, int] = {}
    listing_ids = _collect_listing_ids(completed_transactions)
    listing_map: dict[str, DataListing] = {}
    if listing_ids:
        try:
            listing_rows = await db.execute(
                select(DataListing).where(DataListing.id.in_(listing_ids))
            )
            listing_map = {row.id: row for row in listing_rows.scalars().all()}
        except Exception:
            listing_map = {}

    category_usage: dict[str, dict] = {}
    total_saved = 0.0
    for tx in completed_transactions:
        seller_id = _as_non_empty_str(tx.seller_id) or "unknown"
        amount = _safe_float(tx.amount_usdc, default=0.0)
        by_seller[seller_id] = by_seller.get(seller_id, 0.0) + amount
        by_usage[seller_id] = by_usage.get(seller_id, 0) + 1

        listing = listing_map.get(tx.listing_id)
        if listing is None:
            continue

        category = _as_non_empty_str(getattr(listing, "category", None)) or "unknown"
        entry = category_usage.setdefault(
            category,
            {"category": category, "usage_count": 0, "volume_usd": 0.0, "money_saved_usd": 0.0},
        )
        fresh_cost = _fresh_cost_estimate_usd(listing)
        saved = max(fresh_cost - amount, 0.0)
        entry["usage_count"] += 1
        entry["volume_usd"] += amount
        entry["money_saved_usd"] += saved
        total_saved += saved

    names_result = await db.execute(select(RegisteredAgent.id, RegisteredAgent.name))
    agent_names = {row[0]: row[1] for row in names_result.all()}

    top_agents_by_revenue = [
        {
            "agent_id": seller_id,
            "agent_name": agent_names.get(seller_id, "Unknown"),
            "money_received_usd": round(amount, 6),
        }
        for seller_id, amount in sorted(by_seller.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]

    top_agents_by_usage = [
        {
            "agent_id": seller_id,
            "agent_name": agent_names.get(seller_id, "Unknown"),
            "info_used_count": count,
        }
        for seller_id, count in sorted(by_usage.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]

    top_categories_by_usage = sorted(
        (
            {
                "category": row["category"],
                "usage_count": _safe_int(row["usage_count"], default=0),
                "volume_usd": round(_safe_float(row["volume_usd"], default=0.0), 6),
                "money_saved_usd": round(_safe_float(row["money_saved_usd"], default=0.0), 6),
            }
            for row in category_usage.values()
        ),
        key=lambda item: item["usage_count"],
        reverse=True,
    )[:limit]
    dual_layer = await dual_layer_service.get_dual_layer_open_metrics(db)

    return {
        "generated_at": _utcnow(),
        "total_agents": total_agents,
        "total_listings": total_listings,
        "total_completed_transactions": total_completed,
        "end_users_count": dual_layer["end_users_count"],
        "consumer_orders_count": dual_layer["consumer_orders_count"],
        "developer_profiles_count": dual_layer["developer_profiles_count"],
        "platform_fee_volume_usd": dual_layer["platform_fee_volume_usd"],
        "platform_volume_usd": round(platform_volume, 6),
        "total_money_saved_usd": round(total_saved, 6),
        "top_agents_by_revenue": top_agents_by_revenue,
        "top_agents_by_usage": top_agents_by_usage,
        "top_categories_by_usage": top_categories_by_usage,
    }
