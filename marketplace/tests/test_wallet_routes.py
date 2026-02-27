"""Integration tests for the wallet API routes.

Uses httpx AsyncClient + ASGITransport to test against the real FastAPI app.
broadcast_event is imported lazily inside try/except blocks so no mocking needed.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount
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
        platform = TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0"))
        db.add(platform)

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
        json={"amount_usd": 10.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["amount_usd"] == 10.0
    assert data["status"] == "pending"


async def test_deposit_negative(client):
    _, jwt, _ = await _seed_agent_with_balance(0)
    resp = await client.post(
        "/api/v1/wallet/deposit",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"amount_usd": -5.0},
    )
    assert resp.status_code == 422  # Pydantic validation: gt=0


async def test_deposit_unauthenticated(client):
    resp = await client.post(
        "/api/v1/wallet/deposit",
        json={"amount_usd": 10.0},
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


async def test_transfer_to_self_rejected(client):
    """Cannot transfer to yourself -> 400."""
    sender_id, sender_jwt, _ = await _seed_agent_with_balance(1000)
    resp = await client.post(
        "/api/v1/wallet/transfer",
        headers={"Authorization": f"Bearer {sender_jwt}"},
        json={"to_agent_id": sender_id, "amount": 100.0},
    )
    assert resp.status_code == 400
    assert "Cannot transfer to yourself" in resp.json()["detail"]


async def test_transfer_unauthenticated(client):
    """Transfer without auth -> 401."""
    resp = await client.post(
        "/api/v1/wallet/transfer",
        json={"to_agent_id": "some-id", "amount": 100.0},
    )
    assert resp.status_code == 401


async def test_deposit_confirm_success(client):
    """Confirm a pending deposit credits the agent."""
    agent_id, jwt, _ = await _seed_agent_with_balance(0)
    # Create deposit
    dep_resp = await client.post(
        "/api/v1/wallet/deposit",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"amount_usd": 25.0},
    )
    assert dep_resp.status_code == 200
    deposit_id = dep_resp.json()["id"]

    # Confirm deposit
    confirm_resp = await client.post(
        f"/api/v1/wallet/deposit/{deposit_id}/confirm",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()
    assert confirm_data["status"] == "completed"

    # Check balance increased
    bal_resp = await client.get(
        "/api/v1/wallet/balance",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert bal_resp.status_code == 200
    assert bal_resp.json()["balance"] >= 25.0


async def test_deposit_confirm_unauthenticated(client):
    """Confirm deposit without auth -> 401."""
    resp = await client.post("/api/v1/wallet/deposit/some-id/confirm")
    assert resp.status_code == 401


async def test_history_with_pagination(client):
    """History endpoint respects pagination params."""
    _, jwt, _ = await _seed_agent_with_balance(100)
    resp = await client.get(
        "/api/v1/wallet/history",
        headers={"Authorization": f"Bearer {jwt}"},
        params={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 5


async def test_transfer_with_memo(client):
    """Transfer with memo field included."""
    sender_id, sender_jwt, _ = await _seed_agent_with_balance(1000)
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
        json={"to_agent_id": receiver_id, "amount": 50.0, "memo": "payment for data"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["memo"] == "payment for data"


async def test_wallet_balance_direct(db):
    """Call wallet_balance function directly to cover return line."""
    from marketplace.api.wallet import wallet_balance, BalanceResponse
    from fastapi import Response
    agent_id, jwt, _ = await _seed_agent_with_balance(250)
    resp = Response()
    result = await wallet_balance(resp, db, agent_id)
    assert isinstance(result, BalanceResponse)
    assert result.balance == 250.0


async def test_wallet_history_direct(db):
    """Call wallet_history function directly to cover return line."""
    from marketplace.api.wallet import wallet_history, HistoryResponse
    from fastapi import Response
    agent_id, jwt, _ = await _seed_agent_with_balance(100)
    resp = Response()
    result = await wallet_history(resp, 1, 20, db, agent_id)
    assert isinstance(result, HistoryResponse)
    assert result.page == 1
    assert result.page_size == 20


async def test_wallet_deposit_direct(db):
    """Call wallet_deposit function directly."""
    from marketplace.api.wallet import wallet_deposit, DepositRequest
    from fastapi import Response
    agent_id, jwt, _ = await _seed_agent_with_balance(0)
    resp = Response()
    req = DepositRequest(amount_usd=15.0)
    result = await wallet_deposit(resp, req, db, agent_id)
    assert result["amount_usd"] == 15.0
    assert result["status"] == "pending"


async def test_wallet_deposit_confirm_direct(db):
    """Call wallet_confirm_deposit function directly."""
    from marketplace.api.wallet import wallet_confirm_deposit, wallet_deposit, DepositRequest
    from fastapi import Response
    agent_id, jwt, _ = await _seed_agent_with_balance(0)
    resp = Response()
    req = DepositRequest(amount_usd=30.0)
    deposit = await wallet_deposit(resp, req, db, agent_id)
    dep_id = deposit["id"]
    result = await wallet_confirm_deposit(resp, dep_id, db, agent_id)
    assert result["status"] == "completed"
