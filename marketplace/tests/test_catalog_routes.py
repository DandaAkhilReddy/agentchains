"""Test suite for Data Catalog API routes.

Tests cover:
- POST /api/v1/catalog — register catalog entry
- GET /api/v1/catalog/search — search catalog with filters and pagination
- GET /api/v1/catalog/agent/{id} — get all entries for an agent
- GET /api/v1/catalog/{id} — get single entry
- PATCH /api/v1/catalog/{id} — update entry (owner only)
- DELETE /api/v1/catalog/{id} — delete entry (owner only)
- POST /api/v1/catalog/subscribe — subscribe to catalog updates
- DELETE /api/v1/catalog/subscribe/{id} — unsubscribe (owner only)
- POST /api/v1/catalog/auto-populate — auto-create entries from listings
"""

import pytest


# ── POST /api/v1/catalog ────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_catalog_entry_success(client, make_agent, auth_header):
    """Successfully register a new catalog entry."""
    agent, token = await make_agent(name="seller-agent")

    payload = {
        "namespace": "web_search",
        "topic": "python tutorials",
        "description": "High-quality Python tutorial data",
        "schema_json": {"type": "object", "properties": {"url": {"type": "string"}}},
        "price_range_min": 0.002,
        "price_range_max": 0.015,
    }

    resp = await client.post(
        "/api/v1/catalog",
        json=payload,
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == agent.id
    assert data["namespace"] == "web_search"
    assert data["topic"] == "python tutorials"
    assert data["description"] == "High-quality Python tutorial data"
    assert data["schema_json"] == {"type": "object", "properties": {"url": {"type": "string"}}}
    assert data["price_range"] == [0.002, 0.015]
    assert data["status"] == "active"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_register_catalog_entry_requires_auth(client):
    """POST /api/v1/catalog requires authentication."""
    payload = {
        "namespace": "web_search",
        "topic": "test",
    }

    resp = await client.post("/api/v1/catalog", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_catalog_entry_validation_error(client, make_agent, auth_header):
    """POST /api/v1/catalog validates required fields."""
    agent, token = await make_agent()

    # Missing required namespace
    resp = await client.post(
        "/api/v1/catalog",
        json={"topic": "test"},
        headers=auth_header(token),
    )
    assert resp.status_code == 422

    # Missing required topic
    resp = await client.post(
        "/api/v1/catalog",
        json={"namespace": "test"},
        headers=auth_header(token),
    )
    assert resp.status_code == 422

    # Invalid price range (negative)
    resp = await client.post(
        "/api/v1/catalog",
        json={"namespace": "test", "topic": "test", "price_range_min": -0.01},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


# ── GET /api/v1/catalog/search ─────────────────────────────────


@pytest.mark.asyncio
async def test_search_catalog_no_filters(client, make_agent, make_catalog_entry):
    """Search catalog without filters returns all active entries."""
    agent, _ = await make_agent()
    await make_catalog_entry(agent.id, namespace="web_search", topic="python")
    await make_catalog_entry(agent.id, namespace="image_gen", topic="logos")

    resp = await client.get("/api/v1/catalog/search")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert len(data["entries"]) == 2


@pytest.mark.asyncio
async def test_search_catalog_with_query(client, make_agent, make_catalog_entry):
    """Search catalog with text query filters results."""
    agent, _ = await make_agent()
    await make_catalog_entry(agent.id, namespace="web_search", topic="python tutorials")
    await make_catalog_entry(agent.id, namespace="web_search", topic="javascript guide")

    resp = await client.get("/api/v1/catalog/search?q=python")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["entries"][0]["topic"] == "python tutorials"


@pytest.mark.asyncio
async def test_search_catalog_with_namespace_filter(client, make_agent, make_catalog_entry):
    """Search catalog with namespace filter."""
    agent, _ = await make_agent()
    await make_catalog_entry(agent.id, namespace="web_search", topic="test1")
    await make_catalog_entry(agent.id, namespace="image_gen", topic="test2")

    resp = await client.get("/api/v1/catalog/search?namespace=web_search")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["entries"][0]["namespace"] == "web_search"


@pytest.mark.asyncio
async def test_search_catalog_with_quality_filter(client, make_agent, make_catalog_entry):
    """Search catalog with min_quality filter."""
    agent, _ = await make_agent()
    await make_catalog_entry(agent.id, quality_avg=0.9)
    await make_catalog_entry(agent.id, quality_avg=0.6)

    resp = await client.get("/api/v1/catalog/search?min_quality=0.8")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["entries"][0]["quality_avg"] >= 0.8


@pytest.mark.asyncio
async def test_search_catalog_with_price_filter(client, make_agent, make_catalog_entry):
    """Search catalog with max_price filter."""
    agent, _ = await make_agent()
    await make_catalog_entry(agent.id, price_range_min=0.001, price_range_max=0.005)
    await make_catalog_entry(agent.id, price_range_min=0.02, price_range_max=0.03)

    resp = await client.get("/api/v1/catalog/search?max_price=0.01")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["entries"][0]["price_range"][0] <= 0.01


@pytest.mark.asyncio
async def test_search_catalog_pagination(client, make_agent, make_catalog_entry):
    """Search catalog supports pagination."""
    agent, _ = await make_agent()
    for i in range(5):
        await make_catalog_entry(agent.id, topic=f"topic-{i}")

    # First page
    resp = await client.get("/api/v1/catalog/search?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["entries"]) == 2

    # Second page
    resp = await client.get("/api/v1/catalog/search?page=2&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page"] == 2
    assert len(data["entries"]) == 2

    # Last page
    resp = await client.get("/api/v1/catalog/search?page=3&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 1


# ── GET /api/v1/catalog/agent/{agent_id} ───────────────────────


@pytest.mark.asyncio
async def test_get_agent_catalog(client, make_agent, make_catalog_entry):
    """Get all catalog entries for a specific agent."""
    agent1, _ = await make_agent()
    agent2, _ = await make_agent()
    await make_catalog_entry(agent1.id, topic="agent1-entry1")
    await make_catalog_entry(agent1.id, topic="agent1-entry2")
    await make_catalog_entry(agent2.id, topic="agent2-entry1")

    resp = await client.get(f"/api/v1/catalog/agent/{agent1.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["count"] == 2
    assert len(data["entries"]) == 2
    assert all(e["agent_id"] == agent1.id for e in data["entries"])


@pytest.mark.asyncio
async def test_get_agent_catalog_empty(client, make_agent):
    """Get agent catalog returns empty list if agent has no entries."""
    agent, _ = await make_agent()

    resp = await client.get(f"/api/v1/catalog/agent/{agent.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["count"] == 0
    assert data["entries"] == []


# ── GET /api/v1/catalog/{entry_id} ─────────────────────────────


@pytest.mark.asyncio
async def test_get_catalog_entry_success(client, make_agent, make_catalog_entry):
    """Get a single catalog entry by ID."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id, topic="test-entry")

    resp = await client.get(f"/api/v1/catalog/{entry.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == entry.id
    assert data["topic"] == "test-entry"
    assert data["agent_id"] == agent.id


@pytest.mark.asyncio
async def test_get_catalog_entry_not_found(client):
    """GET /api/v1/catalog/{id} returns 404 for non-existent entry."""
    resp = await client.get("/api/v1/catalog/non-existent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── PATCH /api/v1/catalog/{entry_id} ───────────────────────────


@pytest.mark.asyncio
async def test_update_catalog_entry_success(client, make_agent, make_catalog_entry, auth_header):
    """Update a catalog entry successfully."""
    agent, token = await make_agent()
    entry = await make_catalog_entry(agent.id, topic="original-topic")

    updates = {
        "topic": "updated-topic",
        "description": "Updated description",
        "price_range_min": 0.005,
    }

    resp = await client.patch(
        f"/api/v1/catalog/{entry.id}",
        json=updates,
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["topic"] == "updated-topic"
    assert data["description"] == "Updated description"
    assert data["price_range"][0] == 0.005


@pytest.mark.asyncio
async def test_update_catalog_entry_requires_auth(client, make_agent, make_catalog_entry):
    """PATCH /api/v1/catalog/{id} requires authentication."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id)

    resp = await client.patch(
        f"/api/v1/catalog/{entry.id}",
        json={"topic": "new-topic"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_catalog_entry_wrong_owner(client, make_agent, make_catalog_entry, auth_header):
    """PATCH /api/v1/catalog/{id} fails if not owner."""
    agent1, _ = await make_agent()
    agent2, token2 = await make_agent()
    entry = await make_catalog_entry(agent1.id)

    resp = await client.patch(
        f"/api/v1/catalog/{entry.id}",
        json={"topic": "new-topic"},
        headers=auth_header(token2),
    )
    assert resp.status_code == 404
    assert "not found or not owner" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_catalog_entry_not_found(client, make_agent, auth_header):
    """PATCH /api/v1/catalog/{id} returns 404 for non-existent entry."""
    agent, token = await make_agent()

    resp = await client.patch(
        "/api/v1/catalog/non-existent-id",
        json={"topic": "new-topic"},
        headers=auth_header(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_catalog_entry_with_schema(client, make_agent, make_catalog_entry, auth_header):
    """Update catalog entry with schema_json."""
    agent, token = await make_agent()
    entry = await make_catalog_entry(agent.id)

    new_schema = {"type": "array", "items": {"type": "string"}}
    resp = await client.patch(
        f"/api/v1/catalog/{entry.id}",
        json={"schema_json": new_schema},
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_json"] == new_schema


# ── DELETE /api/v1/catalog/{entry_id} ──────────────────────────


@pytest.mark.asyncio
async def test_delete_catalog_entry_success(client, make_agent, make_catalog_entry, auth_header):
    """Delete (retire) a catalog entry successfully."""
    agent, token = await make_agent()
    entry = await make_catalog_entry(agent.id)

    resp = await client.delete(
        f"/api/v1/catalog/{entry.id}",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    # Verify it's no longer in active search results
    search_resp = await client.get("/api/v1/catalog/search")
    assert search_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_catalog_entry_requires_auth(client, make_agent, make_catalog_entry):
    """DELETE /api/v1/catalog/{id} requires authentication."""
    agent, _ = await make_agent()
    entry = await make_catalog_entry(agent.id)

    resp = await client.delete(f"/api/v1/catalog/{entry.id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_catalog_entry_wrong_owner(client, make_agent, make_catalog_entry, auth_header):
    """DELETE /api/v1/catalog/{id} fails if not owner."""
    agent1, _ = await make_agent()
    agent2, token2 = await make_agent()
    entry = await make_catalog_entry(agent1.id)

    resp = await client.delete(
        f"/api/v1/catalog/{entry.id}",
        headers=auth_header(token2),
    )
    assert resp.status_code == 404
    assert "not found or not owner" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_catalog_entry_not_found(client, make_agent, auth_header):
    """DELETE /api/v1/catalog/{id} returns 404 for non-existent entry."""
    agent, token = await make_agent()

    resp = await client.delete(
        "/api/v1/catalog/non-existent-id",
        headers=auth_header(token),
    )
    assert resp.status_code == 404


# ── POST /api/v1/catalog/subscribe ─────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_success(client, make_agent, auth_header):
    """Successfully subscribe to catalog updates."""
    agent, token = await make_agent()

    payload = {
        "namespace_pattern": "web_search",
        "topic_pattern": "python*",
        "max_price": 0.01,
        "min_quality": 0.8,
    }

    resp = await client.post(
        "/api/v1/catalog/subscribe",
        json=payload,
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["namespace_pattern"] == "web_search"
    assert data["topic_pattern"] == "python*"
    assert data["notify_via"] == "websocket"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_subscribe_requires_auth(client):
    """POST /api/v1/catalog/subscribe requires authentication."""
    payload = {
        "namespace_pattern": "web_search",
    }

    resp = await client.post("/api/v1/catalog/subscribe", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_subscribe_validation_error(client, make_agent, auth_header):
    """POST /api/v1/catalog/subscribe validates required fields."""
    agent, token = await make_agent()

    # Missing required namespace_pattern
    resp = await client.post(
        "/api/v1/catalog/subscribe",
        json={"topic_pattern": "test"},
        headers=auth_header(token),
    )
    assert resp.status_code == 422

    # Invalid max_price (negative)
    resp = await client.post(
        "/api/v1/catalog/subscribe",
        json={"namespace_pattern": "test", "max_price": -0.01},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


# ── DELETE /api/v1/catalog/subscribe/{sub_id} ──────────────────


@pytest.mark.asyncio
async def test_unsubscribe_success(client, make_agent, make_catalog_subscription, auth_header):
    """Successfully unsubscribe from catalog updates."""
    agent, token = await make_agent()
    sub = await make_catalog_subscription(agent.id)

    resp = await client.delete(
        f"/api/v1/catalog/subscribe/{sub.id}",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    assert resp.json() == {"unsubscribed": True}


@pytest.mark.asyncio
async def test_unsubscribe_requires_auth(client, make_agent, make_catalog_subscription):
    """DELETE /api/v1/catalog/subscribe/{id} requires authentication."""
    agent, _ = await make_agent()
    sub = await make_catalog_subscription(agent.id)

    resp = await client.delete(f"/api/v1/catalog/subscribe/{sub.id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unsubscribe_wrong_owner(client, make_agent, make_catalog_subscription, auth_header):
    """DELETE /api/v1/catalog/subscribe/{id} fails if not owner."""
    agent1, _ = await make_agent()
    agent2, token2 = await make_agent()
    sub = await make_catalog_subscription(agent1.id)

    resp = await client.delete(
        f"/api/v1/catalog/subscribe/{sub.id}",
        headers=auth_header(token2),
    )
    assert resp.status_code == 404
    assert "not found or not owner" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unsubscribe_not_found(client, make_agent, auth_header):
    """DELETE /api/v1/catalog/subscribe/{id} returns 404 for non-existent subscription."""
    agent, token = await make_agent()

    resp = await client.delete(
        "/api/v1/catalog/subscribe/non-existent-id",
        headers=auth_header(token),
    )
    assert resp.status_code == 404


# ── POST /api/v1/catalog/auto-populate ─────────────────────────


@pytest.mark.asyncio
async def test_auto_populate_catalog_success(client, make_agent, make_listing, auth_header):
    """Auto-populate catalog from agent's existing listings."""
    agent, token = await make_agent()
    await make_listing(agent.id, category="web_search", price_usdc=0.002)
    await make_listing(agent.id, category="web_search", price_usdc=0.005)
    await make_listing(agent.id, category="image_gen", price_usdc=0.01)

    resp = await client.post(
        "/api/v1/catalog/auto-populate",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 2  # Two categories
    assert len(data["entries"]) == 2

    # Verify entries were created with correct stats
    namespaces = {e["namespace"] for e in data["entries"]}
    assert namespaces == {"web_search", "image_gen"}


@pytest.mark.asyncio
async def test_auto_populate_catalog_requires_auth(client):
    """POST /api/v1/catalog/auto-populate requires authentication."""
    resp = await client.post("/api/v1/catalog/auto-populate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auto_populate_catalog_no_listings(client, make_agent, auth_header):
    """Auto-populate returns empty if agent has no listings."""
    agent, token = await make_agent()

    resp = await client.post(
        "/api/v1/catalog/auto-populate",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 0
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_auto_populate_catalog_skips_existing(client, make_agent, make_listing, make_catalog_entry, auth_header):
    """Auto-populate skips categories that already have catalog entries."""
    agent, token = await make_agent()
    await make_listing(agent.id, category="web_search")
    await make_listing(agent.id, category="image_gen")

    # Pre-create catalog entry for web_search
    await make_catalog_entry(agent.id, namespace="web_search")

    resp = await client.post(
        "/api/v1/catalog/auto-populate",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1  # Only image_gen was created
    assert data["entries"][0]["namespace"] == "image_gen"
