"""Tests for marketplace/api/v2_market.py -- public market browsing and order endpoints.

Uses real HTTP requests through the ``client`` fixture.  The dual_layer_service
is an internal service so we mock it at the service boundary rather than making
full end-to-end calls through the complex user/order creation flow.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from marketplace.core.user_auth import create_user_token
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


MARKET_PREFIX = "/api/v2/market"


# ---------------------------------------------------------------------------
# GET /api/v2/market/listings -- list market listings (public)
# ---------------------------------------------------------------------------

async def test_list_market_listings_success(client):
    """GET /listings returns paginated listing results."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_listings",
        new_callable=AsyncMock,
        return_value=([_MOCK_LISTING], 1),
    ):
        resp = await client.get(f"{MARKET_PREFIX}/listings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["results"]) == 1
    assert body["results"][0]["id"] == "listing-1"


async def test_list_market_listings_with_query_params(client):
    """GET /listings forwards query params to the service."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_listings",
        new_callable=AsyncMock,
        return_value=([], 0),
    ) as mock_list:
        resp = await client.get(
            f"{MARKET_PREFIX}/listings",
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
    """GET /listings returns empty list when no listings exist."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_listings",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        resp = await client.get(f"{MARKET_PREFIX}/listings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []


async def test_list_market_listings_no_auth_required(client):
    """GET /listings is a public endpoint (no auth header needed)."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_listings",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        resp = await client.get(f"{MARKET_PREFIX}/listings")
    assert resp.status_code == 200


async def test_list_market_listings_pagination_bounds(client):
    """GET /listings rejects invalid pagination params."""
    resp = await client.get(
        f"{MARKET_PREFIX}/listings",
        params={"page": 0},  # ge=1 violation
    )
    assert resp.status_code == 422

    resp = await client.get(
        f"{MARKET_PREFIX}/listings",
        params={"page_size": 200},  # le=100 violation
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v2/market/listings/{listing_id} -- get single listing (public)
# ---------------------------------------------------------------------------

async def test_get_market_listing_success(client):
    """GET /listings/{id} returns listing detail."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_market_listing",
        new_callable=AsyncMock,
        return_value=_MOCK_LISTING,
    ):
        resp = await client.get(f"{MARKET_PREFIX}/listings/listing-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "listing-1"
    assert body["title"] == "Test Listing"
    assert body["price_usd"] == 1.50
    assert body["currency"] == "USD"


async def test_get_market_listing_not_found_value_error(client):
    """GET /listings/{id} returns 404 when service raises ValueError."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_market_listing",
        new_callable=AsyncMock,
        side_effect=ValueError("Listing not found"),
    ):
        resp = await client.get(f"{MARKET_PREFIX}/listings/{_new_id()}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_get_market_listing_not_found_generic_error(client):
    """GET /listings/{id} returns 404 on unexpected errors."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_market_listing",
        new_callable=AsyncMock,
        side_effect=RuntimeError("unexpected"),
    ):
        resp = await client.get(f"{MARKET_PREFIX}/listings/{_new_id()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Listing not found"


# ---------------------------------------------------------------------------
# POST /api/v2/market/orders -- create order (authenticated user)
# ---------------------------------------------------------------------------

async def test_create_market_order_success(client):
    """POST /orders creates an order for an authenticated user."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "buyer@test.com")

    with patch(
        "marketplace.api.v2_market.dual_layer_service.create_market_order",
        new_callable=AsyncMock,
        return_value=_MOCK_ORDER,
    ):
        resp = await client.post(
            f"{MARKET_PREFIX}/orders",
            headers=_user_auth(user_token),
            json={"listing_id": "listing-1", "payment_method": "simulated"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "order-1"
    assert body["listing_id"] == "listing-1"
    assert body["status"] == "completed"


async def test_create_market_order_value_error_400(client):
    """POST /orders returns 400 when service raises ValueError."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "buyer@test.com")

    with patch(
        "marketplace.api.v2_market.dual_layer_service.create_market_order",
        new_callable=AsyncMock,
        side_effect=ValueError("Invalid listing"),
    ):
        resp = await client.post(
            f"{MARKET_PREFIX}/orders",
            headers=_user_auth(user_token),
            json={"listing_id": "bad-id", "payment_method": "simulated"},
        )
    assert resp.status_code == 400
    assert "Invalid listing" in resp.json()["detail"]


async def test_create_market_order_unverified_conflict_409(client):
    """POST /orders returns 409 for unverified listings without allow_unverified."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "buyer@test.com")

    with patch(
        "marketplace.api.v2_market.dual_layer_service.create_market_order",
        new_callable=AsyncMock,
        side_effect=ValueError("must set allow_unverified=True"),
    ):
        resp = await client.post(
            f"{MARKET_PREFIX}/orders",
            headers=_user_auth(user_token),
            json={"listing_id": "listing-1", "payment_method": "simulated"},
        )
    assert resp.status_code == 409
    assert "allow_unverified" in resp.json()["detail"]


async def test_create_market_order_no_auth(client):
    """POST /orders without auth returns 401."""
    resp = await client.post(
        f"{MARKET_PREFIX}/orders",
        json={"listing_id": "listing-1", "payment_method": "simulated"},
    )
    assert resp.status_code == 401


async def test_create_market_order_invalid_payment_method(client):
    """POST /orders with invalid payment_method returns 422."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "buyer@test.com")

    resp = await client.post(
        f"{MARKET_PREFIX}/orders",
        headers=_user_auth(user_token),
        json={"listing_id": "listing-1", "payment_method": "bitcoin"},
    )
    assert resp.status_code == 422  # pydantic pattern validation


# ---------------------------------------------------------------------------
# GET /api/v2/market/orders/me -- list user's orders (authenticated)
# ---------------------------------------------------------------------------

async def test_list_market_orders_me_success(client):
    """GET /orders/me returns the authenticated user's orders."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "buyer@test.com")

    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_orders_for_user",
        new_callable=AsyncMock,
        return_value=([_MOCK_ORDER], 1),
    ):
        resp = await client.get(
            f"{MARKET_PREFIX}/orders/me",
            headers=_user_auth(user_token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["orders"]) == 1


async def test_list_market_orders_me_empty(client):
    """GET /orders/me returns empty when no orders exist."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "buyer@test.com")

    with patch(
        "marketplace.api.v2_market.dual_layer_service.list_market_orders_for_user",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        resp = await client.get(
            f"{MARKET_PREFIX}/orders/me",
            headers=_user_auth(user_token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["orders"] == []


async def test_list_market_orders_me_no_auth(client):
    """GET /orders/me without auth returns 401."""
    resp = await client.get(f"{MARKET_PREFIX}/orders/me")
    assert resp.status_code == 401


async def test_list_market_orders_me_agent_token_rejected(client, make_agent):
    """GET /orders/me rejects agent tokens (user-only endpoint)."""
    _, agent_token = await make_agent()
    resp = await client.get(
        f"{MARKET_PREFIX}/orders/me",
        headers=_user_auth(agent_token),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/market/orders/{order_id} -- get single order (authenticated)
# ---------------------------------------------------------------------------

async def test_get_market_order_success(client):
    """GET /orders/{id} returns order detail for the owner."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "buyer@test.com")

    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_market_order_for_user",
        new_callable=AsyncMock,
        return_value=_MOCK_ORDER,
    ):
        resp = await client.get(
            f"{MARKET_PREFIX}/orders/order-1",
            headers=_user_auth(user_token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "order-1"


async def test_get_market_order_not_found(client):
    """GET /orders/{id} returns 404 when order does not exist."""
    user_id = f"user-{_new_id()[:8]}"
    user_token = create_user_token(user_id, "buyer@test.com")

    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_market_order_for_user",
        new_callable=AsyncMock,
        side_effect=ValueError("Order not found"),
    ):
        resp = await client.get(
            f"{MARKET_PREFIX}/orders/{_new_id()}",
            headers=_user_auth(user_token),
        )
    assert resp.status_code == 404


async def test_get_market_order_no_auth(client):
    """GET /orders/{id} without auth returns 401."""
    resp = await client.get(f"{MARKET_PREFIX}/orders/order-1")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/market/collections/featured -- featured collections (public)
# ---------------------------------------------------------------------------

async def test_get_featured_collections_success(client):
    """GET /collections/featured returns collection list."""
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
        resp = await client.get(f"{MARKET_PREFIX}/collections/featured")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["key"] == "trending"


async def test_get_featured_collections_empty(client):
    """GET /collections/featured returns empty list when no collections exist."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_featured_collections",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await client.get(f"{MARKET_PREFIX}/collections/featured")
    assert resp.status_code == 200
    body = resp.json()
    assert body == []


async def test_get_featured_collections_no_auth_required(client):
    """GET /collections/featured is public (no auth needed)."""
    with patch(
        "marketplace.api.v2_market.dual_layer_service.get_featured_collections",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await client.get(f"{MARKET_PREFIX}/collections/featured")
    assert resp.status_code == 200
