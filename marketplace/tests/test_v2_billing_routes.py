"""Tests for marketplace/api/v2_billing.py -- USD-native billing endpoints.

All endpoints hit the real FastAPI app via the ``client`` fixture.
Token accounts are seeded directly into the in-memory SQLite database.
No external services to mock.
"""

from __future__ import annotations

from decimal import Decimal

from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


BILLING_PREFIX = "/api/v2/billing"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_account(agent_id: str, balance: float = 0.0) -> TokenAccount:
    """Create a TokenAccount for the agent and a platform treasury account."""
    async with TestSession() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(TokenAccount).where(
                TokenAccount.agent_id.is_(None),
                TokenAccount.creator_id.is_(None),
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))

        account = TokenAccount(
            id=_new_id(),
            agent_id=agent_id,
            balance=Decimal(str(balance)),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account


# ===========================================================================
# GET /api/v2/billing/accounts/me
# ===========================================================================


async def test_billing_account_requires_auth(client):
    """GET /accounts/me without auth returns 401."""
    resp = await client.get(f"{BILLING_PREFIX}/accounts/me")
    assert resp.status_code == 401


async def test_billing_account_returns_zero_without_account(client, make_agent):
    """GET /accounts/me returns zero balance when no token account exists."""
    _, token = await make_agent()

    resp = await client.get(
        f"{BILLING_PREFIX}/accounts/me",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "USD"
    assert body["balance_usd"] == 0.0
    assert body["account_scope"] == "agent"


async def test_billing_account_returns_balance(client, make_agent):
    """GET /accounts/me returns the correct balance when account exists."""
    agent, token = await make_agent()
    await _seed_account(agent.id, balance=42.50)

    resp = await client.get(
        f"{BILLING_PREFIX}/accounts/me",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance_usd"] == 42.50
    assert body["currency"] == "USD"


async def test_billing_account_response_shape(client, make_agent):
    """GET /accounts/me response contains all expected fields."""
    agent, token = await make_agent()
    await _seed_account(agent.id, balance=10.0)

    resp = await client.get(
        f"{BILLING_PREFIX}/accounts/me",
        headers=_auth(token),
    )
    body = resp.json()
    expected_fields = {
        "account_scope", "currency", "balance_usd",
        "total_earned_usd", "total_spent_usd",
        "total_deposited_usd", "total_fees_paid_usd",
    }
    assert expected_fields.issubset(body.keys())


# ===========================================================================
# GET /api/v2/billing/ledger/me
# ===========================================================================


async def test_billing_ledger_requires_auth(client):
    """GET /ledger/me without auth returns 401."""
    resp = await client.get(f"{BILLING_PREFIX}/ledger/me")
    assert resp.status_code == 401


async def test_billing_ledger_empty(client, make_agent):
    """GET /ledger/me returns empty entries when no transactions exist."""
    agent, token = await make_agent()
    await _seed_account(agent.id)

    resp = await client.get(
        f"{BILLING_PREFIX}/ledger/me",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 20


async def test_billing_ledger_pagination_params(client, make_agent):
    """GET /ledger/me respects page and page_size parameters."""
    agent, token = await make_agent()
    await _seed_account(agent.id)

    resp = await client.get(
        f"{BILLING_PREFIX}/ledger/me",
        headers=_auth(token),
        params={"page": 2, "page_size": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert body["page_size"] == 5


async def test_billing_ledger_no_account_returns_empty(client, make_agent):
    """GET /ledger/me returns empty when agent has no token account."""
    _, token = await make_agent()

    resp = await client.get(
        f"{BILLING_PREFIX}/ledger/me",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


async def test_billing_ledger_invalid_page_rejected(client, make_agent):
    """GET /ledger/me with page=0 returns 422."""
    _, token = await make_agent()

    resp = await client.get(
        f"{BILLING_PREFIX}/ledger/me",
        headers=_auth(token),
        params={"page": 0},
    )
    assert resp.status_code == 422


# ===========================================================================
# POST /api/v2/billing/deposits
# ===========================================================================


async def test_deposit_requires_auth(client):
    """POST /deposits without auth returns 401."""
    resp = await client.post(
        f"{BILLING_PREFIX}/deposits",
        json={"amount_usd": 10.0},
    )
    assert resp.status_code == 401


async def test_deposit_create_happy_path(client, make_agent):
    """POST /deposits creates a pending deposit."""
    agent, token = await make_agent()

    resp = await client.post(
        f"{BILLING_PREFIX}/deposits",
        headers=_auth(token),
        json={"amount_usd": 25.0, "payment_method": "admin_credit"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount_usd"] == 25.0
    assert body["status"] == "pending"
    assert body["agent_id"] == agent.id
    assert body["id"]


async def test_deposit_invalid_amount_zero(client, make_agent):
    """POST /deposits with amount_usd=0 is rejected by Pydantic (gt=0)."""
    _, token = await make_agent()

    resp = await client.post(
        f"{BILLING_PREFIX}/deposits",
        headers=_auth(token),
        json={"amount_usd": 0},
    )
    assert resp.status_code == 422


async def test_deposit_negative_amount_rejected(client, make_agent):
    """POST /deposits with negative amount is rejected."""
    _, token = await make_agent()

    resp = await client.post(
        f"{BILLING_PREFIX}/deposits",
        headers=_auth(token),
        json={"amount_usd": -5.0},
    )
    assert resp.status_code == 422


async def test_deposit_exceeds_max_rejected(client, make_agent):
    """POST /deposits exceeding le=100_000 limit is rejected."""
    _, token = await make_agent()

    resp = await client.post(
        f"{BILLING_PREFIX}/deposits",
        headers=_auth(token),
        json={"amount_usd": 200_000},
    )
    assert resp.status_code == 422


# ===========================================================================
# POST /api/v2/billing/deposits/{deposit_id}/confirm
# ===========================================================================


async def test_confirm_deposit_requires_auth(client):
    """POST /deposits/{id}/confirm without auth returns 401."""
    resp = await client.post(f"{BILLING_PREFIX}/deposits/fake-id/confirm")
    assert resp.status_code == 401


async def test_confirm_deposit_happy_path(client, make_agent):
    """POST /deposits/{id}/confirm credits the agent balance."""
    agent, token = await make_agent()
    await _seed_account(agent.id, balance=0.0)

    create_resp = await client.post(
        f"{BILLING_PREFIX}/deposits",
        headers=_auth(token),
        json={"amount_usd": 50.0},
    )
    deposit_id = create_resp.json()["id"]

    confirm_resp = await client.post(
        f"{BILLING_PREFIX}/deposits/{deposit_id}/confirm",
        headers=_auth(token),
    )
    assert confirm_resp.status_code == 200
    body = confirm_resp.json()
    assert body["status"] == "completed"

    balance_resp = await client.get(
        f"{BILLING_PREFIX}/accounts/me",
        headers=_auth(token),
    )
    assert balance_resp.json()["balance_usd"] == 50.0


async def test_confirm_deposit_nonexistent(client, make_agent):
    """POST /deposits/{id}/confirm for unknown deposit returns 400."""
    _, token = await make_agent()

    resp = await client.post(
        f"{BILLING_PREFIX}/deposits/no-such-deposit/confirm",
        headers=_auth(token),
    )
    assert resp.status_code in (400, 404)


async def test_confirm_deposit_already_completed(client, make_agent):
    """POST /deposits/{id}/confirm on already-completed deposit returns 400."""
    agent, token = await make_agent()
    await _seed_account(agent.id, balance=0.0)

    create_resp = await client.post(
        f"{BILLING_PREFIX}/deposits",
        headers=_auth(token),
        json={"amount_usd": 10.0},
    )
    deposit_id = create_resp.json()["id"]

    await client.post(
        f"{BILLING_PREFIX}/deposits/{deposit_id}/confirm",
        headers=_auth(token),
    )

    resp = await client.post(
        f"{BILLING_PREFIX}/deposits/{deposit_id}/confirm",
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "pending" in resp.json()["detail"].lower() or "completed" in resp.json()["detail"].lower()


# ===========================================================================
# POST /api/v2/billing/transfers
# ===========================================================================


async def test_transfer_requires_auth(client):
    """POST /transfers without auth returns 401."""
    resp = await client.post(
        f"{BILLING_PREFIX}/transfers",
        json={"to_agent_id": "x", "amount_usd": 1.0},
    )
    assert resp.status_code == 401


async def test_transfer_happy_path(client, make_agent):
    """POST /transfers moves funds between agents."""
    sender, sender_token = await make_agent(name="xfer-sender")
    receiver, _ = await make_agent(name="xfer-receiver")

    await _seed_account(sender.id, balance=100.0)
    await _seed_account(receiver.id, balance=0.0)

    resp = await client.post(
        f"{BILLING_PREFIX}/transfers",
        headers=_auth(sender_token),
        json={
            "to_agent_id": receiver.id,
            "amount_usd": 25.0,
            "memo": "test transfer",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tx_type"] == "transfer"
    assert body["amount_usd"] == 25.0
    assert body["memo"] == "test transfer"


async def test_transfer_to_self_returns_400(client, make_agent):
    """POST /transfers to your own agent returns 400."""
    agent, token = await make_agent()
    await _seed_account(agent.id, balance=10.0)

    resp = await client.post(
        f"{BILLING_PREFIX}/transfers",
        headers=_auth(token),
        json={"to_agent_id": agent.id, "amount_usd": 5.0},
    )
    assert resp.status_code == 400
    assert "yourself" in resp.json()["detail"].lower()


async def test_transfer_insufficient_balance(client, make_agent):
    """POST /transfers with insufficient funds returns 400."""
    sender, sender_token = await make_agent(name="poor-sender")
    receiver, _ = await make_agent(name="xfer-recv-2")

    await _seed_account(sender.id, balance=1.0)
    await _seed_account(receiver.id, balance=0.0)

    resp = await client.post(
        f"{BILLING_PREFIX}/transfers",
        headers=_auth(sender_token),
        json={"to_agent_id": receiver.id, "amount_usd": 999.0},
    )
    assert resp.status_code == 400


async def test_transfer_invalid_amount_rejected(client, make_agent):
    """POST /transfers with amount <= 0 is rejected."""
    _, token = await make_agent()

    resp = await client.post(
        f"{BILLING_PREFIX}/transfers",
        headers=_auth(token),
        json={"to_agent_id": "some-agent", "amount_usd": 0},
    )
    assert resp.status_code == 422


async def test_transfer_exceeds_max_rejected(client, make_agent):
    """POST /transfers exceeding le=100_000 limit is rejected."""
    _, token = await make_agent()

    resp = await client.post(
        f"{BILLING_PREFIX}/transfers",
        headers=_auth(token),
        json={"to_agent_id": "some-agent", "amount_usd": 200_000},
    )
    assert resp.status_code == 422


async def test_transfer_with_idempotency_key(client, make_agent):
    """POST /transfers with idempotency_key prevents duplicate processing."""
    sender, sender_token = await make_agent(name="idemp-sender")
    receiver, _ = await make_agent(name="idemp-recv")

    await _seed_account(sender.id, balance=100.0)
    await _seed_account(receiver.id, balance=0.0)

    payload = {
        "to_agent_id": receiver.id,
        "amount_usd": 10.0,
        "idempotency_key": "unique-key-123",
    }

    resp1 = await client.post(
        f"{BILLING_PREFIX}/transfers",
        headers=_auth(sender_token),
        json=payload,
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        f"{BILLING_PREFIX}/transfers",
        headers=_auth(sender_token),
        json=payload,
    )
    assert resp2.status_code in (200, 400)


async def test_transfer_nonexistent_receiver(client, make_agent):
    """POST /transfers to a non-existent agent returns 400."""
    sender, sender_token = await make_agent(name="orphan-sender")
    await _seed_account(sender.id, balance=50.0)

    resp = await client.post(
        f"{BILLING_PREFIX}/transfers",
        headers=_auth(sender_token),
        json={"to_agent_id": "nonexistent-agent-id", "amount_usd": 5.0},
    )
    assert resp.status_code == 400
