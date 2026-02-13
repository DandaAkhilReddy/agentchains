"""Deep unit tests for the USD deposit service.

Covers deposit lifecycle (create / confirm / cancel), pagination,
signup bonus, and edge cases.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services import deposit_service


# ---------------------------------------------------------------------------
# 1-4: create_deposit
# ---------------------------------------------------------------------------

async def test_create_deposit_pending(db: AsyncSession, make_agent):
    """Test 1: New deposit has status='pending'."""
    agent, _ = await make_agent("deep_dep_pending")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0)
    assert dep["status"] == "pending"


async def test_create_deposit_all_fields(db: AsyncSession, make_agent):
    """Test 2: All returned fields are populated correctly."""
    agent, _ = await make_agent("deep_dep_fields")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0)

    assert dep["agent_id"] == agent.id
    assert dep["amount_usd"] == 10.0
    assert dep["currency"] == "USD"
    assert dep["status"] == "pending"
    assert dep["payment_method"] == "admin_credit"
    assert dep["id"] is not None
    assert dep["created_at"] is not None
    assert dep["completed_at"] is None


async def test_create_deposit_negative_amount(db: AsyncSession, make_agent):
    """Test 3: Negative USD amount raises ValueError."""
    agent, _ = await make_agent("deep_dep_neg")
    with pytest.raises(ValueError, match="positive"):
        await deposit_service.create_deposit(db, agent.id, -5.0)


async def test_create_deposit_zero_amount(db: AsyncSession, make_agent):
    """Test 4: Zero USD amount raises ValueError."""
    agent, _ = await make_agent("deep_dep_zero")
    with pytest.raises(ValueError, match="positive"):
        await deposit_service.create_deposit(db, agent.id, 0)


async def test_create_deposit_custom_payment_method(db: AsyncSession, make_agent):
    """Test 5: Custom payment_method='stripe' is stored."""
    agent, _ = await make_agent("deep_dep_stripe")
    dep = await deposit_service.create_deposit(
        db, agent.id, 25.0, payment_method="stripe"
    )
    assert dep["payment_method"] == "stripe"


# ---------------------------------------------------------------------------
# 6-8: confirm_deposit
# ---------------------------------------------------------------------------

async def test_confirm_deposit_credits_usd(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Test 6: Confirming a deposit increases the agent's USD balance."""
    from marketplace.services.token_service import get_balance

    agent, _ = await make_agent("deep_dep_credit")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 10.0)
    await deposit_service.confirm_deposit(db, dep["id"])

    bal = await get_balance(db, agent.id)
    assert bal["balance"] == 10.0  # $10 credited directly


async def test_confirm_deposit_status_completed(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Test 7: Confirmed deposit status becomes 'completed'."""
    agent, _ = await make_agent("deep_dep_status")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0)
    confirmed = await deposit_service.confirm_deposit(db, dep["id"])

    assert confirmed["status"] == "completed"
    assert confirmed["completed_at"] is not None


async def test_confirm_already_completed(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Test 8: Re-confirming an already completed deposit raises ValueError."""
    agent, _ = await make_agent("deep_dep_double")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0)
    await deposit_service.confirm_deposit(db, dep["id"])

    with pytest.raises(ValueError, match="expected 'pending'"):
        await deposit_service.confirm_deposit(db, dep["id"])


# ---------------------------------------------------------------------------
# 9: cancel_deposit
# ---------------------------------------------------------------------------

async def test_cancel_deposit(db: AsyncSession, make_agent):
    """Test 9: Cancelled deposit status becomes 'failed'."""
    agent, _ = await make_agent("deep_dep_cancel")
    dep = await deposit_service.create_deposit(db, agent.id, 5.0)

    cancelled = await deposit_service.cancel_deposit(db, dep["id"])
    assert cancelled["status"] == "failed"


# ---------------------------------------------------------------------------
# 10-12: get_deposits pagination
# ---------------------------------------------------------------------------

async def test_get_deposits_empty(db: AsyncSession, make_agent):
    """Test 10: Agent with no deposits returns empty list and total 0."""
    agent, _ = await make_agent("deep_dep_empty")
    deposits, total = await deposit_service.get_deposits(db, agent.id)

    assert deposits == []
    assert total == 0


async def test_get_deposits_pagination(db: AsyncSession, make_agent):
    """Test 11: Create 5 deposits, page_size=2 returns exactly 2."""
    agent, _ = await make_agent("deep_dep_page")
    for i in range(5):
        await deposit_service.create_deposit(db, agent.id, float(i + 1))

    deposits, total = await deposit_service.get_deposits(
        db, agent.id, page=1, page_size=2
    )
    assert len(deposits) == 2
    assert total == 5


async def test_get_deposits_total_count(db: AsyncSession, make_agent):
    """Test 12: Total count reflects all deposits for the agent."""
    agent, _ = await make_agent("deep_dep_count")
    for _ in range(3):
        await deposit_service.create_deposit(db, agent.id, 1.0)

    _, total = await deposit_service.get_deposits(db, agent.id)
    assert total == 3


# ---------------------------------------------------------------------------
# 13: credit_signup_bonus
# ---------------------------------------------------------------------------

async def test_credit_signup_bonus(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Test 13: Signup bonus creates + auto-confirms deposit, balance = bonus amount."""
    from marketplace.config import settings
    from marketplace.services.token_service import get_balance

    agent, _ = await make_agent("deep_dep_bonus")
    await make_token_account(agent.id, 0)

    result = await deposit_service.credit_signup_bonus(db, agent.id)

    assert result["status"] == "completed"
    assert result["payment_method"] == "signup_bonus"
    assert result["currency"] == "USD"

    bal = await get_balance(db, agent.id)
    assert bal["balance"] == pytest.approx(settings.signup_bonus_usd)  # $0.10


# ---------------------------------------------------------------------------
# 14: Large deposit amount
# ---------------------------------------------------------------------------

async def test_create_deposit_large_amount(db: AsyncSession, make_agent):
    """Test 14: Large USD deposit (e.g. $10,000) is stored correctly."""
    agent, _ = await make_agent("deep_dep_large")
    dep = await deposit_service.create_deposit(db, agent.id, 10000.0)

    assert dep["amount_usd"] == 10000.0
    assert dep["status"] == "pending"


# ---------------------------------------------------------------------------
# 15: Fractional deposit amount
# ---------------------------------------------------------------------------

async def test_create_deposit_fractional_amount(db: AsyncSession, make_agent):
    """Test 15: Fractional USD deposit (e.g. $0.01) is stored correctly."""
    agent, _ = await make_agent("deep_dep_frac")
    dep = await deposit_service.create_deposit(db, agent.id, 0.01)

    assert dep["amount_usd"] == 0.01
    assert dep["status"] == "pending"
