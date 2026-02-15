"""Agent-level trust, memory, and event subscription models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AgentIdentityAttestation(Base):
    __tablename__ = "agent_identity_attestations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    creator_id = Column(String(36), ForeignKey("creators.id"), nullable=True)
    status = Column(String(20), nullable=False, default="completed")
    score = Column(Integer, nullable=False, default=0)
    evidence_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_identity_attest_agent", "agent_id"),
        Index("idx_identity_attest_creator", "creator_id"),
    )


class AgentRuntimeAttestation(Base):
    __tablename__ = "agent_runtime_attestations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    runtime_name = Column(String(80), nullable=False, default="unknown")
    runtime_version = Column(String(80), nullable=False, default="")
    sdk_version = Column(String(80), nullable=False, default="")
    endpoint_reachable = Column(Boolean, nullable=False, default=False)
    supports_memory = Column(Boolean, nullable=False, default=False)
    score = Column(Integer, nullable=False, default=0)
    evidence_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_runtime_attest_agent", "agent_id"),
        Index("idx_runtime_attest_created", "created_at"),
    )


class AgentKnowledgeChallenge(Base):
    __tablename__ = "agent_knowledge_challenges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    capability = Column(String(80), nullable=False)
    challenge_type = Column(String(40), nullable=False)
    prompt = Column(Text, nullable=False)
    expected_schema_json = Column(Text, default="{}")
    expected_keywords_json = Column(Text, default="[]")
    difficulty = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_knowledge_challenge_capability", "capability"),
        Index("idx_knowledge_challenge_type", "challenge_type"),
    )


class AgentKnowledgeChallengeRun(Base):
    __tablename__ = "agent_knowledge_challenge_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    challenge_id = Column(
        String(36), ForeignKey("agent_knowledge_challenges.id"), nullable=True
    )
    status = Column(String(20), nullable=False, default="pending")
    score = Column(Integer, nullable=False, default=0)
    severe_safety_failure = Column(Boolean, nullable=False, default=False)
    evidence_hash = Column(String(71), nullable=True)
    evidence_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_knowledge_run_agent", "agent_id"),
        Index("idx_knowledge_run_status", "status"),
    )


class AgentTrustProfile(Base):
    __tablename__ = "agent_trust_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(
        String(36), ForeignKey("registered_agents.id"), nullable=False, unique=True
    )
    creator_id = Column(String(36), ForeignKey("creators.id"), nullable=True)
    trust_status = Column(String(20), nullable=False, default="unverified")
    trust_tier = Column(String(10), nullable=False, default="T0")
    trust_score = Column(Integer, nullable=False, default=0)
    stage_identity = Column(Integer, nullable=False, default=0)
    stage_runtime = Column(Integer, nullable=False, default=0)
    stage_knowledge = Column(Integer, nullable=False, default=0)
    stage_memory = Column(Integer, nullable=False, default=0)
    stage_abuse = Column(Integer, nullable=False, default=0)
    restricted_reason = Column(Text, default="")
    knowledge_challenge_summary_json = Column(Text, default="{}")
    memory_provenance_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_agent_trust_status", "trust_status"),
        Index("idx_agent_trust_tier", "trust_tier"),
    )


class MemorySnapshot(Base):
    __tablename__ = "memory_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    creator_id = Column(String(36), ForeignKey("creators.id"), nullable=True)
    source_type = Column(String(40), nullable=False, default="sdk")
    label = Column(String(120), nullable=False, default="default")
    manifest_json = Column(Text, default="{}")
    merkle_root = Column(String(71), nullable=False)
    encrypted_blob_ref = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="imported")
    total_records = Column(Integer, nullable=False, default=0)
    total_chunks = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_memory_snapshot_agent", "agent_id"),
        Index("idx_memory_snapshot_status", "status"),
    )


class MemorySnapshotChunk(Base):
    __tablename__ = "memory_snapshot_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id = Column(String(36), ForeignKey("memory_snapshots.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_hash = Column(String(71), nullable=False)
    chunk_payload = Column(Text, default="")
    record_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_memory_chunk_snapshot", "snapshot_id"),
        Index("idx_memory_chunk_index", "chunk_index"),
    )


class MemoryVerificationRun(Base):
    __tablename__ = "memory_verification_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id = Column(String(36), ForeignKey("memory_snapshots.id"), nullable=False)
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    score = Column(Integer, nullable=False, default=0)
    sampled_entries_json = Column(Text, default="[]")
    evidence_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_memory_verify_snapshot", "snapshot_id"),
        Index("idx_memory_verify_agent", "agent_id"),
    )


class EventSubscription(Base):
    __tablename__ = "event_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("registered_agents.id"), nullable=False)
    callback_url = Column(String(500), nullable=False)
    event_types_json = Column(Text, default='["*"]')
    secret = Column(String(128), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    failure_count = Column(Integer, nullable=False, default=0)
    last_delivery_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_event_sub_agent", "agent_id"),
        Index("idx_event_sub_status", "status"),
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id = Column(
        String(36), ForeignKey("event_subscriptions.id"), nullable=False
    )
    event_id = Column(String(36), nullable=False)
    event_type = Column(String(80), nullable=False)
    payload_json = Column(Text, default="{}")
    signature = Column(String(128), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, default="")
    delivery_attempt = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_webhook_delivery_sub", "subscription_id"),
        Index("idx_webhook_delivery_event", "event_id"),
        Index("idx_webhook_delivery_status", "status"),
    )

