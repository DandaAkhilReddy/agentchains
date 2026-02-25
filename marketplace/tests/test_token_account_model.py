"""Tests for TokenAccount, TokenLedger, and TokenDeposit models.

Covers: default values, constraints, column types, utcnow helper, schema creation.
Uses the db fixture from conftest for real SQLite persistence.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from marketplace.models.token_account import TokenAccount, TokenDeposit, TokenLedger, utcnow


# ---------------------------------------------------------------------------
# utcnow helper
# ---------------------------------------------------------------------------


class TestUtcnow:
    def test_returns_utc_datetime(self):
        now = utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc

    def test_returns_current_time(self):
        before = datetime.now(timezone.utc)
        now = utcnow()
        after = datetime.now(timezone.utc)
        assert before <= now <= after


# ---------------------------------------------------------------------------
# TokenAccount model
# ---------------------------------------------------------------------------


class TestTokenAccountModel:
    async def test_create_with_defaults(self, db):
        account = TokenAccount(
            id=str(uuid.uuid4()),
            agent_id=None,
            balance=Decimal("0"),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        assert account.balance == Decimal("0")
        assert account.total_deposited == Decimal("0")
        assert account.total_earned == Decimal("0")
        assert account.total_spent == Decimal("0")
        assert account.total_fees_paid == Decimal("0")
        assert account.created_at is not None
        assert account.updated_at is not None

    async def test_platform_treasury_has_null_agent_id(self, db):
        """Platform treasury account: agent_id=NULL, creator_id=NULL."""
        account = TokenAccount(
            id=str(uuid.uuid4()),
            agent_id=None,
            creator_id=None,
            balance=Decimal("1000"),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        assert account.agent_id is None
        assert account.creator_id is None
        assert account.balance == Decimal("1000")

    async def test_agent_account(self, db, make_agent):
        agent, _ = await make_agent()
        account = TokenAccount(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            balance=Decimal("50.123456"),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        assert account.agent_id == agent.id
        assert account.balance == Decimal("50.123456")

    async def test_balance_precision(self, db):
        """balance is Numeric(18,6) -- should support up to 6 decimal places."""
        account = TokenAccount(
            id=str(uuid.uuid4()),
            balance=Decimal("999999999999.123456"),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        assert account.balance == Decimal("999999999999.123456")

    async def test_accumulation_fields(self, db):
        account = TokenAccount(
            id=str(uuid.uuid4()),
            balance=Decimal("100"),
            total_deposited=Decimal("500"),
            total_earned=Decimal("200"),
            total_spent=Decimal("150"),
            total_fees_paid=Decimal("10"),
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

        assert account.total_deposited == Decimal("500")
        assert account.total_earned == Decimal("200")
        assert account.total_spent == Decimal("150")
        assert account.total_fees_paid == Decimal("10")

    async def test_unique_agent_id_constraint(self, db, make_agent):
        """Two accounts for the same agent should violate uniqueness."""
        agent, _ = await make_agent()
        acct1 = TokenAccount(id=str(uuid.uuid4()), agent_id=agent.id, balance=Decimal("0"))
        db.add(acct1)
        await db.commit()

        acct2 = TokenAccount(id=str(uuid.uuid4()), agent_id=agent.id, balance=Decimal("0"))
        db.add(acct2)
        with pytest.raises(Exception):  # IntegrityError from unique constraint
            await db.commit()
        await db.rollback()

    async def test_query_by_agent_id(self, db, make_agent):
        agent, _ = await make_agent()
        account = TokenAccount(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            balance=Decimal("25"),
        )
        db.add(account)
        await db.commit()

        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id == agent.id)
        )
        found = result.scalar_one()
        assert found.id == account.id


# ---------------------------------------------------------------------------
# TokenLedger model
# ---------------------------------------------------------------------------


class TestTokenLedgerModel:
    async def test_create_ledger_entry(self, db):
        entry = TokenLedger(
            id=str(uuid.uuid4()),
            from_account_id=None,  # deposit
            to_account_id=str(uuid.uuid4()),
            amount=Decimal("10.50"),
            tx_type="deposit",
            memo="Initial deposit",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.tx_type == "deposit"
        assert entry.amount == Decimal("10.50")
        assert entry.from_account_id is None
        assert entry.fee_amount == Decimal("0")
        assert entry.created_at is not None

    async def test_ledger_with_fee(self, db):
        entry = TokenLedger(
            id=str(uuid.uuid4()),
            from_account_id=str(uuid.uuid4()),
            to_account_id=str(uuid.uuid4()),
            amount=Decimal("5.00"),
            fee_amount=Decimal("0.10"),
            tx_type="purchase",
            reference_id=str(uuid.uuid4()),
            reference_type="transaction",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.fee_amount == Decimal("0.10")
        assert entry.reference_type == "transaction"

    async def test_idempotency_key_unique(self, db):
        key = "idem-" + str(uuid.uuid4())
        entry1 = TokenLedger(
            id=str(uuid.uuid4()),
            amount=Decimal("1"),
            tx_type="bonus",
            idempotency_key=key,
        )
        db.add(entry1)
        await db.commit()

        entry2 = TokenLedger(
            id=str(uuid.uuid4()),
            amount=Decimal("1"),
            tx_type="bonus",
            idempotency_key=key,
        )
        db.add(entry2)
        with pytest.raises(Exception):  # unique constraint violation
            await db.commit()
        await db.rollback()

    async def test_hash_chain_fields(self, db):
        entry = TokenLedger(
            id=str(uuid.uuid4()),
            amount=Decimal("10"),
            tx_type="deposit",
            prev_hash="a" * 64,
            entry_hash="b" * 64,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.prev_hash == "a" * 64
        assert entry.entry_hash == "b" * 64

    async def test_genesis_entry_null_prev_hash(self, db):
        entry = TokenLedger(
            id=str(uuid.uuid4()),
            amount=Decimal("100"),
            tx_type="deposit",
            prev_hash=None,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.prev_hash is None

    async def test_memo_default(self, db):
        entry = TokenLedger(
            id=str(uuid.uuid4()),
            amount=Decimal("1"),
            tx_type="bonus",
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        assert entry.memo == ""


# ---------------------------------------------------------------------------
# TokenDeposit model
# ---------------------------------------------------------------------------


class TestTokenDepositModel:
    async def test_create_deposit(self, db, make_agent):
        agent, _ = await make_agent()
        deposit = TokenDeposit(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            amount_usd=Decimal("25.00"),
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)

        assert deposit.status == "pending"
        assert deposit.currency == "USD"
        assert deposit.payment_method == "admin_credit"
        assert deposit.amount_usd == Decimal("25.00")
        assert deposit.completed_at is None

    async def test_deposit_status_transitions(self, db, make_agent):
        agent, _ = await make_agent()
        deposit = TokenDeposit(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            amount_usd=Decimal("10.00"),
            status="pending",
        )
        db.add(deposit)
        await db.commit()

        deposit.status = "completed"
        deposit.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(deposit)

        assert deposit.status == "completed"
        assert deposit.completed_at is not None

    async def test_deposit_payment_methods(self, db, make_agent):
        agent, _ = await make_agent()
        for method in ("stripe", "razorpay", "admin_credit", "signup_bonus"):
            deposit = TokenDeposit(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                amount_usd=Decimal("5.00"),
                payment_method=method,
            )
            db.add(deposit)
            await db.commit()
            await db.refresh(deposit)
            assert deposit.payment_method == method

    async def test_deposit_with_payment_ref(self, db, make_agent):
        agent, _ = await make_agent()
        deposit = TokenDeposit(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            amount_usd=Decimal("50.00"),
            payment_method="stripe",
            payment_ref="pi_1234567890_secret",
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)

        assert deposit.payment_ref == "pi_1234567890_secret"

    async def test_query_deposits_by_status(self, db, make_agent):
        agent, _ = await make_agent()
        for status in ("pending", "completed", "failed"):
            deposit = TokenDeposit(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                amount_usd=Decimal("1.00"),
                status=status,
            )
            db.add(deposit)
        await db.commit()

        result = await db.execute(
            select(TokenDeposit).where(TokenDeposit.status == "completed")
        )
        completed = list(result.scalars().all())
        assert len(completed) == 1
