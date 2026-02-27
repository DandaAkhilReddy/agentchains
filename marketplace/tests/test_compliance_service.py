"""Tests for compliance_service — GDPR data export, deletion, and processing records.

Covers:
- export_agent_data: full export with listings/transactions, missing agent
- delete_agent_data: soft delete (anonymization), hard delete, missing agent
- get_data_processing_record: static record structure
- ComplianceService: class wrapper delegation
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services.compliance_service import (
    ComplianceService,
    delete_agent_data,
    export_agent_data,
    get_data_processing_record,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


async def _make_agent(
    db: AsyncSession,
    name: str | None = None,
    description: str = "Test agent",
) -> RegisteredAgent:
    agent = RegisteredAgent(
        id=_id(),
        name=name or f"agent-{_id()[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test",
        description=description,
        wallet_address="0x1234567890abcdef",
        capabilities='["search"]',
        a2a_endpoint="https://example.com/a2a",
        agent_card_json='{"name": "test"}',
        status="active",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _make_listing(
    db: AsyncSession,
    seller_id: str,
    title: str = "Test Listing",
    price: float = 5.0,
    status: str = "active",
) -> DataListing:
    listing = DataListing(
        id=_id(),
        seller_id=seller_id,
        title=title,
        category="web_search",
        content_hash=f"sha256:{_id().replace('-', '')[:64]}",
        content_size=1024,
        price_usdc=Decimal(str(price)),
        quality_score=Decimal("0.85"),
        status=status,
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing


async def _make_transaction(
    db: AsyncSession,
    buyer_id: str,
    seller_id: str,
    listing_id: str,
    amount: float = 5.0,
    status: str = "completed",
) -> Transaction:
    tx = Transaction(
        id=_id(),
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=Decimal(str(amount)),
        status=status,
        content_hash=f"sha256:{_id().replace('-', '')[:64]}",
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# export_agent_data
# ---------------------------------------------------------------------------


class TestExportAgentData:
    async def test_export_missing_agent(self, db: AsyncSession):
        result = await export_agent_data(db, _id())
        assert result == {"error": "Agent not found"}

    async def test_export_agent_profile(self, db: AsyncSession):
        agent = await _make_agent(db, name="export-me")
        result = await export_agent_data(db, agent.id)

        assert "export_id" in result
        assert result["format_version"] == "1.0"
        assert result["agent"]["id"] == agent.id
        assert result["agent"]["name"] == "export-me"
        assert result["agent"]["agent_type"] == "both"
        assert result["agent"]["description"] == "Test agent"
        assert result["agent"]["created_at"] is not None

    async def test_export_includes_listings(self, db: AsyncSession):
        agent = await _make_agent(db)
        listing = await _make_listing(db, seller_id=agent.id, title="My Data")

        result = await export_agent_data(db, agent.id)
        assert len(result["listings"]) == 1
        assert result["listings"][0]["id"] == listing.id
        assert result["listings"][0]["title"] == "My Data"
        assert result["listings"][0]["category"] == "web_search"
        assert result["listings"][0]["status"] == "active"

    async def test_export_includes_transactions_as_buyer(self, db: AsyncSession):
        buyer = await _make_agent(db, name="buyer-export")
        seller = await _make_agent(db, name="seller-export")
        listing = await _make_listing(db, seller_id=seller.id)
        tx = await _make_transaction(db, buyer.id, seller.id, listing.id, amount=3.5)

        result = await export_agent_data(db, buyer.id)
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["role"] == "buyer"
        assert result["transactions"][0]["amount_usdc"] == 3.5

    async def test_export_includes_transactions_as_seller(self, db: AsyncSession):
        buyer = await _make_agent(db, name="buyer-for-seller")
        seller = await _make_agent(db, name="seller-for-export")
        listing = await _make_listing(db, seller_id=seller.id)
        await _make_transaction(db, buyer.id, seller.id, listing.id, amount=7.0)

        result = await export_agent_data(db, seller.id)
        assert len(result["transactions"]) == 1
        assert result["transactions"][0]["role"] == "seller"
        assert result["transactions"][0]["amount_usdc"] == 7.0

    async def test_export_with_no_listings_or_transactions(self, db: AsyncSession):
        agent = await _make_agent(db)
        result = await export_agent_data(db, agent.id)

        assert result["listings"] == []
        assert result["transactions"] == []
        assert "exported_at" in result

    async def test_export_multiple_listings(self, db: AsyncSession):
        agent = await _make_agent(db)
        await _make_listing(db, seller_id=agent.id, title="Listing 1")
        await _make_listing(db, seller_id=agent.id, title="Listing 2")
        await _make_listing(db, seller_id=agent.id, title="Listing 3")

        result = await export_agent_data(db, agent.id)
        assert len(result["listings"]) == 3


# ---------------------------------------------------------------------------
# delete_agent_data (soft delete)
# ---------------------------------------------------------------------------


class TestDeleteAgentDataSoft:
    async def test_soft_delete_missing_agent(self, db: AsyncSession):
        result = await delete_agent_data(db, _id())
        assert result == {"error": "Agent not found"}

    async def test_soft_delete_anonymizes_agent(self, db: AsyncSession):
        agent = await _make_agent(db, name="soon-deleted")
        result = await delete_agent_data(db, agent.id, soft_delete=True)

        assert result["method"] == "soft_delete"
        assert result["agent_id"] == agent.id
        assert result["deleted_items"]["agent"] is True
        assert "deletion_id" in result
        assert "completed_at" in result

        # Verify agent is anonymized in DB
        await db.refresh(agent)
        assert agent.name.startswith("deleted-")
        assert agent.description == "[REDACTED]"
        assert agent.public_key == "[REDACTED]"
        assert agent.wallet_address == ""
        assert agent.capabilities == "[]"
        assert agent.a2a_endpoint == ""
        assert agent.agent_card_json == "{}"
        assert agent.status == "deleted"

    async def test_soft_delete_anonymizes_listings(self, db: AsyncSession):
        agent = await _make_agent(db)
        listing = await _make_listing(db, seller_id=agent.id, title="Sensitive Data")

        result = await delete_agent_data(db, agent.id, soft_delete=True)
        assert result["deleted_items"]["listings"] == 1

        await db.refresh(listing)
        assert listing.title == "[REDACTED]"
        assert listing.status == "deleted"

    async def test_soft_delete_multiple_listings(self, db: AsyncSession):
        agent = await _make_agent(db)
        await _make_listing(db, seller_id=agent.id, title="L1")
        await _make_listing(db, seller_id=agent.id, title="L2")

        result = await delete_agent_data(db, agent.id, soft_delete=True)
        assert result["deleted_items"]["listings"] == 2

    async def test_soft_delete_agent_with_no_listings(self, db: AsyncSession):
        agent = await _make_agent(db)
        result = await delete_agent_data(db, agent.id, soft_delete=True)
        assert result["deleted_items"]["listings"] == 0
        assert result["deleted_items"]["agent"] is True


# ---------------------------------------------------------------------------
# delete_agent_data (hard delete)
# ---------------------------------------------------------------------------


class TestDeleteAgentDataHard:
    async def test_hard_delete_removes_agent(self, db: AsyncSession):
        agent = await _make_agent(db, name="hard-delete-me")
        agent_id = agent.id
        result = await delete_agent_data(db, agent_id, soft_delete=False)

        assert result["method"] == "hard_delete"
        assert result["deleted_items"]["agent"] is True

        # Agent should be gone from DB
        from sqlalchemy import select
        check = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
        )
        assert check.scalar_one_or_none() is None

    async def test_hard_delete_removes_listings(self, db: AsyncSession):
        agent = await _make_agent(db)
        listing = await _make_listing(db, seller_id=agent.id)
        listing_id = listing.id
        agent_id = agent.id

        result = await delete_agent_data(db, agent_id, soft_delete=False)
        assert result["deleted_items"]["listings"] == 1

        from sqlalchemy import select
        check = await db.execute(
            select(DataListing).where(DataListing.id == listing_id)
        )
        assert check.scalar_one_or_none() is None

    async def test_hard_delete_missing_agent(self, db: AsyncSession):
        result = await delete_agent_data(db, _id(), soft_delete=False)
        assert result == {"error": "Agent not found"}


# ---------------------------------------------------------------------------
# get_data_processing_record
# ---------------------------------------------------------------------------


class TestGetDataProcessingRecord:
    async def test_returns_expected_structure(self, db: AsyncSession):
        result = await get_data_processing_record(db, "any-agent-id")

        assert result["agent_id"] == "any-agent-id"
        assert "agent_profile" in result["data_categories"]
        assert "transaction_history" in result["data_categories"]
        assert "fraud_detection" in result["processing_purposes"]
        assert "marketplace_operations" in result["processing_purposes"]
        assert "transaction_data" in result["retention_periods"]
        assert "generated_at" in result

    async def test_data_categories_complete(self, db: AsyncSession):
        result = await get_data_processing_record(db, "test-id")
        expected = {
            "agent_profile",
            "transaction_history",
            "listing_data",
            "reputation_scores",
            "session_logs",
        }
        assert set(result["data_categories"]) == expected

    async def test_retention_periods_present(self, db: AsyncSession):
        result = await get_data_processing_record(db, "test-id")
        assert "7 years" in result["retention_periods"]["transaction_data"]
        assert "30 days" in result["retention_periods"]["session_logs"]


# ---------------------------------------------------------------------------
# ComplianceService class wrapper
# ---------------------------------------------------------------------------


class TestComplianceServiceClass:
    async def test_export_data_delegates(self, db: AsyncSession):
        agent = await _make_agent(db, name="class-export")
        service = ComplianceService()
        result = await service.export_data(db, agent.id)
        assert result["agent"]["id"] == agent.id
        assert "export_id" in result

    async def test_delete_data_delegates(self, db: AsyncSession):
        agent = await _make_agent(db, name="class-delete")
        service = ComplianceService()
        result = await service.delete_data(db, agent.id)
        assert result["method"] == "soft_delete"
        assert result["deleted_items"]["agent"] is True

    async def test_export_data_missing_agent(self, db: AsyncSession):
        service = ComplianceService()
        result = await service.export_data(db, _id())
        assert result == {"error": "Agent not found"}

    async def test_delete_data_missing_agent(self, db: AsyncSession):
        service = ComplianceService()
        result = await service.delete_data(db, _id())
        assert result == {"error": "Agent not found"}
