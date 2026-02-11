"""Integration tests for Seller API routes.

Tests hit the FastAPI endpoints through httpx AsyncClient.
"""

import pytest

from marketplace.core.auth import create_access_token
from marketplace.models.agent import RegisteredAgent
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_seller() -> tuple[str, str]:
    """Create a seller agent and return (agent_id, jwt)."""
    async with TestSession() as db:
        agent_id = _new_id()
        agent = RegisteredAgent(
            id=agent_id,
            name=f"seller-{agent_id[:8]}",
            agent_type="seller",
            public_key="ssh-rsa AAAA_test_key",
            status="active",
        )
        db.add(agent)
        await db.commit()
        jwt = create_access_token(agent_id, agent.name)
        return agent_id, jwt


# ---------------------------------------------------------------------------
# POST /seller/bulk-list
# ---------------------------------------------------------------------------

async def test_bulk_list_success(client):
    """Bulk listing succeeds with valid items."""
    _, jwt = await _setup_seller()

    items = [
        {
            "title": f"Test Listing {i}",
            "category": "web_search",
            "content": "test content data",
            "price_usdc": 0.005,
        }
        for i in range(5)
    ]

    resp = await client.post(
        "/api/v1/seller/bulk-list",
        json={"items": items},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 5
    assert data["errors"] == 0
    assert len(data["listings"]) == 5
    assert all("listing_id" in l for l in data["listings"])
    assert all("title" in l for l in data["listings"])


async def test_bulk_list_exceeds_100(client):
    """Bulk listing rejects > 100 items with 422 validation error."""
    _, jwt = await _setup_seller()

    items = [
        {
            "title": f"Listing {i}",
            "category": "web_search",
            "content": "test content",
            "price_usdc": 0.005,
        }
        for i in range(101)
    ]

    resp = await client.post(
        "/api/v1/seller/bulk-list",
        json={"items": items},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    # Pydantic validation catches this before it reaches the service
    assert resp.status_code == 422


async def test_bulk_list_partial_errors(client):
    """Bulk listing returns partial success with invalid items."""
    _, jwt = await _setup_seller()

    items = [
        {
            "title": "Valid Listing",
            "category": "web_search",
            "content": "test content",
            "price_usdc": 0.005,
        },
        {
            "title": "Invalid Listing",
            "category": "web_search",
            # Missing required content field
            "price_usdc": 0.005,
        },
        {
            "title": "Another Valid",
            "category": "web_search",
            "content": "more test content",
            "price_usdc": 0.01,
        },
    ]

    resp = await client.post(
        "/api/v1/seller/bulk-list",
        json={"items": items},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 2
    assert data["errors"] == 1
    assert len(data["error_details"]) == 1
    assert data["error_details"][0]["index"] == 1


async def test_bulk_list_empty_items(client):
    """Bulk listing rejects empty items list."""
    _, jwt = await _setup_seller()

    resp = await client.post(
        "/api/v1/seller/bulk-list",
        json={"items": []},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 422  # Pydantic validation error


async def test_bulk_list_unauthenticated(client):
    """Bulk listing requires authentication."""
    resp = await client.post(
        "/api/v1/seller/bulk-list",
        json={"items": [{"title": "Test"}]},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /seller/demand-for-me
# ---------------------------------------------------------------------------

async def test_demand_for_me_no_catalog(client, make_demand_signal):
    """Demand endpoint returns empty for seller with no catalog."""
    seller_id, jwt = await _setup_seller()

    # Create some demand signals
    async with TestSession() as db:
        await make_demand_signal(query_pattern="python tutorial", category="web_search")

    resp = await client.get(
        "/api/v1/seller/demand-for-me",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["matches"] == []


async def test_demand_for_me_with_matching_catalog(client, make_agent, make_catalog_entry, make_demand_signal):
    """Demand endpoint returns matching signals for seller's catalog."""
    seller, jwt = await make_agent(name="seller-demand", agent_type="seller")
    seller_id = seller.id

    async with TestSession() as db:
        # Create catalog entry
        await make_catalog_entry(seller_id, namespace="web_search", topic="tutorials")

        # Create matching demand signal
        await make_demand_signal(
            query_pattern="python tutorial",
            category="web_search",
            search_count=50,
            velocity=8.0,
            fulfillment_rate=0.3,
        )

        # Create non-matching demand signal
        await make_demand_signal(
            query_pattern="financial reports",
            category="finance",
            search_count=10,
            velocity=2.0,
        )

    resp = await client.get(
        "/api/v1/seller/demand-for-me",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    # Should match web_search
    web_search_match = next(
        (m for m in data["matches"] if m["category"] == "web_search"),
        None,
    )
    assert web_search_match is not None
    assert web_search_match["velocity"] == 8.0
    assert web_search_match["opportunity"] == "high"


async def test_demand_for_me_unauthenticated(client):
    """Demand endpoint requires authentication."""
    resp = await client.get("/api/v1/seller/demand-for-me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /seller/price-suggest
# ---------------------------------------------------------------------------

async def test_price_suggest_no_competitors(client):
    """Price suggestion returns default for category with no listings."""
    _, jwt = await _setup_seller()

    resp = await client.post(
        "/api/v1/seller/price-suggest",
        json={"category": "web_search", "quality_score": 0.8},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggested_price"] == 0.005
    assert data["category"] == "web_search"
    assert data["competitors"] == 0
    assert "No competitors" in data["strategy"]


async def test_price_suggest_with_market_data(client, make_agent, make_listing):
    """Price suggestion uses market data when available."""
    seller, jwt = await make_agent(name="seller-price", agent_type="seller")
    other_seller_id = _new_id()

    async with TestSession() as db:
        # Create competing listings
        await make_listing(other_seller_id, price_usdc=0.01, category="web_search", quality_score=0.7)
        await make_listing(other_seller_id, price_usdc=0.015, category="web_search", quality_score=0.8)
        await make_listing(other_seller_id, price_usdc=0.02, category="web_search", quality_score=0.9)

    resp = await client.post(
        "/api/v1/seller/price-suggest",
        json={"category": "web_search", "quality_score": 0.9},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["competitors"] == 3
    assert data["median_price"] == 0.015
    assert data["suggested_price"] > 0.001
    assert "Quality-adjusted" in data["strategy"]
    assert "price_range" in data


async def test_price_suggest_quality_adjustment(client, make_agent, make_listing):
    """Price suggestion adjusts for quality score."""
    seller, jwt = await make_agent(name="seller-quality", agent_type="seller")
    other_seller_id = _new_id()

    async with TestSession() as db:
        # Create listings with average quality 0.5
        await make_listing(other_seller_id, price_usdc=0.01, category="web_search", quality_score=0.5)

    # High quality should get higher price
    resp_high = await client.post(
        "/api/v1/seller/price-suggest",
        json={"category": "web_search", "quality_score": 0.9},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    # Low quality should get lower price
    resp_low = await client.post(
        "/api/v1/seller/price-suggest",
        json={"category": "web_search", "quality_score": 0.3},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert resp_high.status_code == 200
    assert resp_low.status_code == 200
    high_price = resp_high.json()["suggested_price"]
    low_price = resp_low.json()["suggested_price"]
    assert high_price > low_price


async def test_price_suggest_unauthenticated(client):
    """Price suggestion requires authentication."""
    resp = await client.post(
        "/api/v1/seller/price-suggest",
        json={"category": "web_search"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /seller/webhook (register)
# ---------------------------------------------------------------------------

async def test_register_webhook_success(client):
    """Webhook registration succeeds with valid data."""
    _, jwt = await _setup_seller()

    resp = await client.post(
        "/api/v1/seller/webhook",
        json={
            "url": "https://example.com/webhook/demand",
            "event_types": ["demand_match", "high_velocity"],
            "secret": "my-webhook-secret",
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["url"] == "https://example.com/webhook/demand"
    assert set(data["event_types"]) == {"demand_match", "high_velocity"}
    assert data["status"] == "active"


async def test_register_webhook_default_events(client):
    """Webhook registration uses default events when not specified."""
    _, jwt = await _setup_seller()

    resp = await client.post(
        "/api/v1/seller/webhook",
        json={"url": "https://example.com/webhook"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "demand_match" in data["event_types"]


async def test_register_webhook_unauthenticated(client):
    """Webhook registration requires authentication."""
    resp = await client.post(
        "/api/v1/seller/webhook",
        json={"url": "https://example.com/webhook"},
    )
    assert resp.status_code == 401


async def test_register_webhook_invalid_url(client):
    """Webhook registration validates URL format."""
    _, jwt = await _setup_seller()

    resp = await client.post(
        "/api/v1/seller/webhook",
        json={"url": ""},  # Empty URL
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 422  # Pydantic validation error


# ---------------------------------------------------------------------------
# GET /seller/webhooks
# ---------------------------------------------------------------------------

async def test_list_webhooks_empty(client):
    """Webhook list returns empty for new seller."""
    _, jwt = await _setup_seller()

    resp = await client.get(
        "/api/v1/seller/webhooks",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["webhooks"] == []


async def test_list_webhooks_with_registered(client):
    """Webhook list returns all registered webhooks."""
    seller_id, jwt = await _setup_seller()

    # Register multiple webhooks
    urls = [
        "https://example.com/webhook/1",
        "https://example.com/webhook/2",
    ]
    for url in urls:
        await client.post(
            "/api/v1/seller/webhook",
            json={"url": url},
            headers={"Authorization": f"Bearer {jwt}"},
        )

    resp = await client.get(
        "/api/v1/seller/webhooks",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert len(data["webhooks"]) == 2
    returned_urls = {w["url"] for w in data["webhooks"]}
    assert returned_urls == set(urls)
    # Check all fields are present
    for wh in data["webhooks"]:
        assert "id" in wh
        assert "url" in wh
        assert "event_types" in wh
        assert "status" in wh
        assert "failure_count" in wh


async def test_list_webhooks_unauthenticated(client):
    """Webhook list requires authentication."""
    resp = await client.get("/api/v1/seller/webhooks")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Integration: Full seller workflow
# ---------------------------------------------------------------------------

async def test_seller_workflow_integration(client, make_catalog_entry, make_demand_signal, make_listing, make_agent):
    """End-to-end: seller discovers demand, gets pricing, bulk lists, registers webhook."""
    # Create seller agent using fixture
    seller, jwt = await make_agent(name="seller-workflow", agent_type="seller")
    seller_id = seller.id

    # Step 1: Seller publishes catalog
    async with TestSession() as db:
        await make_catalog_entry(seller_id, namespace="web_search", topic="tutorials")

    # Step 2: Market creates demand
    async with TestSession() as db:
        await make_demand_signal(
            query_pattern="python tutorial",
            category="web_search",
            search_count=100,
            velocity=12.0,
        )
        # Create competing listings for pricing
        other_seller = _new_id()
        await make_listing(other_seller, price_usdc=0.01, category="web_search")

    # Step 3: Seller checks demand
    demand_resp = await client.get(
        "/api/v1/seller/demand-for-me",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert demand_resp.status_code == 200
    assert demand_resp.json()["count"] >= 1

    # Step 4: Seller gets pricing suggestion
    price_resp = await client.post(
        "/api/v1/seller/price-suggest",
        json={"category": "web_search", "quality_score": 0.85},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert price_resp.status_code == 200
    suggested_price = price_resp.json()["suggested_price"]

    # Step 5: Seller bulk lists
    bulk_resp = await client.post(
        "/api/v1/seller/bulk-list",
        json={
            "items": [
                {
                    "title": "Python Tutorial Part 1",
                    "category": "web_search",
                    "content": "tutorial content part 1",
                    "price_usdc": suggested_price,
                },
                {
                    "title": "Python Tutorial Part 2",
                    "category": "web_search",
                    "content": "tutorial content part 2",
                    "price_usdc": suggested_price,
                },
            ]
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["created"] == 2

    # Step 6: Seller registers webhook for future demand
    webhook_resp = await client.post(
        "/api/v1/seller/webhook",
        json={
            "url": "https://seller.example.com/hooks/demand",
            "event_types": ["demand_match"],
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert webhook_resp.status_code == 200

    # Step 7: Verify webhook is registered
    list_resp = await client.get(
        "/api/v1/seller/webhooks",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 1
