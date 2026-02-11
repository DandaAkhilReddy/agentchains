"""Creator accounts — humans who own agents and earn ARD tokens."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Index, String, Text
from marketplace.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Creator(Base):
    """Human creator account. Owns agents and accumulates ARD earnings."""
    __tablename__ = "creators"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    display_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    payout_method = Column(String(30), default="none")  # none, upi, bank, gift_card
    payout_details = Column(Text, default="{}")  # JSON: UPI ID, bank details, etc.
    status = Column(String(20), default="active")  # active, suspended, pending_verification
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_creator_email", "email"),
        Index("idx_creator_status", "status"),
    )
