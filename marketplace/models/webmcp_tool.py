import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime
from sqlalchemy.orm import relationship

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class WebMCPTool(Base):
    __tablename__ = "webmcp_tools"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    domain = Column(String(500), nullable=False)  # Website domain hosting the tool
    endpoint_url = Column(String(1000), nullable=False)  # WebMCP endpoint URL
    input_schema = Column(Text, default="{}")  # JSON Schema for parameters
    output_schema = Column(Text, default="{}")  # JSON Schema for results
    schema_hash = Column(String(64), default="")  # SHA-256 of input_schema for Tool Lock
    creator_id = Column(String(36), ForeignKey("creators.id"), nullable=False)
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=True)
    category = Column(String(50), nullable=False)  # shopping | research | form_fill | data_extraction
    version = Column(String(20), nullable=False, default="1.0.0")
    status = Column(String(20), nullable=False, default="pending")  # pending | approved | active | suspended
    approval_notes = Column(Text, nullable=True)
    execution_count = Column(Integer, nullable=False, default=0)
    avg_execution_time_ms = Column(Integer, nullable=False, default=0)
    success_rate = Column(Numeric(5, 4), nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    creator = relationship("Creator", lazy="selectin")
    action_listings = relationship("ActionListing", back_populates="tool", lazy="selectin")

    __table_args__ = (
        Index("idx_webmcp_tools_domain", "domain"),
        Index("idx_webmcp_tools_category", "category"),
        Index("idx_webmcp_tools_status", "status"),
        Index("idx_webmcp_tools_creator", "creator_id"),
    )
