import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String(36), ForeignKey("transactions.id"), nullable=False)
    expected_hash = Column(String(71), nullable=False)
    actual_hash = Column(String(71), nullable=False)
    matches = Column(Integer, nullable=False)  # 0 or 1
    spot_check_data = Column(Text, default="{}")  # JSON
    verified_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_verification_tx", "transaction_id"),
    )
