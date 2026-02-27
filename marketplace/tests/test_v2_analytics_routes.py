"""Tests for marketplace/api/v2_analytics.py -- open analytics endpoints.

All endpoints hit the real FastAPI app via the ``client`` fixture.
Analytics are computed from real data in the in-memory SQLite database.
The graceful fallback test mocks the service layer to simulate an error.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from marketplace.tests.conftest import _new_id


# ===========================================================================
# GET /api/v2/analytics/market/open
# ===========================================================================


async def test_analytics_returns_all_required_fields(client):
    """GET /market/open returns all expected fields."""
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


async def test_analytics_no_auth_required(client):
    """GET /market/open is a public endpoint (no auth needed)."""
    resp = await client.get("/api/v2/analytics/market/open")
    assert resp.status_code == 200


async def test_analytics_empty_database_returns_zeroes(client):
    """GET /market/open returns zeroed metrics on an empty database."""
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
    client, make_agent, make_listing, seed_platform,
):
    """GET /market/open reflects agents and listings in the database."""
    agent, _ = await make_agent()
    await make_listing(seller_id=agent.id, price_usdc=5.0)
    await make_listing(seller_id=agent.id, price_usdc=3.0)

    resp = await client.get("/api/v2/analytics/market/open")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_agents"] >= 1
    assert body["total_listings"] >= 2


async def test_analytics_with_transactions(
    client, make_agent, make_listing, make_transaction, seed_platform,
):
    """GET /market/open reflects completed transactions."""
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


async def test_analytics_limit_query_param(client):
    """GET /market/open accepts limit query parameter."""
    resp = await client.get("/api/v2/analytics/market/open?limit=5")
    assert resp.status_code == 200


async def test_analytics_limit_min_boundary(client):
    """GET /market/open accepts limit=1 (minimum)."""
    resp = await client.get("/api/v2/analytics/market/open?limit=1")
    assert resp.status_code == 200


async def test_analytics_limit_max_boundary(client):
    """GET /market/open accepts limit=50 (maximum)."""
    resp = await client.get("/api/v2/analytics/market/open?limit=50")
    assert resp.status_code == 200


async def test_analytics_limit_below_min_returns_422(client):
    """GET /market/open with limit=0 returns 422."""
    resp = await client.get("/api/v2/analytics/market/open?limit=0")
    assert resp.status_code == 422


async def test_analytics_limit_above_max_returns_422(client):
    """GET /market/open with limit=51 returns 422."""
    resp = await client.get("/api/v2/analytics/market/open?limit=51")
    assert resp.status_code == 422


async def test_analytics_non_integer_limit_returns_422(client):
    """GET /market/open with non-integer limit returns 422."""
    resp = await client.get("/api/v2/analytics/market/open?limit=abc")
    assert resp.status_code == 422


async def test_analytics_graceful_fallback_on_service_error(client):
    """GET /market/open returns zeroed response when service layer errors."""
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
    client, make_agent, make_listing, make_transaction, seed_platform,
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
