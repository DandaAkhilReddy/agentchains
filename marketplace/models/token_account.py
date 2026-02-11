"""AXN Token Economy — Database models for the off-chain double-entry ledger."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class TokenAccount(Base):
    """Per-agent AXN balance. One row per registered agent + one platform account."""

    __tablename__ = "token_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(
        String(36), ForeignKey("registered_agents.id"), unique=True, nullable=True
    )  # NULL = platform treasury account
    balance = Column(Numeric(18, 6), nullable=False, default=0)
    total_deposited = Column(Numeric(18, 6), nullable=False, default=0)
    total_earned = Column(Numeric(18, 6), nullable=False, default=0)
    total_spent = Column(Numeric(18, 6), nullable=False, default=0)
    total_fees_paid = Column(Numeric(18, 6), nullable=False, default=0)
    tier = Column(String(20), nullable=False, default="bronze")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_token_balance_nonneg"),
        Index("idx_token_acct_agent", "agent_id"),
        Index("idx_token_acct_tier", "tier"),
    )


class TokenLedger(Base):
    """Immutable, append-only audit trail. Every token movement = one row."""

    __tablename__ = "token_ledger"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_account_id = Column(
        String(36), ForeignKey("token_accounts.id"), nullable=True
    )  # NULL = mint / deposit
    to_account_id = Column(
        String(36), ForeignKey("token_accounts.id"), nullable=True
    )  # NULL = burn / withdrawal
    amount = Column(Numeric(18, 6), nullable=False)
    fee_amount = Column(Numeric(18, 6), nullable=False, default=0)
    burn_amount = Column(Numeric(18, 6), nullable=False, default=0)
    tx_type = Column(
        String(30), nullable=False
    )  # deposit, purchase, sale, fee, burn, bonus, refund, withdrawal
    reference_id = Column(String(36), nullable=True)  # Transaction.id or deposit ID
    reference_type = Column(String(30), nullable=True)  # transaction, deposit, bonus, refund
    idempotency_key = Column(String(64), unique=True, nullable=True)
    memo = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_ledger_from", "from_account_id"),
        Index("idx_ledger_to", "to_account_id"),
        Index("idx_ledger_type", "tx_type"),
        Index("idx_ledger_ref", "reference_id"),
        Index("idx_ledger_created", "created_at"),
    )


class TokenDeposit(Base):
    """Fiat → AXN on-ramp. Tracks each deposit request and its status."""

    __tablename__ = "token_deposits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    amount_fiat = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    exchange_rate = Column(Numeric(12, 6), nullable=False)  # 1 AXN = X fiat
    amount_axn = Column(Numeric(18, 6), nullable=False)
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, completed, failed, refunded
    payment_method = Column(
        String(30), nullable=False, default="admin_credit"
    )  # stripe, razorpay, admin_credit, signup_bonus
    payment_ref = Column(String(255), nullable=True)  # Stripe payment intent ID etc.
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_deposit_agent", "agent_id"),
        Index("idx_deposit_status", "status"),
    )


class TokenSupply(Base):
    """Singleton row tracking global AXN supply metrics."""

    __tablename__ = "token_supply"

    id = Column(Integer, primary_key=True, default=1)
    total_minted = Column(Numeric(18, 6), nullable=False, default=1_000_000_000)
    total_burned = Column(Numeric(18, 6), nullable=False, default=0)
    circulating = Column(Numeric(18, 6), nullable=False, default=1_000_000_000)
    platform_balance = Column(Numeric(18, 6), nullable=False, default=0)
    last_updated = Column(DateTime(timezone=True), nullable=False, default=utcnow)
