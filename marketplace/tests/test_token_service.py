"""Unit tests for the AXN token service — core transfer engine.

Tests use in-memory SQLite via conftest fixtures.
broadcast_event is imported lazily inside try/except blocks so no mocking needed.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount, TokenLedger, TokenSupply
from marketplace.services import token_service


# ---------------------------------------------------------------------------
# Account creation
# ---------------------------------------------------------------------------

async def test_ensure_platform_account_creates_once(db: AsyncSession):
    """First call creates platform + supply; second returns same account."""
    p1 = await token_service.ensure_platform_account(db)
    assert p1.agent_id is None
    assert p1.tier == "platform"

    p2 = await token_service.ensure_platform_account(db)
    assert p2.id == p1.id  # same row


async def test_create_account_success(db: AsyncSession, make_agent, seed_platform):
    """Creating an account sets balance=0, tier=bronze."""
    agent, _ = await make_agent()
    account = await token_service.create_account(db, agent.id)

    assert account.agent_id == agent.id
    assert float(account.balance) == 0.0
    assert account.tier == "bronze"


async def test_create_account_returns_token_account(db: AsyncSession, make_agent, seed_platform):
    account = await token_service.create_account(db, (await make_agent())[0].id)
    assert isinstance(account, TokenAccount)


async def test_create_account_idempotent(db: AsyncSession, make_agent, seed_platform):
    """Calling create_account twice returns the same account."""
    agent, _ = await make_agent()
    a1 = await token_service.create_account(db, agent.id)
    a2 = await token_service.create_account(db, agent.id)
    assert a1.id == a2.id


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

async def test_transfer_normal(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """Alice(1000) -> Bob(100): Alice=900, Bob~=98, fee & burn applied."""
    alice, _ = await make_agent("alice")
    bob, _ = await make_agent("bob")
    await make_token_account(alice.id, 1000)
    await make_token_account(bob.id, 0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 100, tx_type="purchase",
    )

    assert isinstance(ledger, TokenLedger)
    assert float(ledger.amount) == 100.0
    assert float(ledger.fee_amount) == 2.0   # 2% of 100
    assert float(ledger.burn_amount) == 1.0  # 50% of fee

    alice_bal = await token_service.get_balance(db, alice.id)
    bob_bal = await token_service.get_balance(db, bob.id)
    assert alice_bal["balance"] == 900.0
    assert bob_bal["balance"] == 98.0  # 100 - 2 fee


async def test_transfer_fee_calculation(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """100 AXN transfer: fee=2, burn=1, seller gets 98."""
    a, _ = await make_agent("sender")
    b, _ = await make_agent("receiver")
    await make_token_account(a.id, 500)
    await make_token_account(b.id, 0)

    ledger = await token_service.transfer(db, a.id, b.id, 100, "sale")

    assert float(ledger.fee_amount) == 2.0
    assert float(ledger.burn_amount) == 1.0


async def test_transfer_insufficient_balance(db: AsyncSession, make_agent, make_token_account, seed_platform):
    a, _ = await make_agent("poor")
    b, _ = await make_agent("rich")
    await make_token_account(a.id, 10)
    await make_token_account(b.id, 0)

    with pytest.raises(ValueError, match="Insufficient balance"):
        await token_service.transfer(db, a.id, b.id, 100, "purchase")


async def test_transfer_negative_amount(db: AsyncSession, make_agent, make_token_account, seed_platform):
    a, _ = await make_agent("a")
    b, _ = await make_agent("b")
    await make_token_account(a.id, 100)
    await make_token_account(b.id, 0)

    with pytest.raises(ValueError, match="positive"):
        await token_service.transfer(db, a.id, b.id, -10, "transfer")


async def test_transfer_zero_amount(db: AsyncSession, make_agent, make_token_account, seed_platform):
    a, _ = await make_agent("a2")
    b, _ = await make_agent("b2")
    await make_token_account(a.id, 100)
    await make_token_account(b.id, 0)

    with pytest.raises(ValueError, match="positive"):
        await token_service.transfer(db, a.id, b.id, 0, "transfer")


async def test_transfer_nonexistent_sender(db: AsyncSession, make_agent, make_token_account, seed_platform):
    _, _ = await make_agent("exists")
    b, _ = await make_agent("b3")
    await make_token_account(b.id, 0)

    with pytest.raises(ValueError, match="No token account for sender"):
        await token_service.transfer(db, "nonexistent-id", b.id, 10, "transfer")


async def test_transfer_nonexistent_receiver(db: AsyncSession, make_agent, make_token_account, seed_platform):
    a, _ = await make_agent("a4")
    await make_token_account(a.id, 100)

    with pytest.raises(ValueError, match="No token account for receiver"):
        await token_service.transfer(db, a.id, "nonexistent-id", 10, "transfer")


async def test_transfer_idempotency_prevents_duplicate(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """Same idempotency_key → returns existing, no double-credit."""
    a, _ = await make_agent("idem_a")
    b, _ = await make_agent("idem_b")
    await make_token_account(a.id, 1000)
    await make_token_account(b.id, 0)

    key = "test-idem-key-123"
    l1 = await token_service.transfer(db, a.id, b.id, 100, "purchase", idempotency_key=key)
    l2 = await token_service.transfer(db, a.id, b.id, 100, "purchase", idempotency_key=key)

    assert l1.id == l2.id  # same ledger entry returned

    # Balance should reflect only ONE transfer
    a_bal = await token_service.get_balance(db, a.id)
    assert a_bal["balance"] == 900.0


async def test_transfer_different_keys_both_succeed(db: AsyncSession, make_agent, make_token_account, seed_platform):
    a, _ = await make_agent("diff_a")
    b, _ = await make_agent("diff_b")
    await make_token_account(a.id, 1000)
    await make_token_account(b.id, 0)

    l1 = await token_service.transfer(db, a.id, b.id, 100, "purchase", idempotency_key="key-1")
    l2 = await token_service.transfer(db, a.id, b.id, 100, "purchase", idempotency_key="key-2")

    assert l1.id != l2.id
    a_bal = await token_service.get_balance(db, a.id)
    assert a_bal["balance"] == 800.0  # two transfers of 100


# ---------------------------------------------------------------------------
# Deposits
# ---------------------------------------------------------------------------

async def test_deposit_credits_balance(db: AsyncSession, make_agent, make_token_account, seed_platform):
    agent, _ = await make_agent("dep_agent")
    await make_token_account(agent.id, 0)

    await token_service.deposit(db, agent.id, 500)

    bal = await token_service.get_balance(db, agent.id)
    assert bal["balance"] == 500.0


async def test_deposit_updates_total_deposited(db: AsyncSession, make_agent, make_token_account, seed_platform):
    agent, _ = await make_agent("dep_agent2")
    await make_token_account(agent.id, 0)

    await token_service.deposit(db, agent.id, 200)
    await token_service.deposit(db, agent.id, 300)

    bal = await token_service.get_balance(db, agent.id)
    assert bal["total_deposited"] == 500.0


async def test_deposit_negative_raises(db: AsyncSession, make_agent, make_token_account, seed_platform):
    agent, _ = await make_agent("dep_neg")
    await make_token_account(agent.id, 0)

    with pytest.raises(ValueError, match="positive"):
        await token_service.deposit(db, agent.id, -100)


# ---------------------------------------------------------------------------
# Debit for purchase
# ---------------------------------------------------------------------------

async def test_debit_for_purchase_normal(db: AsyncSession, make_agent, make_token_account, seed_platform):
    buyer, _ = await make_agent("buyer")
    seller, _ = await make_agent("seller")
    await make_token_account(buyer.id, 10000)
    await make_token_account(seller.id, 0)

    result = await token_service.debit_for_purchase(
        db, buyer.id, seller.id, amount_usdc=1.0, listing_quality=0.5, tx_id="tx-001",
    )

    assert result["amount_axn"] == 1000.0  # $1 / 0.001
    assert result["fee_axn"] == 20.0       # 2% of 1000
    assert result["burn_axn"] == 10.0      # 50% of fee
    assert result["buyer_balance"] == 9000.0


async def test_debit_for_purchase_quality_bonus(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """quality=0.85 (>0.80 threshold) → seller gets +10% bonus."""
    buyer, _ = await make_agent("qb_buyer")
    seller, _ = await make_agent("qb_seller")
    await make_token_account(buyer.id, 10000)
    await make_token_account(seller.id, 0)

    result = await token_service.debit_for_purchase(
        db, buyer.id, seller.id, 1.0, listing_quality=0.85, tx_id="tx-002",
    )

    assert result["quality_bonus_axn"] > 0


async def test_debit_for_purchase_no_bonus_below_threshold(db: AsyncSession, make_agent, make_token_account, seed_platform):
    buyer, _ = await make_agent("nb_buyer")
    seller, _ = await make_agent("nb_seller")
    await make_token_account(buyer.id, 10000)
    await make_token_account(seller.id, 0)

    result = await token_service.debit_for_purchase(
        db, buyer.id, seller.id, 1.0, listing_quality=0.5, tx_id="tx-003",
    )

    assert result["quality_bonus_axn"] == 0.0


async def test_debit_for_purchase_insufficient(db: AsyncSession, make_agent, make_token_account, seed_platform):
    buyer, _ = await make_agent("broke_buyer")
    seller, _ = await make_agent("deb_seller")
    await make_token_account(buyer.id, 1)  # only 1 AXN
    await make_token_account(seller.id, 0)

    with pytest.raises(ValueError, match="Insufficient"):
        await token_service.debit_for_purchase(
            db, buyer.id, seller.id, 1.0, listing_quality=0.5, tx_id="tx-004",
        )


# ---------------------------------------------------------------------------
# Tier calculation
# ---------------------------------------------------------------------------

async def test_recalculate_tier_progression(db: AsyncSession, make_agent, seed_platform):
    """Volume 0→bronze, 10K→silver, 100K→gold, 1M→platinum."""
    import uuid

    agent, _ = await make_agent("tier_agent")
    account = TokenAccount(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        balance=Decimal("0"),
        total_earned=Decimal("0"),
        total_spent=Decimal("0"),
    )
    db.add(account)
    await db.commit()

    # bronze (volume < 10K)
    tier = await token_service.recalculate_tier(db, agent.id)
    assert tier == "bronze"

    # silver (volume >= 10K)
    account.total_earned = Decimal("10000")
    await db.commit()
    tier = await token_service.recalculate_tier(db, agent.id)
    assert tier == "silver"

    # gold (volume >= 100K)
    account.total_earned = Decimal("100000")
    await db.commit()
    tier = await token_service.recalculate_tier(db, agent.id)
    assert tier == "gold"

    # platinum (volume >= 1M)
    account.total_earned = Decimal("1000000")
    await db.commit()
    tier = await token_service.recalculate_tier(db, agent.id)
    assert tier == "platinum"


# ---------------------------------------------------------------------------
# Get balance / history / supply
# ---------------------------------------------------------------------------

async def test_get_balance_returns_dict(db: AsyncSession, make_agent, make_token_account, seed_platform):
    agent, _ = await make_agent("bal_agent")
    await make_token_account(agent.id, 42.5)

    bal = await token_service.get_balance(db, agent.id)
    assert isinstance(bal, dict)
    assert "balance" in bal
    assert "tier" in bal
    assert "usd_equivalent" in bal
    assert bal["balance"] == 42.5


async def test_get_history_paginated(db: AsyncSession, make_agent, make_token_account, seed_platform):
    agent, _ = await make_agent("hist_agent")
    await make_token_account(agent.id, 1000)

    # Create some deposits
    await token_service.deposit(db, agent.id, 50, memo="dep1")
    await token_service.deposit(db, agent.id, 60, memo="dep2")

    entries, total = await token_service.get_history(db, agent.id)
    assert total >= 2
    assert isinstance(entries, list)
    assert len(entries) >= 2


async def test_get_supply(db: AsyncSession, seed_platform):
    supply = await token_service.get_supply(db)
    assert isinstance(supply, dict)
    assert "total_minted" in supply
    assert "total_burned" in supply
    assert "circulating" in supply
    assert supply["total_minted"] == 1_000_000_000.0


async def test_get_supply_no_row(db: AsyncSession):
    """When no supply row exists, returns zeroes."""
    supply = await token_service.get_supply(db)
    assert supply["total_minted"] == 0.0
    assert supply["circulating"] == 0.0
