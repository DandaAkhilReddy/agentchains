"""Unit tests for the USD deposit service.

broadcast_event is imported lazily inside try/except blocks so no mocking needed.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services import deposit_service


# ---------------------------------------------------------------------------
# Deposit lifecycle (async DB)
# ---------------------------------------------------------------------------

async def test_create_deposit_pending(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("dep_creator")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0)

    assert dep["status"] == "pending"
    assert dep["currency"] == "USD"
    assert dep["agent_id"] == agent.id


async def test_create_deposit_usd_10(db: AsyncSession, make_agent, seed_platform):
    """$10 USD deposit records amount_usd=10.0."""
    agent, _ = await make_agent("dep_usd10")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0)

    assert dep["amount_usd"] == 10.0


async def test_create_deposit_negative_raises(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("dep_neg")
    with pytest.raises(ValueError, match="positive"):
        await deposit_service.create_deposit(db, agent.id, -5.0)


async def test_confirm_deposit_credits_balance(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """Confirming a pending deposit credits USD to the agent's balance."""
    from marketplace.services.token_service import get_balance

    agent, _ = await make_agent("dep_confirm")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 10.0)
    assert dep["status"] == "pending"

    confirmed = await deposit_service.confirm_deposit(db, dep["id"])
    assert confirmed["status"] == "completed"

    bal = await get_balance(db, agent.id)
    assert bal["balance"] == 10.0  # $10 credited directly


async def test_confirm_already_completed_raises(db: AsyncSession, make_agent, make_token_account, seed_platform):
    agent, _ = await make_agent("dep_double")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0)
    await deposit_service.confirm_deposit(db, dep["id"])

    with pytest.raises(ValueError, match="expected 'pending'"):
        await deposit_service.confirm_deposit(db, dep["id"])


async def test_cancel_deposit(db: AsyncSession, make_agent, seed_platform):
    agent, _ = await make_agent("dep_cancel")
    dep = await deposit_service.create_deposit(db, agent.id, 5.0)

    cancelled = await deposit_service.cancel_deposit(db, dep["id"])
    assert cancelled["status"] == "failed"


async def test_credit_signup_bonus(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """Signup bonus creates and auto-confirms a USD deposit."""
    from marketplace.services.token_service import get_balance
    from marketplace.config import settings

    agent, _ = await make_agent("bonus_agent")
    await make_token_account(agent.id, 0)

    result = await deposit_service.credit_signup_bonus(db, agent.id)
    assert result["status"] == "completed"
    assert result["payment_method"] == "signup_bonus"

    bal = await get_balance(db, agent.id)
    assert bal["balance"] == pytest.approx(settings.signup_bonus_usd)  # $0.10
