"""Tests for marketplace/api/v2_sellers.py -- seller earnings endpoints.

All endpoints hit the real FastAPI app via the ``client`` fixture.
Creator token accounts are seeded directly into the in-memory SQLite database.
No external services to mock.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_creator_account(creator_id: str, balance: float = 25.0) -> None:
    """Seed a TokenAccount for a creator with the given balance."""
    async with TestSession() as db:
        acct = TokenAccount(
            id=_new_id(),
            agent_id=None,
            creator_id=creator_id,
            balance=Decimal(str(balance)),
            total_earned=Decimal(str(balance + 10)),
            total_spent=Decimal("5.0"),
            total_deposited=Decimal(str(balance + 15)),
            total_fees_paid=Decimal("1.50"),
        )
        db.add(acct)
        await db.commit()


# ===========================================================================
# GET /api/v2/sellers/me/earnings
# ===========================================================================


async def test_earnings_returns_usd_fields(client, make_creator):
    """GET /me/earnings returns all expected USD fields."""
    creator, token = await make_creator()
    await _create_creator_account(creator.id, balance=42.0)

    resp = await client.get(
        "/api/v2/sellers/me/earnings",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "USD"
    assert "balance_usd" in body
    assert "total_earned_usd" in body
    assert "total_spent_usd" in body
    assert "total_deposited_usd" in body
    assert "total_fees_paid_usd" in body
    assert "pending_payout_count" in body
    assert "processing_payout_count" in body


async def test_earnings_balance_matches_seeded_account(client, make_creator):
    """GET /me/earnings returns the correct balance from seeded account."""
    creator, token = await make_creator()
    await _create_creator_account(creator.id, balance=99.50)

    resp = await client.get(
        "/api/v2/sellers/me/earnings",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance_usd"] == pytest.approx(99.50, abs=0.01)


async def test_earnings_zero_when_no_account(client, make_creator):
    """GET /me/earnings returns zeroed-out earnings when no account exists."""
    _, token = await make_creator()

    resp = await client.get(
        "/api/v2/sellers/me/earnings",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance_usd"] == 0.0
    assert body["total_earned_usd"] == 0.0


async def test_earnings_payout_counts_default_zero(client, make_creator):
    """GET /me/earnings returns zero payout counts when no redemptions exist."""
    creator, token = await make_creator()
    await _create_creator_account(creator.id)

    resp = await client.get(
        "/api/v2/sellers/me/earnings",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending_payout_count"] == 0
    assert body["processing_payout_count"] == 0


async def test_earnings_rejects_missing_auth(client):
    """GET /me/earnings without auth returns 401."""
    resp = await client.get("/api/v2/sellers/me/earnings")
    assert resp.status_code == 401


async def test_earnings_rejects_invalid_token(client):
    """GET /me/earnings with invalid token returns 401."""
    resp = await client.get(
        "/api/v2/sellers/me/earnings",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert resp.status_code == 401


async def test_earnings_rejects_agent_token(client, make_agent):
    """GET /me/earnings rejects agent tokens (creator-only endpoint)."""
    _, agent_token = await make_agent()
    resp = await client.get(
        "/api/v2/sellers/me/earnings",
        headers=_auth(agent_token),
    )
    assert resp.status_code == 401


async def test_earnings_rejects_malformed_header(client):
    """GET /me/earnings with malformed auth header returns 401."""
    resp = await client.get(
        "/api/v2/sellers/me/earnings",
        headers={"Authorization": "Token abc123"},
    )
    assert resp.status_code == 401
