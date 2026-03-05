"""Semantic Memory SQLAlchemy model — stores embeddings for similarity retrieval."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from marketplace.database import Base


class SemanticMemory(Base):
    """Stores agent memories with embeddings for semantic retrieval."""

    __tablename__ = "semantic_memories"

    id = Column(String(36), primary_key=True)
    agent_id = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=False)  # JSON-serialized float array
    metadata_json = Column(Text, default="{}")
    memory_type = Column(String(50), default="fact")  # fact | episode | skill
    access_count = Column(Integer, default=0)
    relevance_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_accessed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_semantic_memories_agent_type", "agent_id", "memory_type"),
    )
