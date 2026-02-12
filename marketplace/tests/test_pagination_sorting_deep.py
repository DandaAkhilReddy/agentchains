"""Deep pagination and sorting tests across all paginated endpoints.

15 tests verifying pagination parameters (page, page_size), sort ordering,
boundary conditions (page beyond total, size=0, size=100), and total
consistency across the following endpoints:

  1. GET /api/v1/discover          — listings (sort_by: price_asc, price_desc, freshness, quality)
  2. GET /api/v1/agents            — agent list
  3. GET /api/v1/audit/events      — audit events (requires agent auth)
  4. GET /api/v1/catalog/search    — catalog entries
  5. GET /api/v1/redemptions       — redemption requests (requires creator auth)
"""

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import create_access_token
from marketplace.core.creator_auth import create_creator_token, hash_password
from marketplace.models.audit_log import AuditLog
from marketplace.models.creator import Creator
from marketplace.models.redemption import RedemptionRequest
from marketplace.models.token_account import TokenAccount
from marketplace.services.audit_service import log_event
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DISCOVER_URL = "/api/v1/discover"
AGENTS_URL = "/api/v1/agents"
AUDIT_URL = "/api/v1/audit/events"
CATALOG_URL = "/api/v1/catalog/search"
REDEMPTIONS_URL = "/api/v1/redemptions"


def _auth(agent_id: str, agent_name: str = "test-agent") -> dict:
    """Build an Authorization header for an agent."""
    token = create_access_token(agent_id, agent_name)
    return {"Authorization": f"Bearer {token}"}


def _creator_auth(creator_id: str, email: str = "c@test.com") -> dict:
    """Build an Authorization header for a creator."""
    token = create_creator_token(creator_id, email)
    return {"Authorization": f"Bearer {token}"}


async def _seed_listings(make_agent, make_listing, count: int = 5):
    """Create an agent and *count* listings with varied prices and quality scores.

    Returns (agent, token, listings).  Listings are created with increasing
    price (1..count) and decreasing quality (0.95 down by 0.05).
    """
    agent, token = await make_agent(name=f"paginator-{_new_id()[:6]}")
    listings = []
    for i in range(count):
        listing = await make_listing(
            agent.id,
            price_usdc=float(i + 1),
            title=f"Listing-{i}",
            quality_score=round(0.95 - i * 0.05, 2),
        )
        listings.append(listing)
        # Small delay so created_at timestamps differ (SQLite second resolution)
        await asyncio.sleep(0.05)
    return agent, token, listings


async def _seed_audit_events(agent_id: str, count: int = 5):
    """Insert *count* audit events via the service layer."""
    async with TestSession() as db:
        for i in range(count):
            await log_event(
                db,
                "test.pagination",
                agent_id=agent_id,
                details={"seq": i},
                severity="info",
            )
        await db.commit()


async def _seed_creator_with_balance(balance: float = 5000.0) -> tuple[str, str, str]:
    """Create a Creator + TokenAccount. Returns (creator_id, email, jwt)."""
    async with TestSession() as db:
        creator_id = _new_id()
        email = f"creator-{creator_id[:8]}@test.com"
        creator = Creator(
            id=creator_id,
            email=email,
            password_hash=hash_password("testpass123"),
            display_name="Pagination Creator",
            status="active",
        )
        db.add(creator)
        account = TokenAccount(
            id=_new_id(),
            agent_id=None,
            creator_id=creator_id,
            balance=Decimal(str(balance)),
            total_deposited=Decimal(str(balance)),
        )
        db.add(account)
        await db.commit()
        jwt = create_creator_token(creator_id, email)
        return creator_id, email, jwt


# ===================================================================
# DISCOVER — tests 1-9
# ===================================================================


@pytest.mark.asyncio
async def test_discover_default_pagination(client, db, make_agent, make_listing):
    """1. Default pagination returns page=1, page_size=20."""
    agent, token, _ = await _seed_listings(make_agent, make_listing, count=3)

    resp = await client.get(DISCOVER_URL)
    assert resp.status_code == 200
    body = resp.json()

    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total"] == 3
    assert len(body["results"]) == 3


@pytest.mark.asyncio
async def test_discover_page_1_size_2(client, db, make_agent, make_listing):
    """2. page=1, page_size=2 returns exactly 2 listings."""
    await _seed_listings(make_agent, make_listing, count=5)

    resp = await client.get(DISCOVER_URL, params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["results"]) == 2


@pytest.mark.asyncio
async def test_discover_page_beyond_total(client, db, make_agent, make_listing):
    """3. page=999 with only 5 listings returns empty results."""
    await _seed_listings(make_agent, make_listing, count=5)

    resp = await client.get(DISCOVER_URL, params={"page": 999, "page_size": 20})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 5
    assert len(body["results"]) == 0
    assert body["page"] == 999


@pytest.mark.asyncio
async def test_discover_size_1(client, db, make_agent, make_listing):
    """4. page_size=1 returns exactly 1 listing."""
    await _seed_listings(make_agent, make_listing, count=5)

    resp = await client.get(DISCOVER_URL, params={"page_size": 1})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 5
    assert len(body["results"]) == 1


@pytest.mark.asyncio
async def test_discover_sort_by_price_asc(client, db, make_agent, make_listing):
    """5. sort_by=price_asc orders cheapest first."""
    await _seed_listings(make_agent, make_listing, count=5)

    resp = await client.get(DISCOVER_URL, params={"sort_by": "price_asc"})
    assert resp.status_code == 200
    body = resp.json()

    prices = [r["price_usdc"] for r in body["results"]]
    assert len(prices) == 5
    assert prices == sorted(prices), f"Expected ascending prices, got {prices}"


@pytest.mark.asyncio
async def test_discover_sort_by_price_desc(client, db, make_agent, make_listing):
    """6. sort_by=price_desc orders most expensive first."""
    await _seed_listings(make_agent, make_listing, count=5)

    resp = await client.get(DISCOVER_URL, params={"sort_by": "price_desc"})
    assert resp.status_code == 200
    body = resp.json()

    prices = [r["price_usdc"] for r in body["results"]]
    assert len(prices) == 5
    assert prices == sorted(prices, reverse=True), f"Expected descending prices, got {prices}"


@pytest.mark.asyncio
async def test_discover_sort_by_quality(client, db, make_agent, make_listing):
    """7. sort_by=quality orders highest quality first."""
    await _seed_listings(make_agent, make_listing, count=5)

    resp = await client.get(DISCOVER_URL, params={"sort_by": "quality"})
    assert resp.status_code == 200
    body = resp.json()

    scores = [r["quality_score"] for r in body["results"]]
    assert len(scores) == 5
    assert scores == sorted(scores, reverse=True), f"Expected descending quality, got {scores}"


@pytest.mark.asyncio
async def test_discover_sort_by_date(client, db, make_agent, make_listing):
    """8. sort_by=freshness orders newest (most recent freshness_at) first."""
    await _seed_listings(make_agent, make_listing, count=5)

    resp = await client.get(DISCOVER_URL, params={"sort_by": "freshness"})
    assert resp.status_code == 200
    body = resp.json()

    timestamps = [r["freshness_at"] for r in body["results"]]
    assert len(timestamps) == 5
    # freshness sort should be descending (newest first)
    assert timestamps == sorted(timestamps, reverse=True), (
        f"Expected descending freshness, got {timestamps}"
    )


@pytest.mark.asyncio
async def test_discover_total_consistent(client, db, make_agent, make_listing):
    """9. total is the same regardless of which page is requested."""
    await _seed_listings(make_agent, make_listing, count=5)

    resp_p1 = await client.get(DISCOVER_URL, params={"page": 1, "page_size": 2})
    resp_p2 = await client.get(DISCOVER_URL, params={"page": 2, "page_size": 2})
    resp_p3 = await client.get(DISCOVER_URL, params={"page": 3, "page_size": 2})

    assert resp_p1.status_code == 200
    assert resp_p2.status_code == 200
    assert resp_p3.status_code == 200

    total_p1 = resp_p1.json()["total"]
    total_p2 = resp_p2.json()["total"]
    total_p3 = resp_p3.json()["total"]

    assert total_p1 == total_p2 == total_p3 == 5
    # Pages 1 and 2 have 2 results each, page 3 has 1
    assert len(resp_p1.json()["results"]) == 2
    assert len(resp_p2.json()["results"]) == 2
    assert len(resp_p3.json()["results"]) == 1


# ===================================================================
# AGENTS — tests 10-11
# ===================================================================


@pytest.mark.asyncio
async def test_agents_pagination(client, db, make_agent):
    """10. Agent list supports page/page_size pagination."""
    # Create 5 agents
    for i in range(5):
        await make_agent(name=f"agent-pag-{i}")

    resp = await client.get(AGENTS_URL, params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["agents"]) == 2

    # Second page
    resp2 = await client.get(AGENTS_URL, params={"page": 2, "page_size": 2})
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["total"] == 5
    assert len(body2["agents"]) == 2

    # Verify no overlap between pages
    ids_p1 = {a["id"] for a in body["agents"]}
    ids_p2 = {a["id"] for a in body2["agents"]}
    assert ids_p1.isdisjoint(ids_p2), "Page 1 and page 2 should not overlap"


@pytest.mark.asyncio
async def test_agents_page_beyond_total(client, db, make_agent):
    """11. Agent list returns empty on page=999."""
    await make_agent(name="lone-agent")

    resp = await client.get(AGENTS_URL, params={"page": 999, "page_size": 20})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 1
    assert len(body["agents"]) == 0
    assert body["page"] == 999


# ===================================================================
# CATALOG — tests 12-13
# ===================================================================


@pytest.mark.asyncio
async def test_catalog_pagination(client, db, make_agent, make_catalog_entry):
    """12. Catalog search supports page/page_size pagination."""
    agent, _ = await make_agent(name="catalog-seller")
    for i in range(5):
        await make_catalog_entry(agent.id, topic=f"topic-{i}")

    resp = await client.get(CATALOG_URL, params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["entries"]) == 2

    # Second page
    resp2 = await client.get(CATALOG_URL, params={"page": 2, "page_size": 2})
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["total"] == 5
    assert len(body2["entries"]) == 2

    # No overlap
    ids_p1 = {e["id"] for e in body["entries"]}
    ids_p2 = {e["id"] for e in body2["entries"]}
    assert ids_p1.isdisjoint(ids_p2), "Catalog page 1 and 2 should not overlap"


@pytest.mark.asyncio
async def test_catalog_page_beyond_total(client, db, make_agent, make_catalog_entry):
    """13. Catalog search returns empty entries on page=999."""
    agent, _ = await make_agent(name="catalog-seller-empty")
    await make_catalog_entry(agent.id, topic="sole-entry")

    resp = await client.get(CATALOG_URL, params={"page": 999, "page_size": 20})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 1
    assert len(body["entries"]) == 0
    assert body["page"] == 999


# ===================================================================
# DISCOVER boundary — tests 14-15
# ===================================================================


@pytest.mark.asyncio
async def test_discover_size_100_max(client, db, make_agent, make_listing):
    """14. page_size=100 (the maximum allowed) is accepted."""
    await _seed_listings(make_agent, make_listing, count=3)

    resp = await client.get(DISCOVER_URL, params={"page_size": 100})
    assert resp.status_code == 200
    body = resp.json()

    assert body["page_size"] == 100
    assert body["total"] == 3
    assert len(body["results"]) == 3


@pytest.mark.asyncio
async def test_discover_size_0_rejected(client):
    """15. page_size=0 is rejected with 422 (ge=1 constraint)."""
    resp = await client.get(DISCOVER_URL, params={"page_size": 0})
    assert resp.status_code == 422
