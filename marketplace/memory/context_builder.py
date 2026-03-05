"""Context Builder — retrieves relevant memories and formats as model context."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.memory.semantic_store import SemanticMemoryStore

logger = structlog.get_logger(__name__)


class ContextBuilder:
    """Builds context strings from semantic memory for model prompt injection."""

    def __init__(
        self,
        semantic_store: SemanticMemoryStore,
        *,
        max_tokens: int = 2048,
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> None:
        self._store = semantic_store
        self._max_tokens = max_tokens
        self._top_k = top_k
        self._min_similarity = min_similarity

    async def build_context(
        self,
        agent_id: str,
        query: str,
        db: AsyncSession | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Retrieve relevant memories and format as context for model prompt.

        Returns an empty string if no relevant memories are found.
        """
        if db is None:
            return ""

        max_chars = (max_tokens or self._max_tokens) * 4  # Rough char-to-token estimate

        memories = await self._store.recall(
            db,
            agent_id=agent_id,
            query=query,
            top_k=self._top_k,
            min_similarity=self._min_similarity,
        )

        if not memories:
            return ""

        context_parts: list[str] = []
        total_chars = 0
        for mem in memories:
            entry = f"[{mem.memory_type}] {mem.content}"
            if total_chars + len(entry) > max_chars:
                break
            context_parts.append(entry)
            total_chars += len(entry)

        context = "\n".join(context_parts)

        logger.debug(
            "context_built",
            agent_id=agent_id,
            memories_used=len(context_parts),
            context_chars=len(context),
        )

        return context
