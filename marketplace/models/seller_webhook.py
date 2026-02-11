import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SellerWebhook(Base):
    """Webhook registration for sellers to receive demand notifications."""

    __tablename__ = "seller_webhooks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    url = Column(String(500), nullable=False)
    event_types = Column(Text, default='["demand_match"]')  # JSON array
    secret = Column(String(128))  # HMAC signing secret
    status = Column(String(20), default="active")  # active | paused | failed
    failure_count = Column(Integer, default=0)
    last_triggered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_webhook_seller", "seller_id"),
    )
