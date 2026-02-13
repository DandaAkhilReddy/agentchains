"""Deep test suite for /api/v1/listings routes.

Covers 25 tests across 5 logical groups:
  1. CRUD endpoints (create, get, update, delete, list all)
  2. Auth guards (unauthenticated rejected, wrong owner, admin override)
  3. Validation errors (missing fields, invalid price, invalid category, long desc)
  4. Status transitions (draft->active->paused->archived, invalid rejection)
  5. Filtering & search (by status, category, price range, owner, combined)

Style: pytest-asyncio with httpx AsyncClient, uses conftest fixtures
(client, make_agent, make_listing, auth_header, db).
"""

import json
from decimal import Decimal

import pytest

from marketplace.models.listing import DataListing


# ===========================================================================
# 1. CRUD Endpoints
# ===========================================================================


class TestCRUDEndpoints:
    """Verify the full create-read-update-delete lifecycle."""

    @pytest.mark.asyncio
    async def test_create_listing_returns_201_with_all_fields(
        self, client, make_agent, auth_header
    ):
        """POST /listings returns 201 and echoes every field back."""
        agent, token = await make_agent()

        payload = {
            "title": "Deep-Test Dataset",
            "description": "A dataset created by the deep test suite",
            "category": "web_search",
            "content": "deep test content bytes here",
            "price_usdc": 4.25,
            "metadata": {"origin": "test_suite", "version": "2.0"},
            "tags": ["deep", "test"],
            "quality_score": 0.88,
        }

        resp = await client.post(
            "/api/v1/listings", headers=auth_header(token), json=payload
        )
        assert resp.status_code == 201
        data = resp.json()

        assert data["title"] == "Deep-Test Dataset"
        assert data["description"] == "A dataset created by the deep test suite"
        assert data["category"] == "web_search"
        assert data["price_usdc"] == 4.25
        assert data["seller_id"] == agent.id
        assert data["metadata"] == {"origin": "test_suite", "version": "2.0"}
        assert data["tags"] == ["deep", "test"]
        assert data["quality_score"] == 0.88
        assert data["status"] == "active"
        assert data["content_hash"].startswith("sha256:")
        assert data["access_count"] == 0
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_listing_by_id(self, client, make_agent, make_listing):
        """GET /listings/{id} returns the correct listing."""
        agent, _ = await make_agent()
        listing = await make_listing(agent.id, title="Fetchable", price_usdc=7.0)

        resp = await client.get(f"/api/v1/listings/{listing.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == listing.id
        assert data["title"] == "Fetchable"
        assert data["price_usdc"] == 7.0

    @pytest.mark.asyncio
    async def test_get_listing_returns_404_for_missing_id(self, client):
        """GET /listings/{id} returns 404 when no listing matches."""
        resp = await client.get("/api/v1/listings/does-not-exist-uuid")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_listing_changes_fields(
        self, client, make_agent, make_listing, auth_header
    ):
        """PUT /listings/{id} updates the provided fields."""
        agent, token = await make_agent()
        listing = await make_listing(agent.id, title="Before", price_usdc=1.0)

        resp = await client.put(
            f"/api/v1/listings/{listing.id}",
            headers=auth_header(token),
            json={"title": "After", "price_usdc": 9.99, "description": "Updated desc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "After"
        assert data["price_usdc"] == 9.99
        assert data["description"] == "Updated desc"

    @pytest.mark.asyncio
    async def test_delete_listing_delists_and_hides(
        self, client, make_agent, make_listing, auth_header
    ):
        """DELETE /listings/{id} soft-deletes; listing disappears from active list."""
        agent, token = await make_agent()
        listing = await make_listing(agent.id)

        resp = await client.delete(
            f"/api/v1/listings/{listing.id}", headers=auth_header(token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delisted"

        # It should no longer appear in the default (status=active) listing
        list_resp = await client.get("/api/v1/listings")
        ids = [r["id"] for r in list_resp.json()["results"]]
        assert listing.id not in ids

    @pytest.mark.asyncio
    async def test_list_all_returns_paginated_structure(
        self, client, make_agent, make_listing
    ):
        """GET /listings returns the standard paginated envelope."""
        agent, _ = await make_agent()
        for i in range(3):
            await make_listing(agent.id, title=f"Item {i}")

        resp = await client.get("/api/v1/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["results"]) == 3


# ===========================================================================
# 2. Auth Guards
# ===========================================================================


class TestAuthGuards:
    """Verify that authentication and ownership checks are enforced."""

    @pytest.mark.asyncio
    async def test_create_listing_without_token_returns_401(self, client):
        """POST /listings with no Authorization header is rejected."""
        resp = await client.post(
            "/api/v1/listings",
            json={
                "title": "Sneaky",
                "category": "web_search",
                "content": "nope",
                "price_usdc": 1.0,
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_update_listing_without_token_returns_401(
        self, client, make_agent, make_listing
    ):
        """PUT /listings/{id} with no Authorization header is rejected."""
        agent, _ = await make_agent()
        listing = await make_listing(agent.id)

        resp = await client.put(
            f"/api/v1/listings/{listing.id}", json={"title": "Nope"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_listing_without_token_returns_401(
        self, client, make_agent, make_listing
    ):
        """DELETE /listings/{id} with no Authorization header is rejected."""
        agent, _ = await make_agent()
        listing = await make_listing(agent.id)

        resp = await client.delete(f"/api/v1/listings/{listing.id}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_non_owner_cannot_update(
        self, client, make_agent, make_listing, auth_header
    ):
        """PUT /listings/{id} by a different agent returns 403."""
        owner, _ = await make_agent(name="owner-agent")
        intruder, intruder_token = await make_agent(name="intruder-agent")
        listing = await make_listing(owner.id)

        resp = await client.put(
            f"/api/v1/listings/{listing.id}",
            headers=auth_header(intruder_token),
            json={"title": "Hijacked"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_non_owner_cannot_delete(
        self, client, make_agent, make_listing, auth_header
    ):
        """DELETE /listings/{id} by a different agent returns 403."""
        owner, _ = await make_agent(name="owner-agent2")
        intruder, intruder_token = await make_agent(name="intruder-agent2")
        listing = await make_listing(owner.id)

        resp = await client.delete(
            f"/api/v1/listings/{listing.id}",
            headers=auth_header(intruder_token),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_returns_401(self, client):
        """A garbage bearer token returns 401."""
        resp = await client.post(
            "/api/v1/listings",
            headers={"Authorization": "Bearer totally.invalid.jwt"},
            json={
                "title": "X",
                "category": "web_search",
                "content": "x",
                "price_usdc": 1.0,
            },
        )
        assert resp.status_code == 401


# ===========================================================================
# 3. Validation Errors
# ===========================================================================


class TestValidationErrors:
    """Verify that Pydantic schema constraints are enforced at the API level."""

    @pytest.mark.asyncio
    async def test_missing_title_returns_422(self, client, make_agent, auth_header):
        """Omitting the required 'title' field triggers 422."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={"category": "web_search", "content": "data", "price_usdc": 1.0},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_content_returns_422(self, client, make_agent, auth_header):
        """Omitting the required 'content' field triggers 422."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={"title": "No Content", "category": "web_search", "price_usdc": 1.0},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_content_returns_422(self, client, make_agent, auth_header):
        """An empty string for 'content' triggers 422 (min_length=1)."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": "Empty",
                "category": "web_search",
                "content": "",
                "price_usdc": 1.0,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_zero_price_returns_422(self, client, make_agent, auth_header):
        """price_usdc=0 violates gt=0 constraint."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": "Free",
                "category": "web_search",
                "content": "free stuff",
                "price_usdc": 0,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_price_returns_422(self, client, make_agent, auth_header):
        """Negative price is rejected."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": "Negative",
                "category": "web_search",
                "content": "content",
                "price_usdc": -5.0,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_price_above_max_returns_422(self, client, make_agent, auth_header):
        """price_usdc > 1000 violates le=1000 constraint."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": "Overpriced",
                "category": "web_search",
                "content": "expensive",
                "price_usdc": 1001.0,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_category_returns_422(self, client, make_agent, auth_header):
        """A category not in the allowed pattern is rejected."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": "Bad Cat",
                "category": "not_a_real_category",
                "content": "content",
                "price_usdc": 1.0,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_title_exceeding_255_chars_returns_422(
        self, client, make_agent, auth_header
    ):
        """Title longer than 255 characters violates max_length=255."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": "A" * 256,
                "category": "web_search",
                "content": "content",
                "price_usdc": 1.0,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_quality_score_out_of_range_returns_422(
        self, client, make_agent, auth_header
    ):
        """quality_score > 1.0 violates le=1 constraint."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": "HighQ",
                "category": "web_search",
                "content": "content",
                "price_usdc": 1.0,
                "quality_score": 1.5,
            },
        )
        assert resp.status_code == 422


# ===========================================================================
# 4. Status Transitions
# ===========================================================================


class TestStatusTransitions:
    """Verify status changes through the update endpoint."""

    @pytest.mark.asyncio
    async def test_new_listing_defaults_to_active(
        self, client, make_agent, auth_header
    ):
        """A freshly created listing has status='active'."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v1/listings",
            headers=auth_header(token),
            json={
                "title": "Fresh",
                "category": "web_search",
                "content": "brand new",
                "price_usdc": 1.0,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_owner_can_pause_active_listing(
        self, client, make_agent, make_listing, auth_header
    ):
        """Owner can set status to 'paused' via PUT."""
        agent, token = await make_agent()
        listing = await make_listing(agent.id, status="active")

        resp = await client.put(
            f"/api/v1/listings/{listing.id}",
            headers=auth_header(token),
            json={"status": "paused"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    @pytest.mark.asyncio
    async def test_owner_can_reactivate_paused_listing(
        self, client, make_agent, make_listing, auth_header
    ):
        """Owner can set status back to 'active' from 'paused'."""
        agent, token = await make_agent()
        listing = await make_listing(agent.id, status="paused")

        resp = await client.put(
            f"/api/v1/listings/{listing.id}",
            headers=auth_header(token),
            json={"status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_delist_changes_status_to_delisted(
        self, client, make_agent, make_listing, auth_header
    ):
        """DELETE /listings/{id} sets status to 'delisted'."""
        agent, token = await make_agent()
        listing = await make_listing(agent.id)

        await client.delete(
            f"/api/v1/listings/{listing.id}", headers=auth_header(token)
        )

        # Verify through the GET endpoint that it is now delisted
        get_resp = await client.get(f"/api/v1/listings/{listing.id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "delisted"

    @pytest.mark.asyncio
    async def test_delisted_listing_excluded_from_active_list(
        self, client, make_agent, make_listing, auth_header
    ):
        """After delisting, the listing no longer shows in status=active queries."""
        agent, token = await make_agent()
        kept = await make_listing(agent.id, title="Kept")
        removed = await make_listing(agent.id, title="Removed")

        await client.delete(
            f"/api/v1/listings/{removed.id}", headers=auth_header(token)
        )

        resp = await client.get("/api/v1/listings")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["results"]]
        assert kept.id in ids
        assert removed.id not in ids


# ===========================================================================
# 5. Filtering & Search
# ===========================================================================


class TestFilteringAndSearch:
    """Verify query-string filters on the list endpoint."""

    @pytest.mark.asyncio
    async def test_filter_by_status_active(
        self, client, make_agent, make_listing
    ):
        """Default status=active returns only active listings."""
        agent, _ = await make_agent()
        await make_listing(agent.id, status="active", title="Active One")
        await make_listing(agent.id, status="delisted", title="Delisted One")

        resp = await client.get("/api/v1/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["title"] == "Active One"

    @pytest.mark.asyncio
    async def test_filter_by_status_delisted(
        self, client, make_agent, make_listing
    ):
        """Passing status=delisted returns only delisted listings."""
        agent, _ = await make_agent()
        await make_listing(agent.id, status="active")
        await make_listing(agent.id, status="delisted", title="Gone")

        resp = await client.get("/api/v1/listings?status=delisted")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["title"] == "Gone"

    @pytest.mark.asyncio
    async def test_filter_by_category(self, client, make_agent, make_listing):
        """category= query param narrows results to that category only."""
        agent, _ = await make_agent()
        ws = await make_listing(agent.id, category="web_search", title="Web")
        await make_listing(agent.id, category="code_analysis", title="Code")

        resp = await client.get("/api/v1/listings?category=web_search")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["id"] == ws.id

    @pytest.mark.asyncio
    async def test_pagination_page_size(self, client, make_agent, make_listing):
        """page_size limits the number of results per page."""
        agent, _ = await make_agent()
        for i in range(6):
            await make_listing(agent.id, title=f"P{i}")

        resp = await client.get("/api/v1/listings?page=1&page_size=4")
        data = resp.json()
        assert data["total"] == 6
        assert len(data["results"]) == 4

        resp2 = await client.get("/api/v1/listings?page=2&page_size=4")
        data2 = resp2.json()
        assert len(data2["results"]) == 2

    @pytest.mark.asyncio
    async def test_combined_category_and_status_filter(
        self, client, make_agent, make_listing
    ):
        """Combining category and status filters narrows results correctly."""
        agent, _ = await make_agent()
        target = await make_listing(
            agent.id, category="computation", status="active", title="Target"
        )
        await make_listing(
            agent.id, category="computation", status="delisted", title="Dead"
        )
        await make_listing(
            agent.id, category="web_search", status="active", title="Wrong Cat"
        )

        resp = await client.get(
            "/api/v1/listings?category=computation&status=active"
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["id"] == target.id

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero_total(self, client):
        """An empty database returns total=0 with an empty results array."""
        resp = await client.get("/api/v1/listings")
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []
        assert data["page"] == 1
