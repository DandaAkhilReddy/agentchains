import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class DataCatalogEntry(Base):
    """A seller's declaration of capability: 'I can produce X type of data.'

    Buyers discover sellers through catalog search before any listing exists.
    """

    __tablename__ = "data_catalog"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    namespace = Column(String(100), nullable=False)  # e.g. "web_search.python"
    topic = Column(String(200), nullable=False)  # Human-readable topic
    description = Column(Text, default="")
    schema_json = Column(Text, default="{}")  # JSON: expected output schema
    price_range_min = Column(Numeric(10, 6), default=0.001)
    price_range_max = Column(Numeric(10, 6), default=0.01)
    quality_avg = Column(Numeric(3, 2), default=0.5)
    active_listings_count = Column(Integer, default=0)
    status = Column(String(20), default="active")  # active | paused | retired
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_catalog_agent", "agent_id"),
        Index("idx_catalog_namespace", "namespace"),
        Index("idx_catalog_status", "status"),
    )


class CatalogSubscription(Base):
    """A buyer subscribes to a namespace/topic pattern to get notified of new capabilities."""

    __tablename__ = "catalog_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscriber_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    namespace_pattern = Column(String(100), nullable=False)  # glob pattern, e.g. "web_search.*"
    topic_pattern = Column(String(200), default="*")
    category_filter = Column(String(50))
    max_price = Column(Numeric(10, 6))
    min_quality = Column(Numeric(3, 2))
    notify_via = Column(String(20), default="websocket")  # websocket | webhook
    webhook_url = Column(String(500))
    status = Column(String(20), default="active")  # active | paused
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_sub_subscriber", "subscriber_id"),
        Index("idx_sub_namespace", "namespace_pattern"),
    )
