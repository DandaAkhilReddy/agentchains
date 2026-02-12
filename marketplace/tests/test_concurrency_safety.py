"""Concurrency safety tests for the ARD token economy.

Validates financial invariants under rapid sequential operations:
- No double-spend (balance checked before every debit)
- Total supply conservation (minted == circulating + burned)
- Ledger hash chain integrity after many operations
- Idempotency key prevents duplicate processing
- Deterministic fee (2%) and burn (50% of fee) calculations

These tests use a single SQLite session (via the ``db`` fixture). True
parallel DB concurrency is not possible with SQLite's serialised writes,
so we test *sequential rapid-fire* operations that exercise the same code
paths a concurrent system would, verifying that the financial invariants
hold after every step.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount, TokenLedger, TokenSupply
from marketplace.services import token_service
from marketplace.services import deposit_service
from marketplace.services import listing_service
from marketplace.schemas.listing import ListingCreateRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FEE_PCT = Decimal("0.02")       # 2% platform fee
BURN_PCT = Decimal("0.50")      # 50% of fee is burned
QUANT = Decimal("0.000001")     # 6 decimal places


def _q(v) -> Decimal:
    """Quantise a value to 6 decimal places for comparison."""
    return Decimal(str(v)).quantize(QUANT)


# ---------------------------------------------------------------------------
# 1. test_double_spend_exact_balance
# ---------------------------------------------------------------------------

async def test_double_spend_exact_balance(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Agent has exactly 100 ARD. First transfer of 100 succeeds, second
    transfer of 100 raises ValueError (insufficient balance)."""
    alice, _ = await make_agent("alice")
    bob, _ = await make_agent("bob")
    await make_token_account(alice.id, 100)
    await make_token_account(bob.id, 0)

    # First transfer drains alice completely
    await token_service.transfer(db, alice.id, bob.id, 100, tx_type="purchase")

    bal = await token_service.get_balance(db, alice.id)
    assert bal["balance"] == 0.0

    # Second transfer must fail -- no funds left
    with pytest.raises(ValueError, match="Insufficient balance"):
        await token_service.transfer(db, alice.id, bob.id, 100, tx_type="purchase")


# ---------------------------------------------------------------------------
# 2. test_double_spend_two_recipients
# ---------------------------------------------------------------------------

async def test_double_spend_two_recipients(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Agent has 100 ARD, sends 60 to A then tries 60 to B. Second fails."""
    sender, _ = await make_agent("sender")
    recv_a, _ = await make_agent("recv_a")
    recv_b, _ = await make_agent("recv_b")
    await make_token_account(sender.id, 100)
    await make_token_account(recv_a.id, 0)
    await make_token_account(recv_b.id, 0)

    await token_service.transfer(db, sender.id, recv_a.id, 60, tx_type="purchase")

    bal = await token_service.get_balance(db, sender.id)
    assert bal["balance"] == 40.0  # 100 - 60

    with pytest.raises(ValueError, match="Insufficient balance"):
        await token_service.transfer(db, sender.id, recv_b.id, 60, tx_type="purchase")


# ---------------------------------------------------------------------------
# 3. test_parallel_deposits_all_succeed
# ---------------------------------------------------------------------------

async def test_parallel_deposits_all_succeed(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Create 3 deposits, confirm all 3, verify total balance is correct."""
    agent, _ = await make_agent("depositor")
    await make_token_account(agent.id, 0)

    deposit_ids = []
    for i in range(3):
        dep = await deposit_service.create_deposit(
            db, agent.id, amount_fiat=10.0, currency="USD",
        )
        deposit_ids.append(dep["id"])

    for did in deposit_ids:
        await deposit_service.confirm_deposit(db, did)

    bal = await token_service.get_balance(db, agent.id)
    # Each $10 USD at rate 0.001 per ARD = 10000 ARD per deposit
    expected = 10000.0 * 3
    assert bal["balance"] == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# 4. test_confirm_same_deposit_twice_fails
# ---------------------------------------------------------------------------

async def test_confirm_same_deposit_twice_fails(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Confirming a deposit twice raises ValueError on the second attempt."""
    agent, _ = await make_agent("double-confirm")
    await make_token_account(agent.id, 0)

    dep = await deposit_service.create_deposit(
        db, agent.id, amount_fiat=5.0, currency="USD",
    )
    await deposit_service.confirm_deposit(db, dep["id"])

    with pytest.raises(ValueError, match="expected 'pending'"):
        await deposit_service.confirm_deposit(db, dep["id"])


# ---------------------------------------------------------------------------
# 5. test_transfers_preserve_total_supply
# ---------------------------------------------------------------------------

async def test_transfers_preserve_total_supply(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """5 transfers between agents. Verify: total_minted == circulating + total_burned."""
    agents = []
    for i in range(4):
        a, _ = await make_agent(f"supply-agent-{i}")
        await make_token_account(a.id, 1000)
        agents.append(a)

    # Deposit to increase minted supply (transfer debits from existing balance)
    # but we need the supply row to track minted vs burned correctly.
    # Since make_token_account injects balance directly without going through
    # the deposit flow, we do a manual deposit to set minted baseline.
    for a in agents:
        await token_service.deposit(db, a.id, 500, memo="seed")

    transfers = [
        (0, 1, 100), (1, 2, 50), (2, 3, 30), (3, 0, 20), (0, 2, 10),
    ]
    for s_idx, r_idx, amt in transfers:
        await token_service.transfer(
            db, agents[s_idx].id, agents[r_idx].id, amt, tx_type="purchase",
        )

    supply = await token_service.get_supply(db)
    assert supply["total_minted"] == pytest.approx(
        supply["circulating"] + supply["total_burned"], rel=1e-6,
    )


# ---------------------------------------------------------------------------
# 6. test_ledger_chain_valid_after_many_operations
# ---------------------------------------------------------------------------

async def test_ledger_chain_valid_after_many_operations(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Perform 10 operations then verify the SHA-256 hash chain is intact."""
    alice, _ = await make_agent("chain-alice")
    bob, _ = await make_agent("chain-bob")
    await make_token_account(alice.id, 10000)
    await make_token_account(bob.id, 10000)

    for i in range(5):
        await token_service.transfer(
            db, alice.id, bob.id, 10, tx_type="purchase", memo=f"op-{i}",
        )
    for i in range(5):
        await token_service.transfer(
            db, bob.id, alice.id, 5, tx_type="purchase", memo=f"op-back-{i}",
        )

    result = await token_service.verify_ledger_chain(db)
    assert result["valid"] is True
    assert result["total_entries"] >= 10
    assert len(result["errors"]) == 0


# ---------------------------------------------------------------------------
# 7. test_ten_transfers_balance_consistency
# ---------------------------------------------------------------------------

async def test_ten_transfers_balance_consistency(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """10 sequential transfers. Verify the global supply invariant
    (minted == circulating + burned) holds, and the deposited tokens are
    fully accounted for across agent + platform balances + burned tokens."""
    alice, _ = await make_agent("ten-alice")
    bob, _ = await make_agent("ten-bob")

    # Use deposit flow so minted supply is tracked
    await make_token_account(alice.id, 0)
    await make_token_account(bob.id, 0)
    await token_service.deposit(db, alice.id, 5000, memo="seed")
    await token_service.deposit(db, bob.id, 5000, memo="seed")

    supply_before = await token_service.get_supply(db)
    deposited = Decimal("10000")  # 5000 + 5000

    for i in range(10):
        await token_service.transfer(
            db, alice.id, bob.id, 50, tx_type="purchase", memo=f"t-{i}",
        )

    alice_bal = await token_service.get_balance(db, alice.id)
    bob_bal = await token_service.get_balance(db, bob.id)
    supply = await token_service.get_supply(db)

    # Global invariant: total_minted == circulating + total_burned
    assert _q(supply["total_minted"]) == (
        _q(supply["circulating"]) + _q(supply["total_burned"])
    )

    # Agent-level conservation: deposited tokens = sum(balances) + platform_fees_kept + burned
    # The platform keeps (fee - burn) per transfer, and burn is removed from circulation.
    burns_from_transfers = _q(supply["total_burned"]) - _q(supply_before["total_burned"])
    platform_gains = _q(supply["platform_balance"]) - _q(supply_before["platform_balance"])
    total_accounted = (
        _q(alice_bal["balance"])
        + _q(bob_bal["balance"])
        + platform_gains
        + burns_from_transfers
    )
    assert float(total_accounted) == pytest.approx(float(deposited), rel=1e-6)


# ---------------------------------------------------------------------------
# 8. test_balance_never_negative_rapid_operations
# ---------------------------------------------------------------------------

async def test_balance_never_negative_rapid_operations(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Transfer repeatedly, checking balance >= 0 after every operation."""
    alice, _ = await make_agent("nonneg-alice")
    bob, _ = await make_agent("nonneg-bob")
    await make_token_account(alice.id, 500)
    await make_token_account(bob.id, 500)

    for i in range(10):
        try:
            await token_service.transfer(
                db, alice.id, bob.id, 60, tx_type="purchase",
            )
        except ValueError:
            pass  # expected when balance runs out

        a_bal = await token_service.get_balance(db, alice.id)
        b_bal = await token_service.get_balance(db, bob.id)
        assert a_bal["balance"] >= 0, f"Alice balance went negative on iteration {i}"
        assert b_bal["balance"] >= 0, f"Bob balance went negative on iteration {i}"


# ---------------------------------------------------------------------------
# 9. test_supply_minted_equals_circulating_plus_burned
# ---------------------------------------------------------------------------

async def test_supply_minted_equals_circulating_plus_burned(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """After multiple deposits and transfers, verify supply invariant."""
    a1, _ = await make_agent("supply-a1")
    a2, _ = await make_agent("supply-a2")
    await make_token_account(a1.id, 0)
    await make_token_account(a2.id, 0)

    # Deposits add to minted and circulating
    await token_service.deposit(db, a1.id, 2000, memo="d1")
    await token_service.deposit(db, a2.id, 3000, memo="d2")

    # Transfers burn tokens, reducing circulating
    await token_service.transfer(db, a1.id, a2.id, 500, tx_type="purchase")
    await token_service.transfer(db, a2.id, a1.id, 200, tx_type="purchase")

    supply = await token_service.get_supply(db)
    minted = _q(supply["total_minted"])
    circulating = _q(supply["circulating"])
    burned = _q(supply["total_burned"])

    assert minted == circulating + burned


# ---------------------------------------------------------------------------
# 10. test_concurrent_account_creation_idempotent
# ---------------------------------------------------------------------------

async def test_concurrent_account_creation_idempotent(
    db: AsyncSession, make_agent, seed_platform,
):
    """Calling ensure_platform_account twice still results in exactly 1
    platform account row."""
    p1 = await token_service.ensure_platform_account(db)
    p2 = await token_service.ensure_platform_account(db)
    assert p1.id == p2.id

    # Count platform accounts (agent_id IS NULL, creator_id IS NULL)
    result = await db.execute(
        select(func.count(TokenAccount.id)).where(
            TokenAccount.agent_id.is_(None),
            TokenAccount.creator_id.is_(None),
        )
    )
    count = result.scalar()
    assert count == 1


# ---------------------------------------------------------------------------
# 11. test_create_account_twice_raises
# ---------------------------------------------------------------------------

async def test_create_account_twice_raises(
    db: AsyncSession, make_agent, seed_platform,
):
    """create_account for the same agent_id twice returns the same account
    (idempotent -- does NOT raise). Verify same ID returned."""
    agent, _ = await make_agent("dup-agent")
    acct1 = await token_service.create_account(db, agent.id)
    acct2 = await token_service.create_account(db, agent.id)

    # The service is idempotent: returns existing rather than raising
    assert acct1.id == acct2.id

    # Verify only 1 account exists for this agent
    result = await db.execute(
        select(func.count(TokenAccount.id)).where(
            TokenAccount.agent_id == agent.id
        )
    )
    assert result.scalar() == 1


# ---------------------------------------------------------------------------
# 12. test_multiple_listing_creation
# ---------------------------------------------------------------------------

async def test_multiple_listing_creation(
    db: AsyncSession, make_agent, seed_platform,
):
    """Create 10 listings rapidly; all get unique IDs."""
    seller, _ = await make_agent("listing-seller")

    listing_ids = set()
    for i in range(10):
        req = ListingCreateRequest(
            title=f"Listing {i}",
            category="web_search",
            content=f"Content payload for listing {i}",
            price_usdc=1.0 + i * 0.1,
        )
        listing = await listing_service.create_listing(db, seller.id, req)
        listing_ids.add(listing.id)

    assert len(listing_ids) == 10, "All 10 listings must have unique IDs"


# ---------------------------------------------------------------------------
# 13. test_rapid_deposit_withdraw_balance
# ---------------------------------------------------------------------------

async def test_rapid_deposit_withdraw_balance(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Deposit then transfer away. Balance = deposit - transfer amount."""
    agent, _ = await make_agent("dep-withdraw")
    recipient, _ = await make_agent("dep-recv")
    await make_token_account(agent.id, 0)
    await make_token_account(recipient.id, 0)

    # Deposit 1000 ARD
    await token_service.deposit(db, agent.id, 1000, memo="deposit")

    # Transfer 400 away
    await token_service.transfer(
        db, agent.id, recipient.id, 400, tx_type="purchase",
    )

    bal = await token_service.get_balance(db, agent.id)
    # Agent paid 400 total (sender is debited the full amount)
    assert bal["balance"] == pytest.approx(600.0, rel=1e-6)

    # Recipient gets 400 - 2% fee = 392
    recv_bal = await token_service.get_balance(db, recipient.id)
    expected_recv = float(_q(Decimal("400") - Decimal("400") * FEE_PCT))
    assert recv_bal["balance"] == pytest.approx(expected_recv, rel=1e-4)


# ---------------------------------------------------------------------------
# 14. test_transfer_a_to_b_then_b_to_a
# ---------------------------------------------------------------------------

async def test_transfer_a_to_b_then_b_to_a(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Bidirectional transfers both succeed and balances are correct."""
    a, _ = await make_agent("bidir-a")
    b, _ = await make_agent("bidir-b")
    await make_token_account(a.id, 1000)
    await make_token_account(b.id, 1000)

    # A -> B: 200
    await token_service.transfer(db, a.id, b.id, 200, tx_type="purchase")
    # B -> A: 100
    await token_service.transfer(db, b.id, a.id, 100, tx_type="purchase")

    a_bal = await token_service.get_balance(db, a.id)
    b_bal = await token_service.get_balance(db, b.id)

    fee_200 = _q(Decimal("200") * FEE_PCT)    # 4.0
    fee_100 = _q(Decimal("100") * FEE_PCT)     # 2.0

    # A started with 1000, sent 200, received (100 - fee_100)
    expected_a = float(_q(Decimal("1000") - Decimal("200") + (Decimal("100") - fee_100)))
    # B started with 1000, sent 100, received (200 - fee_200)
    expected_b = float(_q(Decimal("1000") - Decimal("100") + (Decimal("200") - fee_200)))

    assert a_bal["balance"] == pytest.approx(expected_a, rel=1e-4)
    assert b_bal["balance"] == pytest.approx(expected_b, rel=1e-4)


# ---------------------------------------------------------------------------
# 15. test_three_way_circular_transfer
# ---------------------------------------------------------------------------

async def test_three_way_circular_transfer(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """A -> B -> C -> A. All succeed. Supply unchanged minus burns."""
    a, _ = await make_agent("circ-a")
    b, _ = await make_agent("circ-b")
    c, _ = await make_agent("circ-c")

    await make_token_account(a.id, 0)
    await make_token_account(b.id, 0)
    await make_token_account(c.id, 0)

    # Seed via deposits so supply is tracked
    await token_service.deposit(db, a.id, 1000, memo="seed-a")
    await token_service.deposit(db, b.id, 1000, memo="seed-b")
    await token_service.deposit(db, c.id, 1000, memo="seed-c")

    supply_before = await token_service.get_supply(db)

    await token_service.transfer(db, a.id, b.id, 100, tx_type="purchase")
    await token_service.transfer(db, b.id, c.id, 80, tx_type="purchase")
    await token_service.transfer(db, c.id, a.id, 60, tx_type="purchase")

    supply_after = await token_service.get_supply(db)

    # Total minted unchanged (no new deposits)
    assert supply_after["total_minted"] == supply_before["total_minted"]

    # Supply invariant still holds
    assert _q(supply_after["total_minted"]) == (
        _q(supply_after["circulating"]) + _q(supply_after["total_burned"])
    )

    # Burns increased
    assert supply_after["total_burned"] > supply_before["total_burned"]


# ---------------------------------------------------------------------------
# 16. test_deterministic_fee_after_many_transfers
# ---------------------------------------------------------------------------

async def test_deterministic_fee_after_many_transfers(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Fee is always exactly 2% of the transfer amount."""
    alice, _ = await make_agent("fee-alice")
    bob, _ = await make_agent("fee-bob")
    await make_token_account(alice.id, 100_000)
    await make_token_account(bob.id, 0)

    amounts = [10, 25, 50, 100, 333, 1000, 7777, 12345]
    for amt in amounts:
        ledger = await token_service.transfer(
            db, alice.id, bob.id, amt, tx_type="purchase",
        )
        expected_fee = _q(Decimal(str(amt)) * FEE_PCT)
        actual_fee = _q(ledger.fee_amount)
        assert actual_fee == expected_fee, (
            f"Fee mismatch for amount={amt}: expected {expected_fee}, got {actual_fee}"
        )


# ---------------------------------------------------------------------------
# 17. test_deterministic_burn_after_many_transfers
# ---------------------------------------------------------------------------

async def test_deterministic_burn_after_many_transfers(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Burn is always exactly 50% of the fee (which is 2% of amount)."""
    alice, _ = await make_agent("burn-alice")
    bob, _ = await make_agent("burn-bob")
    await make_token_account(alice.id, 100_000)
    await make_token_account(bob.id, 0)

    amounts = [10, 25, 50, 100, 333, 1000, 7777, 12345]
    for amt in amounts:
        ledger = await token_service.transfer(
            db, alice.id, bob.id, amt, tx_type="purchase",
        )
        expected_fee = _q(Decimal(str(amt)) * FEE_PCT)
        expected_burn = _q(expected_fee * BURN_PCT)
        actual_burn = _q(ledger.burn_amount)
        assert actual_burn == expected_burn, (
            f"Burn mismatch for amount={amt}: expected {expected_burn}, got {actual_burn}"
        )


# ---------------------------------------------------------------------------
# 18. test_ledger_entries_count_matches_operations
# ---------------------------------------------------------------------------

async def test_ledger_entries_count_matches_operations(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """N operations produce the expected number of ledger entries."""
    alice, _ = await make_agent("count-alice")
    bob, _ = await make_agent("count-bob")
    await make_token_account(alice.id, 0)
    await make_token_account(bob.id, 0)

    # 2 deposits + 3 transfers = 5 ledger entries
    await token_service.deposit(db, alice.id, 5000, memo="d1")
    await token_service.deposit(db, bob.id, 5000, memo="d2")

    for i in range(3):
        await token_service.transfer(
            db, alice.id, bob.id, 100, tx_type="purchase", memo=f"t-{i}",
        )

    count_result = await db.execute(select(func.count(TokenLedger.id)))
    total_entries = count_result.scalar()

    # 2 deposits + 3 transfers = 5
    assert total_entries == 5


# ---------------------------------------------------------------------------
# 19. test_balance_after_mixed_credits_debits
# ---------------------------------------------------------------------------

async def test_balance_after_mixed_credits_debits(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Mix of deposits and transfers. Final balance computed correctly."""
    agent, _ = await make_agent("mixed-agent")
    recipient, _ = await make_agent("mixed-recv")
    await make_token_account(agent.id, 0)
    await make_token_account(recipient.id, 0)

    # Deposit 1000
    await token_service.deposit(db, agent.id, 1000, memo="d1")
    # Deposit another 500
    await token_service.deposit(db, agent.id, 500, memo="d2")
    # Transfer 200 away
    await token_service.transfer(
        db, agent.id, recipient.id, 200, tx_type="purchase",
    )
    # Deposit 300 more
    await token_service.deposit(db, agent.id, 300, memo="d3")
    # Transfer 100 away
    await token_service.transfer(
        db, agent.id, recipient.id, 100, tx_type="purchase",
    )

    bal = await token_service.get_balance(db, agent.id)
    # 1000 + 500 - 200 + 300 - 100 = 1500
    assert bal["balance"] == pytest.approx(1500.0, rel=1e-6)


# ---------------------------------------------------------------------------
# 20. test_idempotency_key_prevents_double_processing
# ---------------------------------------------------------------------------

async def test_idempotency_key_prevents_double_processing(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Transfer with the same idempotency_key returns the existing ledger
    entry on replay, without debiting the sender a second time."""
    alice, _ = await make_agent("idemp-alice")
    bob, _ = await make_agent("idemp-bob")
    await make_token_account(alice.id, 1000)
    await make_token_account(bob.id, 0)

    idem_key = "unique-transfer-key-abc-123"

    ledger1 = await token_service.transfer(
        db, alice.id, bob.id, 100,
        tx_type="purchase",
        idempotency_key=idem_key,
    )

    bal_after_first = await token_service.get_balance(db, alice.id)

    # Second call with same key -- should return same ledger, no second debit
    ledger2 = await token_service.transfer(
        db, alice.id, bob.id, 100,
        tx_type="purchase",
        idempotency_key=idem_key,
    )

    bal_after_second = await token_service.get_balance(db, alice.id)

    # Same ledger entry returned
    assert ledger1.id == ledger2.id

    # Balance unchanged between first and second call
    assert bal_after_first["balance"] == bal_after_second["balance"]

    # Alice was only debited once (1000 - 100 = 900)
    assert bal_after_first["balance"] == pytest.approx(900.0, rel=1e-6)

    # Only one ledger entry with this key
    result = await db.execute(
        select(func.count(TokenLedger.id)).where(
            TokenLedger.idempotency_key == idem_key,
        )
    )
    assert result.scalar() == 1
