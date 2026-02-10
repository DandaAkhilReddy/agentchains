import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Index, Integer, Numeric, String, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class DemandSignal(Base):
    __tablename__ = "demand_signals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_pattern = Column(String(255), nullable=False, unique=True)  # Normalized query
    category = Column(String(50))
    search_count = Column(Integer, nullable=False, default=1)
    unique_requesters = Column(Integer, nullable=False, default=1)
    avg_max_price = Column(Numeric(10, 6))
    fulfillment_rate = Column(Numeric(4, 3), default=0.0)  # % of searches with results
    conversion_rate = Column(Numeric(4, 3), default=0.0)  # % that led to purchase
    velocity = Column(Numeric(8, 2), default=0.0)  # Searches per hour (rolling)
    is_gap = Column(Integer, nullable=False, default=0)  # 1 if fulfillment_rate < 0.2
    first_searched_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_searched_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_demand_pattern", "query_pattern"),
        Index("idx_demand_category", "category"),
        Index("idx_demand_velocity", "velocity"),
        Index("idx_demand_gap", "is_gap"),
    )
