"""Tests for marketplace/api/v2_payouts.py -- USD payout request endpoints.

All endpoints hit the real FastAPI app via the ``client`` fixture.
Creator accounts are seeded directly into the in-memory SQLite database.
Admin settings are temporarily overridden via ``object.__setattr__`` for
admin-only tests.
"""

from __future__ import annotations

from decimal import Decimal

from marketplace.config import settings
from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _creator_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_creator_account(creator_id: str, balance: float = 100.0) -> None:
    """Create a TokenAccount linked to a creator so the payout service can debit."""
    async with TestSession() as db:
        db.add(TokenAccount(
            id=_new_id(),
            agent_id=None,
            creator_id=creator_id,
            balance=Decimal(str(balance)),
        ))
        await db.commit()


# ---------------------------------------------------------------------------
# POST /api/v2/payouts/requests -- create payout request
# ---------------------------------------------------------------------------

async def test_create_payout_request_success(client, make_creator):
    """POST /requests creates a payout request."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=50.0)

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={
            "payout_method": "bank_transfer",
            "amount_usd": 20.0,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["creator_id"] == creator.id
    assert body["amount_usd"] == 20.0
    assert body["status"] in ("pending", "processing", "completed")


async def test_create_payout_request_api_credits_instant(client, make_creator):
    """POST /requests with api_credits method is processed instantly."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=10.0)

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={
            "payout_method": "api_credits",
            "amount_usd": 1.0,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["redemption_type"] == "api_credits"
    assert body["status"] == "completed"


async def test_create_payout_request_upi(client, make_creator):
    """POST /requests with UPI method is accepted."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=50.0)

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={
            "payout_method": "upi",
            "amount_usd": 10.0,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["redemption_type"] == "upi"


async def test_create_payout_unsupported_method(client, make_creator):
    """POST /requests with unsupported method returns 400."""
    creator, token = await make_creator()

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={
            "payout_method": "bitcoin",
            "amount_usd": 10.0,
        },
    )
    assert resp.status_code == 400
    assert "Unsupported payout_method" in resp.json()["detail"]


async def test_create_payout_below_minimum(client, make_creator):
    """POST /requests below minimum threshold returns 400."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=100.0)

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={
            "payout_method": "bank_transfer",
            "amount_usd": 1.0,
        },
    )
    assert resp.status_code == 400
    assert "Minimum" in resp.json()["detail"]


async def test_create_payout_no_auth(client):
    """POST /requests without auth returns 401."""
    resp = await client.post(
        "/api/v2/payouts/requests",
        json={
            "payout_method": "bank_transfer",
            "amount_usd": 20.0,
        },
    )
    assert resp.status_code == 401


async def test_create_payout_invalid_amount_zero(client, make_creator):
    """POST /requests with amount_usd=0 returns 422 (pydantic gt=0)."""
    creator, token = await make_creator()

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={
            "payout_method": "bank_transfer",
            "amount_usd": 0,
        },
    )
    assert resp.status_code == 422


async def test_create_payout_negative_amount(client, make_creator):
    """POST /requests with negative amount returns 422."""
    creator, token = await make_creator()

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={
            "payout_method": "bank_transfer",
            "amount_usd": -5.0,
        },
    )
    assert resp.status_code == 422


async def test_create_payout_exceeds_max(client, make_creator):
    """POST /requests exceeding le=100_000 returns 422."""
    creator, token = await make_creator()

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={
            "payout_method": "bank_transfer",
            "amount_usd": 200_000,
        },
    )
    assert resp.status_code == 422


async def test_create_payout_agent_token_rejected(client, make_agent):
    """POST /requests with agent token (not creator) returns 401."""
    _, agent_token = await make_agent()

    resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(agent_token),
        json={
            "payout_method": "bank_transfer",
            "amount_usd": 20.0,
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/payouts/requests -- list payout requests
# ---------------------------------------------------------------------------

async def test_list_payout_requests_empty(client, make_creator):
    """GET /requests returns empty list for a fresh creator."""
    creator, token = await make_creator()

    resp = await client.get(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["redemptions"] == []


async def test_list_payout_requests_with_data(client, make_creator):
    """GET /requests returns created payout requests."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=100.0)

    await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={"payout_method": "bank_transfer", "amount_usd": 20.0},
    )
    await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={"payout_method": "bank_transfer", "amount_usd": 15.0},
    )

    resp = await client.get(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["redemptions"]) == 2


async def test_list_payout_requests_filter_by_status(client, make_creator):
    """GET /requests?status=pending filters results."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=100.0)

    await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={"payout_method": "bank_transfer", "amount_usd": 20.0},
    )

    resp = await client.get(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        params={"status": "pending"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for entry in body["redemptions"]:
        assert entry["status"] == "pending"


async def test_list_payout_requests_pagination(client, make_creator):
    """GET /requests respects pagination parameters."""
    creator, token = await make_creator()

    resp = await client.get(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        params={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 5


async def test_list_payout_requests_no_auth(client):
    """GET /requests without auth returns 401."""
    resp = await client.get("/api/v2/payouts/requests")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v2/payouts/requests/{request_id}/cancel
# ---------------------------------------------------------------------------

async def test_cancel_payout_request_success(client, make_creator):
    """POST /requests/{id}/cancel cancels a pending payout."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=100.0)

    create_resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={"payout_method": "bank_transfer", "amount_usd": 20.0},
    )
    assert create_resp.status_code == 201
    request_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v2/payouts/requests/{request_id}/cancel",
        headers=_creator_auth(token),
    )
    assert cancel_resp.status_code == 200
    body = cancel_resp.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Cancelled by creator"


async def test_cancel_payout_request_not_found(client, make_creator):
    """POST /requests/{id}/cancel for unknown request returns 400."""
    creator, token = await make_creator()

    resp = await client.post(
        f"/api/v2/payouts/requests/{_new_id()}/cancel",
        headers=_creator_auth(token),
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


async def test_cancel_payout_request_no_auth(client):
    """POST /requests/{id}/cancel without auth returns 401."""
    resp = await client.post(f"/api/v2/payouts/requests/{_new_id()}/cancel")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v2/payouts/requests/{request_id}/approve
# ---------------------------------------------------------------------------

async def test_approve_payout_no_admin_configured(client, make_creator):
    """POST /requests/{id}/approve without admin config returns 403."""
    creator, token = await make_creator()
    original = settings.admin_creator_ids

    try:
        object.__setattr__(settings, "admin_creator_ids", "")
        resp = await client.post(
            f"/api/v2/payouts/requests/{_new_id()}/approve",
            headers=_creator_auth(token),
            json={"admin_notes": "approved"},
        )
    finally:
        object.__setattr__(settings, "admin_creator_ids", original)

    assert resp.status_code == 403
    assert "No admin accounts configured" in resp.json()["detail"]


async def test_approve_payout_non_admin_rejected(client, make_creator):
    """POST /requests/{id}/approve by non-admin creator returns 403."""
    creator, token = await make_creator()
    original = settings.admin_creator_ids

    try:
        object.__setattr__(settings, "admin_creator_ids", "some-other-admin-id")
        resp = await client.post(
            f"/api/v2/payouts/requests/{_new_id()}/approve",
            headers=_creator_auth(token),
            json={"admin_notes": "approved"},
        )
    finally:
        object.__setattr__(settings, "admin_creator_ids", original)

    assert resp.status_code == 403
    assert "Admin access required" in resp.json()["detail"]


async def test_approve_payout_as_admin_success(client, make_creator):
    """POST /requests/{id}/approve by admin succeeds."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=100.0)

    create_resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={"payout_method": "gift_card", "amount_usd": 5.0},
    )
    assert create_resp.status_code == 201
    request_id = create_resp.json()["id"]

    original = settings.admin_creator_ids
    try:
        object.__setattr__(settings, "admin_creator_ids", creator.id)
        resp = await client.post(
            f"/api/v2/payouts/requests/{request_id}/approve",
            headers=_creator_auth(token),
            json={"admin_notes": "looks good"},
        )
    finally:
        object.__setattr__(settings, "admin_creator_ids", original)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("processing", "completed")


async def test_approve_payout_no_auth(client):
    """POST /requests/{id}/approve without auth returns 401."""
    resp = await client.post(
        f"/api/v2/payouts/requests/{_new_id()}/approve",
        json={"admin_notes": ""},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v2/payouts/requests/{request_id}/reject
# ---------------------------------------------------------------------------

async def test_reject_payout_non_admin_rejected(client, make_creator):
    """POST /requests/{id}/reject by non-admin returns 403."""
    creator, token = await make_creator()
    original = settings.admin_creator_ids

    try:
        object.__setattr__(settings, "admin_creator_ids", "some-other-admin-id")
        resp = await client.post(
            f"/api/v2/payouts/requests/{_new_id()}/reject",
            headers=_creator_auth(token),
            json={"reason": "fraudulent"},
        )
    finally:
        object.__setattr__(settings, "admin_creator_ids", original)

    assert resp.status_code == 403


async def test_reject_payout_as_admin_success(client, make_creator):
    """POST /requests/{id}/reject by admin succeeds."""
    creator, token = await make_creator()
    await _seed_creator_account(creator.id, balance=100.0)

    create_resp = await client.post(
        "/api/v2/payouts/requests",
        headers=_creator_auth(token),
        json={"payout_method": "bank_transfer", "amount_usd": 20.0},
    )
    assert create_resp.status_code == 201
    request_id = create_resp.json()["id"]

    original = settings.admin_creator_ids
    try:
        object.__setattr__(settings, "admin_creator_ids", creator.id)
        resp = await client.post(
            f"/api/v2/payouts/requests/{request_id}/reject",
            headers=_creator_auth(token),
            json={"reason": "Suspicious activity"},
        )
    finally:
        object.__setattr__(settings, "admin_creator_ids", original)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Suspicious activity"


async def test_reject_payout_missing_reason(client, make_creator):
    """POST /requests/{id}/reject with empty reason returns 422."""
    creator, token = await make_creator()

    resp = await client.post(
        f"/api/v2/payouts/requests/{_new_id()}/reject",
        headers=_creator_auth(token),
        json={"reason": ""},
    )
    assert resp.status_code == 422


async def test_reject_payout_no_auth(client):
    """POST /requests/{id}/reject without auth returns 401."""
    resp = await client.post(
        f"/api/v2/payouts/requests/{_new_id()}/reject",
        json={"reason": "nope"},
    )
    assert resp.status_code == 401


async def test_reject_payout_not_found(client, make_creator):
    """POST /requests/{id}/reject for unknown request returns 400."""
    creator, token = await make_creator()
    original = settings.admin_creator_ids

    try:
        object.__setattr__(settings, "admin_creator_ids", creator.id)
        resp = await client.post(
            f"/api/v2/payouts/requests/{_new_id()}/reject",
            headers=_creator_auth(token),
            json={"reason": "bad"},
        )
    finally:
        object.__setattr__(settings, "admin_creator_ids", original)

    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


async def test_normalize_payout_method_mapping():
    """Test _normalize_payout_method for all supported mappings."""
    from marketplace.api.v2_payouts import _normalize_payout_method
    assert _normalize_payout_method("bank_transfer") == "bank_withdrawal"
    assert _normalize_payout_method("bank_withdrawal") == "bank_withdrawal"
    assert _normalize_payout_method("upi") == "upi"
    assert _normalize_payout_method("gift_card") == "gift_card"
    assert _normalize_payout_method("api_credits") == "api_credits"


async def test_normalize_payout_method_unsupported():
    """Test _normalize_payout_method raises for unsupported method."""
    from marketplace.api.v2_payouts import _normalize_payout_method
    import pytest as pt
    with pt.raises(ValueError, match="Unsupported payout_method"):
        _normalize_payout_method("bitcoin")


async def test_reject_payout_no_admin_configured_v2(client, make_creator):
    """POST /requests/{id}/reject with no admin configured -> 403."""
    creator, token = await make_creator()
    original = settings.admin_creator_ids
    try:
        object.__setattr__(settings, "admin_creator_ids", "")
        resp = await client.post(
            f"/api/v2/payouts/requests/{_new_id()}/reject",
            headers=_creator_auth(token),
            json={"reason": "bad"},
        )
    finally:
        object.__setattr__(settings, "admin_creator_ids", original)
    assert resp.status_code == 403
    assert "No admin accounts configured" in resp.json()["detail"]
