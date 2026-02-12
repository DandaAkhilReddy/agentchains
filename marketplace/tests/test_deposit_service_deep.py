"""Deep unit tests for the fiat -> ARD deposit service.

Covers exchange-rate helpers, conversion arithmetic, deposit lifecycle
(create / confirm / cancel), pagination, signup bonus, and edge cases.
25 tests total.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services import deposit_service
from marketplace.services.deposit_service import (
    get_exchange_rate,
    get_supported_currencies,
    _calculate_axn,
)


# ---------------------------------------------------------------------------
# 1-6: Exchange rate pure-function tests
# ---------------------------------------------------------------------------

def test_get_exchange_rate_usd():
    """Test 1: USD rate returns Decimal('0.001000')."""
    assert get_exchange_rate("USD") == Decimal("0.001000")


def test_get_exchange_rate_inr():
    """Test 2: INR rate returns Decimal('0.084000')."""
    assert get_exchange_rate("INR") == Decimal("0.084000")


def test_get_exchange_rate_eur():
    """Test 3: EUR rate returns Decimal('0.000920')."""
    assert get_exchange_rate("EUR") == Decimal("0.000920")


def test_get_exchange_rate_gbp():
    """Test 4: GBP rate returns Decimal('0.000790')."""
    assert get_exchange_rate("GBP") == Decimal("0.000790")


def test_get_exchange_rate_unsupported():
    """Test 5: Unsupported currency 'BTC' raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported currency"):
        get_exchange_rate("BTC")


def test_get_exchange_rate_case_insensitive():
    """Test 6: Lowercase 'usd' resolves correctly (upper-cased internally)."""
    rate = get_exchange_rate("usd")
    assert rate == Decimal("0.001000")


# ---------------------------------------------------------------------------
# 7-8: Supported currencies metadata
# ---------------------------------------------------------------------------

def test_get_supported_currencies():
    """Test 7: Returns 4 currencies with all required fields."""
    currencies = get_supported_currencies()
    assert len(currencies) == 4

    codes = {c["code"] for c in currencies}
    assert codes == {"USD", "INR", "EUR", "GBP"}

    required_keys = {"code", "name", "symbol", "rate_per_axn", "axn_per_unit"}
    for c in currencies:
        assert required_keys.issubset(c.keys()), f"Missing keys in {c['code']}"


def test_get_supported_currencies_axn_per_unit():
    """Test 8: USD axn_per_unit should be 1/0.001 = 1000.0."""
    currencies = get_supported_currencies()
    usd = next(c for c in currencies if c["code"] == "USD")
    assert usd["axn_per_unit"] == 1000.0


# ---------------------------------------------------------------------------
# 9-11: _calculate_axn arithmetic
# ---------------------------------------------------------------------------

def test_calculate_axn_usd():
    """Test 9: $10 / 0.001 = 10000 ARD."""
    result = _calculate_axn(Decimal("10"), Decimal("0.001000"))
    assert result == Decimal("10000.000000")


def test_calculate_axn_inr():
    """Test 10: 84 INR / 0.084 = 1000 ARD."""
    result = _calculate_axn(Decimal("84"), Decimal("0.084000"))
    assert result == Decimal("1000.000000")


def test_calculate_axn_precision():
    """Test 11: Result always has exactly 6 decimal places."""
    result = _calculate_axn(Decimal("1"), Decimal("0.001000"))
    # result should be 1000.000000 — verify 6 decimal digits
    assert result.as_tuple().exponent == -6


# ---------------------------------------------------------------------------
# 12-16: create_deposit
# ---------------------------------------------------------------------------

async def test_create_deposit_pending(db: AsyncSession, make_agent):
    """Test 12: New deposit has status='pending'."""
    agent, _ = await make_agent("deep_dep_pending")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0, "USD")
    assert dep["status"] == "pending"


async def test_create_deposit_all_fields(db: AsyncSession, make_agent):
    """Test 13: All returned fields are populated correctly."""
    agent, _ = await make_agent("deep_dep_fields")
    dep = await deposit_service.create_deposit(db, agent.id, 10.0, "USD")

    assert dep["agent_id"] == agent.id
    assert dep["amount_fiat"] == 10.0
    assert dep["currency"] == "USD"
    assert dep["exchange_rate"] == 0.001
    assert dep["amount_axn"] == 10000.0
    assert dep["status"] == "pending"
    assert dep["payment_method"] == "admin_credit"
    assert dep["id"] is not None
    assert dep["created_at"] is not None
    assert dep["completed_at"] is None


async def test_create_deposit_negative_amount(db: AsyncSession, make_agent):
    """Test 14: Negative fiat amount raises ValueError."""
    agent, _ = await make_agent("deep_dep_neg")
    with pytest.raises(ValueError, match="positive"):
        await deposit_service.create_deposit(db, agent.id, -5.0, "USD")


async def test_create_deposit_zero_amount(db: AsyncSession, make_agent):
    """Test 15: Zero fiat amount raises ValueError."""
    agent, _ = await make_agent("deep_dep_zero")
    with pytest.raises(ValueError, match="positive"):
        await deposit_service.create_deposit(db, agent.id, 0, "USD")


async def test_create_deposit_custom_payment_method(db: AsyncSession, make_agent):
    """Test 16: Custom payment_method='stripe' is stored."""
    agent, _ = await make_agent("deep_dep_stripe")
    dep = await deposit_service.create_deposit(
        db, agent.id, 25.0, "USD", payment_method="stripe"
    )
    assert dep["payment_method"] == "stripe"


# ---------------------------------------------------------------------------
# 17-19: confirm_deposit
# ---------------------------------------------------------------------------

async def test_confirm_deposit_credits_ard(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Test 17: Confirming a deposit increases the agent's ARD balance."""
    from marketplace.services.token_service import get_balance

    agent, _ = await make_agent("deep_dep_credit")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 10.0, "USD")
    await deposit_service.confirm_deposit(db, dep["id"])

    bal = await get_balance(db, agent.id)
    assert bal["balance"] == 10000.0  # $10 / 0.001


async def test_confirm_deposit_status_completed(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Test 18: Confirmed deposit status becomes 'completed'."""
    agent, _ = await make_agent("deep_dep_status")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "EUR")
    confirmed = await deposit_service.confirm_deposit(db, dep["id"])

    assert confirmed["status"] == "completed"
    assert confirmed["completed_at"] is not None


async def test_confirm_already_completed(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Test 19: Re-confirming an already completed deposit raises ValueError."""
    agent, _ = await make_agent("deep_dep_double")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "USD")
    await deposit_service.confirm_deposit(db, dep["id"])

    with pytest.raises(ValueError, match="expected 'pending'"):
        await deposit_service.confirm_deposit(db, dep["id"])


# ---------------------------------------------------------------------------
# 20: cancel_deposit
# ---------------------------------------------------------------------------

async def test_cancel_deposit(db: AsyncSession, make_agent):
    """Test 20: Cancelled deposit status becomes 'failed'."""
    agent, _ = await make_agent("deep_dep_cancel")
    dep = await deposit_service.create_deposit(db, agent.id, 5.0, "USD")

    cancelled = await deposit_service.cancel_deposit(db, dep["id"])
    assert cancelled["status"] == "failed"


# ---------------------------------------------------------------------------
# 21-23: get_deposits pagination
# ---------------------------------------------------------------------------

async def test_get_deposits_empty(db: AsyncSession, make_agent):
    """Test 21: Agent with no deposits returns empty list and total 0."""
    agent, _ = await make_agent("deep_dep_empty")
    deposits, total = await deposit_service.get_deposits(db, agent.id)

    assert deposits == []
    assert total == 0


async def test_get_deposits_pagination(db: AsyncSession, make_agent):
    """Test 22: Create 5 deposits, page_size=2 returns exactly 2."""
    agent, _ = await make_agent("deep_dep_page")
    for i in range(5):
        await deposit_service.create_deposit(db, agent.id, float(i + 1), "USD")

    deposits, total = await deposit_service.get_deposits(
        db, agent.id, page=1, page_size=2
    )
    assert len(deposits) == 2
    assert total == 5


async def test_get_deposits_total_count(db: AsyncSession, make_agent):
    """Test 23: Total count reflects all deposits for the agent."""
    agent, _ = await make_agent("deep_dep_count")
    for _ in range(3):
        await deposit_service.create_deposit(db, agent.id, 1.0, "USD")

    _, total = await deposit_service.get_deposits(db, agent.id)
    assert total == 3


# ---------------------------------------------------------------------------
# 24: credit_signup_bonus
# ---------------------------------------------------------------------------

async def test_credit_signup_bonus(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Test 24: Signup bonus creates + auto-confirms deposit, balance = bonus amount."""
    from marketplace.config import settings
    from marketplace.services.token_service import get_balance

    agent, _ = await make_agent("deep_dep_bonus")
    await make_token_account(agent.id, 0)

    result = await deposit_service.credit_signup_bonus(db, agent.id)

    assert result["status"] == "completed"
    assert result["payment_method"] == "signup_bonus"
    assert result["currency"] == "USD"

    bal = await get_balance(db, agent.id)
    assert bal["balance"] == pytest.approx(settings.token_signup_bonus)  # 100.0 ARD


# ---------------------------------------------------------------------------
# 25: INR conversion end-to-end
# ---------------------------------------------------------------------------

async def test_create_deposit_inr_conversion(db: AsyncSession, make_agent):
    """Test 25: INR deposit converts correctly — 840 INR / 0.084 = 10000 ARD."""
    agent, _ = await make_agent("deep_dep_inr")
    dep = await deposit_service.create_deposit(db, agent.id, 840.0, "INR")

    assert dep["currency"] == "INR"
    assert dep["exchange_rate"] == 0.084
    assert dep["amount_axn"] == 10000.0
