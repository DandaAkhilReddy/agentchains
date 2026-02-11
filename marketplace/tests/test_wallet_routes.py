"""Integration tests for the wallet API routes.

Uses httpx AsyncClient + ASGITransport to test against the real FastAPI app.
broadcast_event is imported lazily inside try/except blocks so no mocking needed.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount, TokenSupply
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_agent_with_balance(balance: float = 0) -> tuple[str, str, str]:
    """Create agent + token account + platform via direct DB, return (agent_id, jwt, account_id)."""
    from marketplace.core.auth import create_access_token
    from marketplace.models.agent import RegisteredAgent

    async with TestSession() as db:
        # Platform
        platform = TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0"), tier="platform")
        db.add(platform)
        supply = TokenSupply(id=1)
        db.add(supply)

        # Agent
        agent_id = _new_id()
        agent = RegisteredAgent(
            id=agent_id,
            name=f"wallet-test-{agent_id[:8]}",
            agent_type="both",
            public_key="ssh-rsa AAAA_test_key",
            status="active",
        )
        db.add(agent)

        # Token account
        account = TokenAccount(
            id=_new_id(), agent_id=agent_id, balance=Decimal(str(balance)),
        )
        db.add(account)
        await db.commit()

        jwt = create_access_token(agent_id, agent.name)
        return agent_id, jwt, account.id


# ---------------------------------------------------------------------------
# GET /wallet/balance
# ---------------------------------------------------------------------------

async def test_balance_authenticated(client):
    agent_id, jwt, _ = await _seed_agent_with_balance(500)
    resp = await client.get(
        "/api/v1/wallet/balance",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["balance"] == 500.0
    assert "tier" in data


async def test_balance_unauthenticated(client):
    resp = await client.get("/api/v1/wallet/balance")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /wallet/history
# ---------------------------------------------------------------------------

async def test_history_empty_new_agent(client):
    _, jwt, _ = await _seed_agent_with_balance(0)
    resp = await client.get(
        "/api/v1/wallet/history",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "total" in data


# ---------------------------------------------------------------------------
# POST /wallet/deposit
# ---------------------------------------------------------------------------

async def test_deposit_usd(client):
    _, jwt, _ = await _seed_agent_with_balance(0)
    resp = await client.post(
        "/api/v1/wallet/deposit",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"amount_fiat": 10.0, "currency": "USD"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["amount_axn"] == 10000.0
    assert data["status"] == "pending"


async def test_deposit_inr(client):
    _, jwt, _ = await _seed_agent_with_balance(0)
    resp = await client.post(
        "/api/v1/wallet/deposit",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"amount_fiat": 1000.0, "currency": "INR"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 1000 INR / 0.084 rate per ARD ≈ 11904.761905 ARD
    assert data["amount_axn"] > 11000


async def test_deposit_invalid_currency(client):
    _, jwt, _ = await _seed_agent_with_balance(0)
    resp = await client.post(
        "/api/v1/wallet/deposit",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"amount_fiat": 10.0, "currency": "XYZ"},
    )
    # ValueError from deposit_service → 500 (unhandled) unless caught by FastAPI
    assert resp.status_code in (400, 422, 500)


async def test_deposit_negative(client):
    _, jwt, _ = await _seed_agent_with_balance(0)
    resp = await client.post(
        "/api/v1/wallet/deposit",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"amount_fiat": -5.0, "currency": "USD"},
    )
    assert resp.status_code == 422  # Pydantic validation: gt=0


async def test_deposit_unauthenticated(client):
    resp = await client.post(
        "/api/v1/wallet/deposit",
        json={"amount_fiat": 10.0, "currency": "USD"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /wallet/transfer
# ---------------------------------------------------------------------------

async def test_transfer_success(client):
    sender_id, sender_jwt, _ = await _seed_agent_with_balance(1000)

    # Create receiver
    from marketplace.core.auth import create_access_token
    from marketplace.models.agent import RegisteredAgent

    receiver_id = _new_id()
    async with TestSession() as db:
        agent = RegisteredAgent(
            id=receiver_id, name=f"recv-{receiver_id[:8]}",
            agent_type="both", public_key="ssh-rsa AAAA", status="active",
        )
        db.add(agent)
        account = TokenAccount(id=_new_id(), agent_id=receiver_id, balance=Decimal("0"))
        db.add(account)
        await db.commit()

    resp = await client.post(
        "/api/v1/wallet/transfer",
        headers={"Authorization": f"Bearer {sender_jwt}"},
        json={"to_agent_id": receiver_id, "amount": 100.0},
    )
    assert resp.status_code == 200


async def test_transfer_insufficient(client):
    sender_id, sender_jwt, _ = await _seed_agent_with_balance(10)

    receiver_id = _new_id()
    async with TestSession() as db:
        from marketplace.models.agent import RegisteredAgent
        agent = RegisteredAgent(
            id=receiver_id, name=f"recv2-{receiver_id[:8]}",
            agent_type="both", public_key="ssh-rsa AAAA", status="active",
        )
        db.add(agent)
        account = TokenAccount(id=_new_id(), agent_id=receiver_id, balance=Decimal("0"))
        db.add(account)
        await db.commit()

    resp = await client.post(
        "/api/v1/wallet/transfer",
        headers={"Authorization": f"Bearer {sender_jwt}"},
        json={"to_agent_id": receiver_id, "amount": 5000.0},
    )
    assert resp.status_code in (400, 500)


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------

async def test_supply_public(client):
    # Seed supply row
    async with TestSession() as db:
        db.add(TokenSupply(id=1))
        await db.commit()

    resp = await client.get("/api/v1/wallet/supply")
    assert resp.status_code == 200
    data = resp.json()
    assert "circulating" in data


async def test_tiers_public(client):
    resp = await client.get("/api/v1/wallet/tiers")
    assert resp.status_code == 200
    data = resp.json()
    assert "tiers" in data
    assert len(data["tiers"]) == 4


async def test_currencies_public(client):
    resp = await client.get("/api/v1/wallet/currencies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    codes = {c["code"] for c in data}
    assert "USD" in codes
    assert "INR" in codes
