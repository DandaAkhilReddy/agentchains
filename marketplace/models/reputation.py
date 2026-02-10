import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ReputationScore(Base):
    __tablename__ = "reputation_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), unique=True, nullable=False)
    total_transactions = Column(Integer, nullable=False, default=0)
    successful_deliveries = Column(Integer, nullable=False, default=0)
    failed_deliveries = Column(Integer, nullable=False, default=0)
    verified_count = Column(Integer, nullable=False, default=0)
    verification_failures = Column(Integer, nullable=False, default=0)
    avg_response_ms = Column(Numeric(10, 2))
    total_volume_usdc = Column(Numeric(12, 6), nullable=False, default=0.0)
    composite_score = Column(Numeric(4, 3), nullable=False, default=0.500)  # 0.000 to 1.000
    last_calculated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_reputation_agent", "agent_id"),
        Index("idx_reputation_score", "composite_score"),
    )
