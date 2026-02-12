"""Tests for marketplace config settings and their behavioral impact.

Validates that:
1. Default config values match the documented specification.
2. Monkeypatching settings fields changes runtime behavior (fees, burns,
   peg, quality thresholds, signup bonuses).
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
# Section 1: Default value assertions (10 tests)
# =========================================================================


def test_default_payment_mode():
    """payment_mode defaults to 'simulated'."""
    assert settings.payment_mode == "simulated"


def test_default_token_peg_usd():
    """token_peg_usd defaults to 0.001 (1 ARD = $0.001)."""
    assert settings.token_peg_usd == 0.001


def test_default_token_platform_fee_pct():
    """token_platform_fee_pct defaults to 0.02 (2%)."""
    assert settings.token_platform_fee_pct == 0.02


def test_default_token_burn_pct():
    """token_burn_pct defaults to 0.50 (50% of fees burned)."""
    assert settings.token_burn_pct == 0.50


def test_default_token_signup_bonus():
    """token_signup_bonus defaults to 100.0 ARD."""
    assert settings.token_signup_bonus == 100.0


def test_default_token_quality_threshold():
    """token_quality_threshold defaults to 0.80."""
    assert settings.token_quality_threshold == 0.80


def test_default_token_quality_bonus_pct():
    """token_quality_bonus_pct defaults to 0.10 (10%)."""
    assert settings.token_quality_bonus_pct == 0.10


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
# Section 2: Monkeypatched behavior tests (7 tests)
# =========================================================================


async def test_fee_pct_change_to_5_percent(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting fee_pct to 0.05 makes transfer take a 5% fee."""
    monkeypatch.setattr(settings, "token_platform_fee_pct", 0.05)

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


async def test_burn_pct_zero_means_no_burn(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting burn_pct to 0 means fee stays with platform, burn_amount=0."""
    monkeypatch.setattr(settings, "token_burn_pct", 0.0)

    alice, _ = await make_agent("alice-noburn")
    bob, _ = await make_agent("bob-noburn")
    await make_token_account(alice.id, balance=1000)
    await make_token_account(bob.id, balance=0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 200, tx_type="purchase", memo="no burn test",
    )

    # fee = 200 * 0.02 = 4.0 (default fee_pct)
    assert float(ledger.fee_amount) == pytest.approx(4.0, abs=0.01)
    # burn = 0% of fee = 0
    assert float(ledger.burn_amount) == pytest.approx(0.0, abs=0.001)


async def test_peg_usd_change_affects_usd_equivalent(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Changing peg_usd to 0.01 makes 1000 ARD = $10 USD instead of $1."""
    monkeypatch.setattr(settings, "token_peg_usd", 0.01)

    alice, _ = await make_agent("alice-peg")
    await make_token_account(alice.id, balance=1000)

    balance_info = await token_service.get_balance(db, alice.id)

    # 1000 ARD * $0.01 = $10.00
    assert balance_info["usd_equivalent"] == pytest.approx(10.0, abs=0.01)


async def test_quality_threshold_1_blocks_bonus(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting quality_threshold to 1.0 means no listing qualifies for bonus."""
    monkeypatch.setattr(settings, "token_quality_threshold", 1.0)

    buyer, _ = await make_agent("buyer-qt")
    seller, _ = await make_agent("seller-qt")
    await make_token_account(buyer.id, balance=100_000)
    await make_token_account(seller.id, balance=0)

    result = await token_service.debit_for_purchase(
        db,
        buyer_id=buyer.id,
        seller_id=seller.id,
        amount_usdc=1.0,         # $1 -> 1000 ARD at default peg
        listing_quality=0.95,    # 95% quality, but threshold is 100%
        tx_id="qt-test-001",
    )

    # Quality bonus should be zero because 0.95 < 1.0
    assert result["quality_bonus_axn"] == pytest.approx(0.0, abs=0.001)


async def test_signup_bonus_change_to_50(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting signup_bonus to 50 credits 50 ARD to a new agent."""
    monkeypatch.setattr(settings, "token_signup_bonus", 50.0)

    agent, _ = await make_agent("agent-bonus50")
    await make_token_account(agent.id, balance=0)

    confirmed = await deposit_service.credit_signup_bonus(db, agent.id)

    # The signup bonus should deposit 50 ARD (the fiat equivalent is
    # 50 * 0.001 = $0.05, which converts back to 50 ARD at the USD peg).
    assert confirmed["amount_axn"] == pytest.approx(50.0, abs=0.01)


async def test_fee_pct_zero_means_no_fee(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting fee_pct to 0 means no fee is deducted at all."""
    monkeypatch.setattr(settings, "token_platform_fee_pct", 0.0)

    alice, _ = await make_agent("alice-nofee")
    bob, _ = await make_agent("bob-nofee")
    await make_token_account(alice.id, balance=1000)
    await make_token_account(bob.id, balance=0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 500, tx_type="purchase", memo="zero fee test",
    )

    assert float(ledger.fee_amount) == pytest.approx(0.0, abs=0.001)
    assert float(ledger.burn_amount) == pytest.approx(0.0, abs=0.001)
    # Receiver gets the full amount
    bal = await token_service.get_balance(db, bob.id)
    assert bal["balance"] == pytest.approx(500.0, abs=0.01)


async def test_burn_pct_100_burns_entire_fee(
    db: AsyncSession, make_agent, make_token_account, seed_platform, monkeypatch,
):
    """Setting burn_pct to 1.0 burns 100% of the fee — platform keeps nothing."""
    monkeypatch.setattr(settings, "token_burn_pct", 1.0)

    alice, _ = await make_agent("alice-fullburn")
    bob, _ = await make_agent("bob-fullburn")
    await make_token_account(alice.id, balance=1000)
    await make_token_account(bob.id, balance=0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 100, tx_type="purchase", memo="full burn test",
    )

    # fee = 100 * 0.02 = 2.0
    fee = float(ledger.fee_amount)
    burn = float(ledger.burn_amount)
    assert fee == pytest.approx(2.0, abs=0.01)
    # burn = 100% of fee = 2.0
    assert burn == pytest.approx(fee, abs=0.001)
    # platform_credit = fee - burn = 0
    platform_credit = fee - burn
    assert platform_credit == pytest.approx(0.0, abs=0.001)


# =========================================================================
# Section 3: Threshold validation tests (3 tests)
# =========================================================================


def test_redemption_minimum_thresholds():
    """Redemption minimums: api_credits=100, gift_card=1000, upi=5000, bank=10000."""
    assert settings.redemption_min_api_credits_ard == 100.0
    assert settings.redemption_min_gift_card_ard == 1000.0
    assert settings.redemption_min_upi_ard == 5000.0
    assert settings.redemption_min_bank_ard == 10000.0


def test_rate_limits_authenticated_and_anonymous():
    """Rate limits: authenticated=120 req/min, anonymous=30 req/min."""
    assert settings.rest_rate_limit_authenticated == 120
    assert settings.rest_rate_limit_anonymous == 30


def test_creator_settings_payout_royalty_withdrawal():
    """Creator settings: payout_day=1, royalty_pct=1.0, min_withdrawal=10000."""
    assert settings.creator_payout_day == 1
    assert settings.creator_royalty_pct == 1.0
    assert settings.creator_min_withdrawal_ard == 10000.0
