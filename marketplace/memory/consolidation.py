"""Memory Consolidation — episodic-to-semantic promotion, deduplication, decay.

Provides background-runnable tasks for memory lifecycle management:
- Promote verified episodic snapshots to semantic memory
- Merge near-duplicate memories
- Decay stale unaccessed memories
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.memory.embedding_service import EmbeddingService
from marketplace.memory.semantic_store import SemanticMemoryStore, _cosine_similarity
from marketplace.models.semantic_memory import SemanticMemory

logger = structlog.get_logger(__name__)


class MemoryConsolidator:
    """Manages memory lifecycle: promotion, deduplication, and decay."""

    def __init__(
        self,
        semantic_store: SemanticMemoryStore,
        embedding_service: EmbeddingService,
    ) -> None:
        self._store = semantic_store
        self._embedding = embedding_service

    async def promote_episodic(
        self,
        db: AsyncSession,
        agent_id: str,
        snapshot_id: str,
    ) -> int:
        """Extract key facts from a verified snapshot and store as semantic memory.

        Returns the number of memories promoted.
        """
        from marketplace.models.agent_trust import MemorySnapshotChunk

        result = await db.execute(
            select(MemorySnapshotChunk)
            .where(MemorySnapshotChunk.snapshot_id == snapshot_id)
            .order_by(MemorySnapshotChunk.chunk_index.asc())
        )
        chunks = list(result.scalars().all())

        promoted = 0
        for chunk in chunks:
            try:
                from marketplace.services.memory_service import _decrypt_chunk_payload

                plaintext = _decrypt_chunk_payload(chunk.chunk_payload or "")
                records = json.loads(plaintext) if plaintext else []
                if not isinstance(records, list):
                    continue

                for record in records:
                    if not isinstance(record, dict):
                        continue
                    # Extract content from common fields
                    content = (
                        record.get("text")
                        or record.get("content")
                        or record.get("value")
                        or json.dumps(record, default=str)
                    )
                    if not content or len(content) < 10:
                        continue

                    await self._store.store(
                        db,
                        agent_id=agent_id,
                        content=content[:2000],  # Cap at 2K chars
                        metadata={
                            "source": "episodic_promotion",
                            "snapshot_id": snapshot_id,
                        },
                        memory_type="episode",
                    )
                    promoted += 1

            except Exception:
                logger.warning(
                    "chunk_promotion_failed",
                    snapshot_id=snapshot_id,
                    chunk_index=chunk.chunk_index,
                )

        logger.info(
            "episodic_promotion_completed",
            agent_id=agent_id,
            snapshot_id=snapshot_id,
            promoted=promoted,
        )
        return promoted

    async def merge_similar(
        self,
        db: AsyncSession,
        agent_id: str,
        threshold: float = 0.95,
    ) -> int:
        """Merge near-duplicate memories (cosine similarity >= threshold).

        Keeps the memory with higher access_count, deletes the other.
        Returns the number of memories merged (deleted).
        """
        result = await db.execute(
            select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
        )
        memories = list(result.scalars().all())
        if len(memories) < 2:
            return 0

        # Parse embeddings
        parsed: list[tuple[SemanticMemory, list[float]]] = []
        for mem in memories:
            try:
                emb = json.loads(mem.embedding_json)
                parsed.append((mem, emb))
            except Exception:
                continue

        to_delete: set[str] = set()
        merged = 0

        for i in range(len(parsed)):
            if parsed[i][0].id in to_delete:
                continue
            for j in range(i + 1, len(parsed)):
                if parsed[j][0].id in to_delete:
                    continue

                sim = _cosine_similarity(parsed[i][1], parsed[j][1])
                if sim >= threshold:
                    # Keep the one with higher access count
                    mem_a, mem_b = parsed[i][0], parsed[j][0]
                    if (mem_b.access_count or 0) > (mem_a.access_count or 0):
                        to_delete.add(mem_a.id)
                    else:
                        to_delete.add(mem_b.id)
                    merged += 1

        for mem_id in to_delete:
            mem_result = await db.execute(
                select(SemanticMemory).where(SemanticMemory.id == mem_id)
            )
            mem = mem_result.scalar_one_or_none()
            if mem:
                await db.delete(mem)

        if merged:
            await db.flush()
            logger.info(
                "memory_merge_completed",
                agent_id=agent_id,
                merged=merged,
            )

        return merged

    async def decay(
        self,
        db: AsyncSession,
        agent_id: str,
        max_age_days: int = 90,
        decay_factor: float = 0.9,
    ) -> int:
        """Reduce relevance score of stale unaccessed memories.

        Returns the number of memories decayed.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        result = await db.execute(
            select(SemanticMemory).where(
                SemanticMemory.agent_id == agent_id,
                SemanticMemory.last_accessed_at < cutoff,
            )
        )
        stale = list(result.scalars().all())

        decayed = 0
        for mem in stale:
            old_score = mem.relevance_score or 1.0
            new_score = old_score * decay_factor
            if new_score < 0.01:
                # Too stale — delete
                await db.delete(mem)
            else:
                mem.relevance_score = new_score
            decayed += 1

        if decayed:
            await db.flush()
            logger.info(
                "memory_decay_completed",
                agent_id=agent_id,
                decayed=decayed,
            )

        return decayed
