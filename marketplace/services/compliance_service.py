"""Compliance service — GDPR data export and right-to-deletion.

Implements data subject rights for agents and users:
- Data export (portable format)
- Right to deletion (erasure)
- Consent management
- Data processing records
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def export_agent_data(
    db: AsyncSession,
    agent_id: str,
) -> dict[str, Any]:
    """Export all data associated with an agent (GDPR Article 20).

    Returns a structured dictionary of all personal data.
    """
    from marketplace.models.agent import RegisteredAgent
    from marketplace.models.listing import DataListing
    from marketplace.models.transaction import Transaction

    # Agent profile
    agent_result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        return {"error": "Agent not found"}

    agent_data = {
        "id": agent.id,
        "name": agent.name,
        "agent_type": agent.agent_type,
        "description": agent.description or "",
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }

    # Listings
    listings_result = await db.execute(
        select(DataListing).where(DataListing.seller_id == agent_id)
    )
    listings = listings_result.scalars().all()
    listings_data = [
        {
            "id": l.id,
            "title": l.title,
            "category": l.category,
            "price_usdc": float(l.price_usdc),
            "status": l.status,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in listings
    ]

    # Transactions
    tx_result = await db.execute(
        select(Transaction).where(
            (Transaction.buyer_id == agent_id)
            | (Transaction.seller_id == agent_id)
        )
    )
    transactions = tx_result.scalars().all()
    tx_data = [
        {
            "id": t.id,
            "role": "buyer" if t.buyer_id == agent_id else "seller",
            "amount_usdc": float(t.amount_usdc),
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in transactions
    ]

    return {
        "export_id": str(uuid.uuid4()),
        "agent": agent_data,
        "listings": listings_data,
        "transactions": tx_data,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "format_version": "1.0",
    }


async def delete_agent_data(
    db: AsyncSession,
    agent_id: str,
    *,
    soft_delete: bool = True,
) -> dict[str, Any]:
    """Delete all data associated with an agent (GDPR Article 17).

    By default, performs a soft delete (anonymization).
    Set soft_delete=False for hard deletion (use with caution).
    """
    from marketplace.models.agent import RegisteredAgent
    from marketplace.models.listing import DataListing

    result = await db.execute(
        select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        return {"error": "Agent not found"}

    deleted_items = {"agent": False, "listings": 0}

    if soft_delete:
        # Anonymize agent data
        agent.name = f"deleted-{agent.id[:8]}"
        agent.description = "[REDACTED]"
        agent.public_key = "[REDACTED]"
        agent.wallet_address = ""
        agent.capabilities = "[]"
        agent.a2a_endpoint = ""
        agent.agent_card_json = "{}"
        agent.status = "deleted"
        deleted_items["agent"] = True

        # Anonymize listings
        listings_result = await db.execute(
            select(DataListing).where(DataListing.seller_id == agent_id)
        )
        listings = listings_result.scalars().all()
        for listing in listings:
            listing.title = "[REDACTED]"
            listing.status = "deleted"
            deleted_items["listings"] += 1

    else:
        # Hard delete (cascade)
        listings_result = await db.execute(
            select(DataListing).where(DataListing.seller_id == agent_id)
        )
        listings = listings_result.scalars().all()
        for listing in listings:
            await db.delete(listing)
            deleted_items["listings"] += 1

        await db.delete(agent)
        deleted_items["agent"] = True

    await db.commit()

    logger.info(
        "Agent data %s: %s (agent=%s, listings=%d)",
        "anonymized" if soft_delete else "deleted",
        agent_id,
        deleted_items["agent"],
        deleted_items["listings"],
    )

    return {
        "deletion_id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "method": "soft_delete" if soft_delete else "hard_delete",
        "deleted_items": deleted_items,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_data_processing_record(
    db: AsyncSession,
    agent_id: str,
) -> dict[str, Any]:
    """Get a record of how an agent's data is processed (GDPR Article 30)."""
    return {
        "agent_id": agent_id,
        "data_categories": [
            "agent_profile",
            "transaction_history",
            "listing_data",
            "reputation_scores",
            "session_logs",
        ],
        "processing_purposes": [
            "marketplace_operations",
            "fraud_detection",
            "reputation_scoring",
            "analytics",
        ],
        "retention_periods": {
            "transaction_data": "7 years (financial regulation)",
            "agent_profile": "until deletion requested",
            "session_logs": "30 days",
            "analytics_data": "2 years (aggregated)",
        },
        "data_recipients": [
            "marketplace_platform",
            "payment_processors (Stripe, Razorpay)",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


class ComplianceService:
    """Class wrapper for compliance functions."""

    async def export_data(self, db, agent_id):
        return await export_agent_data(db, agent_id)

    async def delete_data(self, db, agent_id):
        return await delete_agent_data(db, agent_id)
