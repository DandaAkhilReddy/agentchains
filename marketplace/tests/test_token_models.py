"""Unit tests for AXN token SQLAlchemy model constraints and defaults."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.token_account import TokenAccount, TokenLedger, TokenSupply
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# TokenAccount defaults
# ---------------------------------------------------------------------------

async def test_account_default_balance_zero(db: AsyncSession):
    account = TokenAccount(id=_new_id(), agent_id=_new_id())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    assert float(account.balance) == 0.0


async def test_account_default_tier_bronze(db: AsyncSession):
    account = TokenAccount(id=_new_id(), agent_id=_new_id())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    assert account.tier == "bronze"


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

async def test_account_agent_id_unique(db: AsyncSession):
    """Two accounts with same agent_id → IntegrityError."""
    agent_id = _new_id()
    db.add(TokenAccount(id=_new_id(), agent_id=agent_id))
    await db.commit()

    db.add(TokenAccount(id=_new_id(), agent_id=agent_id))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_ledger_idempotency_unique(db: AsyncSession):
    """Two ledger entries with same idempotency_key → IntegrityError."""
    key = "test-idem-unique-key"
    db.add(TokenLedger(
        id=_new_id(), amount=Decimal("10"), tx_type="deposit", idempotency_key=key,
    ))
    await db.commit()

    db.add(TokenLedger(
        id=_new_id(), amount=Decimal("20"), tx_type="deposit", idempotency_key=key,
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


# ---------------------------------------------------------------------------
# Nullable FK tests
# ---------------------------------------------------------------------------

async def test_ledger_nullable_from(db: AsyncSession):
    """from_account_id=None is OK (mint/deposit)."""
    entry = TokenLedger(
        id=_new_id(),
        from_account_id=None,
        to_account_id=_new_id(),
        amount=Decimal("100"),
        tx_type="deposit",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    assert entry.from_account_id is None


async def test_ledger_nullable_to(db: AsyncSession):
    """to_account_id=None is OK (burn)."""
    entry = TokenLedger(
        id=_new_id(),
        from_account_id=_new_id(),
        to_account_id=None,
        amount=Decimal("10"),
        tx_type="burn",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    assert entry.to_account_id is None


# ---------------------------------------------------------------------------
# TokenSupply defaults
# ---------------------------------------------------------------------------

async def test_supply_defaults(db: AsyncSession):
    supply = TokenSupply(id=1)
    db.add(supply)
    await db.commit()
    await db.refresh(supply)

    assert float(supply.total_minted) == 1_000_000_000.0
    assert float(supply.total_burned) == 0.0
    assert float(supply.circulating) == 1_000_000_000.0


async def test_supply_multiple_ids_ok(db: AsyncSession):
    """Can create supply rows with different IDs (not a singleton constraint at DB level)."""
    db.add(TokenSupply(id=1))
    db.add(TokenSupply(id=2))
    await db.commit()

    result = await db.execute(select(TokenSupply))
    rows = result.scalars().all()
    assert len(rows) == 2
