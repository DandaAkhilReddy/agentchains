"""Redemption requests — USD balance to real money (API credits, gift cards, bank, UPI)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Numeric, String, Text

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class RedemptionRequest(Base):
    """Tracks a creator's request to withdraw USD funds."""

    __tablename__ = "redemption_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id = Column(String(36), ForeignKey("creators.id"), nullable=False)

    # Redemption type
    redemption_type = Column(
        String(30), nullable=False
    )  # api_credits | gift_card | bank_withdrawal | upi

    # Amounts
    amount_usd = Column(Numeric(18, 6), nullable=False)
    amount_fiat = Column(Numeric(12, 2), nullable=True)  # NULL for api_credits
    currency = Column(String(10), default="USD")

    # Status
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending | processing | completed | failed | rejected

    # Payout details
    payout_ref = Column(String(255), nullable=True)  # Razorpay payout ID, gift card code, etc.
    payout_method_details = Column(Text, default="{}")  # JSON: bank details, UPI ID used

    # Admin
    admin_notes = Column(Text, default="")
    rejection_reason = Column(Text, default="")

    # Ledger tracking
    ledger_entry_id = Column(String(36), nullable=True)  # FK to token_ledger debit entry

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("amount_usd > 0", name="ck_redemption_amount_positive"),
        Index("idx_redemption_creator", "creator_id"),
        Index("idx_redemption_status", "status"),
        Index("idx_redemption_type", "redemption_type"),
        Index("idx_redemption_created", "created_at"),
    )


class ApiCreditBalance(Base):
    """Tracks API call credits earned from USD balance."""

    __tablename__ = "api_credit_balances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id = Column(String(36), ForeignKey("creators.id"), unique=True, nullable=False)
    credits_remaining = Column(Numeric(12, 0), nullable=False, default=0)
    credits_total_purchased = Column(Numeric(12, 0), nullable=False, default=0)
    rate_limit_tier = Column(String(20), default="free")  # free | pro | enterprise
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_api_credits_creator", "creator_id"),
    )
