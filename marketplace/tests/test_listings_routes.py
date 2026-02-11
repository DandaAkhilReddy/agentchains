"""Comprehensive tests for /api/v1/listings routes."""

import pytest


# ---------------------------------------------------------------------------
# POST /api/v1/listings (create listing)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_listing_requires_auth(client):
    """Creating a listing requires authentication."""
    response = await client.post(
        "/api/v1/listings",
        json={
            "title": "Test Listing",
            "category": "web_search",
            "content": "test content",
            "price_usdc": 1.0,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_listing_validates_fields(client, make_agent, auth_header):
    """Creating a listing validates required fields and constraints."""
    agent, token = await make_agent()

    # Missing title
    response = await client.post(
        "/api/v1/listings",
        headers=auth_header(token),
        json={
            "category": "web_search",
            "content": "test",
            "price_usdc": 1.0,
        },
    )
    assert response.status_code == 422

    # Invalid category
    response = await client.post(
        "/api/v1/listings",
        headers=auth_header(token),
        json={
            "title": "Test",
            "category": "invalid_category",
            "content": "test",
            "price_usdc": 1.0,
        },
    )
    assert response.status_code == 422

    # Price too low (must be > 0)
    response = await client.post(
        "/api/v1/listings",
        headers=auth_header(token),
        json={
            "title": "Test",
            "category": "web_search",
            "content": "test",
            "price_usdc": 0,
        },
    )
    assert response.status_code == 422

    # Price too high (max 1000)
    response = await client.post(
        "/api/v1/listings",
        headers=auth_header(token),
        json={
            "title": "Test",
            "category": "web_search",
            "content": "test",
            "price_usdc": 1001,
        },
    )
    assert response.status_code == 422

    # Empty content
    response = await client.post(
        "/api/v1/listings",
        headers=auth_header(token),
        json={
            "title": "Test",
            "category": "web_search",
            "content": "",
            "price_usdc": 1.0,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_listing_success(client, make_agent, auth_header):
    """Successfully create a listing with valid data."""
    agent, token = await make_agent()

    response = await client.post(
        "/api/v1/listings",
        headers=auth_header(token),
        json={
            "title": "Python Tutorial Dataset",
            "description": "Comprehensive Python tutorials",
            "category": "web_search",
            "content": "Sample python tutorial content",
            "price_usdc": 2.5,
            "metadata": {"source": "test", "version": "1.0"},
            "tags": ["python", "tutorial"],
            "quality_score": 0.9,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Python Tutorial Dataset"
    assert data["description"] == "Comprehensive Python tutorials"
    assert data["category"] == "web_search"
    assert data["price_usdc"] == 2.5
    assert data["seller_id"] == agent.id
    assert data["metadata"] == {"source": "test", "version": "1.0"}
    assert data["tags"] == ["python", "tutorial"]
    assert data["quality_score"] == 0.9
    assert data["status"] == "active"
    assert "id" in data
    assert "content_hash" in data
    assert "created_at" in data


# ---------------------------------------------------------------------------
# GET /api/v1/listings (list listings)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_listings_empty(client):
    """List listings returns empty list when no listings exist."""
    response = await client.get("/api/v1/listings")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["results"] == []


@pytest.mark.asyncio
async def test_list_listings_with_data(client, make_agent, make_listing):
    """List listings returns active listings."""
    agent1, _ = await make_agent()
    agent2, _ = await make_agent()

    listing1 = await make_listing(agent1.id, title="Listing 1")
    listing2 = await make_listing(agent2.id, title="Listing 2")
    await make_listing(agent1.id, status="delisted")  # Should not appear

    response = await client.get("/api/v1/listings")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["results"]) == 2
    assert {r["id"] for r in data["results"]} == {listing1.id, listing2.id}


@pytest.mark.asyncio
async def test_list_listings_filter_by_category(client, make_agent, make_listing):
    """Filter listings by category."""
    agent, _ = await make_agent()

    web_listing = await make_listing(agent.id, category="web_search")
    await make_listing(agent.id, category="code_analysis")

    response = await client.get("/api/v1/listings?category=web_search")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["id"] == web_listing.id
    assert data["results"][0]["category"] == "web_search"


@pytest.mark.asyncio
async def test_list_listings_pagination(client, make_agent, make_listing):
    """Pagination works correctly."""
    agent, _ = await make_agent()

    # Create 5 listings
    for i in range(5):
        await make_listing(agent.id, title=f"Listing {i}")

    # Page 1, 2 per page
    response = await client.get("/api/v1/listings?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["results"]) == 2

    # Page 2
    response = await client.get("/api/v1/listings?page=2&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert len(data["results"]) == 2

    # Page 3 (last page, only 1 item)
    response = await client.get("/api/v1/listings?page=3&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1


# ---------------------------------------------------------------------------
# GET /api/v1/listings/{id} (get single listing)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_listing_success(client, make_agent, make_listing):
    """Get a specific listing by ID."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id, title="Test Listing", price_usdc=5.0)

    response = await client.get(f"/api/v1/listings/{listing.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == listing.id
    assert data["title"] == "Test Listing"
    assert data["price_usdc"] == 5.0
    assert data["seller_id"] == agent.id


@pytest.mark.asyncio
async def test_get_listing_not_found(client):
    """Get listing returns 404 for non-existent listing."""
    response = await client.get("/api/v1/listings/nonexistent-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/listings/{id} (update listing)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_listing_requires_auth(client, make_agent, make_listing):
    """Updating a listing requires authentication."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    response = await client.put(
        f"/api/v1/listings/{listing.id}",
        json={"title": "Updated Title"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_listing_only_owner(client, make_agent, make_listing, auth_header):
    """Only the listing owner can update it."""
    owner, owner_token = await make_agent()
    other_agent, other_token = await make_agent()
    listing = await make_listing(owner.id)

    # Non-owner attempts to update
    response = await client.put(
        f"/api/v1/listings/{listing.id}",
        headers=auth_header(other_token),
        json={"title": "Hacked Title"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_listing_success(client, make_agent, make_listing, auth_header):
    """Owner can successfully update listing fields."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id, title="Original Title", price_usdc=1.0)

    response = await client.put(
        f"/api/v1/listings/{listing.id}",
        headers=auth_header(token),
        json={
            "title": "Updated Title",
            "description": "New description",
            "price_usdc": 2.5,
            "tags": ["updated", "tags"],
            "quality_score": 0.95,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == listing.id
    assert data["title"] == "Updated Title"
    assert data["description"] == "New description"
    assert data["price_usdc"] == 2.5
    assert data["tags"] == ["updated", "tags"]
    assert data["quality_score"] == 0.95


@pytest.mark.asyncio
async def test_update_listing_partial(client, make_agent, make_listing, auth_header):
    """Partial update only changes specified fields."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id, title="Original", price_usdc=1.0)

    # Only update price
    response = await client.put(
        f"/api/v1/listings/{listing.id}",
        headers=auth_header(token),
        json={"price_usdc": 3.0},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Original"  # Unchanged
    assert data["price_usdc"] == 3.0  # Changed


@pytest.mark.asyncio
async def test_update_listing_not_found(client, make_agent, auth_header):
    """Update returns 404 for non-existent listing."""
    agent, token = await make_agent()

    response = await client.put(
        "/api/v1/listings/nonexistent-id",
        headers=auth_header(token),
        json={"title": "Updated"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/listings/{id} (delist)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delist_requires_auth(client, make_agent, make_listing):
    """Delisting a listing requires authentication."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    response = await client.delete(f"/api/v1/listings/{listing.id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delist_only_owner(client, make_agent, make_listing, auth_header):
    """Only the listing owner can delist it."""
    owner, owner_token = await make_agent()
    other_agent, other_token = await make_agent()
    listing = await make_listing(owner.id)

    # Non-owner attempts to delist
    response = await client.delete(
        f"/api/v1/listings/{listing.id}",
        headers=auth_header(other_token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delist_success(client, make_agent, make_listing, auth_header):
    """Owner can successfully delist their listing."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id)

    response = await client.delete(
        f"/api/v1/listings/{listing.id}",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "delisted"

    # Verify listing is no longer in active list
    list_response = await client.get("/api/v1/listings")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert listing.id not in [r["id"] for r in list_data["results"]]


@pytest.mark.asyncio
async def test_delist_not_found(client, make_agent, auth_header):
    """Delist returns 404 for non-existent listing."""
    agent, token = await make_agent()

    response = await client.delete(
        "/api/v1/listings/nonexistent-id",
        headers=auth_header(token),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/discover (discovery search)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discover_empty(client):
    """Discover returns empty results when no listings exist."""
    response = await client.get("/api/v1/discover")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_discover_search_by_text(client, make_agent, db):
    """Discover can search by text in title, description, tags."""
    import json
    from marketplace.models.listing import DataListing
    from decimal import Decimal

    agent, _ = await make_agent()

    # Create listings directly with proper fields since make_listing fixture
    # doesn't support description and tags kwargs
    listing1 = DataListing(
        seller_id=agent.id, title="Python Tutorial", category="web_search",
        content_hash="sha256:abc123", content_size=100, price_usdc=Decimal("1.0"),
    )
    listing2 = DataListing(
        seller_id=agent.id, title="Java Guide", description="Python basics inside",
        category="web_search", content_hash="sha256:abc124", content_size=100,
        price_usdc=Decimal("1.0"),
    )
    listing3 = DataListing(
        seller_id=agent.id, title="Ruby Course", category="web_search",
        content_hash="sha256:abc125", content_size=100, price_usdc=Decimal("1.0"),
        tags=json.dumps(["python", "ruby"]),
    )
    listing4 = DataListing(
        seller_id=agent.id, title="Go Programming", category="web_search",
        content_hash="sha256:abc126", content_size=100, price_usdc=Decimal("1.0"),
    )

    db.add_all([listing1, listing2, listing3, listing4])
    await db.commit()

    # Search for "python" should match first 3 listings
    response = await client.get("/api/v1/discover?q=python")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_discover_filter_by_category(client, make_agent, make_listing):
    """Discover can filter by category."""
    agent, _ = await make_agent()

    await make_listing(agent.id, category="web_search")
    await make_listing(agent.id, category="web_search")
    await make_listing(agent.id, category="code_analysis")

    response = await client.get("/api/v1/discover?category=web_search")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    for result in data["results"]:
        assert result["category"] == "web_search"


@pytest.mark.asyncio
async def test_discover_filter_by_price_range(client, make_agent, make_listing):
    """Discover can filter by price range."""
    agent, _ = await make_agent()

    await make_listing(agent.id, price_usdc=0.5)
    await make_listing(agent.id, price_usdc=1.5)
    await make_listing(agent.id, price_usdc=2.5)
    await make_listing(agent.id, price_usdc=3.5)

    # Filter min_price=1, max_price=3
    response = await client.get("/api/v1/discover?min_price=1.0&max_price=3.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    for result in data["results"]:
        assert 1.0 <= result["price_usdc"] <= 3.0


@pytest.mark.asyncio
async def test_discover_filter_by_quality(client, make_agent, make_listing):
    """Discover can filter by minimum quality score."""
    agent, _ = await make_agent()

    await make_listing(agent.id, quality_score=0.5)
    await make_listing(agent.id, quality_score=0.7)
    await make_listing(agent.id, quality_score=0.9)

    response = await client.get("/api/v1/discover?min_quality=0.75")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["quality_score"] == 0.9


@pytest.mark.asyncio
async def test_discover_filter_by_seller(client, make_agent, make_listing):
    """Discover can filter by seller_id."""
    agent1, _ = await make_agent()
    agent2, _ = await make_agent()

    await make_listing(agent1.id)
    await make_listing(agent1.id)
    await make_listing(agent2.id)

    response = await client.get(f"/api/v1/discover?seller_id={agent1.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    for result in data["results"]:
        assert result["seller_id"] == agent1.id


@pytest.mark.asyncio
async def test_discover_sort_by_price(client, make_agent, make_listing):
    """Discover can sort by price ascending or descending."""
    agent, _ = await make_agent()

    await make_listing(agent.id, price_usdc=3.0, title="Expensive")
    await make_listing(agent.id, price_usdc=1.0, title="Cheap")
    await make_listing(agent.id, price_usdc=2.0, title="Medium")

    # Sort by price ascending
    response = await client.get("/api/v1/discover?sort_by=price_asc")
    assert response.status_code == 200
    data = response.json()
    prices = [r["price_usdc"] for r in data["results"]]
    assert prices == [1.0, 2.0, 3.0]

    # Sort by price descending
    response = await client.get("/api/v1/discover?sort_by=price_desc")
    assert response.status_code == 200
    data = response.json()
    prices = [r["price_usdc"] for r in data["results"]]
    assert prices == [3.0, 2.0, 1.0]


@pytest.mark.asyncio
async def test_discover_sort_by_quality(client, make_agent, make_listing):
    """Discover can sort by quality score descending."""
    agent, _ = await make_agent()

    await make_listing(agent.id, quality_score=0.5)
    await make_listing(agent.id, quality_score=0.9)
    await make_listing(agent.id, quality_score=0.7)

    response = await client.get("/api/v1/discover?sort_by=quality")
    assert response.status_code == 200
    data = response.json()
    scores = [r["quality_score"] for r in data["results"]]
    assert scores == [0.9, 0.7, 0.5]


@pytest.mark.asyncio
async def test_discover_pagination(client, make_agent, make_listing):
    """Discover respects pagination parameters."""
    agent, _ = await make_agent()

    for i in range(5):
        await make_listing(agent.id, title=f"Listing {i}")

    response = await client.get("/api/v1/discover?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["results"]) == 2


@pytest.mark.asyncio
async def test_discover_combined_filters(client, make_agent, make_listing):
    """Discover can combine multiple filters."""
    agent, _ = await make_agent()

    # Create listings with various attributes
    await make_listing(agent.id, title="Python Web", category="web_search", price_usdc=1.0, quality_score=0.8)
    await make_listing(agent.id, title="Python Code", category="code_analysis", price_usdc=2.0, quality_score=0.9)
    await make_listing(agent.id, title="Java Web", category="web_search", price_usdc=1.5, quality_score=0.7)

    # Search for "python" + web_search category + quality >= 0.75
    response = await client.get("/api/v1/discover?q=python&category=web_search&min_quality=0.75")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["title"] == "Python Web"
    assert data["results"][0]["category"] == "web_search"
    assert data["results"][0]["quality_score"] == 0.8
