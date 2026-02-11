import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Numeric, String, Text, DateTime
from sqlalchemy.orm import relationship

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=False)
    buyer_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    seller_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    amount_usdc = Column(Numeric(10, 6), nullable=False)

    # State machine: initiated -> payment_pending -> payment_confirmed ->
    #                delivering -> delivered -> verified -> completed
    #                (or: failed, disputed, refunded)
    status = Column(String(30), nullable=False, default="initiated")

    payment_method = Column(String(20), default="token")  # token | fiat | simulated
    payment_tx_hash = Column(String(66))  # Blockchain tx hash (0x + 64 hex)
    payment_network = Column(String(30), default="base-sepolia")
    amount_axn = Column(Numeric(18, 6), nullable=True)  # ARD token amount
    token_ledger_id = Column(String(36), nullable=True)  # FK to token_ledger entry
    content_hash = Column(String(71), nullable=False)  # Expected hash
    delivered_hash = Column(String(71))  # Actual hash of delivered content
    verification_status = Column(String(20), default="pending")  # pending | verified | failed | skipped
    error_message = Column(Text)

    # Timestamps for each state transition
    initiated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    paid_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    verified_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    listing = relationship("DataListing", back_populates="transactions", lazy="selectin")
    buyer = relationship("RegisteredAgent", foreign_keys=[buyer_id], lazy="selectin")
    seller_rel = relationship("RegisteredAgent", foreign_keys=[seller_id], lazy="selectin")

    __table_args__ = (
        Index("idx_tx_buyer", "buyer_id"),
        Index("idx_tx_seller", "seller_id"),
        Index("idx_tx_listing", "listing_id"),
        Index("idx_tx_status", "status"),
    )
