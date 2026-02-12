"""Integration tests for the FULL ARD token economy lifecycle.

Tests exercise the service layer end-to-end: account creation, deposits,
transfers (with fee + burn), purchases, quality bonuses, tier progression,
ledger hash-chain integrity, pagination, concurrent deposits, and supply
tracking.

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
from marketplace.models.token_account import TokenAccount, TokenLedger, TokenSupply
from marketplace.services import token_service
from marketplace.tests.conftest import TestSession


# ---------------------------------------------------------------------------
# 1. Platform account creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_platform_account_creation(db: AsyncSession):
    """ensure_platform_account creates treasury (agent_id=NULL) + TokenSupply singleton."""
    platform = await token_service.ensure_platform_account(db)

    # Treasury account exists with no agent owner
    assert platform is not None
    assert platform.agent_id is None
    assert platform.tier == "platform"
    assert float(platform.balance) == 0.0

    # TokenSupply singleton row exists
    result = await db.execute(select(TokenSupply).where(TokenSupply.id == 1))
    supply = result.scalar_one_or_none()
    assert supply is not None
    assert float(supply.total_minted) == 1_000_000_000.0


# ---------------------------------------------------------------------------
# 2. Agent account creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_account(db: AsyncSession, seed_platform, make_agent):
    """create_account for an agent produces a bronze-tier account with zero balance."""
    agent, _ = await make_agent()
    account = await token_service.create_account(db, agent.id)

    assert isinstance(account, TokenAccount)
    assert account.agent_id == agent.id
    assert float(account.balance) == 0.0
    assert account.tier == "bronze"


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
    """Deposit adds balance and creates a ledger entry of type 'deposit'."""
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
    assert ledger.from_account_id is None  # mint — no sender


# ---------------------------------------------------------------------------
# 5. Deposit updates supply
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deposit_updates_supply(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """After a deposit, total_minted and circulating increase by the deposited amount."""
    agent, _ = await make_agent()
    await make_token_account(agent.id, balance=0.0)

    supply_before = await token_service.get_supply(db)
    minted_before = supply_before["total_minted"]
    circ_before = supply_before["circulating"]

    await token_service.deposit(db, agent.id, 1000)

    supply_after = await token_service.get_supply(db)
    assert supply_after["total_minted"] == minted_before + 1000.0
    assert supply_after["circulating"] == circ_before + 1000.0


# ---------------------------------------------------------------------------
# 6. Basic transfer with fee and burn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_basic(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Transfer from A to B applies 2% fee and 50% burn on the fee."""
    alice, _ = await make_agent("alice_basic")
    bob, _ = await make_agent("bob_basic")
    await make_token_account(alice.id, balance=1000.0)
    await make_token_account(bob.id, balance=0.0)

    ledger = await token_service.transfer(
        db, alice.id, bob.id, 100, tx_type="sale",
    )

    assert isinstance(ledger, TokenLedger)
    # fee = 100 * 0.02 = 2, burn = 2 * 0.50 = 1
    assert float(ledger.fee_amount) == 2.0
    assert float(ledger.burn_amount) == 1.0

    alice_bal = await token_service.get_balance(db, alice.id)
    bob_bal = await token_service.get_balance(db, bob.id)

    # Alice debited full amount
    assert alice_bal["balance"] == 900.0
    # Bob receives amount - fee = 98
    assert bob_bal["balance"] == 98.0


# ---------------------------------------------------------------------------
# 7. Fee calculation precision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_fee_calculation(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """fee = amount * 0.02, burn = fee * 0.50 — verified with odd amount (250 ARD)."""
    sender, _ = await make_agent("fee_sender")
    receiver, _ = await make_agent("fee_receiver")
    await make_token_account(sender.id, balance=5000.0)
    await make_token_account(receiver.id, balance=0.0)

    ledger = await token_service.transfer(
        db, sender.id, receiver.id, 250, tx_type="sale",
    )

    expected_fee = Decimal("250") * Decimal("0.02")  # 5.0
    expected_burn = expected_fee * Decimal("0.50")     # 2.5

    assert Decimal(str(ledger.fee_amount)) == expected_fee.quantize(Decimal("0.000001"))
    assert Decimal(str(ledger.burn_amount)) == expected_burn.quantize(Decimal("0.000001"))


# ---------------------------------------------------------------------------
# 8. Transfer insufficient balance
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
# 9. Transfer idempotency
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
# 10. Transfer updates circulating supply (burn decreases it)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transfer_updates_supply(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Circulating supply decreases by the burn amount after a transfer."""
    a, _ = await make_agent("supply_a")
    b, _ = await make_agent("supply_b")
    await make_token_account(a.id, balance=5000.0)
    await make_token_account(b.id, balance=0.0)

    supply_before = await token_service.get_supply(db)
    circ_before = supply_before["circulating"]
    burned_before = supply_before["total_burned"]

    ledger = await token_service.transfer(
        db, a.id, b.id, 1000, tx_type="sale",
    )
    burn = float(ledger.burn_amount)  # 1000 * 0.02 * 0.50 = 10

    supply_after = await token_service.get_supply(db)
    assert supply_after["circulating"] == circ_before - burn
    assert supply_after["total_burned"] == burned_before + burn


# ---------------------------------------------------------------------------
# 11. Debit for purchase — full USD->ARD flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debit_for_purchase(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Full purchase: USD->ARD conversion, transfer with fee/burn, balance updates."""
    buyer, _ = await make_agent("purchase_buyer")
    seller, _ = await make_agent("purchase_seller")
    # $1 = 1000 ARD, buyer needs at least 1000 ARD
    await make_token_account(buyer.id, balance=10000.0)
    await make_token_account(seller.id, balance=0.0)

    result = await token_service.debit_for_purchase(
        db,
        buyer_id=buyer.id,
        seller_id=seller.id,
        amount_usdc=1.0,
        listing_quality=0.5,  # below threshold, no bonus
        tx_id=f"tx-{uuid.uuid4()}",
    )

    # $1.00 / $0.001 = 1000 ARD
    assert result["amount_axn"] == 1000.0
    # fee = 1000 * 0.02 = 20
    assert result["fee_axn"] == 20.0
    # burn = 20 * 0.50 = 10
    assert result["burn_axn"] == 10.0
    # buyer balance = 10000 - 1000 = 9000
    assert result["buyer_balance"] == 9000.0
    # seller balance = 1000 - 20 (fee) = 980
    assert result["seller_balance"] == 980.0


# ---------------------------------------------------------------------------
# 12. Quality bonus awarded for quality >= 0.8
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quality_bonus_awarded(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """When listing_quality >= 0.8, seller receives a quality bonus deposit."""
    buyer, _ = await make_agent("qbonus_buyer")
    seller, _ = await make_agent("qbonus_seller")
    await make_token_account(buyer.id, balance=10000.0)
    await make_token_account(seller.id, balance=0.0)

    result = await token_service.debit_for_purchase(
        db,
        buyer_id=buyer.id,
        seller_id=seller.id,
        amount_usdc=1.0,
        listing_quality=0.85,  # above 0.80 threshold
        tx_id=f"tx-qb-{uuid.uuid4()}",
    )

    # Quality bonus = (amount_axn - fee) * quality_bonus_pct
    # amount_axn = 1000, fee = 20, net = 980, bonus = 980 * 0.10 = 98
    assert result["quality_bonus_axn"] > 0
    expected_bonus = float(
        Decimal("980") * Decimal(str(settings.token_quality_bonus_pct))
    )
    assert abs(result["quality_bonus_axn"] - expected_bonus) < 0.01

    # Seller balance = net + bonus = 980 + 98 = 1078
    assert result["seller_balance"] == pytest.approx(980.0 + expected_bonus, abs=0.01)


# ---------------------------------------------------------------------------
# 13. No quality bonus below threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quality_bonus_not_awarded(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """When listing_quality < 0.8, no quality bonus is applied."""
    buyer, _ = await make_agent("nobonus_buyer")
    seller, _ = await make_agent("nobonus_seller")
    await make_token_account(buyer.id, balance=10000.0)
    await make_token_account(seller.id, balance=0.0)

    result = await token_service.debit_for_purchase(
        db,
        buyer_id=buyer.id,
        seller_id=seller.id,
        amount_usdc=1.0,
        listing_quality=0.5,  # below 0.80 threshold
        tx_id=f"tx-nb-{uuid.uuid4()}",
    )

    assert result["quality_bonus_axn"] == 0.0


# ---------------------------------------------------------------------------
# 14. Ledger hash-chain integrity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ledger_chain_integrity(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """After multiple transfers, verify_ledger_chain returns valid=True."""
    a, _ = await make_agent("chain_a")
    b, _ = await make_agent("chain_b")
    await make_token_account(a.id, balance=5000.0)
    await make_token_account(b.id, balance=0.0)

    # Create a series of operations to build the hash chain
    await token_service.deposit(db, a.id, 500, memo="chain deposit 1")
    await token_service.transfer(db, a.id, b.id, 200, tx_type="sale")
    await token_service.deposit(db, b.id, 300, memo="chain deposit 2")
    await token_service.transfer(db, a.id, b.id, 100, tx_type="purchase")

    chain = await token_service.verify_ledger_chain(db)

    assert chain["valid"] is True
    assert chain["total_entries"] >= 4
    assert chain["errors"] == []


# ---------------------------------------------------------------------------
# 15. get_balance returns dict with all expected keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_balance_format(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """get_balance returns a dict with balance, tier, totals, and usd_equivalent."""
    agent, _ = await make_agent("bal_fmt")
    await make_token_account(agent.id, balance=500.0)

    bal = await token_service.get_balance(db, agent.id)

    expected_keys = {
        "balance", "tier", "total_earned", "total_spent",
        "total_deposited", "total_fees_paid", "usd_equivalent",
    }
    assert set(bal.keys()) == expected_keys
    assert bal["balance"] == 500.0
    assert bal["tier"] == "bronze"
    # 500 ARD * $0.001 = $0.50
    assert bal["usd_equivalent"] == pytest.approx(0.50, abs=0.001)


# ---------------------------------------------------------------------------
# 16. get_history pagination
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
# 17. Tier: bronze (low volume)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recalculate_tier_bronze(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Agent with volume < 10,000 ARD stays at bronze."""
    agent, _ = await make_agent("tier_bronze")
    acct = await make_token_account(agent.id, balance=100.0)

    # Set low lifetime volume
    acct.total_earned = Decimal("500")
    acct.total_spent = Decimal("200")
    await db.commit()

    tier = await token_service.recalculate_tier(db, agent.id)
    assert tier == "bronze"


# ---------------------------------------------------------------------------
# 18. Tier: silver (volume >= 10,000)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recalculate_tier_silver(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """Agent with lifetime volume >= 10,000 ARD earns silver tier."""
    agent, _ = await make_agent("tier_silver")
    acct = await make_token_account(agent.id, balance=100.0)

    # total_earned + total_spent = 6000 + 4000 = 10,000 (exactly silver threshold)
    acct.total_earned = Decimal("6000")
    acct.total_spent = Decimal("4000")
    await db.commit()

    tier = await token_service.recalculate_tier(db, agent.id)
    assert tier == "silver"


# ---------------------------------------------------------------------------
# 19. Concurrent deposits do not corrupt balance
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
# 20. get_supply returns correct totals after operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_supply_stats(db: AsyncSession, seed_platform, make_agent, make_token_account):
    """After deposits and transfers, supply stats reflect all changes accurately."""
    a, _ = await make_agent("supply_stat_a")
    b, _ = await make_agent("supply_stat_b")
    await make_token_account(a.id, balance=0.0)
    await make_token_account(b.id, balance=0.0)

    supply_init = await token_service.get_supply(db)
    minted_init = supply_init["total_minted"]
    circ_init = supply_init["circulating"]
    burned_init = supply_init["total_burned"]

    # Deposit 2000 to agent A
    await token_service.deposit(db, a.id, 2000, memo="supply test deposit")

    # Transfer 1000 from A to B (fee=20, burn=10)
    ledger = await token_service.transfer(db, a.id, b.id, 1000, tx_type="sale")
    burn_amount = float(ledger.burn_amount)

    supply_final = await token_service.get_supply(db)

    # Minted increased by deposit amount
    assert supply_final["total_minted"] == minted_init + 2000.0
    # Circulating = initial + deposit - burn
    assert supply_final["circulating"] == pytest.approx(circ_init + 2000.0 - burn_amount, abs=0.01)
    # Burned increased by transfer's burn
    assert supply_final["total_burned"] == pytest.approx(burned_init + burn_amount, abs=0.01)
    # All expected keys present
    assert "platform_balance" in supply_final
    assert "last_updated" in supply_final
    assert supply_final["last_updated"] is not None
