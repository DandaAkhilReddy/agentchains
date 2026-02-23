import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ChainPolicy(Base):
    __tablename__ = "chain_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    policy_type = Column(String(30), nullable=False)  # jurisdiction | data_residency | cost_limit
    rules_json = Column(Text, nullable=False)
    enforcement = Column(String(20), default="block")  # block | warn | log
    owner_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=True)
    scope = Column(String(20), default="chain")  # chain | node | global
    status = Column(String(20), default="active")  # active | disabled
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_chain_policies_owner", "owner_id"),
        Index("idx_chain_policies_type", "policy_type"),
        Index("idx_chain_policies_status", "status"),
    )
