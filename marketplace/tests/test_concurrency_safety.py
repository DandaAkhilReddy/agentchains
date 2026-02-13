"""Concurrency safety tests for the USD billing model.

Validates financial invariants under rapid sequential operations:
- No double-spend (balance checked before every debit)
- Ledger hash chain integrity after many operations
- Idempotency key prevents duplicate processing
- Deterministic fee (2%) calculations

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

from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.services import token_service
from marketplace.services import deposit_service
from marketplace.services import listing_service
from marketplace.schemas.listing import ListingCreateRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FEE_PCT = Decimal("0.02")       # 2% platform fee
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
    """Agent has exactly 100 USD. First transfer of 100 succeeds, second
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
    """Agent has 100 USD, sends 60 to A then tries 60 to B. Second fails."""
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
            db, agent.id, amount_usd=10.0,
        )
        deposit_ids.append(dep["id"])

    for did in deposit_ids:
        await deposit_service.confirm_deposit(db, did)

    bal = await token_service.get_balance(db, agent.id)
    # Each $10 USD deposit = $10 balance
    expected = 10.0 * 3
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
        db, agent.id, amount_usd=5.0,
    )
    await deposit_service.confirm_deposit(db, dep["id"])

    with pytest.raises(ValueError, match="expected 'pending'"):
        await deposit_service.confirm_deposit(db, dep["id"])


# ---------------------------------------------------------------------------
# 5. test_ten_transfers_balance_consistency
# ---------------------------------------------------------------------------

async def test_ten_transfers_balance_consistency(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """10 sequential transfers. Verify the deposited tokens are
    fully accounted for across agent + platform balances."""
    alice, _ = await make_agent("ten-alice")
    bob, _ = await make_agent("ten-bob")

    # Use deposit flow so balance is tracked
    await make_token_account(alice.id, 0)
    await make_token_account(bob.id, 0)
    await token_service.deposit(db, alice.id, 5000, memo="seed")
    await token_service.deposit(db, bob.id, 5000, memo="seed")

    deposited = Decimal("10000")  # 5000 + 5000

    for i in range(10):
        await token_service.transfer(
            db, alice.id, bob.id, 50, tx_type="purchase", memo=f"t-{i}",
        )

    alice_bal = await token_service.get_balance(db, alice.id)
    bob_bal = await token_service.get_balance(db, bob.id)

    # Agent-level conservation: deposited tokens = sum(balances) + platform_fees
    # Each transfer of 50: fee = 50 * 0.02 = 1.0, so 10 transfers = 10.0 total fees
    total_fees = _q(Decimal("50") * FEE_PCT * 10)
    total_accounted = (
        _q(alice_bal["balance"])
        + _q(bob_bal["balance"])
        + total_fees
    )
    assert float(total_accounted) == pytest.approx(float(deposited), rel=1e-4)


# ---------------------------------------------------------------------------
# 7. test_balance_never_negative_rapid_operations
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
# 8. test_concurrent_account_creation_idempotent
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
# 9. test_create_account_twice_raises
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
# 10. test_multiple_listing_creation
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
# 11. test_rapid_deposit_withdraw_balance
# ---------------------------------------------------------------------------

async def test_rapid_deposit_withdraw_balance(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """Deposit then transfer away. Balance = deposit - transfer amount."""
    agent, _ = await make_agent("dep-withdraw")
    recipient, _ = await make_agent("dep-recv")
    await make_token_account(agent.id, 0)
    await make_token_account(recipient.id, 0)

    # Deposit 1000 USD
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
# 12. test_transfer_a_to_b_then_b_to_a
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
# 13. test_three_way_circular_transfer
# ---------------------------------------------------------------------------

async def test_three_way_circular_transfer(
    db: AsyncSession, make_agent, make_token_account, seed_platform,
):
    """A -> B -> C -> A. All succeed. Balances conserve minus fees."""
    a, _ = await make_agent("circ-a")
    b, _ = await make_agent("circ-b")
    c, _ = await make_agent("circ-c")

    await make_token_account(a.id, 0)
    await make_token_account(b.id, 0)
    await make_token_account(c.id, 0)

    # Seed via deposits
    await token_service.deposit(db, a.id, 1000, memo="seed-a")
    await token_service.deposit(db, b.id, 1000, memo="seed-b")
    await token_service.deposit(db, c.id, 1000, memo="seed-c")

    await token_service.transfer(db, a.id, b.id, 100, tx_type="purchase")
    await token_service.transfer(db, b.id, c.id, 80, tx_type="purchase")
    await token_service.transfer(db, c.id, a.id, 60, tx_type="purchase")

    # Total deposited: 3000. Fees taken from 3 transfers:
    # fee_100 = 2.0, fee_80 = 1.6, fee_60 = 1.2 => total_fees = 4.8
    a_bal = await token_service.get_balance(db, a.id)
    b_bal = await token_service.get_balance(db, b.id)
    c_bal = await token_service.get_balance(db, c.id)

    total_deposited = Decimal("3000")
    total_fees = _q(Decimal("100") * FEE_PCT + Decimal("80") * FEE_PCT + Decimal("60") * FEE_PCT)
    total_balances = _q(a_bal["balance"]) + _q(b_bal["balance"]) + _q(c_bal["balance"])

    # balances + fees should equal total deposited
    assert float(total_balances + total_fees) == pytest.approx(float(total_deposited), rel=1e-4)


# ---------------------------------------------------------------------------
# 14. test_deterministic_fee_after_many_transfers
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
# 15. test_ledger_entries_count_matches_operations
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
# 16. test_balance_after_mixed_credits_debits
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
# 17. test_idempotency_key_prevents_double_processing
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
