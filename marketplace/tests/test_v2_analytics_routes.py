"""Tests for v2 open analytics endpoints.

Covers: marketplace/api/v2_analytics.py
  - GET /api/v2/analytics/market/open
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_platform_treasury() -> None:
    """Create the platform treasury account so agent onboarding can proceed."""
    async with TestSession() as db:
        db.add(TokenAccount(
            id=_new_id(),
            agent_id=None,
            creator_id=None,
            balance=Decimal("0"),
        ))
        await db.commit()


# ===========================================================================
# GET /api/v2/analytics/market/open
# ===========================================================================

class TestOpenMarketAnalytics:
    """Tests for the public market analytics endpoint."""

    async def test_analytics_returns_all_required_fields(self, client):
        resp = await client.get("/api/v2/analytics/market/open")
        assert resp.status_code == 200
        body = resp.json()
        assert "generated_at" in body
        assert "total_agents" in body
        assert "total_listings" in body
        assert "total_completed_transactions" in body
        assert "platform_volume_usd" in body
        assert "total_money_saved_usd" in body
        assert "top_agents_by_revenue" in body
        assert "top_agents_by_usage" in body
        assert "top_categories_by_usage" in body

    async def test_analytics_no_auth_required(self, client):
        """The open analytics endpoint is public."""
        resp = await client.get("/api/v2/analytics/market/open")
        assert resp.status_code == 200

    async def test_analytics_empty_database_returns_zeroes(self, client):
        resp = await client.get("/api/v2/analytics/market/open")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_agents"] == 0
        assert body["total_listings"] == 0
        assert body["total_completed_transactions"] == 0
        assert body["platform_volume_usd"] == 0.0
        assert body["total_money_saved_usd"] == 0.0
        assert body["top_agents_by_revenue"] == []
        assert body["top_agents_by_usage"] == []
        assert body["top_categories_by_usage"] == []

    async def test_analytics_with_agents_and_listings(
        self, client, make_agent, make_listing, seed_platform,
    ):
        agent, _ = await make_agent()
        await make_listing(seller_id=agent.id, price_usdc=5.0)
        await make_listing(seller_id=agent.id, price_usdc=3.0)

        resp = await client.get("/api/v2/analytics/market/open")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_agents"] >= 1
        assert body["total_listings"] >= 2

    async def test_analytics_with_transactions(
        self, client, make_agent, make_listing, make_transaction, seed_platform,
    ):
        seller, _ = await make_agent(name="seller-analytics")
        buyer, _ = await make_agent(name="buyer-analytics")
        listing = await make_listing(seller_id=seller.id, price_usdc=10.0)
        await make_transaction(
            buyer_id=buyer.id,
            seller_id=seller.id,
            listing_id=listing.id,
            amount_usdc=10.0,
            status="completed",
        )

        resp = await client.get("/api/v2/analytics/market/open")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_completed_transactions"] >= 1
        assert body["platform_volume_usd"] >= 10.0

    async def test_analytics_limit_query_param(self, client):
        resp = await client.get("/api/v2/analytics/market/open?limit=5")
        assert resp.status_code == 200

    async def test_analytics_limit_min_boundary(self, client):
        resp = await client.get("/api/v2/analytics/market/open?limit=1")
        assert resp.status_code == 200

    async def test_analytics_limit_max_boundary(self, client):
        resp = await client.get("/api/v2/analytics/market/open?limit=50")
        assert resp.status_code == 200

    async def test_analytics_limit_below_min_returns_422(self, client):
        resp = await client.get("/api/v2/analytics/market/open?limit=0")
        assert resp.status_code == 422

    async def test_analytics_limit_above_max_returns_422(self, client):
        resp = await client.get("/api/v2/analytics/market/open?limit=51")
        assert resp.status_code == 422

    async def test_analytics_non_integer_limit_returns_422(self, client):
        resp = await client.get("/api/v2/analytics/market/open?limit=abc")
        assert resp.status_code == 422

    async def test_analytics_graceful_fallback_on_service_error(self, client):
        """When the service layer raises, the endpoint should return zeroed response."""
        with patch(
            "marketplace.api.v2_analytics.dashboard_service.get_open_market_analytics",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db exploded"),
        ):
            resp = await client.get("/api/v2/analytics/market/open")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_agents"] == 0
            assert body["total_listings"] == 0
            assert body["total_completed_transactions"] == 0
            assert body["top_agents_by_revenue"] == []

    async def test_analytics_top_agents_populated_with_transactions(
        self, client, make_agent, make_listing, make_transaction, seed_platform,
    ):
        """Top agents lists should be populated when transactions exist."""
        seller, _ = await make_agent(name="top-seller")
        buyer, _ = await make_agent(name="top-buyer")
        listing = await make_listing(seller_id=seller.id, price_usdc=20.0)
        for _ in range(3):
            await make_transaction(
                buyer_id=buyer.id,
                seller_id=seller.id,
                listing_id=listing.id,
                amount_usdc=20.0,
            )

        resp = await client.get("/api/v2/analytics/market/open?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["top_agents_by_revenue"]) >= 1
        assert len(body["top_agents_by_usage"]) >= 1
