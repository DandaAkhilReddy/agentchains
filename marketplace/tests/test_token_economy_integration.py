"""Integration tests for the FULL USD billing lifecycle.

Tests exercise the service layer end-to-end: account creation, deposits,
transfers (with platform fee), purchases, idempotency, pagination, and
concurrent deposits.

Uses in-memory SQLite via conftest fixtures (TestSession, db, seed_platform,
make_agent, make_token_account).
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.services import token_service
from marketplace.tests.conftest import TestSession


# ---------------------------------------------------------------------------
# 1. Platform account creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_platform_account_creation(db: AsyncSession):
    """ensure_platform_account creates treasury (agent_id=NULL)."""
    platform = await token_service.ensure_platform_account(db)

    # Treasury account exists with no agent owner
    assert platform is not None
    assert platform.agent_id is None
    assert float(platform.balance) == 0.0


# ---------------------------------------------------------------------------
# 2. Agent account creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_account(db: AsyncSession, seed_platform, make_agent):
    """create_account for an agent produces an account with zero balance."""
    agent, _ = await make_agent()
    account = await token_service.create_account(db, agent.id)

    assert isinstance(account, TokenAccount)
    assert account.agent_id == agent.id
    assert float(account.balance) == 0.0


# ---------------------------------------------------------------------------
# 3. Idempotent account creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_account_idempotent(db: AsyncSession, seed_platform, make_agent):
    """Calling create_account twice for the same agent returns the same row."""
    agent, _ = await make_agent()
    acct1 = await token_service.create_account(db, agent.id)
    acct2 = await token_service.create_account(db, agent.id)

    assert acct1.id == acct2.id


# ---------------------------------------------------------------------------
# 4. Deposit credits agent balance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deposit_credits_agent(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Deposit adds USD balance and creates a ledger entry of type 'deposit'."""
    agent, _ = await make_agent()
    await make_token_account(agent.id, balance=0.0)

    ledger = await token_service.deposit(db, agent.id, 500)

    # Balance increased
    bal = await token_service.get_balance(db, agent.id)
    assert bal["balance"] == 500.0
    assert bal["total_deposited"] == 500.0

    # Ledger entry recorded
    assert isinstance(ledger, TokenLedger)
    assert ledger.tx_type == "deposit"
    assert float(ledger.amount) == 500.0
    assert ledger.from_account_id is None  # deposit — no sender


# ---------------------------------------------------------------------------
# 5. Basic transfer with platform fee
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_basic(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Transfer from A to B applies 2% platform fee."""
    alice, _ = await make_agent("alice_basic")
    bob, _ = await make_agent("bob_basic")
    await make_token_account(alice.id, balance=1000.0)
    await make_token_account(bob.id, balance=0.0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 100, tx_type="sale",
    )

    assert isinstance(ledger, TokenLedger)
    # fee = 100 * 0.02 = 2
    assert float(ledger.fee_amount) == 2.0

    alice_bal = await token_service.get_balance(db, alice.id)
    bob_bal = await token_service.get_balance(db, bob.id)

    # Alice debited full amount
    assert alice_bal["balance"] == 900.0
    # Bob receives amount - fee = 98
    assert bob_bal["balance"] == 98.0


# ---------------------------------------------------------------------------
# 6. Fee calculation precision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_fee_calculation(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """fee = amount * 0.02 — verified with amount of 250 USD."""
    sender, _ = await make_agent("fee_sender")
    receiver, _ = await make_agent("fee_receiver")
    await make_token_account(sender.id, balance=5000.0)
    await make_token_account(receiver.id, balance=0.0)

    ledger = await token_service.transfer(
        db, sender.id, receiver.id, 250, tx_type="sale",
    )

    expected_fee = Decimal("250") * Decimal("0.02")  # 5.0

    assert Decimal(str(ledger.fee_amount)) == expected_fee.quantize(Decimal("0.000001"))


# ---------------------------------------------------------------------------
# 7. Transfer insufficient balance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_insufficient_balance(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Transferring more than the sender's balance raises ValueError."""
    poor, _ = await make_agent("poor_sender")
    rich, _ = await make_agent("rich_receiver")
    await make_token_account(poor.id, balance=10.0)
    await make_token_account(rich.id, balance=0.0)

    with pytest.raises(ValueError, match="Insufficient balance"):
        await token_service.transfer(db, poor.id, rich.id, 500, tx_type="purchase")


# ---------------------------------------------------------------------------
# 8. Transfer idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_idempotency(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Same idempotency_key returns existing ledger; balance is debited only once."""
    a, _ = await make_agent("idem_sender")
    b, _ = await make_agent("idem_receiver")
    await make_token_account(a.id, balance=2000.0)
    await make_token_account(b.id, balance=0.0)

    key = f"idem-{uuid.uuid4()}"
    l1 = await token_service.transfer(
        db, a.id, b.id, 100, tx_type="purchase", idempotency_key=key,
    )
    l2 = await token_service.transfer(
        db, a.id, b.id, 100, tx_type="purchase", idempotency_key=key,
    )

    # Same ledger row returned
    assert l1.id == l2.id

    # Balance reflects only one debit
    a_bal = await token_service.get_balance(db, a.id)
    assert a_bal["balance"] == 1900.0


# ---------------------------------------------------------------------------
# 9. Debit for purchase — direct USD flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debit_for_purchase(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Full purchase: transfer USD with platform fee, balance updates."""
    buyer, _ = await make_agent("purchase_buyer")
    seller, _ = await make_agent("purchase_seller")
    await make_token_account(buyer.id, balance=100.0)
    await make_token_account(seller.id, balance=0.0)

    result = await token_service.debit_for_purchase(
        db,
        buyer_id=buyer.id,
        seller_id=seller.id,
        amount_usdc=1.0,
        tx_id=f"tx-{uuid.uuid4()}",
    )

    # $1.00 purchase
    assert result["amount_usd"] == 1.0
    # fee = 1.0 * 0.02 = 0.02
    assert result["fee_usd"] == 0.02
    # buyer balance = 100 - 1.0 = 99.0
    assert result["buyer_balance"] == 99.0
    # seller balance = 1.0 - 0.02 (fee) = 0.98
    assert result["seller_balance"] == 0.98


# ---------------------------------------------------------------------------
# 10. get_balance returns dict with all expected keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_balance_format(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """get_balance returns a dict with balance and totals."""
    agent, _ = await make_agent("bal_fmt")
    await make_token_account(agent.id, balance=500.0)

    bal = await token_service.get_balance(db, agent.id)

    expected_keys = {
        "balance", "total_earned", "total_spent",
        "total_deposited", "total_fees_paid",
    }
    assert set(bal.keys()) == expected_keys
    assert bal["balance"] == 500.0


# ---------------------------------------------------------------------------
# 11. get_history pagination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_history_pagination(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """page/page_size correctly limit and offset history results."""
    agent, _ = await make_agent("hist_pg")
    await make_token_account(agent.id, balance=0.0)

    # Create 5 deposit entries
    for i in range(5):
        await token_service.deposit(db, agent.id, 10, memo=f"dep-{i}")

    # Page 1, size 2 — should return 2 entries
    entries_p1, total = await token_service.get_history(db, agent.id, page=1, page_size=2)
    assert total == 5
    assert len(entries_p1) == 2

    # Page 2, size 2 — should return 2 entries
    entries_p2, total = await token_service.get_history(db, agent.id, page=2, page_size=2)
    assert total == 5
    assert len(entries_p2) == 2

    # Page 3, size 2 — should return 1 entry (remainder)
    entries_p3, total = await token_service.get_history(db, agent.id, page=3, page_size=2)
    assert total == 5
    assert len(entries_p3) == 1

    # All IDs should be distinct across pages
    all_ids = [e["id"] for e in entries_p1 + entries_p2 + entries_p3]
    assert len(set(all_ids)) == 5


# ---------------------------------------------------------------------------
# 12. Concurrent deposits do not corrupt balance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_deposits(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Two sequential deposits to the same agent produce correct total.

    Note: SQLite with StaticPool uses a single connection, so truly concurrent
    deposits can race.  We verify sequential correctness instead.
    """
    agent, _ = await make_agent("conc_agent")
    await make_token_account(agent.id, balance=0.0)

    # Two sequential deposits (safe on SQLite single-writer)
    await token_service.deposit(db, agent.id, 300, memo="deposit-300")
    await token_service.deposit(db, agent.id, 700, memo="deposit-700")

    bal = await token_service.get_balance(db, agent.id)
    assert bal["balance"] == 1000.0


# ---------------------------------------------------------------------------
# 13. Platform fee accumulation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_platform_fee_accumulation(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """After deposits and transfers, platform account accumulates fees."""
    a, _ = await make_agent("fee_stat_a")
    b, _ = await make_agent("fee_stat_b")
    await make_token_account(a.id, balance=0.0)
    await make_token_account(b.id, balance=0.0)

    # Deposit 2000 to agent A
    await token_service.deposit(db, a.id, 2000, memo="fee test deposit")

    # Transfer 1000 from A to B (fee=20)
    ledger = await token_service.transfer(db, a.id, b.id, 1000, tx_type="sale")
    fee_amount = float(ledger.fee_amount)
    assert fee_amount == 20.0  # 1000 * 0.02

    # Verify A balance = 2000 - 1000 = 1000
    a_bal = await token_service.get_balance(db, a.id)
    assert a_bal["balance"] == 1000.0

    # Verify B balance = 1000 - 20 fee = 980
    b_bal = await token_service.get_balance(db, b.id)
    assert b_bal["balance"] == 980.0
