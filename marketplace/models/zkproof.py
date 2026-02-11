import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, String, Text, DateTime

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ZKProof(Base):
    """Zero-knowledge proof record for a listing.

    Each listing gets up to 4 proof types generated at creation time:
    - merkle_root:  SHA-256 Merkle tree root of 1KB content chunks
    - schema:       JSON schema fingerprint (field names, types, counts)
    - bloom_filter: 256-byte bloom filter of content keywords
    - metadata:     Hash commitment of (size, category, freshness, quality)
    """

    __tablename__ = "zk_proofs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=False)
    proof_type = Column(String(30), nullable=False)  # merkle_root | schema | bloom_filter | metadata
    commitment = Column(String(128), nullable=False)  # hex-encoded hash or root
    proof_data = Column(Text, nullable=False, default="{}")  # JSON: full proof payload
    public_inputs = Column(Text, nullable=False, default="{}")  # JSON: verifiable without content
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_zkp_listing", "listing_id"),
        Index("idx_zkp_type", "listing_id", "proof_type"),
    )
