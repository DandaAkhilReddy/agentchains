"""J-2 Token Economy Judge — 15 mathematical invariant tests for the ARD token economy.

Verifies double-entry bookkeeping, decimal precision, fee/burn ratios,
supply conservation, idempotency, hash-chain integrity, tier boundaries,
and creator royalty deduction.

Every test uses Decimal(str(value)) to avoid floating-point drift.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.token_account import TokenAccount, TokenLedger, TokenSupply
from marketplace.services import token_service
from marketplace.services.token_service import (
    ensure_platform_account,
    create_account,
    transfer,
    deposit,
    get_balance,
    get_supply,
    verify_ledger_chain,
    debit_for_purchase,
    recalculate_tier,
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
    """For every transfer, sum of all balance changes = 0 (debits = credits + burn).

    The sender loses `amount`. The receiver gains `amount - fee`. The platform
    gains `fee - burn`. The burn is permanently destroyed.  So:
        -amount + (amount - fee) + (fee - burn) + burn = 0
    We verify this by snapshotting all balances before and after.
    """
    alice, _ = await make_agent("de_alice")
    bob, _ = await make_agent("de_bob")
    await make_token_account(alice.id, 5000)
    await make_token_account(bob.id, 0)

    # Snapshot balances before
    platform_before = Decimal(str((await get_balance(db, alice.id))["balance"]))  # placeholder
    # Actually get platform account balance directly
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

    supply_before = await get_supply(db)
    burned_before = Decimal(str(supply_before["total_burned"]))

    # Execute transfer
    ledger = await transfer(db, alice.id, bob.id, 1000, tx_type="sale")

    # Refresh platform account
    await db.refresh(platform_acct)
    platform_bal_after = Decimal(str(platform_acct.balance))

    alice_bal_after = Decimal(str((await get_balance(db, alice.id))["balance"]))
    bob_bal_after = Decimal(str((await get_balance(db, bob.id))["balance"]))

    supply_after = await get_supply(db)
    burned_after = Decimal(str(supply_after["total_burned"]))

    # Delta for each party
    delta_alice = alice_bal_after - alice_bal_before        # negative (sender)
    delta_bob = bob_bal_after - bob_bal_before              # positive (receiver)
    delta_platform = platform_bal_after - platform_bal_before  # positive (fee - burn)
    delta_burned = burned_after - burned_before             # positive (destroyed)

    # The invariant: all balance deltas + burn = 0
    net = delta_alice + delta_bob + delta_platform + delta_burned
    assert net == Decimal("0"), f"Double-entry violated: net = {net}"


# ---------------------------------------------------------------------------
# 2. Decimal precision — 6 decimal places maintained
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decimal_precision_no_rounding(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """0.000001 ARD transfers maintain 6 decimal places."""
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
# 3. Burn = fee * 50%
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_burn_matches_fee_pct(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """burn_amount = fee_amount * 0.50 exactly."""
    alice, _ = await make_agent("burn_alice")
    bob, _ = await make_agent("burn_bob")
    await make_token_account(alice.id, 5000)
    await make_token_account(bob.id, 0)

    ledger = await transfer(db, alice.id, bob.id, 1000, tx_type="sale")

    fee = Decimal(str(ledger.fee_amount))
    burn = Decimal(str(ledger.burn_amount))
    burn_pct = Decimal(str(settings.token_burn_pct))

    expected_burn = (fee * burn_pct).quantize(Decimal("0.000001"))
    assert burn == expected_burn, f"Burn {burn} != fee {fee} * {burn_pct} = {expected_burn}"


# ---------------------------------------------------------------------------
# 4. Fee = transfer_amount * 2%
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fee_matches_platform_pct(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """fee_amount = transfer_amount * 0.02 exactly."""
    alice, _ = await make_agent("fee_alice")
    bob, _ = await make_agent("fee_bob")
    await make_token_account(alice.id, 5000)
    await make_token_account(bob.id, 0)

    amount = Decimal("1000")
    ledger = await transfer(db, alice.id, bob.id, amount, tx_type="sale")

    fee = Decimal(str(ledger.fee_amount))
    fee_pct = Decimal(str(settings.token_platform_fee_pct))
    expected_fee = (amount * fee_pct).quantize(Decimal("0.000001"))

    assert fee == expected_fee, f"Fee {fee} != {amount} * {fee_pct} = {expected_fee}"


# ---------------------------------------------------------------------------
# 5. $0 listing -> zero ARD -> no transfer needed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_price_fee_calc(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """$0 listing -> 0 ARD -> transfer of 0 should raise ValueError (amount must be positive)."""
    buyer, _ = await make_agent("zp_buyer")
    seller, _ = await make_agent("zp_seller")
    await make_token_account(buyer.id, 5000)
    await make_token_account(seller.id, 0)

    # $0 listing means 0 / 0.001 = 0 ARD — transfer of 0 is rejected
    zero_ard = Decimal("0") / Decimal(str(settings.token_peg_usd))
    assert zero_ard == Decimal("0")

    with pytest.raises(ValueError, match="positive"):
        await transfer(db, buyer.id, seller.id, zero_ard, tx_type="purchase")


# ---------------------------------------------------------------------------
# 6. $100 listing -> correct ARD amount, fee, and burn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_price_fee_calc(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """$100 listing -> correct ARD amount and fee/burn."""
    buyer, _ = await make_agent("max_buyer")
    seller, _ = await make_agent("max_seller")

    peg = Decimal(str(settings.token_peg_usd))           # 0.001
    price_usd = Decimal("100")
    amount_ard = (price_usd / peg).quantize(Decimal("0.000001"))  # 100,000 ARD

    await make_token_account(buyer.id, float(amount_ard + Decimal("1000")))
    await make_token_account(seller.id, 0)

    ledger = await transfer(db, buyer.id, seller.id, amount_ard, tx_type="purchase")

    fee_pct = Decimal(str(settings.token_platform_fee_pct))
    burn_pct = Decimal(str(settings.token_burn_pct))

    expected_fee = (amount_ard * fee_pct).quantize(Decimal("0.000001"))
    expected_burn = (expected_fee * burn_pct).quantize(Decimal("0.000001"))

    assert Decimal(str(ledger.amount)) == amount_ard
    assert Decimal(str(ledger.fee_amount)) == expected_fee
    assert Decimal(str(ledger.burn_amount)) == expected_burn


# ---------------------------------------------------------------------------
# 7. Idempotency key dedup — same key twice returns same entry
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
# 8. Supply = sum(all balances) + total_burned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supply_equals_sum_of_balances(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """total_minted = sum(all balances) + total_burned."""
    alice, _ = await make_agent("sup_alice")
    bob, _ = await make_agent("sup_bob")
    await make_token_account(alice.id, 0)
    await make_token_account(bob.id, 0)

    # Deposit tokens (minting)
    await deposit(db, alice.id, 5000, deposit_id="sup-dep-1")
    await deposit(db, bob.id, 3000, deposit_id="sup-dep-2")

    # Execute a transfer to create some burn
    await transfer(db, alice.id, bob.id, 1000, tx_type="sale")

    # Sum all balances
    balance_sum_result = await db.execute(
        select(func.sum(TokenAccount.balance))
    )
    total_balances = Decimal(str(balance_sum_result.scalar() or 0))

    # Get supply
    supply_result = await db.execute(select(TokenSupply).where(TokenSupply.id == 1))
    supply = supply_result.scalar_one()
    total_minted = Decimal(str(supply.total_minted))
    total_burned = Decimal(str(supply.total_burned))

    # The invariant for user-deposited tokens:
    # deposits (8000) = sum_of_user_balances + platform_balance + burned
    # TokenSupply.total_minted includes a 1B genesis that's not in accounts,
    # so we verify the delta: our deposits = all balances + burned
    our_deposits = Decimal("8000.000000")  # 5000 + 3000
    assert our_deposits == total_balances + total_burned, (
        f"Supply invariant violated: deposits={our_deposits} != "
        f"balances={total_balances} + burned={total_burned} "
        f"= {total_balances + total_burned}"
    )


# ---------------------------------------------------------------------------
# 9. Platform treasury grows by (fee - burn) per transfer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_platform_treasury_grows_by_net_fee(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """platform.balance grows by (fee - burn) per transfer."""
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
    burn = Decimal(str(ledger.burn_amount))
    expected_growth = (fee - burn).quantize(Decimal("0.000001"))

    # Refresh
    await db.refresh(platform_acct)
    balance_after = Decimal(str(platform_acct.balance))

    actual_growth = (balance_after - balance_before).quantize(Decimal("0.000001"))
    assert actual_growth == expected_growth, (
        f"Platform grew by {actual_growth}, expected {expected_growth} (fee={fee}, burn={burn})"
    )


# ---------------------------------------------------------------------------
# 10. Quality bonus comes from mint (increases total_minted)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quality_bonus_comes_from_mint(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """Bonus deposit increases total_minted."""
    buyer, _ = await make_agent("qm_buyer")
    seller, _ = await make_agent("qm_seller")
    await make_token_account(buyer.id, 100000)
    await make_token_account(seller.id, 0)

    supply_before_result = await db.execute(select(TokenSupply).where(TokenSupply.id == 1))
    supply_before = supply_before_result.scalar_one()
    minted_before = Decimal(str(supply_before.total_minted))

    # Purchase with high quality to trigger bonus
    result = await debit_for_purchase(
        db, buyer.id, seller.id,
        amount_usdc=1.0, listing_quality=0.90, tx_id="qm-tx-001",
    )

    supply_after_result = await db.execute(select(TokenSupply).where(TokenSupply.id == 1))
    supply_after = supply_after_result.scalar_one()
    minted_after = Decimal(str(supply_after.total_minted))

    quality_bonus = Decimal(str(result["quality_bonus_axn"]))
    assert quality_bonus > Decimal("0"), "Expected a quality bonus for quality=0.90"

    # Minted should have increased by the purchase deposit amount + quality bonus
    # The purchase itself is a transfer (no mint), but the quality bonus IS a deposit (mint)
    # Also the initial deposits to fund accounts are mints
    # We just need: minted_after > minted_before, and the delta includes the bonus
    minted_delta = minted_after - minted_before
    assert minted_delta >= quality_bonus, (
        f"Minted delta {minted_delta} should include quality bonus {quality_bonus}"
    )


# ---------------------------------------------------------------------------
# 11. Signup bonus increases total_minted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signup_bonus_increases_minted(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """Deposit for signup bonus tracked in total_minted."""
    agent, _ = await make_agent("signup_agent")
    await make_token_account(agent.id, 0)

    supply_before_result = await db.execute(select(TokenSupply).where(TokenSupply.id == 1))
    supply_before = supply_before_result.scalar_one()
    minted_before = Decimal(str(supply_before.total_minted))

    signup_bonus = Decimal(str(settings.token_signup_bonus))  # 100 ARD
    await deposit(
        db, agent.id, float(signup_bonus),
        deposit_id="signup-bonus-001", memo="Signup bonus",
    )

    supply_after_result = await db.execute(select(TokenSupply).where(TokenSupply.id == 1))
    supply_after = supply_after_result.scalar_one()
    minted_after = Decimal(str(supply_after.total_minted))

    delta = minted_after - minted_before
    assert delta == signup_bonus.quantize(Decimal("0.000001")), (
        f"Minted delta {delta} != signup bonus {signup_bonus}"
    )


# ---------------------------------------------------------------------------
# 12. Ledger hash chain unbroken
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ledger_hash_chain_unbroken(
    db: AsyncSession, seed_platform, make_agent, make_token_account
):
    """Every entry's prev_hash matches previous entry's entry_hash."""
    alice, _ = await make_agent("hash_alice")
    bob, _ = await make_agent("hash_bob")
    await make_token_account(alice.id, 10000)
    await make_token_account(bob.id, 0)

    # Create multiple ledger entries to build a chain
    await deposit(db, alice.id, 500, deposit_id="hash-dep-1")
    await transfer(db, alice.id, bob.id, 200, tx_type="sale")
    await deposit(db, bob.id, 300, deposit_id="hash-dep-2")
    await transfer(db, alice.id, bob.id, 100, tx_type="purchase")

    # Verify chain using the service function
    chain_result = await verify_ledger_chain(db)

    assert chain_result["valid"] is True, (
        f"Ledger hash chain broken: {chain_result['errors']}"
    )
    assert chain_result["total_entries"] >= 4


# ---------------------------------------------------------------------------
# 13. Negative transfer rejected
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
# 14. Tier calculation boundaries — exactly 10,000 ARD volume = silver
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tier_calculation_boundaries(
    db: AsyncSession, seed_platform, make_agent
):
    """Exactly 10000 ARD volume -> silver (not bronze)."""
    agent, _ = await make_agent("tier_boundary")
    account = TokenAccount(
        id=_id(),
        agent_id=agent.id,
        balance=Decimal("0"),
        total_earned=Decimal("5000"),
        total_spent=Decimal("5000"),  # total volume = 10,000
    )
    db.add(account)
    await db.commit()

    tier = await recalculate_tier(db, agent.id)
    assert tier == "silver", f"Volume=10000 should be silver, got {tier}"

    # Just below the threshold: 9999.999999 -> bronze
    account.total_earned = Decimal("4999.999999")
    account.total_spent = Decimal("5000")
    await db.commit()

    tier = await recalculate_tier(db, agent.id)
    assert tier == "bronze", f"Volume=9999.999999 should be bronze, got {tier}"

    # Exactly at gold boundary: 100,000
    account.total_earned = Decimal("50000")
    account.total_spent = Decimal("50000")
    await db.commit()

    tier = await recalculate_tier(db, agent.id)
    assert tier == "gold", f"Volume=100000 should be gold, got {tier}"


# ---------------------------------------------------------------------------
# 15. Creator royalty deducted from agent after purchase
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
    amount_ard = Decimal("1000")
    ledger = await transfer(
        db, buyer.id, seller.id, amount_ard,
        tx_type="purchase", reference_id="royalty-tx-001",
    )

    fee = Decimal(str(ledger.fee_amount))
    net_to_seller = (amount_ard - fee).quantize(Decimal("0.000001"))
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
