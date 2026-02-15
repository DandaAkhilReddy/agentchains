import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String, Text, DateTime
from sqlalchemy.orm import relationship

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class DataListing(Base):
    __tablename__ = "data_listings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    category = Column(String(50), nullable=False)  # web_search | code_analysis | document_summary | api_response | computation
    content_hash = Column(String(71), nullable=False)  # sha256:<64 hex chars>
    content_size = Column(Integer, nullable=False)
    content_type = Column(String(50), nullable=False, default="application/json")
    price_usdc = Column(Numeric(10, 6), nullable=False)  # Stored as USD amount
    currency = Column(String(10), nullable=False, default="USD")
    metadata_json = Column(Text, default="{}")  # JSON: source, query, params, model_used
    tags = Column(Text, default="[]")  # JSON array of searchable tags
    quality_score = Column(Numeric(3, 2), default=0.5)  # 0.00 to 1.00
    freshness_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True))
    status = Column(String(20), nullable=False, default="active")
    trust_status = Column(String(32), nullable=False, default="pending_verification")
    trust_score = Column(Integer, nullable=False, default=0)
    verification_summary_json = Column(Text, default="{}")
    provenance_json = Column(Text, default="{}")
    verification_updated_at = Column(DateTime(timezone=True), nullable=True)
    access_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    seller = relationship("RegisteredAgent", back_populates="listings", lazy="selectin")
    transactions = relationship("Transaction", back_populates="listing", lazy="selectin")

    __table_args__ = (
        Index("idx_listings_seller", "seller_id"),
        Index("idx_listings_category", "category"),
        Index("idx_listings_status", "status"),
        Index("idx_listings_content_hash", "content_hash"),
        Index("idx_listings_freshness", "freshness_at"),
    )
