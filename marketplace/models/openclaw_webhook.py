import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class OpenClawWebhook(Base):
    """Webhook registration for pushing marketplace events to OpenClaw agents."""

    __tablename__ = "openclaw_webhooks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    gateway_url = Column(String(500), nullable=False)  # OpenClaw POST /hooks/agent URL
    bearer_token = Column(String(500), nullable=False)  # OpenClaw webhook auth token
    event_types = Column(Text, default='["opportunity","demand_spike","transaction"]')
    filters = Column(Text, default='{}')  # JSON: {"categories":["web_search"],"min_urgency":0.5}
    status = Column(String(20), default="active")  # active | paused | failed
    failure_count = Column(Integer, default=0)
    last_delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_oc_webhook_agent", "agent_id"),
        Index("idx_oc_webhook_status", "status"),
    )
