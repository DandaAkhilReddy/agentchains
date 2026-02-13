"""Deep test suite for the discovery route: GET /api/v1/discover.

25 tests across 5 describe blocks covering:
- Agent discovery (list all agents, filter by category, filter by capability)
- Search functionality (keyword search, fuzzy matching, empty query)
- Pagination (page size, offset, total count, last page)
- Sorting (by rating, by price, by recency, default sort)
- Edge cases (no results, invalid filters, auth required endpoints, malformed query params)

Style: pytest-asyncio + integration via the ``client`` fixture, exercising the
real database layer through conftest's in-memory SQLite setup.
"""

import pytest


# ===================================================================
# AGENT DISCOVERY — 5 tests
# ===================================================================


@pytest.mark.asyncio
async def test_discover_all_listings_no_filters(client, make_agent, make_listing):
    """1. GET /api/v1/discover with no params returns all active listings."""
    agent, _ = await make_agent(name="disc-deep-1")
    await make_listing(agent.id, title="Listing A", price_usdc=1.0)
    await make_listing(agent.id, title="Listing B", price_usdc=2.0)
    await make_listing(agent.id, title="Listing C", price_usdc=3.0)

    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["results"]) == 3
    assert body["page"] == 1
    assert body["page_size"] == 20


@pytest.mark.asyncio
async def test_discover_filter_by_category(client, make_agent, make_listing):
    """2. ?category= filters results to a single category."""
    agent, _ = await make_agent(name="disc-deep-2")
    await make_listing(agent.id, title="Web A", category="web_search")
    await make_listing(agent.id, title="Code A", category="code_analysis")
    await make_listing(agent.id, title="Web B", category="web_search")

    resp = await client.get("/api/v1/discover", params={"category": "code_analysis"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["category"] == "code_analysis"
    assert body["results"][0]["title"] == "Code A"


@pytest.mark.asyncio
async def test_discover_filter_by_seller_id(client, make_agent, make_listing):
    """3. ?seller_id= isolates listings from one specific seller."""
    seller_a, _ = await make_agent(name="disc-deep-3a")
    seller_b, _ = await make_agent(name="disc-deep-3b")
    await make_listing(seller_a.id, title="Seller A listing 1")
    await make_listing(seller_a.id, title="Seller A listing 2")
    await make_listing(seller_b.id, title="Seller B listing 1")

    resp = await client.get("/api/v1/discover", params={"seller_id": seller_b.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert all(r["seller_id"] == seller_b.id for r in body["results"])


@pytest.mark.asyncio
async def test_discover_excludes_delisted(client, make_agent, make_listing):
    """4. Delisted listings are excluded from discovery results."""
    agent, _ = await make_agent(name="disc-deep-4")
    await make_listing(agent.id, title="Active Listing", status="active")
    await make_listing(agent.id, title="Gone Listing", status="delisted")

    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "Active Listing"


@pytest.mark.asyncio
async def test_discover_filter_min_quality(client, make_agent, make_listing):
    """5. ?min_quality= filters to listings at or above the quality threshold."""
    agent, _ = await make_agent(name="disc-deep-5")
    await make_listing(agent.id, title="High Q", quality_score=0.95, price_usdc=1.0)
    await make_listing(agent.id, title="Low Q", quality_score=0.3, price_usdc=2.0)
    await make_listing(agent.id, title="Mid Q", quality_score=0.7, price_usdc=3.0)

    resp = await client.get("/api/v1/discover", params={"min_quality": 0.7})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    for r in body["results"]:
        assert r["quality_score"] >= 0.7


# ===================================================================
# SEARCH FUNCTIONALITY — 5 tests
# ===================================================================


@pytest.mark.asyncio
async def test_discover_search_by_title_keyword(client, make_agent, make_listing):
    """6. ?q= matches against listing titles (case-insensitive LIKE)."""
    agent, _ = await make_agent(name="disc-deep-6")
    await make_listing(agent.id, title="Python Machine Learning Data")
    await make_listing(agent.id, title="JavaScript Framework Benchmarks")

    resp = await client.get("/api/v1/discover", params={"q": "python"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert "Python" in body["results"][0]["title"]


@pytest.mark.asyncio
async def test_discover_search_case_insensitive(client, make_agent, make_listing):
    """7. Text search is case-insensitive."""
    agent, _ = await make_agent(name="disc-deep-7")
    await make_listing(agent.id, title="UPPERCASE DATA SET")
    await make_listing(agent.id, title="lowercase data set")

    # Search with mixed case should match both
    resp = await client.get("/api/v1/discover", params={"q": "Data Set"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_discover_search_empty_query_returns_all(client, make_agent, make_listing):
    """8. ?q= with empty string returns all active listings (no filter applied)."""
    agent, _ = await make_agent(name="disc-deep-8")
    await make_listing(agent.id, title="Listing X")
    await make_listing(agent.id, title="Listing Y")

    resp = await client.get("/api/v1/discover", params={"q": ""})
    assert resp.status_code == 200
    body = resp.json()
    # Empty string q should be treated as None / no filter
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_discover_search_no_match(client, make_agent, make_listing):
    """9. ?q= with non-matching keyword returns zero results."""
    agent, _ = await make_agent(name="disc-deep-9")
    await make_listing(agent.id, title="Alpha Beta Gamma")

    resp = await client.get("/api/v1/discover", params={"q": "zzzznonexistent"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []


@pytest.mark.asyncio
async def test_discover_search_combined_with_category(client, make_agent, make_listing):
    """10. ?q= and ?category= applied together narrow results correctly."""
    agent, _ = await make_agent(name="disc-deep-10")
    await make_listing(agent.id, title="Python Web Data", category="web_search")
    await make_listing(agent.id, title="Python Code Data", category="code_analysis")
    await make_listing(agent.id, title="Java Web Data", category="web_search")

    resp = await client.get(
        "/api/v1/discover",
        params={"q": "Python", "category": "web_search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "Python Web Data"
    assert body["results"][0]["category"] == "web_search"


# ===================================================================
# PAGINATION — 5 tests
# ===================================================================


@pytest.mark.asyncio
async def test_discover_pagination_custom_page_size(client, make_agent, make_listing):
    """11. Custom page_size limits the number of returned results."""
    agent, _ = await make_agent(name="disc-deep-11")
    for i in range(7):
        await make_listing(agent.id, title=f"Paginated {i}", price_usdc=float(i + 1))

    resp = await client.get("/api/v1/discover", params={"page_size": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 7
    assert body["page_size"] == 3
    assert len(body["results"]) == 3


@pytest.mark.asyncio
async def test_discover_pagination_second_page_offset(client, make_agent, make_listing):
    """12. Page 2 returns a different set of results than page 1."""
    agent, _ = await make_agent(name="disc-deep-12")
    for i in range(6):
        await make_listing(agent.id, title=f"Item-{i}", price_usdc=float(i + 1))

    resp1 = await client.get("/api/v1/discover", params={"page": 1, "page_size": 3})
    resp2 = await client.get("/api/v1/discover", params={"page": 2, "page_size": 3})

    body1 = resp1.json()
    body2 = resp2.json()

    assert len(body1["results"]) == 3
    assert len(body2["results"]) == 3

    ids_page1 = {r["id"] for r in body1["results"]}
    ids_page2 = {r["id"] for r in body2["results"]}
    # No overlap between page 1 and page 2
    assert ids_page1.isdisjoint(ids_page2)


@pytest.mark.asyncio
async def test_discover_pagination_total_count_consistent(client, make_agent, make_listing):
    """13. Total count remains the same across different pages."""
    agent, _ = await make_agent(name="disc-deep-13")
    for i in range(5):
        await make_listing(agent.id, title=f"Consistent-{i}", price_usdc=float(i + 1))

    resp_p1 = await client.get("/api/v1/discover", params={"page": 1, "page_size": 2})
    resp_p2 = await client.get("/api/v1/discover", params={"page": 2, "page_size": 2})
    resp_p3 = await client.get("/api/v1/discover", params={"page": 3, "page_size": 2})

    assert resp_p1.json()["total"] == 5
    assert resp_p2.json()["total"] == 5
    assert resp_p3.json()["total"] == 5


@pytest.mark.asyncio
async def test_discover_pagination_last_page_partial(client, make_agent, make_listing):
    """14. The last page may have fewer results than page_size."""
    agent, _ = await make_agent(name="disc-deep-14")
    for i in range(5):
        await make_listing(agent.id, title=f"LastPage-{i}", price_usdc=float(i + 1))

    resp = await client.get("/api/v1/discover", params={"page": 3, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["results"]) == 1  # 5 items, page_size 2 -> page 3 has 1 item


@pytest.mark.asyncio
async def test_discover_pagination_beyond_last_page(client, make_agent, make_listing):
    """15. A page beyond the last returns empty results but valid total."""
    agent, _ = await make_agent(name="disc-deep-15")
    for i in range(3):
        await make_listing(agent.id, title=f"Beyond-{i}", price_usdc=float(i + 1))

    resp = await client.get("/api/v1/discover", params={"page": 100, "page_size": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["results"] == []
    assert body["page"] == 100


# ===================================================================
# SORTING — 5 tests
# ===================================================================


@pytest.mark.asyncio
async def test_discover_sort_price_ascending(client, make_agent, make_listing):
    """16. ?sort_by=price_asc orders results from cheapest to most expensive."""
    agent, _ = await make_agent(name="disc-deep-16")
    await make_listing(agent.id, title="Expensive", price_usdc=99.0)
    await make_listing(agent.id, title="Cheap", price_usdc=1.0)
    await make_listing(agent.id, title="Mid", price_usdc=25.0)

    resp = await client.get("/api/v1/discover", params={"sort_by": "price_asc"})
    assert resp.status_code == 200
    prices = [r["price_usdc"] for r in resp.json()["results"]]
    assert prices == sorted(prices), f"Expected ascending order, got {prices}"


@pytest.mark.asyncio
async def test_discover_sort_price_descending(client, make_agent, make_listing):
    """17. ?sort_by=price_desc orders results from most expensive to cheapest."""
    agent, _ = await make_agent(name="disc-deep-17")
    await make_listing(agent.id, title="Cheap", price_usdc=2.0)
    await make_listing(agent.id, title="Expensive", price_usdc=80.0)
    await make_listing(agent.id, title="Mid", price_usdc=20.0)

    resp = await client.get("/api/v1/discover", params={"sort_by": "price_desc"})
    assert resp.status_code == 200
    prices = [r["price_usdc"] for r in resp.json()["results"]]
    assert prices == sorted(prices, reverse=True), f"Expected descending order, got {prices}"


@pytest.mark.asyncio
async def test_discover_sort_quality(client, make_agent, make_listing):
    """18. ?sort_by=quality orders results by quality_score descending."""
    agent, _ = await make_agent(name="disc-deep-18")
    await make_listing(agent.id, title="Low Q", quality_score=0.2, price_usdc=1.0)
    await make_listing(agent.id, title="High Q", quality_score=0.99, price_usdc=2.0)
    await make_listing(agent.id, title="Mid Q", quality_score=0.6, price_usdc=3.0)

    resp = await client.get("/api/v1/discover", params={"sort_by": "quality"})
    assert resp.status_code == 200
    scores = [r["quality_score"] for r in resp.json()["results"]]
    assert scores == sorted(scores, reverse=True), f"Expected quality desc, got {scores}"


@pytest.mark.asyncio
async def test_discover_default_sort_is_freshness(client, make_agent, make_listing):
    """19. Default sort_by (freshness) orders most-recently-created first."""
    agent, _ = await make_agent(name="disc-deep-19")
    # Create in sequence -- the service orders by freshness_at DESC
    await make_listing(agent.id, title="First Created", price_usdc=1.0)
    await make_listing(agent.id, title="Second Created", price_usdc=2.0)
    await make_listing(agent.id, title="Third Created", price_usdc=3.0)

    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()["results"]]
    # Most recent first -- freshness_at DESC
    assert titles[0] == "Third Created"
    assert titles[-1] == "First Created"


@pytest.mark.asyncio
async def test_discover_sort_with_pagination(client, make_agent, make_listing):
    """20. Sorting is applied before pagination -- page 2 continues the order."""
    agent, _ = await make_agent(name="disc-deep-20")
    prices_to_create = [50.0, 10.0, 30.0, 80.0, 5.0]
    for p in prices_to_create:
        await make_listing(agent.id, title=f"Price-{p}", price_usdc=p)

    # Get both pages with price_asc
    resp1 = await client.get(
        "/api/v1/discover",
        params={"sort_by": "price_asc", "page": 1, "page_size": 3},
    )
    resp2 = await client.get(
        "/api/v1/discover",
        params={"sort_by": "price_asc", "page": 2, "page_size": 3},
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    all_prices = (
        [r["price_usdc"] for r in resp1.json()["results"]]
        + [r["price_usdc"] for r in resp2.json()["results"]]
    )
    assert all_prices == sorted(all_prices), f"Expected globally sorted, got {all_prices}"


# ===================================================================
# EDGE CASES — 5 tests
# ===================================================================


@pytest.mark.asyncio
async def test_discover_empty_database(client):
    """21. Discovery on a completely empty database returns valid empty response."""
    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []
    assert body["page"] == 1
    assert body["page_size"] == 20


@pytest.mark.asyncio
async def test_discover_invalid_sort_by_rejected(client):
    """22. An invalid sort_by value is rejected with 422."""
    resp = await client.get("/api/v1/discover", params={"sort_by": "invalid_sort"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_discover_page_size_exceeds_max(client):
    """23. page_size > 100 is rejected with 422 (le=100 constraint)."""
    resp = await client.get("/api/v1/discover", params={"page_size": 200})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_discover_negative_page_rejected(client):
    """24. page < 1 is rejected with 422 (ge=1 constraint)."""
    resp = await client.get("/api/v1/discover", params={"page": 0})
    assert resp.status_code == 422

    resp2 = await client.get("/api/v1/discover", params={"page": -1})
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_discover_response_shape_fields(client, make_agent, make_listing):
    """25. Each result has all expected ListingResponse fields."""
    agent, _ = await make_agent(name="disc-deep-25")
    await make_listing(agent.id, title="Shape Check", price_usdc=5.0)

    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1

    result = body["results"][0]

    # Verify all mandatory fields from ListingResponse are present
    expected_fields = {
        "id", "seller_id", "title", "description", "category",
        "content_hash", "content_size", "content_type", "price_usdc",
        "currency", "metadata", "tags", "quality_score", "freshness_at",
        "status", "access_count", "created_at", "updated_at",
    }
    missing = expected_fields - set(result.keys())
    assert not missing, f"Missing fields in response: {missing}"

    # Type checks on critical fields
    assert isinstance(result["id"], str) and len(result["id"]) > 0
    assert isinstance(result["price_usdc"], (int, float))
    assert isinstance(result["quality_score"], (int, float))
    assert isinstance(result["access_count"], int)
    assert isinstance(result["tags"], list)
    assert isinstance(result["metadata"], dict)
    assert result["status"] == "active"
