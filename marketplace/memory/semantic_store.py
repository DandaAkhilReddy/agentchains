"""Semantic Memory Store — embed, persist, and recall memories by similarity.

SQLite-backed — no external vector DB required for development.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.memory.embedding_service import EmbeddingService
from marketplace.models.semantic_memory import SemanticMemory

logger = structlog.get_logger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class MemoryEntry:
    """A retrieved memory with similarity score."""

    def __init__(
        self,
        memory_id: str,
        content: str,
        similarity: float,
        memory_type: str,
        metadata: dict[str, Any],
    ) -> None:
        self.memory_id = memory_id
        self.content = content
        self.similarity = similarity
        self.memory_type = memory_type
        self.metadata = metadata


class SemanticMemoryStore:
    """Stores and retrieves agent memories using embedding similarity."""

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedding = embedding_service

    async def store(
        self,
        db: AsyncSession,
        agent_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        memory_type: str = "fact",
    ) -> str:
        """Embed content and persist as a semantic memory."""
        embedding = await self._embedding.embed(content)
        memory_id = str(uuid.uuid4())

        memory = SemanticMemory(
            id=memory_id,
            agent_id=agent_id,
            content=content,
            embedding_json=json.dumps(embedding),
            metadata_json=json.dumps(metadata or {}),
            memory_type=memory_type,
        )
        db.add(memory)
        await db.flush()

        logger.info(
            "memory_stored",
            agent_id=agent_id,
            memory_id=memory_id,
            memory_type=memory_type,
            content_length=len(content),
        )
        return memory_id

    async def recall(
        self,
        db: AsyncSession,
        agent_id: str,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> list[MemoryEntry]:
        """Retrieve memories by embedding similarity."""
        query_embedding = await self._embedding.embed(query)

        # Load all memories for this agent
        result = await db.execute(
            select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
        )
        memories = list(result.scalars().all())

        # Compute similarities
        scored: list[tuple[SemanticMemory, float]] = []
        for mem in memories:
            mem_embedding = json.loads(mem.embedding_json)
            sim = _cosine_similarity(query_embedding, mem_embedding)
            if sim >= min_similarity:
                scored.append((mem, sim))

        # Sort by similarity (descending) and take top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        # Update access counts and last_accessed_at
        now = datetime.now(timezone.utc)
        entries: list[MemoryEntry] = []
        for mem, sim in top:
            mem.access_count = (mem.access_count or 0) + 1
            mem.last_accessed_at = now
            entries.append(MemoryEntry(
                memory_id=mem.id,
                content=mem.content,
                similarity=sim,
                memory_type=mem.memory_type or "fact",
                metadata=json.loads(mem.metadata_json) if mem.metadata_json else {},
            ))

        if entries:
            await db.flush()

        return entries

    async def forget(
        self,
        db: AsyncSession,
        agent_id: str,
        memory_id: str,
    ) -> bool:
        """Delete a specific memory."""
        result = await db.execute(
            select(SemanticMemory).where(
                SemanticMemory.id == memory_id,
                SemanticMemory.agent_id == agent_id,
            )
        )
        memory = result.scalar_one_or_none()
        if memory is None:
            return False

        await db.delete(memory)
        await db.flush()
        logger.info("memory_forgotten", agent_id=agent_id, memory_id=memory_id)
        return True
