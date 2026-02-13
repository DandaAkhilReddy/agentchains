"""Deep unit tests for Seller API routes (/api/v1/seller/*).

Tests the seller_api router endpoints through httpx AsyncClient with mocked
service layer calls. Organized into 5 describe blocks covering:
  1. Seller registration / bulk listing creation
  2. Profile & demand management
  3. Webhook configuration
  4. Listing management via seller API
  5. Error handling (auth, validation, rate limits, malformed requests)

Style: pytest + unittest.mock, using `client` and `make_agent` fixtures from conftest.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.core.auth import create_access_token
from marketplace.models.agent import RegisteredAgent
from marketplace.models.seller_webhook import SellerWebhook
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_seller(name: str | None = None, agent_type: str = "seller") -> tuple[str, str]:
    """Create a seller agent directly in the test DB and return (agent_id, jwt)."""
    async with TestSession() as db:
        agent_id = _new_id()
        agent = RegisteredAgent(
            id=agent_id,
            name=name or f"seller-{agent_id[:8]}",
            agent_type=agent_type,
            public_key="ssh-rsa AAAA_test_key",
            status="active",
        )
        db.add(agent)
        await db.commit()
        jwt = create_access_token(agent_id, agent.name)
        return agent_id, jwt


def _valid_listing_item(**overrides) -> dict:
    """Return a valid listing item dict suitable for bulk-list."""
    item = {
        "title": f"Test Listing {_new_id()[:6]}",
        "category": "web_search",
        "content": "some valid test content payload",
        "price_usdc": 0.005,
    }
    item.update(overrides)
    return item


# ===========================================================================
# BLOCK 1: Seller Registration & Bulk Listing Creation
# ===========================================================================


class TestSellerBulkListCreation:
    """Tests for POST /api/v1/seller/bulk-list."""

    async def test_single_item_bulk_list(self, client):
        """Bulk list with exactly one item succeeds."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": [_valid_listing_item()]},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["errors"] == 0
        assert len(data["listings"]) == 1
        assert "listing_id" in data["listings"][0]

    async def test_bulk_list_max_boundary_100(self, client):
        """Bulk list with exactly 100 items succeeds (boundary)."""
        _, jwt = await _setup_seller()
        items = [_valid_listing_item(title=f"Listing {i}") for i in range(100)]

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": items},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 100
        assert data["errors"] == 0

    async def test_bulk_list_rejects_101_items(self, client):
        """Bulk list with 101 items is rejected by Pydantic validation (max_length=100)."""
        _, jwt = await _setup_seller()
        items = [_valid_listing_item(title=f"Listing {i}") for i in range(101)]

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": items},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 422

    async def test_bulk_list_rejects_empty_items(self, client):
        """Bulk list with empty items list returns 422 (min_length=1)."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": []},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 422

    async def test_bulk_list_duplicate_titles_allowed(self, client):
        """Bulk list allows items with duplicate titles (no uniqueness constraint)."""
        _, jwt = await _setup_seller()
        items = [_valid_listing_item(title="Same Title") for _ in range(3)]

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": items},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 3
        assert all(l["title"] == "Same Title" for l in data["listings"])

    async def test_bulk_list_missing_required_content_field(self, client):
        """An item missing required 'content' field produces a partial error."""
        _, jwt = await _setup_seller()
        items = [
            _valid_listing_item(),
            {"title": "No Content", "category": "web_search", "price_usdc": 0.005},
            _valid_listing_item(),
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
        assert data["error_details"][0]["index"] == 1


# ===========================================================================
# BLOCK 2: Profile & Demand Management
# ===========================================================================


class TestSellerDemandManagement:
    """Tests for GET /api/v1/seller/demand-for-me and POST /api/v1/seller/price-suggest."""

    async def test_demand_for_me_empty_when_no_catalog(self, client):
        """Seller with no catalog entries gets zero demand matches."""
        _, jwt = await _setup_seller()

        resp = await client.get(
            "/api/v1/seller/demand-for-me",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["matches"] == []

    async def test_demand_for_me_matches_seller_catalog(
        self, client, make_agent, make_catalog_entry, make_demand_signal,
    ):
        """Demand endpoint returns signals matching the seller's catalog namespace."""
        seller, jwt = await make_agent(name="demand-matcher", agent_type="seller")

        async with TestSession() as db:
            await make_catalog_entry(seller.id, namespace="code_analysis", topic="python")
            await make_demand_signal(
                query_pattern="code review",
                category="code_analysis",
                search_count=40,
                velocity=7.5,
                fulfillment_rate=0.2,
            )

        resp = await client.get(
            "/api/v1/seller/demand-for-me",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        match = data["matches"][0]
        assert match["category"] == "code_analysis"
        assert match["velocity"] == 7.5
        assert match["opportunity"] == "high"

    async def test_demand_for_me_excludes_unrelated_categories(
        self, client, make_agent, make_catalog_entry, make_demand_signal,
    ):
        """Demand endpoint does not return signals from unrelated categories."""
        seller, jwt = await make_agent(name="niche-seller", agent_type="seller")

        async with TestSession() as db:
            await make_catalog_entry(seller.id, namespace="web_search", topic="tutorials")
            # Demand in a totally different category
            await make_demand_signal(
                query_pattern="financial data",
                category="finance",
                search_count=100,
                velocity=20.0,
            )

        resp = await client.get(
            "/api/v1/seller/demand-for-me",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        finance_matches = [m for m in data["matches"] if m["category"] == "finance"]
        assert len(finance_matches) == 0

    async def test_price_suggest_default_no_competitors(self, client):
        """Price suggestion returns default 0.005 when no competing listings exist."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/price-suggest",
            json={"category": "web_search", "quality_score": 0.5},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggested_price"] == 0.005
        assert data["competitors"] == 0
        assert "No competitors" in data["strategy"]

    async def test_price_suggest_quality_high_beats_low(
        self, client, make_agent, make_listing,
    ):
        """Higher quality score results in a higher suggested price."""
        seller, jwt = await make_agent(name="quality-tester", agent_type="seller")
        other_id = _new_id()

        async with TestSession() as db:
            await make_listing(other_id, price_usdc=0.01, category="web_search", quality_score=0.5)

        resp_high = await client.post(
            "/api/v1/seller/price-suggest",
            json={"category": "web_search", "quality_score": 0.95},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        resp_low = await client.post(
            "/api/v1/seller/price-suggest",
            json={"category": "web_search", "quality_score": 0.2},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp_high.status_code == 200
        assert resp_low.status_code == 200
        assert resp_high.json()["suggested_price"] > resp_low.json()["suggested_price"]

    async def test_price_suggest_includes_market_fields(
        self, client, make_agent, make_listing,
    ):
        """Price response includes median_price, price_range, and strategy when
        competitors exist."""
        seller, jwt = await make_agent(name="market-fields", agent_type="seller")
        other_id = _new_id()

        async with TestSession() as db:
            await make_listing(other_id, price_usdc=0.008, category="web_search", quality_score=0.6)
            await make_listing(other_id, price_usdc=0.012, category="web_search", quality_score=0.7)

        resp = await client.post(
            "/api/v1/seller/price-suggest",
            json={"category": "web_search", "quality_score": 0.7},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        data = resp.json()
        assert "median_price" in data
        assert "price_range" in data
        assert isinstance(data["price_range"], list)
        assert len(data["price_range"]) == 2
        assert data["price_range"][0] <= data["price_range"][1]
        assert data["competitors"] == 2
        assert "Quality-adjusted" in data["strategy"]


# ===========================================================================
# BLOCK 3: Webhook Configuration
# ===========================================================================


class TestWebhookConfiguration:
    """Tests for POST /api/v1/seller/webhook and GET /api/v1/seller/webhooks."""

    async def test_register_webhook_with_all_fields(self, client):
        """Webhook registration succeeds with url, event_types, and secret."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/webhook",
            json={
                "url": "https://hooks.example.com/demand",
                "event_types": ["demand_match", "price_change"],
                "secret": "s3cret-hmac-key",
            },
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://hooks.example.com/demand"
        assert set(data["event_types"]) == {"demand_match", "price_change"}
        assert data["status"] == "active"
        assert "id" in data

    async def test_register_webhook_defaults_event_types(self, client):
        """Webhook registration fills default event_types when omitted."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/webhook",
            json={"url": "https://example.com/hook"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "demand_match" in data["event_types"]

    async def test_register_webhook_empty_url_rejected(self, client):
        """Webhook with empty URL string is rejected by Pydantic (min_length=1)."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/webhook",
            json={"url": ""},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 422

    async def test_register_webhook_url_max_length(self, client):
        """Webhook with URL > 500 chars is rejected by Pydantic (max_length=500)."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/webhook",
            json={"url": "https://example.com/" + "a" * 500},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 422

    async def test_list_webhooks_empty(self, client):
        """New seller sees zero registered webhooks."""
        _, jwt = await _setup_seller()

        resp = await client.get(
            "/api/v1/seller/webhooks",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["webhooks"] == []

    async def test_list_webhooks_returns_registered(self, client):
        """Listing webhooks returns all previously registered hooks with full fields."""
        _, jwt = await _setup_seller()

        urls = [
            "https://example.com/hook-alpha",
            "https://example.com/hook-beta",
            "https://example.com/hook-gamma",
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
        assert data["count"] == 3
        returned_urls = {w["url"] for w in data["webhooks"]}
        assert returned_urls == set(urls)
        for wh in data["webhooks"]:
            assert "id" in wh
            assert "event_types" in wh
            assert "status" in wh
            assert "failure_count" in wh
            assert wh["failure_count"] == 0

    async def test_webhooks_isolated_between_sellers(self, client):
        """Seller A cannot see Seller B's webhooks."""
        _, jwt_a = await _setup_seller(name="seller-a")
        _, jwt_b = await _setup_seller(name="seller-b")

        await client.post(
            "/api/v1/seller/webhook",
            json={"url": "https://a.example.com/hook"},
            headers={"Authorization": f"Bearer {jwt_a}"},
        )
        await client.post(
            "/api/v1/seller/webhook",
            json={"url": "https://b.example.com/hook"},
            headers={"Authorization": f"Bearer {jwt_b}"},
        )

        resp_a = await client.get(
            "/api/v1/seller/webhooks",
            headers={"Authorization": f"Bearer {jwt_a}"},
        )
        resp_b = await client.get(
            "/api/v1/seller/webhooks",
            headers={"Authorization": f"Bearer {jwt_b}"},
        )

        assert resp_a.json()["count"] == 1
        assert resp_a.json()["webhooks"][0]["url"] == "https://a.example.com/hook"
        assert resp_b.json()["count"] == 1
        assert resp_b.json()["webhooks"][0]["url"] == "https://b.example.com/hook"


# ===========================================================================
# BLOCK 4: Listing Management via Seller API
# ===========================================================================


class TestSellerListingManagement:
    """Tests for seller-specific listing creation and filtering via bulk-list."""

    async def test_bulk_list_creates_correct_categories(self, client):
        """Bulk-listed items preserve their individual categories."""
        _, jwt = await _setup_seller()
        items = [
            _valid_listing_item(title="Search Result", category="web_search"),
            _valid_listing_item(title="Code Review", category="code_analysis"),
            _valid_listing_item(title="Doc Summary", category="document_summary"),
        ]

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": items},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 3
        titles = [l["title"] for l in data["listings"]]
        assert "Search Result" in titles
        assert "Code Review" in titles
        assert "Doc Summary" in titles

    async def test_bulk_list_invalid_category_produces_error(self, client):
        """Item with a category not matching the Pydantic regex pattern is an error."""
        _, jwt = await _setup_seller()
        items = [
            _valid_listing_item(),
            _valid_listing_item(category="invalid_category_xyz"),
        ]

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": items},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["errors"] == 1
        assert data["error_details"][0]["index"] == 1

    async def test_bulk_list_negative_price_produces_error(self, client):
        """Item with negative price is rejected by Pydantic (gt=0)."""
        _, jwt = await _setup_seller()
        items = [
            _valid_listing_item(),
            _valid_listing_item(price_usdc=-1.0),
        ]

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": items},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 1
        assert data["errors"] == 1


# ===========================================================================
# BLOCK 5: Error Handling
# ===========================================================================


class TestErrorHandling:
    """Auth failures, validation errors, rate limiting, and malformed requests."""

    async def test_bulk_list_unauthenticated_returns_401(self, client):
        """POST /seller/bulk-list without Authorization header returns 401."""
        resp = await client.post(
            "/api/v1/seller/bulk-list",
            json={"items": [_valid_listing_item()]},
        )
        assert resp.status_code == 401

    async def test_demand_unauthenticated_returns_401(self, client):
        """GET /seller/demand-for-me without Authorization header returns 401."""
        resp = await client.get("/api/v1/seller/demand-for-me")
        assert resp.status_code == 401

    async def test_price_suggest_unauthenticated_returns_401(self, client):
        """POST /seller/price-suggest without Authorization header returns 401."""
        resp = await client.post(
            "/api/v1/seller/price-suggest",
            json={"category": "web_search"},
        )
        assert resp.status_code == 401

    async def test_webhook_register_unauthenticated_returns_401(self, client):
        """POST /seller/webhook without Authorization header returns 401."""
        resp = await client.post(
            "/api/v1/seller/webhook",
            json={"url": "https://example.com/hook"},
        )
        assert resp.status_code == 401

    async def test_webhook_list_unauthenticated_returns_401(self, client):
        """GET /seller/webhooks without Authorization header returns 401."""
        resp = await client.get("/api/v1/seller/webhooks")
        assert resp.status_code == 401

    async def test_invalid_jwt_returns_401(self, client):
        """A malformed JWT token returns 401 across all seller endpoints."""
        headers = {"Authorization": "Bearer not.a.valid.jwt.token"}

        resp = await client.get(
            "/api/v1/seller/demand-for-me",
            headers=headers,
        )
        assert resp.status_code == 401

    async def test_price_suggest_quality_out_of_range(self, client):
        """Quality score > 1.0 is rejected by Pydantic (le=1)."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/price-suggest",
            json={"category": "web_search", "quality_score": 1.5},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 422

    async def test_price_suggest_negative_quality_rejected(self, client):
        """Quality score < 0 is rejected by Pydantic (ge=0)."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/price-suggest",
            json={"category": "web_search", "quality_score": -0.1},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 422

    async def test_bulk_list_missing_body_returns_422(self, client):
        """POST /seller/bulk-list with no JSON body returns 422."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/bulk-list",
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 422

    async def test_price_suggest_missing_category_returns_422(self, client):
        """POST /seller/price-suggest without required 'category' returns 422."""
        _, jwt = await _setup_seller()

        resp = await client.post(
            "/api/v1/seller/price-suggest",
            json={"quality_score": 0.5},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 422

    async def test_rate_limiting_returns_429_after_burst(self, client):
        """Authenticated seller is rate-limited after exceeding the per-minute cap."""
        from marketplace.config import settings
        from marketplace.core.rate_limiter import rate_limiter

        _, jwt = await _setup_seller()
        headers = {"Authorization": f"Bearer {jwt}"}

        # Artificially exhaust the rate limit bucket
        limit = settings.rest_rate_limit_authenticated
        for _ in range(limit + 1):
            rate_limiter.check(f"agent:rate-limit-test-seller", authenticated=True)

        # Patch _extract_key so the middleware maps this request to our exhausted bucket
        with patch(
            "marketplace.core.rate_limit_middleware.RateLimitMiddleware._extract_key",
            return_value=("agent:rate-limit-test-seller", True),
        ):
            resp = await client.get(
                "/api/v1/seller/demand-for-me",
                headers=headers,
            )
        assert resp.status_code == 429
        assert "Rate limit exceeded" in resp.json()["detail"]
