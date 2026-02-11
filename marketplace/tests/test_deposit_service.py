"""Unit tests for the fiat → ARD deposit service.

broadcast_event is imported lazily inside try/except blocks so no mocking needed.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services import deposit_service


# ---------------------------------------------------------------------------
# Exchange rates (pure functions)
# ---------------------------------------------------------------------------

def test_get_exchange_rate_usd():
    rate = deposit_service.get_exchange_rate("USD")
    assert rate == Decimal("0.001000")


def test_get_exchange_rate_inr():
    rate = deposit_service.get_exchange_rate("INR")
    assert rate == Decimal("0.084000")


def test_get_exchange_rate_eur():
    rate = deposit_service.get_exchange_rate("EUR")
    assert rate == Decimal("0.000920")


def test_get_exchange_rate_gbp():
    rate = deposit_service.get_exchange_rate("GBP")
    assert rate == Decimal("0.000790")


def test_get_exchange_rate_unsupported():
    with pytest.raises(ValueError, match="Unsupported currency"):
        deposit_service.get_exchange_rate("JPY")


def test_get_supported_currencies():
    currencies = deposit_service.get_supported_currencies()
    assert len(currencies) == 4
    codes = {c["code"] for c in currencies}
    assert codes == {"USD", "INR", "EUR", "GBP"}
    for c in currencies:
        assert "rate_per_axn" in c
        assert "axn_per_unit" in c
        assert "symbol" in c


# ---------------------------------------------------------------------------
# Deposit lifecycle (async DB)
# ---------------------------------------------------------------------------

async def test_create_deposit_pending(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("dep_creator")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0, "USD")

    assert dep["status"] == "pending"
    assert dep["currency"] == "USD"
    assert dep["agent_id"] == agent.id


async def test_create_deposit_usd_10(db: AsyncSession, make_agent, seed_platform):
    """$10 USD → 10,000 ARD (rate: 1 ARD = $0.001)."""
    agent, _ = await make_agent("dep_usd10")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0, "USD")

    assert dep["amount_axn"] == 10000.0


async def test_create_deposit_negative_raises(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("dep_neg")
    with pytest.raises(ValueError, match="positive"):
        await deposit_service.create_deposit(db, agent.id, -5.0, "USD")


async def test_confirm_deposit_credits_tokens(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """Confirming a pending deposit credits ARD to the agent's balance."""
    from marketplace.services.token_service import get_balance

    agent, _ = await make_agent("dep_confirm")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 10.0, "USD")
    assert dep["status"] == "pending"

    confirmed = await deposit_service.confirm_deposit(db, dep["id"])
    assert confirmed["status"] == "completed"

    bal = await get_balance(db, agent.id)
    assert bal["balance"] == 10000.0  # $10 / 0.001 = 10K ARD


async def test_confirm_already_completed_raises(db: AsyncSession, make_agent, make_token_account, seed_platform):
    agent, _ = await make_agent("dep_double")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "USD")
    await deposit_service.confirm_deposit(db, dep["id"])

    with pytest.raises(ValueError, match="expected 'pending'"):
        await deposit_service.confirm_deposit(db, dep["id"])


async def test_cancel_deposit(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("dep_cancel")
    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "USD")

    cancelled = await deposit_service.cancel_deposit(db, dep["id"])
    assert cancelled["status"] == "failed"


async def test_credit_signup_bonus(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """Signup bonus creates and auto-confirms 100 ARD deposit."""
    from marketplace.services.token_service import get_balance

    agent, _ = await make_agent("bonus_agent")
    await make_token_account(agent.id, 0)

    result = await deposit_service.credit_signup_bonus(db, agent.id)
    assert result["status"] == "completed"
    assert result["payment_method"] == "signup_bonus"

    bal = await get_balance(db, agent.id)
    assert bal["balance"] == 100.0  # settings.token_signup_bonus = 100
