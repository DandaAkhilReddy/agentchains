"""J-2 Token Economy Judge — 10 mathematical invariant tests for the USD billing model.

Verifies double-entry bookkeeping, decimal precision, fee ratios,
idempotency, and creator royalty deduction.

Every test uses Decimal(str(value)) to avoid floating-point drift.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.services import token_service
from marketplace.services.token_service import (
    ensure_platform_account,
    create_account,
    transfer,
    deposit,
    get_balance,
    debit_for_purchase,
)


def _id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1. Double-entry: sum of all balance changes = 0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_double_entry_sum_zero(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """For every transfer, sum of all balance changes = 0 (debits = credits).

    The sender loses `amount`. The receiver gains `amount - fee`. The platform
    gains `fee`.  So:
        -amount + (amount - fee) + fee = 0
    We verify this by snapshotting all balances before and after.
    """
    alice, _ = await make_agent("de_alice")
    bob, _ = await make_agent("de_bob")
    await make_token_account(alice.id, 5000)
    await make_token_account(bob.id, 0)

    # Get platform account balance directly
    platform_acct_result = await db.execute(
        select(TokenAccount).where(
            TokenAccount.agent_id.is_(None),
            TokenAccount.creator_id.is_(None),
        )
    )
    platform_acct = platform_acct_result.scalar_one()
    platform_bal_before = Decimal(str(platform_acct.balance))

    alice_bal_before = Decimal(str((await get_balance(db, alice.id))["balance"]))
    bob_bal_before = Decimal(str((await get_balance(db, bob.id))["balance"]))

    # Execute transfer
    ledger = await transfer(db, alice.id, bob.id, 1000, tx_type="sale")

    # Refresh platform account
    await db.refresh(platform_acct)
    platform_bal_after = Decimal(str(platform_acct.balance))

    alice_bal_after = Decimal(str((await get_balance(db, alice.id))["balance"]))
    bob_bal_after = Decimal(str((await get_balance(db, bob.id))["balance"]))

    # Delta for each party
    delta_alice = alice_bal_after - alice_bal_before        # negative (sender)
    delta_bob = bob_bal_after - bob_bal_before              # positive (receiver)
    delta_platform = platform_bal_after - platform_bal_before  # positive (fee)

    # The invariant: all balance deltas = 0
    net = delta_alice + delta_bob + delta_platform
    assert net == Decimal("0"), f"Double-entry violated: net = {net}"


# ---------------------------------------------------------------------------
# 2. Decimal precision — 6 decimal places maintained
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decimal_precision_no_rounding(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """0.000001 USD transfers maintain 6 decimal places."""
    alice, _ = await make_agent("prec_alice")
    bob, _ = await make_agent("prec_bob")
    await make_token_account(alice.id, 1000)
    await make_token_account(bob.id, 0)

    tiny_amount = Decimal("0.000001")
    ledger = await transfer(db, alice.id, bob.id, tiny_amount, tx_type="transfer")

    assert Decimal(str(ledger.amount)) == tiny_amount
    # Verify 6 decimal places preserved in account balances
    alice_bal = await get_balance(db, alice.id)
    expected_alice = Decimal("1000") - tiny_amount
    assert Decimal(str(alice_bal["balance"])) == expected_alice.quantize(Decimal("0.000001"))


# ---------------------------------------------------------------------------
# 3. Fee = transfer_amount * platform_fee_pct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fee_matches_platform_pct(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """fee_amount = transfer_amount * platform_fee_pct exactly."""
    alice, _ = await make_agent("fee_alice")
    bob, _ = await make_agent("fee_bob")
    await make_token_account(alice.id, 5000)
    await make_token_account(bob.id, 0)

    amount = Decimal("1000")
    ledger = await transfer(db, alice.id, bob.id, amount, tx_type="sale")

    fee = Decimal(str(ledger.fee_amount))
    fee_pct = Decimal(str(settings.platform_fee_pct))
    expected_fee = (amount * fee_pct).quantize(Decimal("0.000001"))

    assert fee == expected_fee, f"Fee {fee} != {amount} * {fee_pct} = {expected_fee}"


# ---------------------------------------------------------------------------
# 4. $0 listing -> zero USD -> no transfer needed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_price_fee_calc(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """$0 listing -> transfer of 0 should raise ValueError (amount must be positive)."""
    buyer, _ = await make_agent("zp_buyer")
    seller, _ = await make_agent("zp_seller")
    await make_token_account(buyer.id, 5000)
    await make_token_account(seller.id, 0)

    with pytest.raises(ValueError, match="positive"):
        await transfer(db, buyer.id, seller.id, 0, tx_type="purchase")


# ---------------------------------------------------------------------------
# 5. $100 listing -> correct fee
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_price_fee_calc(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """$100 listing -> correct fee calculation."""
    buyer, _ = await make_agent("max_buyer")
    seller, _ = await make_agent("max_seller")

    amount_usd = Decimal("100")

    await make_token_account(buyer.id, float(amount_usd + Decimal("1000")))
    await make_token_account(seller.id, 0)

    ledger = await transfer(db, buyer.id, seller.id, amount_usd, tx_type="purchase")

    fee_pct = Decimal(str(settings.platform_fee_pct))
    expected_fee = (amount_usd * fee_pct).quantize(Decimal("0.000001"))

    assert Decimal(str(ledger.amount)) == amount_usd
    assert Decimal(str(ledger.fee_amount)) == expected_fee


# ---------------------------------------------------------------------------
# 6. Idempotency key dedup — same key twice returns same entry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotency_key_dedup(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """Same idempotency key twice returns same ledger entry, no double-charge."""
    alice, _ = await make_agent("idem_alice")
    bob, _ = await make_agent("idem_bob")
    await make_token_account(alice.id, 5000)
    await make_token_account(bob.id, 0)

    key = "judge-test-idem-key-unique"
    l1 = await transfer(db, alice.id, bob.id, 500, tx_type="purchase", idempotency_key=key)
    l2 = await transfer(db, alice.id, bob.id, 500, tx_type="purchase", idempotency_key=key)

    # Same ledger entry returned
    assert l1.id == l2.id

    # Balance reflects only ONE transfer (alice started at 5000, sent 500)
    alice_bal = await get_balance(db, alice.id)
    assert Decimal(str(alice_bal["balance"])) == Decimal("4500")

    # Total ledger entries with this key = 1
    count_result = await db.execute(
        select(func.count(TokenLedger.id)).where(
            TokenLedger.idempotency_key == key
        )
    )
    assert count_result.scalar() == 1


# ---------------------------------------------------------------------------
# 7. Platform treasury grows by fee per transfer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_platform_treasury_grows_by_fee(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """platform.balance grows by fee per transfer."""
    alice, _ = await make_agent("plat_alice")
    bob, _ = await make_agent("plat_bob")
    await make_token_account(alice.id, 5000)
    await make_token_account(bob.id, 0)

    # Get platform balance before
    platform_result = await db.execute(
        select(TokenAccount).where(
            TokenAccount.agent_id.is_(None),
            TokenAccount.creator_id.is_(None),
        )
    )
    platform_acct = platform_result.scalar_one()
    balance_before = Decimal(str(platform_acct.balance))

    # Transfer
    ledger = await transfer(db, alice.id, bob.id, 1000, tx_type="sale")

    fee = Decimal(str(ledger.fee_amount))

    # Refresh
    await db.refresh(platform_acct)
    balance_after = Decimal(str(platform_acct.balance))

    actual_growth = (balance_after - balance_before).quantize(Decimal("0.000001"))
    assert actual_growth == fee, (
        f"Platform grew by {actual_growth}, expected {fee}"
    )


# ---------------------------------------------------------------------------
# 8. Signup bonus equals settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signup_bonus_deposit(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """Deposit for signup bonus credits the correct USD amount."""
    agent, _ = await make_agent("signup_agent")
    await make_token_account(agent.id, 0)

    signup_bonus = Decimal(str(settings.signup_bonus_usd))
    await deposit(
        db, agent.id, float(signup_bonus),
        deposit_id="signup-bonus-001", memo="Signup bonus",
    )

    bal = await get_balance(db, agent.id)
    assert Decimal(str(bal["balance"])) == signup_bonus.quantize(Decimal("0.000001")), (
        f"Balance {bal['balance']} != signup bonus {signup_bonus}"
    )


# ---------------------------------------------------------------------------
# 9. Negative transfer rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_negative_transfer_rejected(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """amount < 0 or == 0 raises ValueError."""
    alice, _ = await make_agent("neg_alice")
    bob, _ = await make_agent("neg_bob")
    await make_token_account(alice.id, 5000)
    await make_token_account(bob.id, 0)

    # Negative amount
    with pytest.raises(ValueError, match="positive"):
        await transfer(db, alice.id, bob.id, -100, tx_type="transfer")

    # Zero amount
    with pytest.raises(ValueError, match="positive"):
        await transfer(db, alice.id, bob.id, 0, tx_type="transfer")

    # Also verify deposit rejects negatives
    with pytest.raises(ValueError, match="positive"):
        await deposit(db, alice.id, -50)

    # Verify balance unchanged (no partial state mutation)
    alice_bal = await get_balance(db, alice.id)
    assert Decimal(str(alice_bal["balance"])) == Decimal("5000")


# ---------------------------------------------------------------------------
# 10. Creator royalty deducted from agent after purchase
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creator_royalty_deducted_from_agent(
    db: AsyncSession, seed_platform, make_agent, make_token_account, make_creator
):
    """After purchase with creator-linked agent, agent balance has royalty deducted."""
    # Create creator and their token account
    creator, _creator_token = await make_creator(
        email="royalty-judge@test.com", display_name="Royalty Judge Creator"
    )
    creator_acct = TokenAccount(
        id=_id(),
        creator_id=creator.id,
        balance=Decimal("0"),
    )
    db.add(creator_acct)
    await db.commit()
    await db.refresh(creator_acct)

    # Create seller agent and link to creator
    seller, _ = await make_agent("royalty_seller")
    seller.creator_id = creator.id
    await db.commit()

    seller_acct = await create_account(db, seller.id)

    # Create buyer with funds
    buyer, _ = await make_agent("royalty_buyer")
    await make_token_account(buyer.id, 50000)

    # Execute a purchase — this triggers royalty auto-flow
    amount_usd = Decimal("1000")
    ledger = await transfer(
        db, buyer.id, seller.id, amount_usd,
        tx_type="purchase", reference_id="royalty-tx-001",
    )

    fee = Decimal(str(ledger.fee_amount))
    net_to_seller = (amount_usd - fee).quantize(Decimal("0.000001"))
    royalty_pct = Decimal(str(settings.creator_royalty_pct))
    expected_royalty = (net_to_seller * royalty_pct).quantize(Decimal("0.000001"))

    # Refresh accounts
    await db.refresh(seller_acct)
    await db.refresh(creator_acct)

    seller_balance = Decimal(str(seller_acct.balance))
    creator_balance = Decimal(str(creator_acct.balance))

    # Seller should have net_to_seller MINUS the royalty deducted
    expected_seller_balance = (net_to_seller - expected_royalty).quantize(Decimal("0.000001"))
    assert seller_balance == expected_seller_balance, (
        f"Seller balance {seller_balance} != expected {expected_seller_balance} "
        f"(net={net_to_seller}, royalty={expected_royalty})"
    )

    # Creator should have received the royalty
    assert creator_balance == expected_royalty, (
        f"Creator balance {creator_balance} != expected royalty {expected_royalty}"
    )
