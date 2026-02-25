"""Tests for redemption (withdrawal) API endpoints.

Covers: marketplace/api/redemptions.py
  - POST   /api/v1/redemptions
  - GET    /api/v1/redemptions
  - GET    /api/v1/redemptions/methods
  - GET    /api/v1/redemptions/{redemption_id}
  - POST   /api/v1/redemptions/{redemption_id}/cancel
  - POST   /api/v1/redemptions/admin/{redemption_id}/approve
  - POST   /api/v1/redemptions/admin/{redemption_id}/reject
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from marketplace.config import settings
from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_creator_with_balance(make_creator, balance: float = 100.0):
    """Register a creator and seed a token account with the given balance."""
    creator, token = await make_creator()
    async with TestSession() as db:
        acct = TokenAccount(
            id=_new_id(),
            agent_id=None,
            creator_id=creator.id,
            balance=Decimal(str(balance)),
            total_earned=Decimal(str(balance)),
            total_spent=Decimal("0"),
            total_deposited=Decimal(str(balance)),
            total_fees_paid=Decimal("0"),
        )
        db.add(acct)
        await db.commit()
    return creator, token


# ===========================================================================
# POST /api/v1/redemptions
# ===========================================================================

class TestCreateRedemption:
    """Tests for creating withdrawal requests."""

    async def test_create_api_credits_happy_path(self, client, make_creator):
        creator, token = await _create_creator_with_balance(make_creator, balance=50.0)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "api_credits",
                "amount_usd": 5.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["redemption_type"] == "api_credits"
        assert body["amount_usd"] == pytest.approx(5.0)
        assert body["creator_id"] == creator.id
        # API credits are auto-processed to "completed"
        assert body["status"] == "completed"

    async def test_create_gift_card_happy_path(self, client, make_creator):
        creator, token = await _create_creator_with_balance(make_creator, balance=50.0)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "gift_card",
                "amount_usd": 10.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["redemption_type"] == "gift_card"
        assert body["status"] == "pending"

    async def test_create_bank_withdrawal_happy_path(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator, balance=100.0)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "bank_withdrawal",
                "amount_usd": 25.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["redemption_type"] == "bank_withdrawal"
        assert body["status"] == "pending"

    async def test_create_upi_happy_path(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator, balance=50.0)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "upi",
                "amount_usd": 10.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["redemption_type"] == "upi"
        assert body["status"] == "pending"

    async def test_create_below_minimum_returns_400(self, client, make_creator):
        """bank_withdrawal minimum is $10.00."""
        _, token = await _create_creator_with_balance(make_creator, balance=50.0)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "bank_withdrawal",
                "amount_usd": 5.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 400

    async def test_create_insufficient_balance_returns_400(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator, balance=2.0)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "gift_card",
                "amount_usd": 100.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 400
        assert "Insufficient" in resp.json()["detail"]

    async def test_create_no_token_account_returns_400(self, client, make_creator):
        """Creator without a token account should get a clear error."""
        _, token = await make_creator()

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "api_credits",
                "amount_usd": 1.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 400
        assert "no token account" in resp.json()["detail"].lower()

    async def test_create_invalid_redemption_type_returns_422(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "bitcoin",
                "amount_usd": 10.0,
                "currency": "USD",
            },
        )
        # Pydantic validation on the regex pattern should catch this
        assert resp.status_code == 422

    async def test_create_zero_amount_returns_422(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "api_credits",
                "amount_usd": 0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 422

    async def test_create_negative_amount_returns_422(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "api_credits",
                "amount_usd": -5.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 422

    async def test_create_rejects_missing_auth(self, client):
        resp = await client.post(
            "/api/v1/redemptions",
            json={
                "redemption_type": "api_credits",
                "amount_usd": 1.0,
                "currency": "USD",
            },
        )
        assert resp.status_code == 401

    async def test_create_has_deprecation_headers(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator)

        resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "redemption_type": "api_credits",
                "amount_usd": 1.0,
                "currency": "USD",
            },
        )
        assert resp.headers.get("Deprecation") == "true"
        assert "Sunset" in resp.headers


# ===========================================================================
# GET /api/v1/redemptions
# ===========================================================================

class TestListRedemptions:
    """Tests for listing redemption requests."""

    async def test_list_empty_returns_zero(self, client, make_creator):
        _, token = await make_creator()

        resp = await client.get(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["redemptions"] == []
        assert body["total"] == 0
        assert body["page"] == 1

    async def test_list_returns_created_redemptions(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator, balance=100.0)

        # Create two redemptions
        await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={"redemption_type": "api_credits", "amount_usd": 1.0, "currency": "USD"},
        )
        await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={"redemption_type": "gift_card", "amount_usd": 5.0, "currency": "USD"},
        )

        resp = await client.get(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["redemptions"]) == 2

    async def test_list_filter_by_status(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator, balance=100.0)

        # api_credits auto-completes, gift_card stays pending
        await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={"redemption_type": "api_credits", "amount_usd": 1.0, "currency": "USD"},
        )
        await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={"redemption_type": "gift_card", "amount_usd": 5.0, "currency": "USD"},
        )

        # Filter for completed only
        resp = await client.get(
            "/api/v1/redemptions?status=completed",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for r in body["redemptions"]:
            assert r["status"] == "completed"

    async def test_list_pagination(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator, balance=100.0)

        for _ in range(3):
            await client.post(
                "/api/v1/redemptions",
                headers={"Authorization": f"Bearer {token}"},
                json={"redemption_type": "api_credits", "amount_usd": 0.50, "currency": "USD"},
            )

        resp = await client.get(
            "/api/v1/redemptions?page=1&page_size=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["redemptions"]) == 2
        assert body["page"] == 1

    async def test_list_rejects_missing_auth(self, client):
        resp = await client.get("/api/v1/redemptions")
        assert resp.status_code == 401

    async def test_list_has_deprecation_headers(self, client, make_creator):
        _, token = await make_creator()
        resp = await client.get(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.headers.get("Deprecation") == "true"


# ===========================================================================
# GET /api/v1/redemptions/methods
# ===========================================================================

class TestRedemptionMethods:
    """Tests for retrieving available redemption methods."""

    async def test_methods_returns_all_types(self, client):
        resp = await client.get("/api/v1/redemptions/methods")
        assert resp.status_code == 200
        body = resp.json()
        assert "methods" in body
        types = {m["type"] for m in body["methods"]}
        assert "api_credits" in types
        assert "gift_card" in types
        assert "upi" in types
        assert "bank_withdrawal" in types

    async def test_methods_include_min_usd(self, client):
        resp = await client.get("/api/v1/redemptions/methods")
        body = resp.json()
        for method in body["methods"]:
            assert "min_usd" in method
            assert isinstance(method["min_usd"], (int, float))
            assert method["min_usd"] > 0

    async def test_methods_include_processing_time(self, client):
        resp = await client.get("/api/v1/redemptions/methods")
        body = resp.json()
        for method in body["methods"]:
            assert "processing_time" in method
            assert isinstance(method["processing_time"], str)

    async def test_methods_no_auth_required(self, client):
        """Methods endpoint should work without authentication."""
        resp = await client.get("/api/v1/redemptions/methods")
        assert resp.status_code == 200

    async def test_methods_has_deprecation_headers(self, client):
        resp = await client.get("/api/v1/redemptions/methods")
        assert resp.headers.get("Deprecation") == "true"


# ===========================================================================
# GET /api/v1/redemptions/{redemption_id}
# ===========================================================================

class TestGetRedemption:
    """Tests for retrieving a specific redemption by ID."""

    async def test_get_specific_redemption(self, client, make_creator):
        _, token = await _create_creator_with_balance(make_creator, balance=50.0)

        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={"redemption_type": "api_credits", "amount_usd": 2.0, "currency": "USD"},
        )
        redemption_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/redemptions/{redemption_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == redemption_id
        assert body["redemption_type"] == "api_credits"

    async def test_get_nonexistent_returns_404(self, client, make_creator):
        _, token = await make_creator()
        fake_id = str(uuid.uuid4())

        resp = await client.get(
            f"/api/v1/redemptions/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_get_other_creators_redemption_returns_404(self, client, make_creator):
        """Creator A should not see Creator B's redemptions."""
        _, token_a = await _create_creator_with_balance(make_creator, balance=50.0)
        _, token_b = await make_creator()

        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"redemption_type": "api_credits", "amount_usd": 1.0, "currency": "USD"},
        )
        redemption_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/redemptions/{redemption_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404

    async def test_get_rejects_missing_auth(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/redemptions/{fake_id}")
        assert resp.status_code == 401


# ===========================================================================
# POST /api/v1/redemptions/{redemption_id}/cancel
# ===========================================================================

class TestCancelRedemption:
    """Tests for cancelling a pending redemption."""

    async def test_cancel_pending_gift_card(self, client, make_creator):
        creator, token = await _create_creator_with_balance(make_creator, balance=50.0)

        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={"redemption_type": "gift_card", "amount_usd": 5.0, "currency": "USD"},
        )
        assert create_resp.status_code == 201
        redemption_id = create_resp.json()["id"]

        cancel_resp = await client.post(
            f"/api/v1/redemptions/{redemption_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel_resp.status_code == 200
        body = cancel_resp.json()
        assert body["status"] == "rejected"
        assert body["rejection_reason"] == "Cancelled by creator"

    async def test_cancel_completed_returns_400(self, client, make_creator):
        """Cannot cancel an already-completed redemption (api_credits auto-completes)."""
        _, token = await _create_creator_with_balance(make_creator, balance=50.0)

        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token}"},
            json={"redemption_type": "api_credits", "amount_usd": 1.0, "currency": "USD"},
        )
        redemption_id = create_resp.json()["id"]

        cancel_resp = await client.post(
            f"/api/v1/redemptions/{redemption_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel_resp.status_code == 400

    async def test_cancel_nonexistent_returns_400(self, client, make_creator):
        _, token = await make_creator()
        fake_id = str(uuid.uuid4())

        resp = await client.post(
            f"/api/v1/redemptions/{fake_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_cancel_other_creators_redemption_returns_400(self, client, make_creator):
        """Creator B cannot cancel Creator A's redemption."""
        _, token_a = await _create_creator_with_balance(make_creator, balance=50.0)
        _, token_b = await make_creator()

        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"redemption_type": "gift_card", "amount_usd": 5.0, "currency": "USD"},
        )
        redemption_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/redemptions/{redemption_id}/cancel",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 400

    async def test_cancel_rejects_missing_auth(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.post(f"/api/v1/redemptions/{fake_id}/cancel")
        assert resp.status_code == 401


# ===========================================================================
# POST /api/v1/redemptions/admin/{redemption_id}/approve
# ===========================================================================

class TestAdminApprove:
    """Tests for admin approval of redemptions."""

    async def test_admin_approve_happy_path(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        # Create a creator with a pending redemption
        _, user_token = await _create_creator_with_balance(make_creator, balance=50.0)
        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"redemption_type": "gift_card", "amount_usd": 5.0, "currency": "USD"},
        )
        assert create_resp.status_code == 201
        redemption_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/redemptions/admin/{redemption_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"admin_notes": "Approved after review"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Gift card goes to processing
        assert body["status"] in ("processing", "completed")

    async def test_admin_approve_rejects_non_admin(self, client, make_creator, monkeypatch):
        admin_creator, _ = await make_creator()
        _, non_admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.post(
            f"/api/v1/redemptions/admin/{str(uuid.uuid4())}/approve",
            headers={"Authorization": f"Bearer {non_admin_token}"},
            json={"admin_notes": ""},
        )
        assert resp.status_code == 403

    async def test_admin_approve_rejects_empty_admin_config(self, client, make_creator, monkeypatch):
        """When no admin IDs are configured, should return 403."""
        monkeypatch.setattr(settings, "admin_creator_ids", "")
        _, creator_token = await make_creator()

        resp = await client.post(
            f"/api/v1/redemptions/admin/{str(uuid.uuid4())}/approve",
            headers={"Authorization": f"Bearer {creator_token}"},
            json={"admin_notes": ""},
        )
        assert resp.status_code == 403
        assert "No admin accounts configured" in resp.json()["detail"]

    async def test_admin_approve_nonexistent_returns_400(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.post(
            f"/api/v1/redemptions/admin/{str(uuid.uuid4())}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"admin_notes": ""},
        )
        assert resp.status_code == 400

    async def test_admin_approve_rejects_missing_auth(self, client):
        resp = await client.post(
            f"/api/v1/redemptions/admin/{str(uuid.uuid4())}/approve",
            json={"admin_notes": ""},
        )
        assert resp.status_code == 401

    async def test_admin_approve_has_deprecation_headers(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        _, user_token = await _create_creator_with_balance(make_creator, balance=50.0)
        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"redemption_type": "gift_card", "amount_usd": 5.0, "currency": "USD"},
        )
        redemption_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/redemptions/admin/{redemption_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"admin_notes": ""},
        )
        assert resp.headers.get("Deprecation") == "true"


# ===========================================================================
# POST /api/v1/redemptions/admin/{redemption_id}/reject
# ===========================================================================

class TestAdminReject:
    """Tests for admin rejection of redemptions."""

    async def test_admin_reject_happy_path(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        _, user_token = await _create_creator_with_balance(make_creator, balance=50.0)
        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"redemption_type": "gift_card", "amount_usd": 5.0, "currency": "USD"},
        )
        redemption_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/redemptions/admin/{redemption_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Fraudulent activity detected"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
        assert body["rejection_reason"] == "Fraudulent activity detected"

    async def test_admin_reject_rejects_non_admin(self, client, make_creator, monkeypatch):
        admin_creator, _ = await make_creator()
        _, non_admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.post(
            f"/api/v1/redemptions/admin/{str(uuid.uuid4())}/reject",
            headers={"Authorization": f"Bearer {non_admin_token}"},
            json={"reason": "test"},
        )
        assert resp.status_code == 403

    async def test_admin_reject_requires_reason(self, client, make_creator, monkeypatch):
        """AdminRejectRequest requires a non-empty reason string."""
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.post(
            f"/api/v1/redemptions/admin/{str(uuid.uuid4())}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": ""},
        )
        # Empty reason violates min_length=1
        assert resp.status_code == 422

    async def test_admin_reject_nonexistent_returns_400(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.post(
            f"/api/v1/redemptions/admin/{str(uuid.uuid4())}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "not found"},
        )
        assert resp.status_code == 400

    async def test_admin_reject_refunds_balance(self, client, make_creator, monkeypatch):
        """Rejecting a redemption should refund the creator's balance."""
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        creator, user_token = await _create_creator_with_balance(make_creator, balance=50.0)
        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"redemption_type": "gift_card", "amount_usd": 10.0, "currency": "USD"},
        )
        redemption_id = create_resp.json()["id"]

        # Reject it
        reject_resp = await client.post(
            f"/api/v1/redemptions/admin/{redemption_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Rejected for testing"},
        )
        assert reject_resp.status_code == 200

        # Verify balance was refunded by checking earnings endpoint or listing again
        list_resp = await client.get(
            "/api/v1/redemptions?status=rejected",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert list_resp.status_code == 200
        rejected = list_resp.json()["redemptions"]
        assert any(r["id"] == redemption_id for r in rejected)

    async def test_admin_reject_rejects_missing_auth(self, client):
        resp = await client.post(
            f"/api/v1/redemptions/admin/{str(uuid.uuid4())}/reject",
            json={"reason": "test"},
        )
        assert resp.status_code == 401

    async def test_admin_reject_has_deprecation_headers(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        _, user_token = await _create_creator_with_balance(make_creator, balance=50.0)
        create_resp = await client.post(
            "/api/v1/redemptions",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"redemption_type": "gift_card", "amount_usd": 5.0, "currency": "USD"},
        )
        redemption_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/redemptions/admin/{redemption_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "test"},
        )
        assert resp.headers.get("Deprecation") == "true"
