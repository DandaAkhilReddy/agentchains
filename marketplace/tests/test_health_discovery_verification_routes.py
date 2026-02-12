"""Integration tests for /api/v1/health, /api/v1/discover, and /api/v1/verify routes.

20 async integration tests exercising the health, discovery, and verification
HTTP endpoints via the ``client`` fixture (httpx AsyncClient with ASGI transport).
"""

import hashlib
import uuid

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


def _sha256(text: str) -> str:
    """Return a prefixed sha256 hash for the given text."""
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


# ===================================================================
# HEALTH — 5 tests
# ===================================================================


@pytest.mark.asyncio
async def test_health_basic(client):
    """1. GET /api/v1/health returns 200 with status 'healthy'."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_includes_counts(client):
    """2. Health response contains agents_count and listings_count fields."""
    resp = await client.get("/api/v1/health")
    body = resp.json()
    assert "agents_count" in body
    assert "listings_count" in body
    # Counts are integers >= 0
    assert isinstance(body["agents_count"], int)
    assert isinstance(body["listings_count"], int)
    assert body["agents_count"] >= 0
    assert body["listings_count"] >= 0


@pytest.mark.asyncio
async def test_health_includes_cache_stats(client):
    """3. Health response includes cache_stats with sub-keys."""
    resp = await client.get("/api/v1/health")
    body = resp.json()
    assert "cache_stats" in body
    stats = body["cache_stats"]
    assert "listings" in stats
    assert "content" in stats
    assert "agents" in stats


@pytest.mark.asyncio
async def test_health_includes_version(client):
    """4. Health response includes a version field."""
    resp = await client.get("/api/v1/health")
    body = resp.json()
    assert "version" in body
    assert isinstance(body["version"], str)
    assert len(body["version"]) > 0


@pytest.mark.asyncio
async def test_health_cors_headers(client):
    """5. Response includes CORS Access-Control-Allow-Origin header."""
    resp = await client.get("/api/v1/health", headers={"Origin": "http://example.com"})
    # CORSMiddleware with allow_origins=["*"] reflects the origin or sets "*"
    assert resp.status_code == 200
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin is not None


# ===================================================================
# DISCOVERY — 10 tests
# ===================================================================


@pytest.mark.asyncio
async def test_discover_empty(client):
    """6. GET /api/v1/discover returns empty list when no listings exist."""
    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []


@pytest.mark.asyncio
async def test_discover_returns_listings(client, db, make_agent, make_listing):
    """7. Discover returns listings after creation."""
    agent, _token = await make_agent(name="seller-disc-7")
    await make_listing(agent.id, price_usdc=5.0, title="Alpha Data")
    await make_listing(agent.id, price_usdc=10.0, title="Beta Data")

    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["results"]) == 2


@pytest.mark.asyncio
async def test_discover_search_query(client, db, make_agent, make_listing):
    """8. ?q=keyword filters results by title/description/tags."""
    agent, _ = await make_agent(name="seller-disc-8")
    await make_listing(agent.id, title="Python Tutorial")
    await make_listing(agent.id, title="Rust Handbook")

    resp = await client.get("/api/v1/discover", params={"q": "Python"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert "Python" in body["results"][0]["title"]


@pytest.mark.asyncio
async def test_discover_filter_category(client, db, make_agent, make_listing):
    """9. ?category=web_search filters by category (adapted from agent_type filter)."""
    agent, _ = await make_agent(name="seller-disc-9")
    await make_listing(agent.id, title="Web result", category="web_search")
    await make_listing(agent.id, title="Code result", category="code_analysis")

    resp = await client.get("/api/v1/discover", params={"category": "web_search"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["category"] == "web_search"


@pytest.mark.asyncio
async def test_discover_filter_seller(client, db, make_agent, make_listing):
    """10. ?seller_id=<id> filters by seller (adapted from status filter)."""
    agent_a, _ = await make_agent(name="seller-disc-10a")
    agent_b, _ = await make_agent(name="seller-disc-10b")
    await make_listing(agent_a.id, title="Agent A listing")
    await make_listing(agent_b.id, title="Agent B listing")

    resp = await client.get("/api/v1/discover", params={"seller_id": agent_a.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["seller_id"] == agent_a.id


@pytest.mark.asyncio
async def test_discover_sort_price_asc(client, db, make_agent, make_listing):
    """11. ?sort_by=price_asc orders results cheapest first."""
    agent, _ = await make_agent(name="seller-disc-11")
    await make_listing(agent.id, price_usdc=50.0, title="Expensive")
    await make_listing(agent.id, price_usdc=5.0, title="Cheap")
    await make_listing(agent.id, price_usdc=25.0, title="Mid")

    resp = await client.get("/api/v1/discover", params={"sort_by": "price_asc"})
    assert resp.status_code == 200
    prices = [r["price_usdc"] for r in resp.json()["results"]]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_discover_sort_price_desc(client, db, make_agent, make_listing):
    """12. ?sort_by=price_desc orders results most expensive first."""
    agent, _ = await make_agent(name="seller-disc-12")
    await make_listing(agent.id, price_usdc=5.0, title="Cheap")
    await make_listing(agent.id, price_usdc=50.0, title="Expensive")
    await make_listing(agent.id, price_usdc=25.0, title="Mid")

    resp = await client.get("/api/v1/discover", params={"sort_by": "price_desc"})
    assert resp.status_code == 200
    prices = [r["price_usdc"] for r in resp.json()["results"]]
    assert prices == sorted(prices, reverse=True)


@pytest.mark.asyncio
async def test_discover_pagination_page_size(client, db, make_agent, make_listing):
    """13. ?page=1&page_size=2 limits results to 2 per page."""
    agent, _ = await make_agent(name="seller-disc-13")
    for i in range(5):
        await make_listing(agent.id, price_usdc=float(i + 1), title=f"Item {i}")

    resp = await client.get("/api/v1/discover", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["results"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2


@pytest.mark.asyncio
async def test_discover_pagination_page_2(client, db, make_agent, make_listing):
    """14. Page 2 returns remaining items."""
    agent, _ = await make_agent(name="seller-disc-14")
    for i in range(5):
        await make_listing(agent.id, price_usdc=float(i + 1), title=f"Item {i}")

    resp = await client.get("/api/v1/discover", params={"page": 2, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["results"]) == 2  # items 3 and 4
    assert body["page"] == 2


@pytest.mark.asyncio
async def test_discover_min_max_price(client, db, make_agent, make_listing):
    """15. ?min_price=10&max_price=50 filters by price range."""
    agent, _ = await make_agent(name="seller-disc-15")
    await make_listing(agent.id, price_usdc=5.0, title="Too cheap")
    await make_listing(agent.id, price_usdc=25.0, title="In range A")
    await make_listing(agent.id, price_usdc=40.0, title="In range B")
    await make_listing(agent.id, price_usdc=100.0, title="Too expensive")

    resp = await client.get("/api/v1/discover", params={"min_price": 10, "max_price": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    for r in body["results"]:
        assert 10 <= r["price_usdc"] <= 50


# ===================================================================
# VERIFICATION — 5 tests
# ===================================================================


@pytest.mark.asyncio
async def test_verify_matching_content(client, db, make_agent, make_listing, make_transaction):
    """16. POST /api/v1/verify with correct hash returns verified=true."""
    agent, _ = await make_agent(name="seller-ver-16")
    buyer, _ = await make_agent(name="buyer-ver-16")
    listing = await make_listing(agent.id, price_usdc=1.0)
    tx = await make_transaction(buyer.id, agent.id, listing.id)

    content_text = "hello world"
    expected_hash = _sha256(content_text)

    resp = await client.post("/api/v1/verify", json={
        "transaction_id": tx.id,
        "content": content_text,
        "expected_hash": expected_hash,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True


@pytest.mark.asyncio
async def test_verify_mismatching_content(client, db, make_agent, make_listing, make_transaction):
    """17. POST /api/v1/verify with wrong hash returns verified=false."""
    agent, _ = await make_agent(name="seller-ver-17")
    buyer, _ = await make_agent(name="buyer-ver-17")
    listing = await make_listing(agent.id, price_usdc=1.0)
    tx = await make_transaction(buyer.id, agent.id, listing.id)

    content_text = "hello world"
    wrong_hash = _sha256("totally different content")

    resp = await client.post("/api/v1/verify", json={
        "transaction_id": tx.id,
        "content": content_text,
        "expected_hash": wrong_hash,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False


@pytest.mark.asyncio
async def test_verify_missing_fields(client):
    """18. POST /api/v1/verify with missing required fields returns 422."""
    # Missing transaction_id, content, expected_hash
    resp = await client.post("/api/v1/verify", json={})
    assert resp.status_code == 422

    # Partial — missing content and expected_hash
    resp2 = await client.post("/api/v1/verify", json={"transaction_id": "abc"})
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_verify_returns_hashes(client, db, make_agent, make_listing, make_transaction):
    """19. Verification response includes expected_hash and actual_hash."""
    agent, _ = await make_agent(name="seller-ver-19")
    buyer, _ = await make_agent(name="buyer-ver-19")
    listing = await make_listing(agent.id, price_usdc=1.0)
    tx = await make_transaction(buyer.id, agent.id, listing.id)

    content_text = "verification data"
    expected_hash = _sha256(content_text)

    resp = await client.post("/api/v1/verify", json={
        "transaction_id": tx.id,
        "content": content_text,
        "expected_hash": expected_hash,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "expected_hash" in body
    assert "actual_hash" in body
    assert body["expected_hash"] == expected_hash
    assert body["actual_hash"] == expected_hash  # matching content => same hash
    assert body["transaction_id"] == tx.id


@pytest.mark.asyncio
async def test_verify_creates_record(client, db, make_agent, make_listing, make_transaction):
    """20. Verification persists a VerificationRecord to the database."""
    from marketplace.models.verification import VerificationRecord
    from sqlalchemy import select

    agent, _ = await make_agent(name="seller-ver-20")
    buyer, _ = await make_agent(name="buyer-ver-20")
    listing = await make_listing(agent.id, price_usdc=1.0)
    tx = await make_transaction(buyer.id, agent.id, listing.id)

    content_text = "persisted verification"
    expected_hash = _sha256(content_text)

    resp = await client.post("/api/v1/verify", json={
        "transaction_id": tx.id,
        "content": content_text,
        "expected_hash": expected_hash,
    })
    assert resp.status_code == 200

    # Query the DB through a fresh session to confirm persistence
    from marketplace.tests.conftest import TestSession
    async with TestSession() as fresh_db:
        result = await fresh_db.execute(
            select(VerificationRecord).where(
                VerificationRecord.transaction_id == tx.id
            )
        )
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.expected_hash == expected_hash
        assert record.actual_hash == expected_hash
        assert record.matches == 1
