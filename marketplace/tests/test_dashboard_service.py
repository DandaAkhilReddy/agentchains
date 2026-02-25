"""Tests for dashboard_service — 25 tests covering agent, creator, and open analytics.

Covers get_agent_dashboard, get_creator_dashboard_v2, get_agent_public_dashboard,
get_open_market_analytics, and internal helpers.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.agent_trust import AgentTrustProfile
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.services import dashboard_service
from marketplace.services.dashboard_service import (
    _as_non_empty_str,
    _collect_listing_ids,
    _fresh_cost_estimate_usd,
    get_agent_dashboard,
    get_agent_public_dashboard,
    get_creator_dashboard_v2,
    get_open_market_analytics,
)
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestAsNonEmptyStr:
    """Tests for the _as_non_empty_str helper."""

    def test_returns_stripped_string(self):
        assert _as_non_empty_str("  hello  ") == "hello"

    def test_returns_none_for_empty_string(self):
        assert _as_non_empty_str("") is None

    def test_returns_none_for_whitespace_only(self):
        assert _as_non_empty_str("   ") is None

    def test_returns_none_for_non_string(self):
        assert _as_non_empty_str(42) is None
        assert _as_non_empty_str(None) is None


class TestCollectListingIds:
    """Tests for _collect_listing_ids."""

    def test_collects_unique_ids(self):
        tx1 = Transaction(id="t1", listing_id="L1", buyer_id="b", seller_id="s",
                          amount_usdc=Decimal("1"), status="completed")
        tx2 = Transaction(id="t2", listing_id="L2", buyer_id="b", seller_id="s",
                          amount_usdc=Decimal("1"), status="completed")
        tx3 = Transaction(id="t3", listing_id="L1", buyer_id="b", seller_id="s",
                          amount_usdc=Decimal("1"), status="completed")
        result = _collect_listing_ids([tx1, tx2, tx3])
        assert result == {"L1", "L2"}

    def test_skips_empty_listing_ids(self):
        tx = Transaction(id="t1", listing_id="", buyer_id="b", seller_id="s",
                         amount_usdc=Decimal("1"), status="completed")
        result = _collect_listing_ids([tx])
        assert result == set()

    def test_empty_list_returns_empty_set(self):
        assert _collect_listing_ids([]) == set()


class TestFreshCostEstimate:
    """Tests for _fresh_cost_estimate_usd."""

    def test_uses_metadata_value_when_present(self):
        listing = DataListing(
            id="L1", seller_id="s", title="Test", category="web_search",
            content_hash="abc", content_size=100, price_usdc=Decimal("1"),
            quality_score=Decimal("0.8"), status="active",
        )
        import json
        listing.metadata_json = json.dumps({"estimated_fresh_cost_usd": 0.05})
        assert _fresh_cost_estimate_usd(listing) == 0.05

    def test_falls_back_to_category_estimate(self):
        listing = DataListing(
            id="L1", seller_id="s", title="Test", category="code_analysis",
            content_hash="abc", content_size=100, price_usdc=Decimal("1"),
            quality_score=Decimal("0.8"), status="active",
        )
        listing.metadata_json = None
        assert _fresh_cost_estimate_usd(listing) == 0.02

    def test_unknown_category_defaults_to_001(self):
        listing = DataListing(
            id="L1", seller_id="s", title="Test", category="exotic_type",
            content_hash="abc", content_size=100, price_usdc=Decimal("1"),
            quality_score=Decimal("0.8"), status="active",
        )
        listing.metadata_json = None
        assert _fresh_cost_estimate_usd(listing) == 0.01


# ---------------------------------------------------------------------------
# get_agent_dashboard
# ---------------------------------------------------------------------------


class TestGetAgentDashboard:
    """Tests for get_agent_dashboard — queries transactions, listings, trust."""

    async def test_empty_dashboard_for_new_agent(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent()
        result = await get_agent_dashboard(db, agent.id)
        assert result["agent_id"] == agent.id
        assert result["money_received_usd"] == 0.0
        assert result["money_spent_usd"] == 0.0
        assert result["info_used_count"] == 0
        assert result["other_agents_served_count"] == 0
        assert result["data_served_bytes"] == 0
        assert result["trust_status"] == "unverified"
        assert result["trust_tier"] == "T0"
        assert result["trust_score"] == 0

    async def test_dashboard_with_seller_transactions(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=0.005)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=0.005)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=0.005)

        result = await get_agent_dashboard(db, seller.id)
        assert result["money_received_usd"] == 0.01
        assert result["info_used_count"] == 2
        assert result["other_agents_served_count"] == 1

    async def test_dashboard_with_buyer_transactions(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=2.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=2.0)

        result = await get_agent_dashboard(db, buyer.id)
        assert result["money_spent_usd"] == 2.0
        assert result["info_used_count"] == 0  # buyer has no seller transactions

    async def test_dashboard_with_trust_profile(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent()
        trust = AgentTrustProfile(
            id=_new_id(),
            agent_id=agent.id,
            trust_status="verified",
            trust_tier="T2",
            trust_score=85,
        )
        db.add(trust)
        await db.commit()

        result = await get_agent_dashboard(db, agent.id)
        assert result["trust_status"] == "verified"
        assert result["trust_tier"] == "T2"
        assert result["trust_score"] == 85

    async def test_dashboard_savings_calculation(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """When listing price < fresh cost, savings is positive."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        # web_search fresh cost is 0.01
        listing = await make_listing(
            seller.id, price_usdc=0.003, category="web_search"
        )
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=0.003)

        result = await get_agent_dashboard(db, seller.id)
        # Fresh cost 0.01 - price 0.003 = 0.007 saved
        assert result["savings"]["money_saved_for_others_usd"] == pytest.approx(0.007, abs=1e-6)
        assert result["savings"]["fresh_cost_estimate_total_usd"] == pytest.approx(0.01, abs=1e-6)


# ---------------------------------------------------------------------------
# get_agent_public_dashboard
# ---------------------------------------------------------------------------


class TestGetAgentPublicDashboard:

    async def test_returns_agent_name_and_metrics(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="public-agent")
        result = await get_agent_public_dashboard(db, agent.id)
        assert result["agent_id"] == agent.id
        assert result["agent_name"] == "public-agent"
        assert "money_received_usd" in result
        assert "trust_status" in result

    async def test_raises_for_nonexistent_agent(self, db: AsyncSession):
        with pytest.raises(ValueError, match="not found"):
            await get_agent_public_dashboard(db, "nonexistent-id")


# ---------------------------------------------------------------------------
# get_creator_dashboard_v2
# ---------------------------------------------------------------------------


class TestGetCreatorDashboardV2:

    @patch.object(dashboard_service, "creator_service")
    @patch.object(dashboard_service, "dual_layer_service")
    async def test_returns_creator_metrics(
        self, mock_dual_layer, mock_creator, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="creator-agent")
        mock_creator.get_creator_dashboard = AsyncMock(return_value={
            "agents": [{"agent_id": agent.id, "status": "active"}],
            "agents_count": 1,
            "total_agent_earnings": 5.0,
            "total_agent_spent": 1.0,
        })
        mock_creator.get_creator_wallet = AsyncMock(return_value={
            "balance": 4.0,
            "total_earned": 5.0,
        })
        mock_dual_layer.get_creator_dual_layer_metrics = AsyncMock(return_value={
            "creator_gross_revenue_usd": 10.0,
            "creator_platform_fees_usd": 1.0,
            "creator_net_revenue_usd": 9.0,
            "creator_pending_payout_usd": 3.0,
        })

        result = await get_creator_dashboard_v2(db, "creator-123")
        assert result["creator_id"] == "creator-123"
        assert result["creator_balance_usd"] == 4.0
        assert result["total_agents"] == 1
        assert result["active_agents"] == 1
        assert result["creator_gross_revenue_usd"] == 10.0

    @patch.object(dashboard_service, "creator_service")
    @patch.object(dashboard_service, "dual_layer_service")
    async def test_handles_zero_agents(
        self, mock_dual_layer, mock_creator, db: AsyncSession
    ):
        mock_creator.get_creator_dashboard = AsyncMock(return_value={
            "agents": [],
            "agents_count": 0,
            "total_agent_earnings": 0,
            "total_agent_spent": 0,
        })
        mock_creator.get_creator_wallet = AsyncMock(return_value={
            "balance": 0,
            "total_earned": 0,
        })
        mock_dual_layer.get_creator_dual_layer_metrics = AsyncMock(return_value={
            "creator_gross_revenue_usd": 0,
            "creator_platform_fees_usd": 0,
            "creator_net_revenue_usd": 0,
            "creator_pending_payout_usd": 0,
        })

        result = await get_creator_dashboard_v2(db, "empty-creator")
        assert result["total_agents"] == 0
        assert result["active_agents"] == 0
        assert result["money_saved_for_others_usd"] == 0.0
        assert result["data_served_bytes"] == 0


# ---------------------------------------------------------------------------
# get_open_market_analytics
# ---------------------------------------------------------------------------


class TestGetOpenMarketAnalytics:

    @patch.object(dashboard_service, "dual_layer_service")
    async def test_empty_market(self, mock_dual_layer, db: AsyncSession):
        mock_dual_layer.get_dual_layer_open_metrics = AsyncMock(return_value={
            "end_users_count": 0,
            "consumer_orders_count": 0,
            "developer_profiles_count": 0,
            "platform_fee_volume_usd": 0.0,
        })
        result = await get_open_market_analytics(db)
        assert result["total_agents"] == 0
        assert result["total_listings"] == 0
        assert result["total_completed_transactions"] == 0
        assert result["platform_volume_usd"] == 0.0
        assert result["top_agents_by_revenue"] == []
        assert result["top_agents_by_usage"] == []
        assert result["top_categories_by_usage"] == []

    @patch.object(dashboard_service, "dual_layer_service")
    async def test_market_with_transactions(
        self, mock_dual_layer, db: AsyncSession,
        make_agent, make_listing, make_transaction
    ):
        mock_dual_layer.get_dual_layer_open_metrics = AsyncMock(return_value={
            "end_users_count": 10,
            "consumer_orders_count": 5,
            "developer_profiles_count": 2,
            "platform_fee_volume_usd": 0.5,
        })
        seller, _ = await make_agent(name="top-seller")
        buyer, _ = await make_agent(name="buyer-1")
        listing = await make_listing(seller.id, price_usdc=0.005, category="web_search")
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=0.005)

        result = await get_open_market_analytics(db)
        assert result["total_agents"] == 2
        assert result["total_listings"] == 1
        assert result["total_completed_transactions"] == 1
        assert result["platform_volume_usd"] == pytest.approx(0.005, abs=1e-6)
        assert len(result["top_agents_by_revenue"]) == 1
        assert result["top_agents_by_revenue"][0]["agent_name"] == "top-seller"
        assert result["end_users_count"] == 10

    @patch.object(dashboard_service, "dual_layer_service")
    async def test_market_limit_parameter(
        self, mock_dual_layer, db: AsyncSession,
        make_agent, make_listing, make_transaction
    ):
        """The limit parameter caps the number of top agents returned."""
        mock_dual_layer.get_dual_layer_open_metrics = AsyncMock(return_value={
            "end_users_count": 0,
            "consumer_orders_count": 0,
            "developer_profiles_count": 0,
            "platform_fee_volume_usd": 0.0,
        })
        agents = []
        for i in range(5):
            a, _ = await make_agent(name=f"seller-{i}")
            agents.append(a)
        buyer, _ = await make_agent(name="buyer")
        for agent in agents:
            listing = await make_listing(agent.id, price_usdc=0.001)
            await make_transaction(buyer.id, agent.id, listing.id, amount_usdc=0.001)

        result = await get_open_market_analytics(db, limit=3)
        assert len(result["top_agents_by_revenue"]) <= 3
        assert len(result["top_agents_by_usage"]) <= 3
