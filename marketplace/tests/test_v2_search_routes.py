"""Tests for marketplace/api/v2_search.py -- Search V2 API routes.

The search service wraps Azure AI Search (an external dependency), so we mock
``get_search_service`` and the ``sync_*_index`` helpers.  All HTTP calls still
flow through the real FastAPI stack via the ``client`` fixture.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_search_service(
    results: list[dict] | None = None,
    count: int = 0,
    facets: dict | None = None,
) -> MagicMock:
    """Build a mock SearchV2Service that returns deterministic data."""
    svc = MagicMock()
    default = {
        "results": results or [],
        "count": count,
        "facets": facets or {},
    }
    svc.search_listings.return_value = default
    svc.search_agents.return_value = default
    svc.search_tools.return_value = default
    svc.ensure_indexes.return_value = {}
    return svc


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


SEARCH_PREFIX = "/api/v2/search"


# ---------------------------------------------------------------------------
# GET /api/v2/search -- unified search_all
# ---------------------------------------------------------------------------

async def test_search_all_listings_default(client):
    """Default search with type=listing returns SearchResult shape."""
    svc = _mock_search_service(
        results=[{"id": "l1", "title": "Python Dataset"}],
        count=1,
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(f"{SEARCH_PREFIX}", params={"q": "python"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert len(body["results"]) == 1
    assert body["results"][0]["title"] == "Python Dataset"
    svc.search_listings.assert_called_once()


async def test_search_all_agents(client):
    """search_all with type=agent delegates to search_agents."""
    svc = _mock_search_service(
        results=[{"id": "a1", "name": "TestAgent"}],
        count=1,
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}", params={"q": "test", "type": "agent"}
        )
    assert resp.status_code == 200
    svc.search_agents.assert_called_once()


async def test_search_all_tools(client):
    """search_all with type=tool delegates to search_tools."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}", params={"q": "scraper", "type": "tool"}
        )
    assert resp.status_code == 200
    svc.search_tools.assert_called_once()


async def test_search_all_invalid_type(client):
    """search_all rejects unknown entity types with 400."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}", params={"q": "x", "type": "invalid"}
        )
    assert resp.status_code == 400
    assert "Invalid type" in resp.json()["detail"]


async def test_search_all_invalid_sort_field(client):
    """search_all rejects sort fields not in the whitelist."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}", params={"q": "x", "sort_by": "malicious_field"}
        )
    assert resp.status_code == 400
    assert "Invalid sort field" in resp.json()["detail"]


async def test_search_all_valid_sort_field(client):
    """search_all accepts sort fields in the whitelist."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}", params={"q": "x", "sort_by": "price_usd"}
        )
    assert resp.status_code == 200


async def test_search_all_with_category_filter(client):
    """search_all passes category filter through to search service."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}",
            params={"q": "data", "category": "web_search"},
        )
    assert resp.status_code == 200
    call_kwargs = svc.search_listings.call_args
    assert "web_search" in call_kwargs.kwargs.get("filters", "")


async def test_search_all_with_price_range(client):
    """search_all passes price range filters for listing type."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}",
            params={"q": "", "min_price": 1.0, "max_price": 10.0},
        )
    assert resp.status_code == 200
    call_kwargs = svc.search_listings.call_args
    filters = call_kwargs.kwargs.get("filters", "")
    assert "ge 1.0" in filters
    assert "le 10.0" in filters


async def test_search_all_empty_query(client):
    """search_all with empty query still returns results."""
    svc = _mock_search_service(results=[], count=0)
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(f"{SEARCH_PREFIX}", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


# ---------------------------------------------------------------------------
# GET /api/v2/search/listings
# ---------------------------------------------------------------------------

async def test_search_listings_empty(client):
    """search_listings returns empty result set when nothing matches."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(f"{SEARCH_PREFIX}/listings", params={"q": "nothing"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["count"] == 0


async def test_search_listings_with_facets(client):
    """search_listings returns facets when present."""
    svc = _mock_search_service(
        results=[{"id": "l1", "title": "Test"}],
        count=1,
        facets={"category": [{"value": "web_search", "count": 3}]},
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(f"{SEARCH_PREFIX}/listings", params={"q": "test"})
    assert resp.status_code == 200
    body = resp.json()
    assert "category" in body["facets"]
    assert body["facets"]["category"][0]["value"] == "web_search"


async def test_search_listings_pagination(client):
    """search_listings respects top and skip parameters."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/listings",
            params={"q": "x", "top": 5, "skip": 10},
        )
    assert resp.status_code == 200
    call_kwargs = svc.search_listings.call_args
    assert call_kwargs.kwargs["top"] == 5
    assert call_kwargs.kwargs["skip"] == 10


async def test_search_listings_with_price_filters(client):
    """search_listings passes price range to backend OData filter."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/listings",
            params={"q": "", "min_price": 2.5, "max_price": 50.0, "category": "code_analysis"},
        )
    assert resp.status_code == 200
    call_kwargs = svc.search_listings.call_args
    filters = call_kwargs.kwargs.get("filters", "")
    assert "code_analysis" in filters
    assert "ge 2.5" in filters
    assert "le 50.0" in filters


# ---------------------------------------------------------------------------
# GET /api/v2/search/agents
# ---------------------------------------------------------------------------

async def test_search_agents_basic(client):
    """search_agents returns results for agent queries."""
    svc = _mock_search_service(
        results=[{"id": "a1", "name": "DataBot"}],
        count=1,
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(f"{SEARCH_PREFIX}/agents", params={"q": "data"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


async def test_search_agents_with_type_filter(client):
    """search_agents passes agent_type filter."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/agents",
            params={"q": "", "agent_type": "seller"},
        )
    assert resp.status_code == 200
    call_kwargs = svc.search_agents.call_args
    assert "seller" in call_kwargs.kwargs.get("filters", "")


async def test_search_agents_with_status_filter(client):
    """search_agents passes status filter."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/agents",
            params={"q": "", "status": "active"},
        )
    assert resp.status_code == 200
    call_kwargs = svc.search_agents.call_args
    assert "active" in call_kwargs.kwargs.get("filters", "")


async def test_search_agents_combined_filters(client):
    """search_agents combines agent_type and status filters."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/agents",
            params={"q": "", "agent_type": "buyer", "status": "active"},
        )
    assert resp.status_code == 200
    call_kwargs = svc.search_agents.call_args
    filters = call_kwargs.kwargs.get("filters", "")
    assert "buyer" in filters
    assert "active" in filters


# ---------------------------------------------------------------------------
# GET /api/v2/search/tools
# ---------------------------------------------------------------------------

async def test_search_tools_basic(client):
    """search_tools returns results for tool queries."""
    svc = _mock_search_service(
        results=[{"id": "t1", "name": "WebScraper"}],
        count=1,
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(f"{SEARCH_PREFIX}/tools", params={"q": "scrape"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


async def test_search_tools_with_category(client):
    """search_tools passes category filter."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/tools",
            params={"q": "", "category": "scraping"},
        )
    assert resp.status_code == 200
    call_kwargs = svc.search_tools.call_args
    assert "scraping" in call_kwargs.kwargs.get("filters", "")


# ---------------------------------------------------------------------------
# GET /api/v2/search/suggestions
# ---------------------------------------------------------------------------

async def test_suggestions_listings(client):
    """suggestions for listings returns title-based suggestions."""
    svc = _mock_search_service(
        results=[
            {"title": "Python Tutorial"},
            {"title": "Python Advanced"},
        ],
        count=2,
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/suggestions",
            params={"q": "py", "type": "listing"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "Python Tutorial" in body["suggestions"]
    assert "Python Advanced" in body["suggestions"]


async def test_suggestions_agents(client):
    """suggestions for agents returns name-based suggestions."""
    svc = _mock_search_service(
        results=[{"name": "DataBot"}, {"name": "DataMiner"}],
        count=2,
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/suggestions",
            params={"q": "data", "type": "agent"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "DataBot" in body["suggestions"]


async def test_suggestions_tools(client):
    """suggestions for tools returns name-based suggestions."""
    svc = _mock_search_service(
        results=[{"name": "WebScraper"}],
        count=1,
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/suggestions",
            params={"q": "web", "type": "tool"},
        )
    assert resp.status_code == 200
    assert "WebScraper" in resp.json()["suggestions"]


async def test_suggestions_invalid_type(client):
    """suggestions rejects unknown entity types."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/suggestions",
            params={"q": "x", "type": "bogus"},
        )
    assert resp.status_code == 400
    assert "Invalid type" in resp.json()["detail"]


async def test_suggestions_respects_top_param(client):
    """suggestions passes top limit to the search service."""
    svc = _mock_search_service(
        results=[{"title": "A"}, {"title": "B"}, {"title": "C"}],
        count=3,
    )
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/suggestions",
            params={"q": "test", "type": "listing", "top": 2},
        )
    assert resp.status_code == 200
    # The search service itself was called with top=2
    call_kwargs = svc.search_listings.call_args
    assert call_kwargs.kwargs["top"] == 2


# ---------------------------------------------------------------------------
# POST /api/v2/search/reindex -- admin-only
# ---------------------------------------------------------------------------

async def test_reindex_no_auth_returns_401(client):
    """reindex without auth returns 401."""
    resp = await client.post(f"{SEARCH_PREFIX}/reindex")
    assert resp.status_code in (401, 403, 500)


async def test_reindex_non_admin_returns_403(client, make_creator):
    """reindex by a non-admin creator returns 403."""
    creator, token = await make_creator()
    resp = await client.post(
        f"{SEARCH_PREFIX}/reindex",
        headers=_auth(token),
    )
    assert resp.status_code == 403


async def test_reindex_admin_succeeds(client, make_creator):
    """reindex by an admin creator succeeds."""
    creator, token = await make_creator()
    svc = _mock_search_service()
    svc.ensure_indexes.return_value = {"agentchains-listings": True}

    sync_result = {"synced": 0, "status": "ok"}

    async def _fake_sync(_db):
        return sync_result

    with (
        patch("marketplace.api.v2_search.settings") as mock_settings,
        patch("marketplace.api.v2_search.get_search_service", return_value=svc),
        patch(
            "marketplace.services.search_v2_service.sync_listings_index",
            side_effect=_fake_sync,
        ),
        patch(
            "marketplace.services.search_v2_service.sync_agents_index",
            side_effect=_fake_sync,
        ),
        patch(
            "marketplace.services.search_v2_service.sync_tools_index",
            side_effect=_fake_sync,
        ),
    ):
        mock_settings.admin_creator_ids = creator.id
        resp = await client.post(
            f"{SEARCH_PREFIX}/reindex",
            headers=_auth(token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert "documents_indexed" in body
    assert "indexes_created" in body


# ---------------------------------------------------------------------------
# OData sanitization
# ---------------------------------------------------------------------------

async def test_odata_injection_single_quote_rejected(client):
    """Category filter with single quote is rejected (OData injection prevention)."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}",
            params={"q": "x", "category": "web'search"},
        )
    assert resp.status_code == 400
    assert "single quotes" in resp.json()["detail"]


async def test_odata_injection_keyword_rejected(client):
    """Category filter containing OData keyword is rejected."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}",
            params={"q": "x", "category": "web eq true"},
        )
    assert resp.status_code == 400
    assert "reserved keyword" in resp.json()["detail"]


async def test_odata_injection_agent_type_single_quote(client):
    """Agent type filter with single quote is rejected."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/agents",
            params={"q": "", "agent_type": "sell'er"},
        )
    assert resp.status_code == 400
    assert "single quotes" in resp.json()["detail"]


async def test_odata_injection_status_keyword(client):
    """Status filter containing OData keyword is rejected."""
    svc = _mock_search_service()
    with patch("marketplace.api.v2_search.get_search_service", return_value=svc):
        resp = await client.get(
            f"{SEARCH_PREFIX}/agents",
            params={"q": "", "status": "active or 1"},
        )
    assert resp.status_code == 400
    assert "reserved keyword" in resp.json()["detail"]
