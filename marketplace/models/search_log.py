import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_text = Column(Text, nullable=False)
    category = Column(String(50))
    source = Column(String(30), nullable=False, default="discover")  # discover | auto_match | express
    requester_id = Column(String(36), ForeignKey("registered_agents.id"))
    matched_count = Column(Integer, nullable=False, default=0)
    led_to_purchase = Column(Integer, nullable=False, default=0)  # 0 or 1
    max_price = Column(Numeric(10, 6))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_search_query", "query_text"),
        Index("idx_search_category", "category"),
        Index("idx_search_created", "created_at"),
        Index("idx_search_requester", "requester_id"),
    )
