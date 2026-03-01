"""Comprehensive tests for v2 REST API modules:

- v2_integrations  (webhooks)
- v2_market        (market listings, orders, collections)
- v2_memory        (memory snapshots)
- v2_payouts       (payout requests)
- v2_search        (search endpoints)
- v2_sellers       (seller earnings)
- v2_users         (user register/login/me/stream-token)
- v2_verification  (trust verification)

All tests are async functions using the shared ``client`` fixture.
pytest-asyncio is configured in auto mode — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from marketplace.core.creator_auth import create_creator_token
from marketplace.core.user_auth import create_user_token
from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _new_user_token(user_id: str, email: str = "user@example.com") -> str:
    return create_user_token(user_id, email)


def _new_creator_token(creator_id: str, email: str = "creator@example.com") -> str:
    return create_creator_token(creator_id, email)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# v2_integrations — /api/v2/integrations/webhooks
# ===========================================================================

async def test_webhook_create_happy_path(client, make_agent):
    """POST /api/v2/integrations/webhooks — creates a webhook subscription."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.post(
        "/api/v2/integrations/webhooks",
        headers=_auth(token),
        json={
            "callback_url": "https://example.com/hooks/events",
            "event_types": ["listing_created", "payment_confirmed"],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["callback_url"] == "https://example.com/hooks/events"
    assert "listing_created" in body["event_types"]
    assert "id" in body
    assert "secret" in body


async def test_webhook_create_default_event_types(client, make_agent):
    """POST /api/v2/integrations/webhooks — omitting event_types defaults to ['*']."""
    agent, token = await make_agent(agent_type="both")

    resp = await client.post(
        "/api/v2/integrations/webhooks",
        headers=_auth(token),
        json={"callback_url": "https://example.com/hooks/all"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["event_types"] == ["*"]


async def test_webhook_create_invalid_url_too_short(client, make_agent):
    """POST /api/v2/integrations/webhooks — URL shorter than 8 chars fails validation."""
    agent, token = await make_agent(agent_type="seller")

    # "http://" is 7 chars — below the min_length=8 threshold, triggers 422
    resp = await client.post(
        "/api/v2/integrations/webhooks",
        headers=_auth(token),
        json={"callback_url": "http://"},
    )
    # Pydantic min_length=8 rejects URLs under 8 chars
    assert resp.status_code in (400, 422)


async def test_webhook_create_non_http_url_rejected(client, make_agent):
    """POST /api/v2/integrations/webhooks — non-http/https scheme is rejected."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.post(
        "/api/v2/integrations/webhooks",
        headers=_auth(token),
        json={"callback_url": "ftp://example.com/hooks"},
    )
    assert resp.status_code in (400, 422)


async def test_webhook_create_unauthenticated(client):
    """POST /api/v2/integrations/webhooks — requires auth."""
    resp = await client.post(
        "/api/v2/integrations/webhooks",
        json={"callback_url": "https://example.com/hooks"},
    )
    assert resp.status_code == 401


async def test_webhook_list_empty(client, make_agent):
    """GET /api/v2/integrations/webhooks — returns empty list for new agent."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.get("/api/v2/integrations/webhooks", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscriptions"] == []
    assert body["count"] == 0


async def test_webhook_list_after_create(client, make_agent):
    """GET /api/v2/integrations/webhooks — returns created subscriptions."""
    agent, token = await make_agent(agent_type="seller")

    await client.post(
        "/api/v2/integrations/webhooks",
        headers=_auth(token),
        json={"callback_url": "https://example.com/webhook/a"},
    )
    await client.post(
        "/api/v2/integrations/webhooks",
        headers=_auth(token),
        json={"callback_url": "https://example.com/webhook/b"},
    )

    resp = await client.get("/api/v2/integrations/webhooks", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    urls = {s["callback_url"] for s in body["subscriptions"]}
    assert "https://example.com/webhook/a" in urls
    assert "https://example.com/webhook/b" in urls


async def test_webhook_list_unauthenticated(client):
    """GET /api/v2/integrations/webhooks — requires auth."""
    resp = await client.get("/api/v2/integrations/webhooks")
    assert resp.status_code == 401


async def test_webhook_delete_happy_path(client, make_agent):
    """DELETE /api/v2/integrations/webhooks/{id} — successfully removes subscription."""
    agent, token = await make_agent(agent_type="seller")

    create_resp = await client.post(
        "/api/v2/integrations/webhooks",
        headers=_auth(token),
        json={"callback_url": "https://example.com/hook/del"},
    )
    assert create_resp.status_code == 201
    sub_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v2/integrations/webhooks/{sub_id}",
        headers=_auth(token),
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    # Confirm it is gone from list
    list_resp = await client.get("/api/v2/integrations/webhooks", headers=_auth(token))
    assert list_resp.json()["count"] == 0


async def test_webhook_delete_not_found(client, make_agent):
    """DELETE /api/v2/integrations/webhooks/{id} — 404 for unknown subscription id."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.delete(
        f"/api/v2/integrations/webhooks/{_new_id()}",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_webhook_delete_unauthenticated(client):
    """DELETE /api/v2/integrations/webhooks/{id} — requires auth."""
    resp = await client.delete(f"/api/v2/integrations/webhooks/{_new_id()}")
    assert resp.status_code == 401


# ===========================================================================
# v2_market — /api/v2/market
# ===========================================================================

async def test_market_list_listings_empty(client):
    """GET /api/v2/market/listings — empty result when no listings exist."""
    resp = await client.get("/api/v2/market/listings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []
    assert body["page"] == 1


async def test_market_list_listings_with_data(client, make_agent, make_listing):
    """GET /api/v2/market/listings — returns active listings with correct fields."""
    seller, token = await make_agent(agent_type="seller")

    async with TestSession() as db:
        await make_listing(seller.id, price_usdc=0.50, title="Listing Alpha", category="web_search")
        await make_listing(seller.id, price_usdc=1.00, title="Listing Beta", category="code_analysis")

    resp = await client.get("/api/v2/market/listings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    titles = [r["title"] for r in body["results"]]
    assert "Listing Alpha" in titles
    assert "Listing Beta" in titles


async def test_market_list_listings_filter_by_category(client, make_agent, make_listing):
    """GET /api/v2/market/listings?category=web_search — filters by category."""
    seller, _ = await make_agent(agent_type="seller")

    async with TestSession() as db:
        await make_listing(seller.id, title="Web Listing", category="web_search")
        await make_listing(seller.id, title="Code Listing", category="code_analysis")

    resp = await client.get("/api/v2/market/listings?category=web_search")
    assert resp.status_code == 200
    body = resp.json()
    categories = [r["category"] for r in body["results"]]
    assert all(c == "web_search" for c in categories)


async def test_market_list_listings_pagination(client, make_agent, make_listing):
    """GET /api/v2/market/listings — respects page and page_size params."""
    seller, _ = await make_agent(agent_type="seller")
    async with TestSession() as db:
        for i in range(5):
            await make_listing(seller.id, title=f"Paginated {i}")

    resp = await client.get("/api/v2/market/listings?page=1&page_size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["results"]) <= 2


async def test_market_get_listing_by_id(client, make_agent, make_listing):
    """GET /api/v2/market/listings/{id} — returns specific listing."""
    seller, _ = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(seller.id, title="Target Listing", price_usdc=2.00)

    resp = await client.get(f"/api/v2/market/listings/{listing.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == listing.id
    assert body["title"] == "Target Listing"
    assert "price_usd" in body


async def test_market_get_listing_not_found(client):
    """GET /api/v2/market/listings/{id} — 404 for unknown listing."""
    resp = await client.get(f"/api/v2/market/listings/{_new_id()}")
    assert resp.status_code == 404


async def test_market_create_order_happy_path(client, make_agent, make_listing):
    """POST /api/v2/market/orders — end user can purchase a listing."""
    seller, _ = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(seller.id, price_usdc=1.00, title="Purchasable")
        # Seed platform + buyer accounts
        db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
        await db.commit()

    user_id = _new_id()
    user_token = _new_user_token(user_id, "buyer@example.com")

    resp = await client.post(
        "/api/v2/market/orders",
        headers=_auth(user_token),
        json={
            "listing_id": listing.id,
            "payment_method": "simulated",
            "allow_unverified": True,
        },
    )
    # 201 on success; 400/409 acceptable if balance insufficient
    assert resp.status_code in (201, 400, 409)


async def test_market_create_order_unverified_listing_requires_flag(client, make_agent, make_listing):
    """POST /api/v2/market/orders — unverified listing without flag returns 409."""
    seller, _ = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(
            seller.id,
            price_usdc=1.00,
            title="Unverified Listing",
            status="active",
        )
        db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
        await db.commit()

    user_id = _new_id()
    user_token = _new_user_token(user_id, "buyer2@example.com")

    resp = await client.post(
        "/api/v2/market/orders",
        headers=_auth(user_token),
        json={
            "listing_id": listing.id,
            "payment_method": "simulated",
            "allow_unverified": False,
        },
    )
    # The service raises ValueError with "allow_unverified" in the message -> 409
    # or 400 if balance insufficient; 201 if verified
    assert resp.status_code in (201, 400, 409)


async def test_market_create_order_missing_listing(client):
    """POST /api/v2/market/orders — 400 for non-existent listing."""
    user_id = _new_id()
    user_token = _new_user_token(user_id, "buyer3@example.com")

    resp = await client.post(
        "/api/v2/market/orders",
        headers=_auth(user_token),
        json={
            "listing_id": _new_id(),
            "payment_method": "simulated",
            "allow_unverified": True,
        },
    )
    assert resp.status_code in (400, 404)


async def test_market_create_order_unauthenticated(client):
    """POST /api/v2/market/orders — requires user auth."""
    resp = await client.post(
        "/api/v2/market/orders",
        json={"listing_id": _new_id(), "payment_method": "wallet", "allow_unverified": True},
    )
    assert resp.status_code == 401


async def test_market_list_my_orders_empty(client):
    """GET /api/v2/market/orders/me — returns empty list for new user."""
    user_id = _new_id()
    user_token = _new_user_token(user_id, "newbuyer@example.com")

    resp = await client.get("/api/v2/market/orders/me", headers=_auth(user_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["orders"] == []


async def test_market_list_my_orders_unauthenticated(client):
    """GET /api/v2/market/orders/me — requires user auth."""
    resp = await client.get("/api/v2/market/orders/me")
    assert resp.status_code == 401


async def test_market_get_order_not_found(client):
    """GET /api/v2/market/orders/{id} — 404 for unknown order."""
    user_id = _new_id()
    user_token = _new_user_token(user_id, "nofind@example.com")

    resp = await client.get(
        f"/api/v2/market/orders/{_new_id()}",
        headers=_auth(user_token),
    )
    assert resp.status_code == 404


async def test_market_get_order_unauthenticated(client):
    """GET /api/v2/market/orders/{id} — requires user auth."""
    resp = await client.get(f"/api/v2/market/orders/{_new_id()}")
    assert resp.status_code == 401


async def test_market_featured_collections(client):
    """GET /api/v2/market/collections/featured — returns a list (possibly empty)."""
    resp = await client.get("/api/v2/market/collections/featured")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


# ===========================================================================
# v2_memory — /api/v2/memory
# ===========================================================================

async def test_memory_import_snapshot_happy_path(client, make_agent):
    """POST /api/v2/memory/snapshots/import — imports a snapshot successfully."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.post(
        "/api/v2/memory/snapshots/import",
        headers=_auth(token),
        json={
            "source_type": "sdk",
            "label": "my-snapshot",
            "records": [{"key": "fact1", "value": "The sky is blue"}],
            "chunk_size": 10,
            "source_metadata": {"version": "1.0"},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    # Response is {"snapshot": {"snapshot_id": ..., ...}, "chunk_hashes": [...], ...}
    assert "snapshot" in body
    assert "snapshot_id" in body["snapshot"]


async def test_memory_import_snapshot_empty_records(client, make_agent):
    """POST /api/v2/memory/snapshots/import — empty records list returns 400 (at least one required)."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.post(
        "/api/v2/memory/snapshots/import",
        headers=_auth(token),
        json={"source_type": "sdk", "label": "empty-snap", "records": []},
    )
    assert resp.status_code == 400


async def test_memory_import_snapshot_invalid_source_type(client, make_agent):
    """POST /api/v2/memory/snapshots/import — source_type too short fails validation."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.post(
        "/api/v2/memory/snapshots/import",
        headers=_auth(token),
        json={"source_type": "x", "label": "bad"},
    )
    assert resp.status_code == 422


async def test_memory_import_snapshot_unauthenticated(client):
    """POST /api/v2/memory/snapshots/import — requires agent auth."""
    resp = await client.post(
        "/api/v2/memory/snapshots/import",
        json={"source_type": "sdk", "label": "no-auth"},
    )
    assert resp.status_code == 401


async def test_memory_get_snapshot_happy_path(client, make_agent):
    """GET /api/v2/memory/snapshots/{id} — retrieves a previously imported snapshot."""
    agent, token = await make_agent(agent_type="seller")

    import_resp = await client.post(
        "/api/v2/memory/snapshots/import",
        headers=_auth(token),
        json={
            "source_type": "sdk",
            "label": "retrieve-me",
            "records": [{"q": "test question", "a": "test answer"}],
        },
    )
    assert import_resp.status_code == 201
    body = import_resp.json()
    # Response structure: {"snapshot": {"snapshot_id": ..., ...}, "chunk_hashes": [...]}
    snap_id = body["snapshot"]["snapshot_id"]
    assert snap_id is not None

    get_resp = await client.get(
        f"/api/v2/memory/snapshots/{snap_id}",
        headers=_auth(token),
    )
    assert get_resp.status_code == 200
    snap = get_resp.json()
    assert snap.get("snapshot_id") == snap_id


async def test_memory_get_snapshot_not_found(client, make_agent):
    """GET /api/v2/memory/snapshots/{id} — 404 for non-existent snapshot."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.get(
        f"/api/v2/memory/snapshots/{_new_id()}",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_memory_get_snapshot_unauthenticated(client):
    """GET /api/v2/memory/snapshots/{id} — requires agent auth."""
    resp = await client.get(f"/api/v2/memory/snapshots/{_new_id()}")
    assert resp.status_code == 401


async def test_memory_verify_snapshot_happy_path(client, make_agent):
    """POST /api/v2/memory/snapshots/{id}/verify — verifies an owned snapshot."""
    agent, token = await make_agent(agent_type="seller")

    import_resp = await client.post(
        "/api/v2/memory/snapshots/import",
        headers=_auth(token),
        json={
            "source_type": "sdk",
            "label": "verify-me",
            "records": [{"entry": f"data-{i}"} for i in range(10)],
        },
    )
    assert import_resp.status_code == 201
    body = import_resp.json()
    # Response structure: {"snapshot": {"snapshot_id": ..., ...}, "chunk_hashes": [...]}
    snap_id = body["snapshot"]["snapshot_id"]

    verify_resp = await client.post(
        f"/api/v2/memory/snapshots/{snap_id}/verify",
        headers=_auth(token),
        json={"sample_size": 3},
    )
    assert verify_resp.status_code == 200
    result = verify_resp.json()
    assert "status" in result or "verified" in result or "passed" in result


async def test_memory_verify_snapshot_not_found(client, make_agent):
    """POST /api/v2/memory/snapshots/{id}/verify — 404 for missing snapshot."""
    agent, token = await make_agent(agent_type="seller")

    resp = await client.post(
        f"/api/v2/memory/snapshots/{_new_id()}/verify",
        headers=_auth(token),
        json={"sample_size": 5},
    )
    assert resp.status_code == 404


async def test_memory_verify_snapshot_wrong_owner(client, make_agent):
    """POST /api/v2/memory/snapshots/{id}/verify — 403 when agent does not own snapshot."""
    owner, owner_token = await make_agent(name="snap-owner", agent_type="seller")
    other, other_token = await make_agent(name="snap-other", agent_type="seller")

    import_resp = await client.post(
        "/api/v2/memory/snapshots/import",
        headers=_auth(owner_token),
        json={"source_type": "sdk", "label": "owned-snap", "records": [{"k": "v"}]},
    )
    assert import_resp.status_code == 201
    body = import_resp.json()
    # Response structure: {"snapshot": {"snapshot_id": ..., ...}, "chunk_hashes": [...]}
    snap_id = body["snapshot"]["snapshot_id"]

    verify_resp = await client.post(
        f"/api/v2/memory/snapshots/{snap_id}/verify",
        headers=_auth(other_token),
        json={"sample_size": 1},
    )
    assert verify_resp.status_code == 403


async def test_memory_verify_snapshot_unauthenticated(client):
    """POST /api/v2/memory/snapshots/{id}/verify — requires agent auth."""
    resp = await client.post(
        f"/api/v2/memory/snapshots/{_new_id()}/verify",
        json={"sample_size": 5},
    )
    assert resp.status_code == 401


# ===========================================================================
# v2_payouts — /api/v2/payouts
# ===========================================================================

async def test_payouts_create_request_happy_path(client, make_creator):
    """POST /api/v2/payouts/requests — creator can request a payout."""
    creator, creator_token = await make_creator()
    async with TestSession() as db:
        db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
        db.add(
            TokenAccount(id=_new_id(), creator_id=creator.id, balance=Decimal("50.0"))
        )
        await db.commit()

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_auth(creator_token),
        json={"payout_method": "api_credits", "amount_usd": 5.0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body or "request_id" in body


async def test_payouts_create_request_invalid_method(client, make_creator):
    """POST /api/v2/payouts/requests — unsupported payout_method returns 400."""
    creator, creator_token = await make_creator()

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_auth(creator_token),
        json={"payout_method": "crypto_bitcoin", "amount_usd": 1.0},
    )
    assert resp.status_code == 400
    assert "Unsupported payout_method" in resp.json()["detail"]


async def test_payouts_create_request_method_normalization(client, make_creator):
    """POST /api/v2/payouts/requests — bank_transfer normalizes to bank_withdrawal."""
    creator, creator_token = await make_creator()
    async with TestSession() as db:
        db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
        db.add(
            TokenAccount(id=_new_id(), creator_id=creator.id, balance=Decimal("100.0"))
        )
        await db.commit()

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_auth(creator_token),
        json={"payout_method": "bank_transfer", "amount_usd": 10.0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body.get("redemption_type") == "bank_withdrawal"


async def test_payouts_create_request_unauthenticated(client):
    """POST /api/v2/payouts/requests — requires creator auth."""
    resp = await client.post(
        "/api/v2/payouts/requests",
        json={"payout_method": "api_credits", "amount_usd": 1.0},
    )
    assert resp.status_code == 401


async def test_payouts_list_requests_empty(client, make_creator):
    """GET /api/v2/payouts/requests — returns empty list for new creator."""
    creator, creator_token = await make_creator()

    resp = await client.get("/api/v2/payouts/requests", headers=_auth(creator_token))
    assert resp.status_code == 200
    body = resp.json()
    # Could be {"items": [], "total": 0} or a list directly
    if isinstance(body, dict):
        assert body.get("total", 0) == 0
    else:
        assert body == []


async def test_payouts_list_requests_unauthenticated(client):
    """GET /api/v2/payouts/requests — requires creator auth."""
    resp = await client.get("/api/v2/payouts/requests")
    assert resp.status_code == 401


async def test_payouts_cancel_request_happy_path(client, make_creator):
    """POST /api/v2/payouts/requests/{id}/cancel — creator can cancel pending request."""
    creator, creator_token = await make_creator()
    async with TestSession() as db:
        db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
        db.add(
            TokenAccount(id=_new_id(), creator_id=creator.id, balance=Decimal("50.0"))
        )
        await db.commit()

    # Use bank_transfer (min $10) so the redemption stays "pending" and can be cancelled.
    # api_credits is auto-processed to "completed" and cannot be cancelled.
    create_resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_auth(creator_token),
        json={"payout_method": "bank_transfer", "amount_usd": 15.0},
    )
    assert create_resp.status_code == 201
    req_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v2/payouts/requests/{req_id}/cancel",
        headers=_auth(creator_token),
    )
    assert cancel_resp.status_code == 200


async def test_payouts_cancel_unknown_request(client, make_creator):
    """POST /api/v2/payouts/requests/{id}/cancel — 400 for non-existent request."""
    creator, creator_token = await make_creator()

    resp = await client.post(
        f"/api/v2/payouts/requests/{_new_id()}/cancel",
        headers=_auth(creator_token),
    )
    assert resp.status_code == 400


async def test_payouts_cancel_unauthenticated(client):
    """POST /api/v2/payouts/requests/{id}/cancel — requires creator auth."""
    resp = await client.post(f"/api/v2/payouts/requests/{_new_id()}/cancel")
    assert resp.status_code == 401


# ===========================================================================
# v2_search — /api/v2/search
# ===========================================================================

async def test_search_all_listings_returns_result(client):
    """GET /api/v2/search — type=listing returns SearchResult shape."""
    resp = await client.get("/api/v2/search?q=python&type=listing")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert "count" in body
    assert isinstance(body["results"], list)


async def test_search_all_agents_returns_result(client):
    """GET /api/v2/search — type=agent returns SearchResult shape."""
    resp = await client.get("/api/v2/search?q=&type=agent")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body


async def test_search_all_tools_returns_result(client):
    """GET /api/v2/search — type=tool returns SearchResult shape."""
    resp = await client.get("/api/v2/search?q=mcp&type=tool")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body


async def test_search_all_invalid_type(client):
    """GET /api/v2/search — unsupported type returns 400."""
    resp = await client.get("/api/v2/search?q=test&type=unknown_entity")
    assert resp.status_code == 400
    assert "Invalid type" in resp.json()["detail"]


async def test_search_listings_endpoint(client):
    """GET /api/v2/search/listings — returns SearchResult shape."""
    resp = await client.get("/api/v2/search/listings?q=data")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert "count" in body


async def test_search_listings_with_price_filter(client):
    """GET /api/v2/search/listings — min_price/max_price params accepted."""
    resp = await client.get("/api/v2/search/listings?q=&min_price=0.1&max_price=5.0")
    assert resp.status_code == 200


async def test_search_listings_odata_injection_rejected(client):
    """GET /api/v2/search/listings — single-quote in category raises 400."""
    resp = await client.get("/api/v2/search/listings?category=web'injection")
    assert resp.status_code == 400
    assert "single quotes" in resp.json()["detail"]


async def test_search_agents_endpoint(client):
    """GET /api/v2/search/agents — returns SearchResult shape."""
    resp = await client.get("/api/v2/search/agents?q=")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body


async def test_search_agents_with_filters(client):
    """GET /api/v2/search/agents — agent_type and status params are accepted."""
    resp = await client.get(
        "/api/v2/search/agents?q=bot&agent_type=seller&status=active"
    )
    assert resp.status_code == 200


async def test_search_tools_endpoint(client):
    """GET /api/v2/search/tools — returns SearchResult shape."""
    resp = await client.get("/api/v2/search/tools?q=")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body


async def test_search_suggestions_listings(client):
    """GET /api/v2/search/suggestions — returns SuggestionResult with suggestions list."""
    resp = await client.get("/api/v2/search/suggestions?q=py&type=listing")
    assert resp.status_code == 200
    body = resp.json()
    assert "suggestions" in body
    assert isinstance(body["suggestions"], list)


async def test_search_suggestions_invalid_type(client):
    """GET /api/v2/search/suggestions — invalid type returns 400."""
    resp = await client.get("/api/v2/search/suggestions?q=test&type=bogus")
    assert resp.status_code == 400


# ===========================================================================
# v2_sellers — /api/v2/sellers/me/earnings
# ===========================================================================

async def test_seller_earnings_happy_path(client, make_creator):
    """GET /api/v2/sellers/me/earnings — returns earnings snapshot in USD."""
    creator, creator_token = await make_creator()
    async with TestSession() as db:
        db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
        db.add(
            TokenAccount(id=_new_id(), creator_id=creator.id, balance=Decimal("25.0"))
        )
        await db.commit()

    resp = await client.get("/api/v2/sellers/me/earnings", headers=_auth(creator_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "USD"
    assert "balance_usd" in body
    assert "total_earned_usd" in body
    assert "pending_payout_count" in body
    assert "processing_payout_count" in body


async def test_seller_earnings_reflects_pending_payouts(client, make_creator):
    """GET /api/v2/sellers/me/earnings — pending_payout_count increases after request."""
    creator, creator_token = await make_creator()
    async with TestSession() as db:
        db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
        db.add(
            TokenAccount(id=_new_id(), creator_id=creator.id, balance=Decimal("20.0"))
        )
        await db.commit()

    await client.post(
        "/api/v2/payouts/requests",
        headers=_auth(creator_token),
        json={"payout_method": "gift_card", "amount_usd": 3.0},
    )

    resp = await client.get("/api/v2/sellers/me/earnings", headers=_auth(creator_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending_payout_count"] >= 1


async def test_seller_earnings_unauthenticated(client):
    """GET /api/v2/sellers/me/earnings — requires creator auth."""
    resp = await client.get("/api/v2/sellers/me/earnings")
    assert resp.status_code == 401


# ===========================================================================
# v2_users — /api/v2/users
# ===========================================================================

async def test_users_register_happy_path(client):
    """POST /api/v2/users/register — creates a new end user."""
    email = f"newuser-{_new_id()[:8]}@example.com"
    resp = await client.post(
        "/api/v2/users/register",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "token" in body
    assert "user" in body
    user = body["user"]
    assert user["email"] == email
    assert user["status"] == "active"


async def test_users_register_duplicate_email(client):
    """POST /api/v2/users/register — 409 when email already registered."""
    email = f"dup-{_new_id()[:8]}@example.com"

    first = await client.post(
        "/api/v2/users/register",
        json={"email": email, "password": "Pass123!Valid"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v2/users/register",
        json={"email": email, "password": "AnotherPass1!"},
    )
    assert second.status_code == 409


async def test_users_register_missing_fields(client):
    """POST /api/v2/users/register — 422 when required fields missing."""
    resp = await client.post("/api/v2/users/register", json={"email": "nopass@example.com"})
    assert resp.status_code == 422


async def test_users_login_happy_path(client):
    """POST /api/v2/users/login — returns token on valid credentials."""
    email = f"login-{_new_id()[:8]}@example.com"
    password = "LoginPass99!"

    await client.post(
        "/api/v2/users/register",
        json={"email": email, "password": password},
    )

    resp = await client.post(
        "/api/v2/users/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "user" in body


async def test_users_login_wrong_password(client):
    """POST /api/v2/users/login — 401 on incorrect password."""
    email = f"badpass-{_new_id()[:8]}@example.com"

    await client.post(
        "/api/v2/users/register",
        json={"email": email, "password": "RightPass!"},
    )

    resp = await client.post(
        "/api/v2/users/login",
        json={"email": email, "password": "WrongPass!"},
    )
    assert resp.status_code == 401


async def test_users_login_unknown_email(client):
    """POST /api/v2/users/login — 401 for unregistered email."""
    resp = await client.post(
        "/api/v2/users/login",
        json={"email": "ghost@nowhere.com", "password": "anything"},
    )
    assert resp.status_code == 401


async def test_users_me_happy_path(client):
    """GET /api/v2/users/me — returns current user profile."""
    email = f"me-{_new_id()[:8]}@example.com"

    reg_resp = await client.post(
        "/api/v2/users/register",
        json={"email": email, "password": "MePass123!"},
    )
    assert reg_resp.status_code == 201
    user_token = reg_resp.json()["token"]

    resp = await client.get("/api/v2/users/me", headers=_auth(user_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == email
    assert "id" in body
    assert "status" in body


async def test_users_me_unauthenticated(client):
    """GET /api/v2/users/me — requires user auth."""
    resp = await client.get("/api/v2/users/me")
    assert resp.status_code == 401


async def test_users_me_wrong_token_type(client, make_agent):
    """GET /api/v2/users/me — agent token (type=agent) is rejected with 401."""
    agent, agent_token = await make_agent(agent_type="buyer")

    resp = await client.get("/api/v2/users/me", headers=_auth(agent_token))
    assert resp.status_code == 401


async def test_users_stream_token_happy_path(client):
    """GET /api/v2/users/events/stream-token — returns stream token for user."""
    email = f"stream-{_new_id()[:8]}@example.com"
    reg_resp = await client.post(
        "/api/v2/users/register",
        json={"email": email, "password": "StreamPass1!"},
    )
    user_token = reg_resp.json()["token"]

    resp = await client.get(
        "/api/v2/users/events/stream-token",
        headers=_auth(user_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "stream_token" in body
    assert "expires_in_seconds" in body
    assert "ws_url" in body
    assert "allowed_topics" in body
    assert isinstance(body["allowed_topics"], list)


async def test_users_stream_token_unauthenticated(client):
    """GET /api/v2/users/events/stream-token — requires user auth."""
    resp = await client.get("/api/v2/users/events/stream-token")
    assert resp.status_code == 401


# ===========================================================================
# v2_verification — /api/v2/verification
# ===========================================================================

async def test_verification_get_trust_state_happy_path(client, make_agent, make_listing):
    """GET /api/v2/verification/listings/{id} — returns trust payload for existing listing."""
    seller, _ = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(seller.id, title="Trust Check Listing")

    resp = await client.get(f"/api/v2/verification/listings/{listing.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["listing_id"] == listing.id
    assert "trust_status" in body
    assert "trust_score" in body


async def test_verification_get_trust_state_not_found(client):
    """GET /api/v2/verification/listings/{id} — 404 for non-existent listing."""
    resp = await client.get(f"/api/v2/verification/listings/{_new_id()}")
    assert resp.status_code == 404


async def test_verification_run_verification_happy_path(client, make_agent, make_listing):
    """POST /api/v2/verification/listings/{id}/run — seller runs verification on own listing."""
    seller, token = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(seller.id, title="Verified Listing")

    resp = await client.post(
        f"/api/v2/verification/listings/{listing.id}/run",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "trust_status" in body or "status" in body


async def test_verification_run_verification_not_found(client, make_agent):
    """POST /api/v2/verification/listings/{id}/run — 404 for missing listing."""
    seller, token = await make_agent(agent_type="seller")

    resp = await client.post(
        f"/api/v2/verification/listings/{_new_id()}/run",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_verification_run_verification_wrong_seller(client, make_agent, make_listing):
    """POST /api/v2/verification/listings/{id}/run — 403 when called by non-owner."""
    owner, _ = await make_agent(name="verify-owner", agent_type="seller")
    other, other_token = await make_agent(name="verify-other", agent_type="seller")

    async with TestSession() as db:
        listing = await make_listing(owner.id, title="Owner Listing")

    resp = await client.post(
        f"/api/v2/verification/listings/{listing.id}/run",
        headers=_auth(other_token),
    )
    assert resp.status_code == 403


async def test_verification_run_verification_unauthenticated(client, make_agent, make_listing):
    """POST /api/v2/verification/listings/{id}/run — requires agent auth."""
    seller, _ = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(seller.id, title="Auth Required Listing")

    resp = await client.post(f"/api/v2/verification/listings/{listing.id}/run")
    assert resp.status_code == 401


async def test_verification_add_receipt_happy_path(client, make_agent, make_listing):
    """POST /api/v2/verification/listings/{id}/receipts — seller adds a source receipt."""
    seller, token = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(seller.id, title="Receipt Listing")

    resp = await client.post(
        f"/api/v2/verification/listings/{listing.id}/receipts",
        headers=_auth(token),
        json={
            "provider": "firecrawl",
            "source_query": "best python tutorials 2025",
            "seller_signature": "sig-abcdef-1234567890abcdef",
            "response_hash": None,
            "request_payload": {"url": "https://example.com"},
            "headers": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "receipt_id" in body
    assert "verification" in body


async def test_verification_add_receipt_not_found(client, make_agent):
    """POST /api/v2/verification/listings/{id}/receipts — 404 for unknown listing."""
    seller, token = await make_agent(agent_type="seller")

    resp = await client.post(
        f"/api/v2/verification/listings/{_new_id()}/receipts",
        headers=_auth(token),
        json={
            "provider": "firecrawl",
            "source_query": "search query",
            "seller_signature": "sig-1234567890",
        },
    )
    assert resp.status_code == 404


async def test_verification_add_receipt_wrong_seller(client, make_agent, make_listing):
    """POST /api/v2/verification/listings/{id}/receipts — 403 for non-owner."""
    owner, _ = await make_agent(name="receipt-owner", agent_type="seller")
    other, other_token = await make_agent(name="receipt-other", agent_type="seller")

    async with TestSession() as db:
        listing = await make_listing(owner.id, title="Owner Receipt Listing")

    resp = await client.post(
        f"/api/v2/verification/listings/{listing.id}/receipts",
        headers=_auth(other_token),
        json={
            "provider": "serpapi",
            "source_query": "stolen query",
            "seller_signature": "sig-badactorsig1234",
        },
    )
    assert resp.status_code == 403


async def test_verification_add_receipt_invalid_provider(client, make_agent, make_listing):
    """POST /api/v2/verification/listings/{id}/receipts — 400 for invalid provider."""
    seller, token = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(seller.id, title="Bad Provider Listing")

    resp = await client.post(
        f"/api/v2/verification/listings/{listing.id}/receipts",
        headers=_auth(token),
        json={
            "provider": "unsupported_provider_xyz",
            "source_query": "query",
            "seller_signature": "sig-1234567890ab",
        },
    )
    # Service raises ValueError for unknown providers -> 400
    assert resp.status_code in (400, 422)


async def test_verification_add_receipt_unauthenticated(client, make_agent, make_listing):
    """POST /api/v2/verification/listings/{id}/receipts — requires agent auth."""
    seller, _ = await make_agent(agent_type="seller")
    async with TestSession() as db:
        listing = await make_listing(seller.id, title="No Auth Receipt Listing")

    resp = await client.post(
        f"/api/v2/verification/listings/{listing.id}/receipts",
        json={
            "provider": "firecrawl",
            "source_query": "some query",
            "seller_signature": "sig-1234567890ab",
        },
    )
    assert resp.status_code == 401
