"""Tests for marketplace/api/v2_market.py — public market browsing and order endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from marketplace.core.user_auth import get_current_user_id
from marketplace.main import app
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _override_user_id(user_id: str = "user-1"):
    """Set a FastAPI dependency override for get_current_user_id."""
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def _clear_user_override():
    app.dependency_overrides.pop(get_current_user_id, None)


# Mock return values matching schema shapes
_MOCK_LISTING = {
    "id": "listing-1",
    "title": "Test Listing",
    "description": "A test listing",
    "category": "web_search",
    "seller_id": "seller-1",
    "seller_name": "TestSeller",
    "price_usd": 1.50,
    "currency": "USD",
    "trust_status": "pending_verification",
    "trust_score": 50,
    "requires_unverified_confirmation": True,
    "freshness_at": "2026-01-01T00:00:00",
    "created_at": "2026-01-01T00:00:00",
}

_MOCK_ORDER = {
    "id": "order-1",
    "listing_id": "listing-1",
    "tx_id": "tx-1",
    "status": "completed",
    "amount_usd": 1.50,
    "fee_usd": 0.15,
    "payout_usd": 1.35,
    "trust_status": "pending_verification",
    "warning_acknowledged": False,
    "created_at": "2026-01-01T00:00:00",
    "content": "some content",
}


# ---------------------------------------------------------------------------
# GET /api/v2/market/listings — list market listings (public)
# ---------------------------------------------------------------------------

async def test_list_market_listings_success(client):
    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_listings",
        new_callable=AsyncMock,
        return_value=([_MOCK_LISTING], 1),
    ):
        resp = await client.get("/api/v2/market/listings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["results"]) == 1
    assert body["results"][0]["id"] == "listing-1"


async def test_list_market_listings_with_query_params(client):
    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_listings",
        new_callable=AsyncMock,
        return_value=([], 0),
    ) as mock_list:
        resp = await client.get(
            "/api/v2/market/listings",
            params={"q": "python", "category": "code_analysis", "page": 2, "page_size": 10},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["page"] == 2
    assert body["page_size"] == 10
    assert body["results"] == []

    mock_list.assert_called_once()
    call_kwargs = mock_list.call_args
    assert call_kwargs.kwargs.get("q") == "python" or call_kwargs[1].get("q") == "python"


async def test_list_market_listings_empty(client):
    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_listings",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        resp = await client.get("/api/v2/market/listings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []


async def test_list_market_listings_pagination_bounds(client):
    resp = await client.get(
        "/api/v2/market/listings",
        params={"page": 0},  # ge=1 violation
    )
    assert resp.status_code == 422

    resp = await client.get(
        "/api/v2/market/listings",
        params={"page_size": 200},  # le=100 violation
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v2/market/listings/{listing_id} — get single listing (public)
# ---------------------------------------------------------------------------

async def test_get_market_listing_success(client):
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_market_listing",
        new_callable=AsyncMock,
        return_value=_MOCK_LISTING,
    ):
        resp = await client.get("/api/v2/market/listings/listing-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "listing-1"
    assert body["title"] == "Test Listing"


async def test_get_market_listing_not_found_value_error(client):
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_market_listing",
        new_callable=AsyncMock,
        side_effect=ValueError("Listing not found"),
    ):
        resp = await client.get(f"/api/v2/market/listings/{_new_id()}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_get_market_listing_not_found_generic_error(client):
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_market_listing",
        new_callable=AsyncMock,
        side_effect=RuntimeError("unexpected"),
    ):
        resp = await client.get(f"/api/v2/market/listings/{_new_id()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Listing not found"


# ---------------------------------------------------------------------------
# POST /api/v2/market/orders — create order (authenticated user)
# ---------------------------------------------------------------------------

async def test_create_market_order_success(client):
    _override_user_id("user-1")
    try:
        with patch(
            "marketplace.api.v2_market.dual_layer_service.create_market_order",
            new_callable=AsyncMock,
            return_value=_MOCK_ORDER,
        ):
            resp = await client.post(
                "/api/v2/market/orders",
                json={"listing_id": "listing-1", "payment_method": "simulated"},
            )
    finally:
        _clear_user_override()

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "order-1"
    assert body["listing_id"] == "listing-1"


async def test_create_market_order_value_error_400(client):
    _override_user_id("user-1")
    try:
        with patch(
            "marketplace.api.v2_market.dual_layer_service.create_market_order",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid listing"),
        ):
            resp = await client.post(
                "/api/v2/market/orders",
                json={"listing_id": "bad-id", "payment_method": "simulated"},
            )
    finally:
        _clear_user_override()

    assert resp.status_code == 400
    assert "Invalid listing" in resp.json()["detail"]


async def test_create_market_order_unverified_conflict_409(client):
    _override_user_id("user-1")
    try:
        with patch(
            "marketplace.api.v2_market.dual_layer_service.create_market_order",
            new_callable=AsyncMock,
            side_effect=ValueError("must set allow_unverified=True"),
        ):
            resp = await client.post(
                "/api/v2/market/orders",
                json={"listing_id": "listing-1", "payment_method": "simulated"},
            )
    finally:
        _clear_user_override()

    assert resp.status_code == 409
    assert "allow_unverified" in resp.json()["detail"]


async def test_create_market_order_no_auth(client):
    resp = await client.post(
        "/api/v2/market/orders",
        json={"listing_id": "listing-1", "payment_method": "simulated"},
    )
    assert resp.status_code == 401


async def test_create_market_order_invalid_payment_method(client):
    _override_user_id("user-1")
    try:
        resp = await client.post(
            "/api/v2/market/orders",
            json={"listing_id": "listing-1", "payment_method": "bitcoin"},
        )
    finally:
        _clear_user_override()

    assert resp.status_code == 422  # pydantic pattern validation


# ---------------------------------------------------------------------------
# GET /api/v2/market/orders/me — list user's orders (authenticated)
# ---------------------------------------------------------------------------

async def test_list_market_orders_me_success(client):
    _override_user_id("user-1")
    try:
        with patch(
            "marketplace.api.v2_market.dual_layer_service.list_market_orders_for_user",
            new_callable=AsyncMock,
            return_value=([_MOCK_ORDER], 1),
        ):
            resp = await client.get("/api/v2/market/orders/me")
    finally:
        _clear_user_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["orders"]) == 1


async def test_list_market_orders_me_empty(client):
    _override_user_id("user-1")
    try:
        with patch(
            "marketplace.api.v2_market.dual_layer_service.list_market_orders_for_user",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            resp = await client.get("/api/v2/market/orders/me")
    finally:
        _clear_user_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["orders"] == []


async def test_list_market_orders_me_no_auth(client):
    resp = await client.get("/api/v2/market/orders/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/market/orders/{order_id} — get single order (authenticated)
# ---------------------------------------------------------------------------

async def test_get_market_order_success(client):
    _override_user_id("user-1")
    try:
        with patch(
            "marketplace.api.v2_market.dual_layer_service.get_market_order_for_user",
            new_callable=AsyncMock,
            return_value=_MOCK_ORDER,
        ):
            resp = await client.get("/api/v2/market/orders/order-1")
    finally:
        _clear_user_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "order-1"


async def test_get_market_order_not_found(client):
    _override_user_id("user-1")
    try:
        with patch(
            "marketplace.api.v2_market.dual_layer_service.get_market_order_for_user",
            new_callable=AsyncMock,
            side_effect=ValueError("Order not found"),
        ):
            resp = await client.get(f"/api/v2/market/orders/{_new_id()}")
    finally:
        _clear_user_override()

    assert resp.status_code == 404


async def test_get_market_order_no_auth(client):
    resp = await client.get("/api/v2/market/orders/order-1")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/market/collections/featured — featured collections (public)
# ---------------------------------------------------------------------------

async def test_get_featured_collections_success(client):
    mock_collection = {
        "key": "trending",
        "title": "Trending Now",
        "description": "Most popular listings",
        "listings": [_MOCK_LISTING],
    }
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_featured_collections",
        new_callable=AsyncMock,
        return_value=[mock_collection],
    ):
        resp = await client.get("/api/v2/market/collections/featured")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["key"] == "trending"


async def test_get_featured_collections_empty(client):
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_featured_collections",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await client.get("/api/v2/market/collections/featured")
    assert resp.status_code == 200
    body = resp.json()
    assert body == []
