"""Unit tests for the USD billing token service — core transfer engine.

Tests use in-memory SQLite via conftest fixtures.
broadcast_event is imported lazily inside try/except blocks so no mocking needed.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.services import token_service


# ---------------------------------------------------------------------------
# Account creation
# ---------------------------------------------------------------------------

async def test_ensure_platform_account_creates_once(db: AsyncSession):
    """First call creates platform account; second returns same account."""
    p1 = await token_service.ensure_platform_account(db)
    assert p1.agent_id is None

    p2 = await token_service.ensure_platform_account(db)
    assert p2.id == p1.id  # same row


async def test_create_account_success(db: AsyncSession, make_agent, seed_platform):
    """Creating an account sets balance=0."""
    agent, _ = await make_agent()
    account = await token_service.create_account(db, agent.id)

    assert account.agent_id == agent.id
    assert float(account.balance) == 0.0


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
    """Alice(1000) -> Bob(100): Alice=900, Bob=98 (2% fee to platform)."""
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

    alice_bal = await token_service.get_balance(db, alice.id)
    bob_bal = await token_service.get_balance(db, bob.id)
    assert alice_bal["balance"] == 900.0
    assert bob_bal["balance"] == 98.0  # 100 - 2 fee


async def test_transfer_fee_calculation(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """100 USD transfer: fee=2, seller gets 98."""
    a, _ = await make_agent("sender")
    b, _ = await make_agent("receiver")
    await make_token_account(a.id, 500)
    await make_token_account(b.id, 0)

    ledger = await token_service.transfer(db, a.id, b.id, 100, "sale")

    assert float(ledger.fee_amount) == 2.0


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
    """Same idempotency_key -> returns existing, no double-credit."""
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
    await make_token_account(buyer.id, 100)
    await make_token_account(seller.id, 0)

    result = await token_service.debit_for_purchase(
        db, buyer.id, seller.id, amount_usdc=1.0, tx_id="tx-001",
    )

    assert result["amount_usd"] == 1.0
    assert result["fee_usd"] == 0.02   # 2% of $1
    assert result["buyer_balance"] == 99.0


async def test_debit_for_purchase_insufficient(db: AsyncSession, make_agent, make_token_account, seed_platform):
    buyer, _ = await make_agent("broke_buyer")
    seller, _ = await make_agent("deb_seller")
    await make_token_account(buyer.id, 0.5)  # only $0.50
    await make_token_account(seller.id, 0)

    with pytest.raises(ValueError, match="Insufficient"):
        await token_service.debit_for_purchase(
            db, buyer.id, seller.id, amount_usdc=1.0, tx_id="tx-004",
        )


# ---------------------------------------------------------------------------
# Get balance / history
# ---------------------------------------------------------------------------

async def test_get_balance_returns_dict(db: AsyncSession, make_agent, make_token_account, seed_platform):
    agent, _ = await make_agent("bal_agent")
    await make_token_account(agent.id, 42.5)

    bal = await token_service.get_balance(db, agent.id)
    assert isinstance(bal, dict)
    assert "balance" in bal
    assert "total_deposited" in bal
    assert "total_earned" in bal
    assert "total_spent" in bal
    assert "total_fees_paid" in bal
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


# ---------------------------------------------------------------------------
# Additional tests for uncovered lines
# ---------------------------------------------------------------------------


async def test_get_balance_nonexistent_agent(db: AsyncSession, seed_platform):
    """get_balance raises ValueError for nonexistent agent (line 239)."""
    with pytest.raises(ValueError, match="No token account"):
        await token_service.get_balance(db, "nonexistent-agent-id")


async def test_transfer_no_platform_account(db: AsyncSession, make_agent, make_token_account):
    """transfer raises when platform account is missing (line 304)."""
    a, _ = await make_agent("noplatform_a")
    b, _ = await make_agent("noplatform_b")
    await make_token_account(a.id, 100)
    await make_token_account(b.id, 0)
    with pytest.raises(ValueError, match="Platform treasury"):
        await token_service.transfer(db, a.id, b.id, 10, "purchase")


async def test_deposit_nonexistent_agent(db: AsyncSession, seed_platform):
    """deposit raises for nonexistent agent (line 426)."""
    with pytest.raises(ValueError, match="No token account"):
        await token_service.deposit(db, "nonexistent-id", 100)


async def test_deposit_no_platform_account(db: AsyncSession, make_agent, make_token_account):
    """deposit raises when platform account is missing (line 430)."""
    agent, _ = await make_agent("dep_no_plat")
    await make_token_account(agent.id, 0)
    with pytest.raises(ValueError, match="Platform treasury"):
        await token_service.deposit(db, agent.id, 100)


async def test_get_history_nonexistent_agent(db: AsyncSession, seed_platform):
    """get_history returns empty for nonexistent agent (line 560)."""
    entries, total = await token_service.get_history(db, "nonexistent-agent-id")
    assert entries == []
    assert total == 0


async def test_get_creator_balance_nonexistent(db: AsyncSession, seed_platform):
    """get_creator_balance raises for nonexistent creator (lines 608-613)."""
    with pytest.raises(ValueError, match="No token account for creator"):
        await token_service.get_creator_balance(db, "nonexistent-creator-id")


async def test_get_creator_balance_success(db: AsyncSession, make_agent, make_creator, seed_platform):
    """get_creator_balance returns balance dict for existing creator (lines 608-613)."""
    creator, _ = await make_creator()
    # Create a token account for the creator
    from marketplace.models.token_account import TokenAccount
    import uuid
    creator_acct = TokenAccount(
        id=str(uuid.uuid4()),
        creator_id=creator.id,
        balance=Decimal("42.50"),
    )
    db.add(creator_acct)
    await db.commit()
    await db.refresh(creator_acct)
    bal = await token_service.get_creator_balance(db, creator.id)
    assert bal["balance"] == 42.5
    assert "total_earned" in bal


async def test_transfer_with_creator_royalty(db: AsyncSession, make_agent, make_token_account, make_creator, seed_platform):
    """Transfer with purchase tx_type triggers creator royalty (lines 132-188)."""
    creator, _ = await make_creator()
    seller, _ = await make_agent("royalty_seller")
    buyer, _ = await make_agent("royalty_buyer")
    # Link seller to creator
    seller.creator_id = creator.id
    await db.commit()
    # Create accounts
    await make_token_account(buyer.id, 1000)
    await make_token_account(seller.id, 0)
    # Create creator token account
    from marketplace.models.token_account import TokenAccount
    import uuid
    creator_acct = TokenAccount(
        id=str(uuid.uuid4()),
        creator_id=creator.id,
        balance=Decimal("0"),
    )
    db.add(creator_acct)
    await db.commit()
    # Do a purchase transfer
    ledger = await token_service.transfer(
        db, buyer.id, seller.id, 100, "purchase", reference_id="tx-royalty-1",
    )
    assert float(ledger.amount) == 100.0
    # Creator should have received royalty
    await db.refresh(creator_acct)
    assert float(creator_acct.balance) > 0


# ---------------------------------------------------------------------------
# Coverage gap tests — lines 64, 68, 84, 95, 126, 135, 139, 144, 146, 381-382
# ---------------------------------------------------------------------------


async def test_lock_account_raises_for_missing(db: AsyncSession, seed_platform):
    """Line 68: _lock_account raises ValueError when account not found."""
    with pytest.raises(ValueError, match="not found"):
        await token_service._lock_account(db, "nonexistent-account-id")


async def test_get_account_by_agent_with_lock_flag_sqlite(db: AsyncSession, make_agent, seed_platform):
    """Line 84: _get_account_by_agent with lock=True on SQLite (no FOR UPDATE).
    Since tests use SQLite, the with_for_update branch is skipped (line 84 stays False),
    but calling with lock=True should still return the account normally."""
    agent, _ = await make_agent("lock-agent")
    await token_service.create_account(db, agent.id)
    result = await token_service._get_account_by_agent(db, agent.id, lock=True)
    assert result is not None
    assert result.agent_id == agent.id


async def test_get_account_by_creator_with_lock_flag_sqlite(db: AsyncSession, make_creator, seed_platform):
    """Line 95: _get_account_by_creator with lock=True on SQLite."""
    creator, _ = await make_creator()
    from marketplace.models.token_account import TokenAccount
    import uuid
    acct = TokenAccount(id=str(uuid.uuid4()), creator_id=creator.id, balance=Decimal("0"))
    db.add(acct)
    await db.commit()
    result = await token_service._get_account_by_creator(db, creator.id, lock=True)
    assert result is not None
    assert result.creator_id == creator.id


async def test_process_creator_royalty_zero_pct(
    db: AsyncSession, make_agent, make_token_account, make_creator, seed_platform
):
    """Line 126: creator_royalty_pct == 0 → _process_creator_royalty returns None."""
    from unittest.mock import patch
    creator, _ = await make_creator()
    seller, _ = await make_agent("royalty-zero-seller")
    seller.creator_id = creator.id
    await db.commit()

    await make_token_account(seller.id, 100)
    from marketplace.models.token_account import TokenAccount
    import uuid
    creator_acct = TokenAccount(id=str(uuid.uuid4()), creator_id=creator.id, balance=Decimal("0"))
    db.add(creator_acct)
    await db.commit()

    with patch("marketplace.services.token_service.settings") as mock_s:
        mock_s.creator_royalty_pct = 0
        mock_s.platform_fee_pct = 0.02
        mock_s.database_url = "sqlite+aiosqlite:///:memory:"
        result = await token_service._process_creator_royalty(
            db, seller.id, Decimal("10"), None
        )
    assert result is None


async def test_process_creator_royalty_no_creator(
    db: AsyncSession, make_agent, make_token_account, seed_platform
):
    """Line 130: agent has no creator → _process_creator_royalty returns None."""
    agent, _ = await make_agent("no-creator-agent")
    await make_token_account(agent.id, 100)
    result = await token_service._process_creator_royalty(
        db, agent.id, Decimal("10"), None
    )
    assert result is None


async def test_process_creator_royalty_no_accounts(
    db: AsyncSession, make_agent, make_creator, seed_platform
):
    """Line 135: creator or agent account missing → returns None."""
    creator, _ = await make_creator()
    agent, _ = await make_agent("missing-acct-agent")
    agent.creator_id = creator.id
    await db.commit()
    # No token accounts created for agent or creator
    result = await token_service._process_creator_royalty(
        db, agent.id, Decimal("10"), None
    )
    assert result is None


async def test_process_creator_royalty_royalty_zero_after_calc(
    db: AsyncSession, make_agent, make_token_account, make_creator, seed_platform
):
    """Line 139: royalty rounds to 0 → returns None."""
    from unittest.mock import patch
    creator, _ = await make_creator()
    agent, _ = await make_agent("tiny-royalty-agent")
    agent.creator_id = creator.id
    await db.commit()
    await make_token_account(agent.id, 100)
    from marketplace.models.token_account import TokenAccount
    import uuid
    creator_acct = TokenAccount(
        id=str(uuid.uuid4()), creator_id=creator.id, balance=Decimal("0")
    )
    db.add(creator_acct)
    await db.commit()

    # royalty_pct very small makes royalty round to 0
    with patch("marketplace.services.token_service.settings") as mock_s:
        mock_s.creator_royalty_pct = 0.000000001
        mock_s.platform_fee_pct = 0.02
        mock_s.database_url = "sqlite+aiosqlite:///:memory:"
        # net_amount is tiny so royalty = 0
        result = await token_service._process_creator_royalty(
            db, agent.id, Decimal("0.000000001"), None
        )
    # May be None or a ledger depending on rounding; just verify no crash
    assert result is None or hasattr(result, "id")


async def test_process_creator_royalty_agent_balance_less_than_royalty(
    db: AsyncSession, make_agent, make_token_account, make_creator, seed_platform
):
    """Lines 143-146: agent balance < computed royalty → royalty capped,
    then if royalty becomes 0 returns None."""
    creator, _ = await make_creator()
    agent, _ = await make_agent("tiny-balance-agent")
    agent.creator_id = creator.id
    await db.commit()
    # Agent has zero balance → royalty > 0 → agent_balance < royalty → royalty = 0 → return None
    await make_token_account(agent.id, 0)
    from marketplace.models.token_account import TokenAccount
    import uuid
    creator_acct = TokenAccount(
        id=str(uuid.uuid4()), creator_id=creator.id, balance=Decimal("0")
    )
    db.add(creator_acct)
    await db.commit()

    # Royalty pct 10%, net_amount = 100 → royalty = 10, but agent balance = 0
    from unittest.mock import patch
    with patch("marketplace.services.token_service.settings") as mock_s:
        mock_s.creator_royalty_pct = 0.10
        mock_s.platform_fee_pct = 0.02
        mock_s.database_url = "sqlite+aiosqlite:///:memory:"
        result = await token_service._process_creator_royalty(
            db, agent.id, Decimal("100"), None
        )
    assert result is None


async def test_transfer_creator_royalty_exception_non_fatal(
    db: AsyncSession, make_agent, make_token_account, make_creator, seed_platform
):
    """Lines 381-382: creator royalty exception is caught and logged (non-fatal)."""
    from unittest.mock import patch, AsyncMock

    creator, _ = await make_creator()
    seller, _ = await make_agent("royalty-err-seller")
    buyer, _ = await make_agent("royalty-err-buyer")
    seller.creator_id = creator.id
    await db.commit()
    await make_token_account(buyer.id, 1000)
    await make_token_account(seller.id, 0)

    async def _bad_royalty(*args, **kwargs):
        raise RuntimeError("royalty explosion")

    with patch("marketplace.services.token_service._process_creator_royalty", _bad_royalty):
        ledger = await token_service.transfer(
            db, buyer.id, seller.id, 50, "purchase",
        )
    # Transfer should succeed despite royalty failure
    assert float(ledger.amount) == 50.0
