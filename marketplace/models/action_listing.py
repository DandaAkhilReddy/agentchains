import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime
from sqlalchemy.orm import relationship

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ActionListing(Base):
    __tablename__ = "action_listings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tool_id = Column(String(36), ForeignKey("webmcp_tools.id"), nullable=False)
    seller_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    price_per_execution = Column(Numeric(10, 6), nullable=False)  # USD per run
    currency = Column(String(10), nullable=False, default="USD")
    default_parameters = Column(Text, default="{}")  # JSON default params
    max_executions_per_hour = Column(Integer, nullable=False, default=60)
    requires_consent = Column(Boolean, nullable=False, default=True)
    domain_lock = Column(Text, default="[]")  # JSON array of allowed domains
    status = Column(String(20), nullable=False, default="active")  # active | paused | suspended
    tags = Column(Text, default="[]")  # JSON array of searchable tags
    access_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    tool = relationship("WebMCPTool", back_populates="action_listings", lazy="selectin")
    seller = relationship("RegisteredAgent", lazy="selectin")
    executions = relationship("ActionExecution", back_populates="action_listing", lazy="selectin")

    __table_args__ = (
        Index("idx_action_listings_tool", "tool_id"),
        Index("idx_action_listings_seller", "seller_id"),
        Index("idx_action_listings_status", "status"),
    )
