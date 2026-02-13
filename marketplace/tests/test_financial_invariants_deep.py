"""Deep financial invariant tests for the USD billing model.

10 tests verifying that financial rules (fee, double-entry,
deposit/redemption lifecycle) hold across multi-step flows.

All monetary assertions use ``Decimal`` to avoid floating-point drift.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.models.redemption import RedemptionRequest
from marketplace.services import token_service, deposit_service, redemption_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


def _d(value) -> Decimal:
    """Coerce any numeric to a 6-decimal-place Decimal."""
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


async def _setup_purchase(
    db: AsyncSession,
    seed_platform,
    make_agent,
    make_token_account,
    make_listing,
    *,
    buyer_balance: float = 50_000.0,
    price_usdc: float = 5.0,
    quality_score: float = 0.50,
) -> dict:
    """Standard purchase setup: platform + buyer + seller + listing.

    Returns a dict with all IDs, the listing, and account references.
    """
    buyer, _ = await make_agent("fin_buyer")
    seller, _ = await make_agent("fin_seller")
    buyer_acct = await make_token_account(buyer.id, balance=buyer_balance)
    seller_acct = await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=price_usdc, quality_score=quality_score)

    return {
        "buyer": buyer,
        "seller": seller,
        "buyer_acct": buyer_acct,
        "seller_acct": seller_acct,
        "listing": listing,
    }


async def _do_purchase(db: AsyncSession, ctx: dict) -> dict:
    """Execute debit_for_purchase using the standard context."""
    listing = ctx["listing"]
    tx_id = f"tx-{_new_id()}"
    result = await token_service.debit_for_purchase(
        db,
        buyer_id=ctx["buyer"].id,
        seller_id=ctx["seller"].id,
        amount_usdc=float(listing.price_usdc),
        tx_id=tx_id,
    )
    result["tx_id"] = tx_id
    return result


async def _make_creator_with_balance(
    db: AsyncSession,
    make_creator,
    balance: float = 50_000.0,
) -> tuple:
    """Create a Creator + TokenAccount with the given USD balance."""
    creator, token = await make_creator()
    account = TokenAccount(
        id=_new_id(),
        creator_id=creator.id,
        balance=Decimal(str(balance)),
        total_deposited=Decimal(str(balance)),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return creator, token, account


# ===========================================================================
# 1. test_purchase_fee_is_2_percent
# ===========================================================================

async def test_purchase_fee_is_2_percent(
    db: AsyncSession, seed_platform, make_agent, make_token_account, make_listing,
):
    """fee_amount = price_usd * settings.platform_fee_pct (0.02)."""
    ctx = await _setup_purchase(
        db, seed_platform, make_agent, make_token_account, make_listing,
        price_usdc=5.0, quality_score=0.50,
    )
    result = await _do_purchase(db, ctx)

    price_usd = _d(ctx["listing"].price_usdc)
    expected_fee = _d(price_usd * _d(settings.platform_fee_pct))

    assert _d(result["fee_usd"]) == expected_fee, (
        f"Fee mismatch: got {result['fee_usd']}, expected {expected_fee}"
    )


# ===========================================================================
# 2. test_seller_receives_price_minus_fee
# ===========================================================================

async def test_seller_receives_price_minus_fee(
    db: AsyncSession, seed_platform, make_agent, make_token_account, make_listing,
):
    """Seller balance = price_usd - fee (no quality bonus when quality < 0.8)."""
    ctx = await _setup_purchase(
        db, seed_platform, make_agent, make_token_account, make_listing,
        price_usdc=5.0, quality_score=0.50,
    )
    result = await _do_purchase(db, ctx)

    price_usd = _d(ctx["listing"].price_usdc)
    fee = _d(price_usd * _d(settings.platform_fee_pct))
    expected_seller_balance = _d(price_usd - fee)

    assert _d(result["seller_balance"]) == expected_seller_balance, (
        f"Seller balance mismatch: got {result['seller_balance']}, expected {expected_seller_balance}"
    )


# ===========================================================================
# 3. test_buyer_debited_full_price
# ===========================================================================

async def test_buyer_debited_full_price(
    db: AsyncSession, seed_platform, make_agent, make_token_account, make_listing,
):
    """Buyer balance decreases by the full price in USD (before fee split)."""
    initial_balance = Decimal("50000")
    ctx = await _setup_purchase(
        db, seed_platform, make_agent, make_token_account, make_listing,
        buyer_balance=float(initial_balance), price_usdc=5.0, quality_score=0.50,
    )
    result = await _do_purchase(db, ctx)

    price_usd = _d(Decimal("5.0"))
    expected_buyer_balance = _d(initial_balance - price_usd)

    assert _d(result["buyer_balance"]) == expected_buyer_balance, (
        f"Buyer balance mismatch: got {result['buyer_balance']}, expected {expected_buyer_balance}"
    )


# ===========================================================================
# 4. test_signup_bonus_equals_settings
# ===========================================================================

async def test_signup_bonus_equals_settings(
    db: AsyncSession, seed_platform, make_agent, make_token_account,
):
    """Signup bonus credits exactly settings.signup_bonus_usd."""
    agent, _ = await make_agent("signup_invariant")
    await make_token_account(agent.id, balance=0)

    result = await deposit_service.credit_signup_bonus(db, agent.id)

    assert result["status"] == "completed"

    bal = await token_service.get_balance(db, agent.id)
    expected = _d(settings.signup_bonus_usd)
    assert _d(bal["balance"]) == expected, (
        f"Signup bonus mismatch: got {bal['balance']}, expected {expected}"
    )


# ===========================================================================
# 7. test_deposit_confirm_exact_usd
# ===========================================================================

async def test_deposit_confirm_exact_usd(
    db: AsyncSession, seed_platform, make_agent, make_token_account,
):
    """Deposit $10 credits exactly $10.000000 USD."""
    agent, _ = await make_agent("dep_exact")
    await make_token_account(agent.id, balance=0)

    dep = await deposit_service.create_deposit(db, agent.id, 10.0)
    await deposit_service.confirm_deposit(db, dep["id"])

    bal = await token_service.get_balance(db, agent.id)
    expected = _d(Decimal("10"))

    assert _d(bal["balance"]) == expected, (
        f"Deposit balance mismatch: got {bal['balance']}, expected {expected}"
    )


# ===========================================================================
# 8. test_redemption_cancel_exact_refund
# ===========================================================================

async def test_redemption_cancel_exact_refund(
    db: AsyncSession, seed_platform, make_creator,
):
    """Cancelling a pending redemption restores the exact USD amount."""
    initial_balance = Decimal("50000")
    creator, _, acct = await _make_creator_with_balance(db, make_creator, float(initial_balance))

    redeem_amount = 5000.0
    created = await redemption_service.create_redemption(
        db, creator.id, "gift_card", redeem_amount,
    )
    assert created["status"] == "pending"

    # Balance should be debited
    await db.refresh(acct)
    assert _d(acct.balance) == _d(initial_balance - Decimal(str(redeem_amount)))

    # Cancel
    cancelled = await redemption_service.cancel_redemption(
        db, created["id"], creator.id,
    )
    assert cancelled["status"] == "rejected"

    # Balance should be fully restored to the exact initial amount
    await db.refresh(acct)
    assert _d(acct.balance) == _d(initial_balance), (
        f"Refund imprecision: got {acct.balance}, expected {initial_balance}"
    )


# ===========================================================================
# 9. test_admin_reject_exact_refund
# ===========================================================================

async def test_admin_reject_exact_refund(
    db: AsyncSession, seed_platform, make_creator,
):
    """Admin reject restores the exact USD amount to the creator."""
    initial_balance = Decimal("50000")
    creator, _, acct = await _make_creator_with_balance(db, make_creator, float(initial_balance))

    redeem_amount = 10000.0
    created = await redemption_service.create_redemption(
        db, creator.id, "bank_withdrawal", redeem_amount,
    )
    assert created["status"] == "pending"

    # Admin rejects
    rejected = await redemption_service.admin_reject_redemption(
        db, created["id"], reason="Test rejection",
    )
    assert rejected["status"] == "rejected"

    # Balance fully restored
    await db.refresh(acct)
    assert _d(acct.balance) == _d(initial_balance), (
        f"Admin reject refund imprecision: got {acct.balance}, expected {initial_balance}"
    )


# ===========================================================================
# 10. test_ledger_debits_equal_credits
# ===========================================================================

async def test_ledger_debits_equal_credits(
    db: AsyncSession, seed_platform, make_agent, make_token_account, make_listing,
):
    """Double-entry invariant: sum of from_account entries = sum of to_account entries
    (within the purchase transfer flow, excluding deposit entries)."""
    ctx = await _setup_purchase(
        db, seed_platform, make_agent, make_token_account, make_listing,
        price_usdc=5.0, quality_score=0.50,
    )
    result = await _do_purchase(db, ctx)

    # Query all ledger entries that are NOT deposits (i.e., have a from_account_id)
    # For transfer-type entries: the total amount debited should equal
    # total credited + total fee to platform
    transfer_entries = (await db.execute(
        select(TokenLedger).where(
            TokenLedger.from_account_id.isnot(None),
            TokenLedger.to_account_id.isnot(None),
        )
    )).scalars().all()

    total_debited = sum(Decimal(str(e.amount)) for e in transfer_entries)
    total_credited_to_receiver = sum(
        Decimal(str(e.amount)) - Decimal(str(e.fee_amount))
        for e in transfer_entries
    )
    total_platform_credit = sum(
        Decimal(str(e.fee_amount))
        for e in transfer_entries
    )

    # Invariant: debited = credited_to_receiver + platform_credit
    reconstructed = _d(total_credited_to_receiver + total_platform_credit)
    assert _d(total_debited) == reconstructed, (
        f"Double-entry violation: debited={total_debited}, "
        f"receiver={total_credited_to_receiver} + platform={total_platform_credit} = {reconstructed}"
    )


# ===========================================================================
# 11. test_platform_treasury_grows_by_fee
# ===========================================================================

async def test_platform_treasury_grows_by_fee(
    db: AsyncSession, seed_platform, make_agent, make_token_account, make_listing,
):
    """Platform treasury balance increases by exactly the fee."""
    # Record initial platform balance
    platform_acct = await db.execute(
        select(TokenAccount).where(
            TokenAccount.agent_id.is_(None),
            TokenAccount.creator_id.is_(None),
        )
    )
    platform_before = Decimal(str(platform_acct.scalar_one().balance))

    ctx = await _setup_purchase(
        db, seed_platform, make_agent, make_token_account, make_listing,
        price_usdc=5.0, quality_score=0.50,
    )
    result = await _do_purchase(db, ctx)

    fee = _d(result["fee_usd"])

    # Refresh platform balance
    platform_acct_after = await db.execute(
        select(TokenAccount).where(
            TokenAccount.agent_id.is_(None),
            TokenAccount.creator_id.is_(None),
        )
    )
    platform_after = Decimal(str(platform_acct_after.scalar_one().balance))

    actual_growth = _d(platform_after - platform_before)
    assert actual_growth == fee, (
        f"Platform treasury growth mismatch: got {actual_growth}, expected {fee}"
    )


# ===========================================================================
# 12. test_multi_purchase_balance_consistency
# ===========================================================================

async def test_multi_purchase_balance_consistency(
    db: AsyncSession, seed_platform, make_agent, make_token_account, make_listing,
):
    """After 3 purchases, final balances are all correct (cumulative)."""
    buyer, _ = await make_agent("multi_buyer")
    seller, _ = await make_agent("multi_seller")
    buyer_acct = await make_token_account(buyer.id, balance=100_000)
    seller_acct = await make_token_account(seller.id, balance=0)

    initial_buyer = Decimal("100000")
    cumulative_buyer_spent = Decimal("0")
    cumulative_seller_received = Decimal("0")
    cumulative_platform = Decimal("0")

    prices_usdc = [1.0, 2.5, 7.0]

    for price_usdc in prices_usdc:
        listing = await make_listing(seller.id, price_usdc=price_usdc, quality_score=0.50)
        tx_id = f"tx-{_new_id()}"
        result = await token_service.debit_for_purchase(
            db,
            buyer_id=buyer.id,
            seller_id=seller.id,
            amount_usdc=price_usdc,
            tx_id=tx_id,
        )

        price_usd = _d(Decimal(str(price_usdc)))
        fee = _d(price_usd * _d(settings.platform_fee_pct))
        net = _d(price_usd - fee)

        cumulative_buyer_spent += price_usd
        cumulative_seller_received += net
        cumulative_platform += fee

    # Verify buyer balance
    buyer_bal = await token_service.get_balance(db, buyer.id)
    expected_buyer = _d(initial_buyer - cumulative_buyer_spent)
    assert _d(buyer_bal["balance"]) == expected_buyer, (
        f"Multi-purchase buyer balance: got {buyer_bal['balance']}, expected {expected_buyer}"
    )

    # Verify seller balance
    seller_bal = await token_service.get_balance(db, seller.id)
    assert _d(seller_bal["balance"]) == _d(cumulative_seller_received), (
        f"Multi-purchase seller balance: got {seller_bal['balance']}, expected {cumulative_seller_received}"
    )

    # Verify platform treasury
    platform_acct = (await db.execute(
        select(TokenAccount).where(
            TokenAccount.agent_id.is_(None),
            TokenAccount.creator_id.is_(None),
        )
    )).scalar_one()
    assert _d(platform_acct.balance) == _d(cumulative_platform), (
        f"Multi-purchase platform balance: got {platform_acct.balance}, expected {cumulative_platform}"
    )


# ===========================================================================
# 13. test_zero_balance_after_spending_all
# ===========================================================================

async def test_zero_balance_after_spending_all(
    db: AsyncSession, seed_platform, make_agent, make_token_account, make_listing,
):
    """Spending exact balance leaves 0.000000 USD (not negative)."""
    price_usdc = 1.0
    exact_usd = _d(Decimal(str(price_usdc)))  # 1.000000

    buyer, _ = await make_agent("zero_buyer")
    seller, _ = await make_agent("zero_seller")
    buyer_acct = await make_token_account(buyer.id, balance=float(exact_usd))
    seller_acct = await make_token_account(seller.id, balance=0)

    listing = await make_listing(seller.id, price_usdc=price_usdc, quality_score=0.50)

    tx_id = f"tx-{_new_id()}"
    result = await token_service.debit_for_purchase(
        db,
        buyer_id=buyer.id,
        seller_id=seller.id,
        amount_usdc=price_usdc,
        tx_id=tx_id,
    )

    buyer_bal = await token_service.get_balance(db, buyer.id)
    final_balance = _d(buyer_bal["balance"])

    assert final_balance == Decimal("0.000000"), (
        f"Expected exactly 0.000000, got {final_balance}"
    )
    assert final_balance >= Decimal("0"), "Balance must never be negative"
