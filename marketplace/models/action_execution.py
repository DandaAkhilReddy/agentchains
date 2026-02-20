import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime

from sqlalchemy.orm import relationship

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ActionExecution(Base):
    __tablename__ = "action_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_listing_id = Column(String(36), ForeignKey("action_listings.id"), nullable=False)
    buyer_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    tool_id = Column(String(36), ForeignKey("webmcp_tools.id"), nullable=False)
    parameters = Column(Text, default="{}")  # JSON input params
    result = Column(Text, default="{}")  # JSON output
    status = Column(String(30), nullable=False, default="pending")  # pending | executing | completed | failed | timeout
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    proof_of_execution = Column(Text, nullable=True)  # JWT signed proof
    proof_verified = Column(Boolean, nullable=False, default=False)
    amount_usdc = Column(Numeric(10, 6), nullable=False)
    payment_status = Column(String(20), nullable=False, default="held")  # held | captured | released | refunded
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    action_listing = relationship("ActionListing", back_populates="executions", lazy="selectin")
    buyer = relationship("RegisteredAgent", lazy="selectin")
    tool = relationship("WebMCPTool", lazy="selectin")

    __table_args__ = (
        Index("idx_action_executions_listing", "action_listing_id"),
        Index("idx_action_executions_buyer", "buyer_id"),
        Index("idx_action_executions_status", "status"),
        Index("idx_action_executions_tool", "tool_id"),
    )
