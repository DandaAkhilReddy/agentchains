import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AgentStats(Base):
    __tablename__ = "agent_stats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), unique=True, nullable=False)

    # Helpfulness metrics
    unique_buyers_served = Column(Integer, nullable=False, default=0)
    total_listings_created = Column(Integer, nullable=False, default=0)
    total_cache_hits = Column(Integer, nullable=False, default=0)
    category_count = Column(Integer, nullable=False, default=0)
    categories_json = Column(Text, default="[]")  # JSON array

    # Financial metrics
    total_earned_usdc = Column(Numeric(12, 6), nullable=False, default=0.0)
    total_spent_usdc = Column(Numeric(12, 6), nullable=False, default=0.0)
    earnings_by_category_json = Column(Text, default="{}")  # JSON {category: amount}

    # Contribution metrics
    demand_gaps_filled = Column(Integer, nullable=False, default=0)
    avg_listing_quality = Column(Numeric(3, 2), default=0.5)
    total_data_bytes_contributed = Column(Integer, nullable=False, default=0)

    # Scores
    helpfulness_score = Column(Numeric(4, 3), nullable=False, default=0.500)
    helpfulness_rank = Column(Integer)
    earnings_rank = Column(Integer)

    # Specialization
    specialization_tags_json = Column(Text, default="[]")  # JSON array
    primary_specialization = Column(String(50))

    last_calculated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_stats_agent", "agent_id"),
        Index("idx_stats_helpfulness", "helpfulness_score"),
        Index("idx_stats_earnings", "total_earned_usdc"),
    )
