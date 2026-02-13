"""Tests for marketplace config settings and their behavioral impact.

Validates that:
1. Default config values match the documented specification.
2. Monkeypatching settings fields changes runtime behavior (fees,
   signup bonuses).
3. Threshold groups (redemption minimums, rate limits, creator settings)
   are correctly wired.

Uses in-memory SQLite via conftest fixtures.  ``monkeypatch`` auto-restores
all patched attributes after each test.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.services import token_service
from marketplace.services import deposit_service


# =========================================================================
# Section 1: Default value assertions (7 tests)
# =========================================================================


def test_default_payment_mode():
    """payment_mode defaults to 'simulated'."""
    assert settings.payment_mode == "simulated"


def test_default_platform_fee_pct():
    """platform_fee_pct defaults to 0.02 (2%)."""
    assert settings.platform_fee_pct == 0.02


def test_default_signup_bonus_usd():
    """signup_bonus_usd defaults to 0.10."""
    assert settings.signup_bonus_usd == 0.10


def test_default_jwt_algorithm():
    """jwt_algorithm defaults to 'HS256'."""
    assert settings.jwt_algorithm == "HS256"


def test_default_mcp_rate_limit_per_minute():
    """mcp_rate_limit_per_minute defaults to 60."""
    assert settings.mcp_rate_limit_per_minute == 60


def test_default_cdn_hot_cache_max_bytes():
    """cdn_hot_cache_max_bytes defaults to 256 MiB."""
    assert settings.cdn_hot_cache_max_bytes == 256 * 1024 * 1024


# =========================================================================
# Section 2: Monkeypatched behavior tests (4 tests)
# =========================================================================


async def test_fee_pct_change_to_5_percent(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting fee_pct to 0.05 makes transfer take a 5% fee."""
    monkeypatch.setattr(settings, "platform_fee_pct", 0.05)

    alice, _ = await make_agent("alice-fee5")
    bob, _ = await make_agent("bob-fee5")
    await make_token_account(alice.id, balance=1000)
    await make_token_account(bob.id, balance=0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 100, tx_type="purchase", memo="5% fee test",
    )

    # fee = 100 * 0.05 = 5.0
    assert float(ledger.fee_amount) == pytest.approx(5.0, abs=0.01)
    # receiver gets 100 - 5 = 95
    receiver_credit = float(ledger.amount) - float(ledger.fee_amount)
    assert receiver_credit == pytest.approx(95.0, abs=0.01)


async def test_signup_bonus_change(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting signup_bonus_usd to 0.50 credits $0.50 to a new agent."""
    monkeypatch.setattr(settings, "signup_bonus_usd", 0.50)

    agent, _ = await make_agent("agent-bonus50")
    await make_token_account(agent.id, balance=0)

    confirmed = await deposit_service.credit_signup_bonus(db, agent.id)

    assert confirmed["amount_usd"] == pytest.approx(0.50, abs=0.01)


async def test_fee_pct_zero_means_no_fee(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting fee_pct to 0 means no fee is deducted at all."""
    monkeypatch.setattr(settings, "platform_fee_pct", 0.0)

    alice, _ = await make_agent("alice-nofee")
    bob, _ = await make_agent("bob-nofee")
    await make_token_account(alice.id, balance=1000)
    await make_token_account(bob.id, balance=0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 500, tx_type="purchase", memo="zero fee test",
    )

    assert float(ledger.fee_amount) == pytest.approx(0.0, abs=0.001)
    # Receiver gets the full amount
    bal = await token_service.get_balance(db, bob.id)
    assert bal["balance"] == pytest.approx(500.0, abs=0.01)


async def test_fee_pct_100_percent(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting fee_pct to 1.0 takes 100% of the transfer as fee."""
    monkeypatch.setattr(settings, "platform_fee_pct", 1.0)

    alice, _ = await make_agent("alice-fullfee")
    bob, _ = await make_agent("bob-fullfee")
    await make_token_account(alice.id, balance=1000)
    await make_token_account(bob.id, balance=0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 100, tx_type="purchase", memo="full fee test",
    )

    # fee = 100 * 1.0 = 100.0
    fee = float(ledger.fee_amount)
    assert fee == pytest.approx(100.0, abs=0.01)


# =========================================================================
# Section 3: Threshold validation tests (3 tests)
# =========================================================================


def test_redemption_minimum_thresholds():
    """Redemption minimums: api_credits=$0.10, gift_card=$1.00, upi=$5.00, bank=$10.00."""
    assert settings.redemption_min_api_credits_usd == 0.10
    assert settings.redemption_min_gift_card_usd == 1.00
    assert settings.redemption_min_upi_usd == 5.00
    assert settings.redemption_min_bank_usd == 10.00


def test_rate_limits_authenticated_and_anonymous():
    """Rate limits: authenticated=120 req/min, anonymous=30 req/min."""
    assert settings.rest_rate_limit_authenticated == 120
    assert settings.rest_rate_limit_anonymous == 30


def test_creator_settings_payout_royalty_withdrawal():
    """Creator settings: payout_day=1, royalty_pct=1.0, min_withdrawal=$10.00."""
    assert settings.creator_payout_day == 1
    assert settings.creator_royalty_pct == 1.0
    assert settings.creator_min_withdrawal_usd == 10.00
