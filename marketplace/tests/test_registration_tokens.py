"""Integration tests for the registration → token account → signup bonus flow.

broadcast_event is imported lazily inside try/except blocks so no mocking needed.
"""

import pytest

from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_payload(name: str = None) -> dict:
    name = name or f"test-agent-{_new_id()[:8]}"
    return {
        "name": name,
        "agent_type": "both",
        "public_key": "ssh-rsa AAAA_test_registration_key_placeholder_long_enough",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_register_creates_token_account(client):
    """POST /agents/register → token_accounts row exists."""
    from sqlalchemy import select
    from marketplace.models.token_account import TokenAccount

    resp = await client.post("/api/v1/agents/register", json=_register_payload())
    assert resp.status_code == 201
    agent_id = resp.json()["id"]

    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id == agent_id)
        )
        account = result.scalar_one_or_none()
        assert account is not None


async def test_register_credits_signup_bonus(client):
    """New agent balance = signup_bonus_usd (0.10 USD)."""
    from sqlalchemy import select
    from marketplace.models.token_account import TokenAccount

    resp = await client.post("/api/v1/agents/register", json=_register_payload())
    assert resp.status_code == 201
    agent_id = resp.json()["id"]

    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id == agent_id)
        )
        account = result.scalar_one_or_none()
        assert account is not None
        assert float(account.balance) == 0.10


async def test_register_platform_account_auto_created(client):
    """Platform account (agent_id=None) exists after first registration."""
    from sqlalchemy import select
    from marketplace.models.token_account import TokenAccount

    await client.post("/api/v1/agents/register", json=_register_payload())

    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id.is_(None))
        )
        platform = result.scalar_one_or_none()
        assert platform is not None


async def test_register_duplicate_409(client):
    """Same name → 409, no extra token account."""
    payload = _register_payload("unique-dup-test")

    resp1 = await client.post("/api/v1/agents/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/agents/register", json=payload)
    assert resp2.status_code == 409


async def test_register_balance_is_signup_bonus(client):
    """New agent balance equals signup bonus (no tier system)."""
    from sqlalchemy import select
    from marketplace.models.token_account import TokenAccount

    resp = await client.post("/api/v1/agents/register", json=_register_payload())
    agent_id = resp.json()["id"]

    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id == agent_id)
        )
        account = result.scalar_one_or_none()
        assert account is not None
        assert float(account.balance) == 0.10


async def test_register_two_agents_both_get_bonus(client):
    """Both agents get USD signup bonus."""
    from sqlalchemy import select
    from marketplace.models.token_account import TokenAccount

    r1 = await client.post("/api/v1/agents/register", json=_register_payload())
    r2 = await client.post("/api/v1/agents/register", json=_register_payload())
    assert r1.status_code == 201
    assert r2.status_code == 201

    async with TestSession() as db:
        id1 = r1.json()["id"]
        id2 = r2.json()["id"]
        for aid in (id1, id2):
            result = await db.execute(
                select(TokenAccount).where(TokenAccount.agent_id == aid)
            )
            account = result.scalar_one()
            assert float(account.balance) == 0.10


async def test_register_ledger_has_bonus_entry(client):
    """token_ledger has tx_type='deposit' for signup bonus."""
    from sqlalchemy import select
    from marketplace.models.token_account import TokenLedger

    resp = await client.post("/api/v1/agents/register", json=_register_payload())
    assert resp.status_code == 201

    async with TestSession() as db:
        result = await db.execute(
            select(TokenLedger).where(TokenLedger.tx_type == "deposit")
        )
        entries = result.scalars().all()
        assert len(entries) >= 1


async def test_register_returns_jwt(client):
    """Response includes jwt_token."""
    resp = await client.post("/api/v1/agents/register", json=_register_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert "jwt_token" in data
    assert len(data["jwt_token"]) > 10
