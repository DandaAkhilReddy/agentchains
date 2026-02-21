import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Index, Integer, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class MCPServerEntry(Base):
    __tablename__ = "mcp_servers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    base_url = Column(String(500), nullable=False)
    namespace = Column(String(100), nullable=False)
    description = Column(Text, default="")
    tools_json = Column(Text, default="[]")
    resources_json = Column(Text, default="[]")
    health_score = Column(Integer, default=100)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="active")
    auth_type = Column(String(20), default="none")
    auth_credential_ref = Column(String(200), default="")
    registered_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_mcp_servers_namespace", "namespace"),
        Index("idx_mcp_servers_status", "status"),
    )
