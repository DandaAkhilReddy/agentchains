"""Strict trust verification artifacts for listing provenance and safety."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SourceReceipt(Base):
    __tablename__ = "source_receipts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=False)
    provider = Column(String(64), nullable=False)
    source_query = Column(Text, nullable=False)
    request_payload_json = Column(Text, default="{}")
    response_hash = Column(String(71), nullable=False)
    headers_json = Column(Text, default="{}")
    seller_signature = Column(String(256), nullable=False)
    platform_signature = Column(String(256), nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_source_receipts_listing", "listing_id"),
        Index("idx_source_receipts_provider", "provider"),
    )


class ArtifactManifest(Base):
    __tablename__ = "artifact_manifests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=False)
    canonical_hash = Column(String(71), nullable=False)
    mime_type = Column(String(80), nullable=False)
    content_size = Column(Integer, nullable=False)
    schema_fingerprint = Column(String(71), nullable=True)
    dependency_chain_json = Column(Text, default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_artifact_manifest_listing", "listing_id"),
        Index("idx_artifact_manifest_hash", "canonical_hash"),
    )


class VerificationJob(Base):
    __tablename__ = "verification_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=False)
    status = Column(String(24), nullable=False, default="pending")  # pending|running|completed|failed
    trigger_source = Column(String(40), nullable=False, default="listing_create")
    requested_by = Column(String(36), nullable=True)
    stage_status_json = Column(Text, default="{}")
    failure_reason = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_verification_jobs_listing", "listing_id"),
        Index("idx_verification_jobs_status", "status"),
    )


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("verification_jobs.id"), nullable=False)
    listing_id = Column(String(36), ForeignKey("data_listings.id"), nullable=False)
    passed = Column(Boolean, nullable=False, default=False)
    trust_score = Column(Integer, nullable=False, default=0)
    provenance_passed = Column(Boolean, nullable=False, default=False)
    integrity_passed = Column(Boolean, nullable=False, default=False)
    safety_passed = Column(Boolean, nullable=False, default=False)
    reproducibility_passed = Column(Boolean, nullable=False, default=False)
    policy_passed = Column(Boolean, nullable=False, default=False)
    evidence_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_verification_results_listing", "listing_id"),
        Index("idx_verification_results_job", "job_id"),
        Index("idx_verification_results_passed", "passed"),
    )

