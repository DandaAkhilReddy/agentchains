import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class OpportunitySignal(Base):
    __tablename__ = "opportunity_signals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demand_signal_id = Column(String(36), ForeignKey("demand_signals.id"), nullable=False)
    query_pattern = Column(String(255), nullable=False)
    category = Column(String(50))
    estimated_revenue_usdc = Column(Numeric(10, 6), nullable=False)
    search_velocity = Column(Numeric(8, 2), nullable=False)
    competing_listings = Column(Integer, nullable=False, default=0)
    urgency_score = Column(Numeric(4, 3), nullable=False)  # 0.000 to 1.000
    status = Column(String(20), nullable=False, default="active")  # active | fulfilled | expired
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_opp_urgency", "urgency_score"),
        Index("idx_opp_status", "status"),
        Index("idx_opp_category", "category"),
    )
