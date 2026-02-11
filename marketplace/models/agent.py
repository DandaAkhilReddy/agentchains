import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, String, Text, DateTime
from sqlalchemy.orm import relationship

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class RegisteredAgent(Base):
    __tablename__ = "registered_agents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, default="")
    agent_type = Column(String(20), nullable=False)  # seller | buyer | both
    public_key = Column(Text, nullable=False)  # RSA public key PEM
    wallet_address = Column(String(42), default="")  # Ethereum address
    capabilities = Column(Text, default="[]")  # JSON array
    a2a_endpoint = Column(String(255), default="")
    agent_card_json = Column(Text, default="{}")  # Full A2A AgentCard
    creator_id = Column(String(36), ForeignKey("creators.id"), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    last_seen_at = Column(DateTime(timezone=True))

    # Relationships
    listings = relationship("DataListing", back_populates="seller", lazy="selectin")

    __table_args__ = (
        Index("idx_agents_type", "agent_type"),
        Index("idx_agents_status", "status"),
    )
