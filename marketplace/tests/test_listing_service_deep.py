"""Deep listing service coverage — 20 tests for discover() filters, sorting,
cache interactions, content/metadata, and combined filters.

Tests mix direct service-layer calls (via ``listing_service.discover``) with
HTTP-level assertions (via ``client.get("/api/v1/discover", ...)``) depending
on what each test is exercising.

All tests are async, self-contained, and rely on the shared conftest fixtures
(``db``, ``client``, ``make_agent``, ``make_listing``).
"""

import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.listing import DataListing
from marketplace.schemas.listing import ListingCreateRequest, ListingUpdateRequest
from marketplace.services import listing_service
from marketplace.services.cache_service import listing_cache


# ---------------------------------------------------------------------------
# Helper: seed listings via create_listing (lightweight, uses service layer)
# ---------------------------------------------------------------------------

async def _seed_listing(db, agent_id, **overrides):
    """Create a listing through the service layer with sensible defaults."""
    defaults = dict(
        title="Untitled",
        description="",
        category="web_search",
        content="seed-content",
        price_usdc=1.0,
        metadata={},
        tags=[],
        quality_score=0.5,
    )
    defaults.update(overrides)
    req = ListingCreateRequest(**defaults)
    return await listing_service.create_listing(db, agent_id, req)


# ===================================================================
# discover() filters (5 tests)
# ===================================================================


async def test_discover_filter_by_min_price(db: AsyncSession, make_agent):
    """3 listings at $1, $5, $10; min_price=5 returns the 2 that are >= 5."""
    agent, _ = await make_agent()

    await _seed_listing(db, agent.id, title="Cheap",    price_usdc=1.0)
    await _seed_listing(db, agent.id, title="Mid",      price_usdc=5.0)
    await _seed_listing(db, agent.id, title="Expensive", price_usdc=10.0)

    listings, total = await listing_service.discover(db, min_price=5.0)

    assert total == 2
    prices = sorted(float(l.price_usdc) for l in listings)
    assert prices == [5.0, 10.0]


async def test_discover_filter_by_max_price(db: AsyncSession, make_agent):
    """3 listings at $1, $5, $10; max_price=5 returns the 2 that are <= 5."""
    agent, _ = await make_agent()

    await _seed_listing(db, agent.id, title="Cheap",    price_usdc=1.0)
    await _seed_listing(db, agent.id, title="Mid",      price_usdc=5.0)
    await _seed_listing(db, agent.id, title="Expensive", price_usdc=10.0)

    listings, total = await listing_service.discover(db, max_price=5.0)

    assert total == 2
    prices = sorted(float(l.price_usdc) for l in listings)
    assert prices == [1.0, 5.0]


async def test_discover_filter_by_price_range(db: AsyncSession, make_agent):
    """min_price=3, max_price=7 returns only the $5 listing."""
    agent, _ = await make_agent()

    await _seed_listing(db, agent.id, title="Cheap",    price_usdc=1.0)
    await _seed_listing(db, agent.id, title="Mid",      price_usdc=5.0)
    await _seed_listing(db, agent.id, title="Expensive", price_usdc=10.0)

    listings, total = await listing_service.discover(db, min_price=3.0, max_price=7.0)

    assert total == 1
    assert float(listings[0].price_usdc) == 5.0
    assert listings[0].title == "Mid"


async def test_discover_filter_by_min_quality(db: AsyncSession, make_agent):
    """Listings with quality 0.3, 0.6, 0.9; min_quality=0.5 returns 2."""
    agent, _ = await make_agent()

    await _seed_listing(db, agent.id, title="Low",  quality_score=0.3)
    await _seed_listing(db, agent.id, title="Med",  quality_score=0.6)
    await _seed_listing(db, agent.id, title="High", quality_score=0.9)

    listings, total = await listing_service.discover(db, min_quality=0.5)

    assert total == 2
    scores = sorted(float(l.quality_score) for l in listings)
    assert scores == [0.6, 0.9]


async def test_discover_filter_by_category(db: AsyncSession, make_agent):
    """Listings in 2 categories; filter returns only matching category."""
    agent, _ = await make_agent()

    await _seed_listing(db, agent.id, title="Web 1", category="web_search")
    await _seed_listing(db, agent.id, title="Web 2", category="web_search")
    await _seed_listing(db, agent.id, title="Code",  category="code_analysis")

    listings, total = await listing_service.discover(db, category="code_analysis")

    assert total == 1
    assert listings[0].title == "Code"
    assert listings[0].category == "code_analysis"


# ===================================================================
# discover() sorting (4 tests)
# ===================================================================


async def test_discover_sort_by_price_asc(db: AsyncSession, make_agent):
    """Results ordered by price ascending."""
    agent, _ = await make_agent()

    for price in [7.0, 2.0, 9.0, 4.0]:
        await _seed_listing(db, agent.id, title=f"P{price}", price_usdc=price)

    listings, total = await listing_service.discover(db, sort_by="price_asc")

    assert total == 4
    prices = [float(l.price_usdc) for l in listings]
    assert prices == [2.0, 4.0, 7.0, 9.0]


async def test_discover_sort_by_price_desc(db: AsyncSession, make_agent):
    """Results ordered by price descending."""
    agent, _ = await make_agent()

    for price in [7.0, 2.0, 9.0, 4.0]:
        await _seed_listing(db, agent.id, title=f"P{price}", price_usdc=price)

    listings, total = await listing_service.discover(db, sort_by="price_desc")

    assert total == 4
    prices = [float(l.price_usdc) for l in listings]
    assert prices == [9.0, 7.0, 4.0, 2.0]


async def test_discover_sort_by_quality(db: AsyncSession, make_agent):
    """Results ordered by quality descending."""
    agent, _ = await make_agent()

    for q in [0.4, 0.95, 0.1, 0.7]:
        await _seed_listing(db, agent.id, title=f"Q{q}", quality_score=q)

    listings, total = await listing_service.discover(db, sort_by="quality")

    assert total == 4
    scores = [float(l.quality_score) for l in listings]
    assert scores == [0.95, 0.7, 0.4, 0.1]


async def test_discover_default_sort_freshness(db: AsyncSession, make_agent):
    """Default sort is freshness_at descending (newest first)."""
    agent, _ = await make_agent()

    ids = []
    for i in range(3):
        listing = await _seed_listing(db, agent.id, title=f"Fresh {i}")
        ids.append(listing.id)
        time.sleep(0.02)  # ensure distinct timestamps

    # Default sort (no sort_by parameter)
    listings, total = await listing_service.discover(db)

    assert total == 3
    # Newest first means the last-created listing comes first
    assert listings[0].id == ids[2]
    assert listings[1].id == ids[1]
    assert listings[2].id == ids[0]


# ===================================================================
# discover() text search (3 tests)
# ===================================================================


async def test_discover_search_matches_title(db: AsyncSession, make_agent):
    """q='python' matches 'Python Tutorial' in the title."""
    agent, _ = await make_agent()

    await _seed_listing(db, agent.id, title="Python Tutorial", description="A guide")
    await _seed_listing(db, agent.id, title="JavaScript Basics", description="JS intro")
    await _seed_listing(db, agent.id, title="Rust Handbook", description="Systems lang")

    listings, total = await listing_service.discover(db, q="python")

    assert total == 1
    assert listings[0].title == "Python Tutorial"


async def test_discover_search_case_insensitive(db: AsyncSession, make_agent):
    """q='PYTHON' matches lowercase content via ilike."""
    agent, _ = await make_agent()

    await _seed_listing(db, agent.id, title="python basics", description="lower case python")
    await _seed_listing(db, agent.id, title="Java Course", description="no match here")

    listings, total = await listing_service.discover(db, q="PYTHON")

    assert total == 1
    assert "python" in listings[0].title.lower()


async def test_discover_excludes_delisted(db: AsyncSession, make_agent):
    """Delisted listings do not appear in discover results."""
    agent, _ = await make_agent()

    active = await _seed_listing(db, agent.id, title="Active Listing")
    to_delist = await _seed_listing(db, agent.id, title="Doomed Listing")

    # Delist one
    await listing_service.delist(db, to_delist.id, agent.id)

    listings, total = await listing_service.discover(db)

    assert total == 1
    assert listings[0].id == active.id
    assert listings[0].status == "active"


# ===================================================================
# Cache interactions (3 tests)
# ===================================================================


async def test_get_listing_caches_result(db: AsyncSession, make_agent):
    """After get_listing, verify listing_cache has the entry."""
    agent, _ = await make_agent()
    created = await _seed_listing(db, agent.id, title="Cache Me")

    # Clear cache to start fresh (create_listing already caches it)
    listing_cache.clear()
    assert listing_cache.get(f"listing:{created.id}") is None

    # get_listing should populate the cache
    fetched = await listing_service.get_listing(db, created.id)

    cached = listing_cache.get(f"listing:{fetched.id}")
    assert cached is not None
    assert cached.id == fetched.id
    assert cached.title == "Cache Me"


async def test_update_listing_invalidates_cache(db: AsyncSession, make_agent):
    """After update, the cache entry for that listing is gone."""
    agent, _ = await make_agent()
    listing = await _seed_listing(db, agent.id, title="Before Update")

    # Confirm it is cached after creation
    assert listing_cache.get(f"listing:{listing.id}") is not None

    # Update the listing
    update_req = ListingUpdateRequest(title="After Update")
    await listing_service.update_listing(db, listing.id, agent.id, update_req)

    # Cache entry should be invalidated
    assert listing_cache.get(f"listing:{listing.id}") is None


async def test_delist_invalidates_cache(db: AsyncSession, make_agent):
    """After delist, cache entry is gone."""
    agent, _ = await make_agent()
    listing = await _seed_listing(db, agent.id, title="Soon Delisted")

    # Confirm it is cached after creation
    assert listing_cache.get(f"listing:{listing.id}") is not None

    await listing_service.delist(db, listing.id, agent.id)

    # Cache entry should be invalidated
    assert listing_cache.get(f"listing:{listing.id}") is None


# ===================================================================
# Content & metadata (3 tests)
# ===================================================================


async def test_create_listing_stores_metadata(db: AsyncSession, make_agent):
    """Complex metadata dict is preserved in DB as JSON."""
    agent, _ = await make_agent()
    complex_meta = {
        "source": "web_crawler",
        "author": "Deep Researcher",
        "model_used": "gpt-4o",
        "params": {"temperature": 0.7, "max_tokens": 4096},
        "nested": {"level1": {"level2": [1, 2, 3]}},
    }

    listing = await _seed_listing(
        db, agent.id,
        title="Meta Test",
        metadata=complex_meta,
    )

    # Read back from DB
    fetched = await listing_service.get_listing(db, listing.id)
    stored_meta = json.loads(fetched.metadata_json)

    assert stored_meta == complex_meta
    assert stored_meta["params"]["temperature"] == 0.7
    assert stored_meta["nested"]["level1"]["level2"] == [1, 2, 3]


async def test_create_listing_tags_json(db: AsyncSession, make_agent):
    """Tags array is stored and retrieved correctly as JSON."""
    agent, _ = await make_agent()
    tags = ["machine-learning", "nlp", "transformers", "bert", "fine-tuning"]

    listing = await _seed_listing(
        db, agent.id,
        title="Tagged Listing",
        tags=tags,
    )

    fetched = await listing_service.get_listing(db, listing.id)
    stored_tags = json.loads(fetched.tags)

    assert stored_tags == tags
    assert len(stored_tags) == 5
    assert "bert" in stored_tags


async def test_list_listings_pagination(db: AsyncSession, make_agent):
    """15 listings, page=2 size=5 returns 5 items with total=15."""
    agent, _ = await make_agent()

    for i in range(15):
        await _seed_listing(
            db, agent.id,
            title=f"Paginated {i:02d}",
            price_usdc=1.0 + i * 0.1,
        )

    listings, total = await listing_service.list_listings(db, page=2, page_size=5)

    assert total == 15
    assert len(listings) == 5


# ===================================================================
# Combined filters (2 tests)
# ===================================================================


async def test_discover_combined_filters(client, db, make_agent):
    """q + category + min_quality together via the HTTP discover endpoint."""
    agent, _ = await make_agent()

    # Listing 1: matches q="data", category=web_search, quality=0.9
    await _seed_listing(
        db, agent.id,
        title="Data Science Guide",
        category="web_search",
        quality_score=0.9,
    )
    # Listing 2: matches q="data" but wrong category
    await _seed_listing(
        db, agent.id,
        title="Data Engineering",
        category="code_analysis",
        quality_score=0.8,
    )
    # Listing 3: matches category + quality but not q
    await _seed_listing(
        db, agent.id,
        title="Machine Learning",
        category="web_search",
        quality_score=0.95,
    )
    # Listing 4: matches q + category but low quality
    await _seed_listing(
        db, agent.id,
        title="Data Overview",
        category="web_search",
        quality_score=0.3,
    )

    resp = await client.get("/api/v1/discover", params={
        "q": "data",
        "category": "web_search",
        "min_quality": 0.5,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "Data Science Guide"


async def test_discover_empty_results_with_strict_filters(client, db, make_agent):
    """Very strict filters that no listing satisfies yield total=0."""
    agent, _ = await make_agent()

    await _seed_listing(db, agent.id, title="Normal Listing", price_usdc=5.0, quality_score=0.6)
    await _seed_listing(db, agent.id, title="Another Listing", price_usdc=10.0, quality_score=0.8)

    resp = await client.get("/api/v1/discover", params={
        "q": "nonexistent-xyz-term",
        "category": "computation",
        "min_price": 999.0,
        "max_price": 1000.0,
        "min_quality": 0.99,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []
    assert body["page"] == 1
