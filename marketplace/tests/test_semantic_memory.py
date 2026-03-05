"""Tests for SemanticMemoryStore, ContextBuilder, and SemanticMemory model."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.memory.context_builder import ContextBuilder
from marketplace.memory.embedding_service import EmbeddingService
from marketplace.memory.semantic_store import (
    MemoryEntry,
    SemanticMemoryStore,
    _cosine_similarity,
)
from marketplace.models.semantic_memory import SemanticMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit_vec(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in values))
    if norm == 0:
        return values
    return [x / norm for x in values]


def _mock_embedding_service(vector: list[float] | None = None) -> EmbeddingService:
    """Return an EmbeddingService whose embed() always returns *vector*."""
    svc = MagicMock(spec=EmbeddingService)
    vec = vector or _unit_vec([1.0, 0.0, 0.0, 0.0])
    svc.embed = AsyncMock(return_value=vec)
    return svc


def _store(vector: list[float] | None = None) -> SemanticMemoryStore:
    return SemanticMemoryStore(_mock_embedding_service(vector))


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# _cosine_similarity — unit tests (no DB needed)
# ---------------------------------------------------------------------------

def test_cosine_similarity_identical_vectors():
    v = _unit_vec([1.0, 2.0, 3.0])
    result = _cosine_similarity(v, v)
    assert abs(result - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-9


def test_cosine_similarity_opposite_vectors():
    v = _unit_vec([1.0, 0.0, 0.0])
    neg = [-x for x in v]
    result = _cosine_similarity(v, neg)
    assert abs(result - (-1.0)) < 1e-9


def test_cosine_similarity_zero_vector_returns_zero():
    a = [0.0, 0.0, 0.0]
    b = [1.0, 2.0, 3.0]
    # Zero vector has norm 0 — should not divide-by-zero
    result = _cosine_similarity(a, b)
    assert result == 0.0


def test_cosine_similarity_empty_vectors_returns_zero():
    result = _cosine_similarity([], [])
    assert result == 0.0


def test_cosine_similarity_mismatched_lengths_returns_zero():
    result = _cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])
    assert result == 0.0


# ---------------------------------------------------------------------------
# SemanticMemoryStore.store()
# ---------------------------------------------------------------------------

async def test_store_creates_db_record(db: AsyncSession):
    store = _store()
    agent_id = _new_id()
    memory_id = await store.store(db, agent_id=agent_id, content="hello world memory")

    from sqlalchemy import select
    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == memory_id))
    mem = result.scalar_one_or_none()

    assert mem is not None
    assert mem.agent_id == agent_id
    assert mem.content == "hello world memory"


async def test_store_returns_uuid_string(db: AsyncSession):
    store = _store()
    memory_id = await store.store(db, agent_id=_new_id(), content="return id check")
    assert isinstance(memory_id, str)
    # Validate it parses as a UUID
    uuid.UUID(memory_id)


async def test_store_with_metadata(db: AsyncSession):
    from sqlalchemy import select
    store = _store()
    agent_id = _new_id()
    meta = {"source": "unit-test", "tag": 42}
    memory_id = await store.store(db, agent_id=agent_id, content="meta content", metadata=meta)

    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == memory_id))
    mem = result.scalar_one()
    assert json.loads(mem.metadata_json) == meta


async def test_store_default_memory_type_is_fact(db: AsyncSession):
    from sqlalchemy import select
    store = _store()
    memory_id = await store.store(db, agent_id=_new_id(), content="default type check")

    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == memory_id))
    mem = result.scalar_one()
    assert mem.memory_type == "fact"


async def test_store_custom_memory_type(db: AsyncSession):
    from sqlalchemy import select
    store = _store()
    memory_id = await store.store(
        db, agent_id=_new_id(), content="custom type content", memory_type="episode"
    )

    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == memory_id))
    mem = result.scalar_one()
    assert mem.memory_type == "episode"


async def test_store_persists_embedding_json(db: AsyncSession):
    from sqlalchemy import select
    vec = _unit_vec([0.1, 0.2, 0.3, 0.4])
    store = _store(vector=vec)
    memory_id = await store.store(db, agent_id=_new_id(), content="embedding persist check")

    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == memory_id))
    mem = result.scalar_one()
    stored_vec = json.loads(mem.embedding_json)
    assert stored_vec == vec


# ---------------------------------------------------------------------------
# SemanticMemoryStore.recall()
# ---------------------------------------------------------------------------

async def test_recall_returns_similar_memories(db: AsyncSession):
    vec = _unit_vec([1.0, 0.0, 0.0, 0.0])
    store = _store(vector=vec)
    agent_id = _new_id()

    await store.store(db, agent_id=agent_id, content="memory about python")
    await store.store(db, agent_id=agent_id, content="memory about databases")

    entries = await store.recall(db, agent_id=agent_id, query="python query", min_similarity=0.0)
    assert len(entries) >= 1
    assert all(isinstance(e, MemoryEntry) for e in entries)


async def test_recall_top_k_limit(db: AsyncSession):
    vec = _unit_vec([1.0, 0.0, 0.0, 0.0])
    store = _store(vector=vec)
    agent_id = _new_id()

    for i in range(5):
        await store.store(db, agent_id=agent_id, content=f"memory item {i}")

    entries = await store.recall(db, agent_id=agent_id, query="any query", top_k=2, min_similarity=0.0)
    assert len(entries) <= 2


async def test_recall_min_similarity_filters_low_scores(db: AsyncSession):
    """Memories with similarity < min_similarity should not be returned."""
    agent_id = _new_id()

    # Store memory with a known embedding
    stored_vec = _unit_vec([1.0, 0.0, 0.0])
    emb_svc_store = _mock_embedding_service(stored_vec)
    store_obj = SemanticMemoryStore(emb_svc_store)
    await store_obj.store(db, agent_id=agent_id, content="stored memory content")

    # Recall with an orthogonal query vector → similarity = 0.0
    query_vec = _unit_vec([0.0, 1.0, 0.0])
    emb_svc_recall = _mock_embedding_service(query_vec)
    recall_store = SemanticMemoryStore(emb_svc_recall)

    entries = await recall_store.recall(
        db, agent_id=agent_id, query="orthogonal query", min_similarity=0.5
    )
    assert len(entries) == 0


async def test_recall_empty_store_returns_empty_list(db: AsyncSession):
    store = _store()
    entries = await store.recall(db, agent_id=_new_id(), query="nothing here")
    assert entries == []


async def test_recall_agent_isolation(db: AsyncSession):
    """Memories of agent A should not appear in recall for agent B."""
    vec = _unit_vec([1.0, 0.0, 0.0, 0.0])
    store = _store(vector=vec)

    agent_a = _new_id()
    agent_b = _new_id()

    await store.store(db, agent_id=agent_a, content="agent A memory")

    entries_b = await store.recall(db, agent_id=agent_b, query="query", min_similarity=0.0)
    assert len(entries_b) == 0


async def test_recall_updates_access_count(db: AsyncSession):
    from sqlalchemy import select
    vec = _unit_vec([1.0, 0.0, 0.0, 0.0])
    store = _store(vector=vec)
    agent_id = _new_id()

    memory_id = await store.store(db, agent_id=agent_id, content="access count test")

    # First recall
    await store.recall(db, agent_id=agent_id, query="q", min_similarity=0.0)

    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == memory_id))
    mem = result.scalar_one()
    assert (mem.access_count or 0) >= 1


async def test_recall_updates_last_accessed_at(db: AsyncSession):
    from sqlalchemy import select
    vec = _unit_vec([1.0, 0.0, 0.0, 0.0])
    store = _store(vector=vec)
    agent_id = _new_id()
    before = datetime.now(timezone.utc)

    memory_id = await store.store(db, agent_id=agent_id, content="last accessed update")
    await store.recall(db, agent_id=agent_id, query="q", min_similarity=0.0)

    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == memory_id))
    mem = result.scalar_one()
    assert mem.last_accessed_at is not None


# ---------------------------------------------------------------------------
# SemanticMemoryStore.forget()
# ---------------------------------------------------------------------------

async def test_forget_deletes_memory(db: AsyncSession):
    from sqlalchemy import select
    vec = _unit_vec([1.0, 0.0, 0.0, 0.0])
    store = _store(vector=vec)
    agent_id = _new_id()

    memory_id = await store.store(db, agent_id=agent_id, content="to be forgotten")
    deleted = await store.forget(db, agent_id=agent_id, memory_id=memory_id)

    assert deleted is True
    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == memory_id))
    assert result.scalar_one_or_none() is None


async def test_forget_nonexistent_returns_false_no_crash(db: AsyncSession):
    store = _store()
    result = await store.forget(db, agent_id=_new_id(), memory_id=_new_id())
    assert result is False


# ---------------------------------------------------------------------------
# ContextBuilder
# ---------------------------------------------------------------------------

def _make_context_builder(
    recall_result: list[MemoryEntry] | None = None,
    max_tokens: int = 2048,
) -> ContextBuilder:
    store_mock = MagicMock(spec=SemanticMemoryStore)
    store_mock.recall = AsyncMock(return_value=recall_result or [])
    return ContextBuilder(store_mock, max_tokens=max_tokens)


async def test_context_builder_returns_string(db: AsyncSession):
    entries = [MemoryEntry("id1", "Python is a language", 0.9, "fact", {})]
    builder = _make_context_builder(recall_result=entries)
    context = await builder.build_context("agent-1", "Python", db=db)
    assert isinstance(context, str)
    assert len(context) > 0


async def test_context_builder_formats_memory_type(db: AsyncSession):
    entries = [MemoryEntry("id1", "Content here", 0.9, "episode", {})]
    builder = _make_context_builder(recall_result=entries)
    context = await builder.build_context("agent-1", "query", db=db)
    assert "[episode]" in context


async def test_context_builder_respects_max_tokens(db: AsyncSession):
    long_content = "x" * 10000
    entries = [
        MemoryEntry("id1", long_content, 0.95, "fact", {}),
        MemoryEntry("id2", long_content, 0.90, "fact", {}),
    ]
    # max_tokens=10 → max_chars=40 — both entries too long to fit
    builder = _make_context_builder(recall_result=entries, max_tokens=10)
    context = await builder.build_context("agent-1", "query", db=db, max_tokens=10)
    # Each entry is 10005 chars; budget is 40 — so nothing fits → empty
    assert context == ""


async def test_context_builder_no_memories_returns_empty_string(db: AsyncSession):
    builder = _make_context_builder(recall_result=[])
    context = await builder.build_context("agent-1", "query", db=db)
    assert context == ""


async def test_context_builder_db_none_returns_empty_string():
    builder = _make_context_builder()
    context = await builder.build_context("agent-1", "query", db=None)
    assert context == ""


async def test_context_builder_multiple_types_joined(db: AsyncSession):
    entries = [
        MemoryEntry("id1", "fact content", 0.9, "fact", {}),
        MemoryEntry("id2", "episode content", 0.8, "episode", {}),
        MemoryEntry("id3", "skill content", 0.7, "skill", {}),
    ]
    builder = _make_context_builder(recall_result=entries)
    context = await builder.build_context("agent-1", "query", db=db)
    assert "[fact]" in context
    assert "[episode]" in context
    assert "[skill]" in context
    assert context.count("\n") == 2  # Three lines joined with newline


# ---------------------------------------------------------------------------
# SemanticMemory model — structural tests
# ---------------------------------------------------------------------------

def test_semantic_memory_table_name():
    assert SemanticMemory.__tablename__ == "semantic_memories"


def test_semantic_memory_default_access_count():
    # Column default value is 0
    col = SemanticMemory.__table__.c.access_count
    assert col.default.arg == 0


def test_semantic_memory_default_relevance_score():
    col = SemanticMemory.__table__.c.relevance_score
    assert col.default.arg == 1.0


def test_semantic_memory_composite_index_exists():
    """ix_semantic_memories_agent_type composite index must be declared."""
    index_names = [idx.name for idx in SemanticMemory.__table__.indexes]
    assert "ix_semantic_memories_agent_type" in index_names


def test_semantic_memory_agent_id_column_is_indexed():
    col = SemanticMemory.__table__.c.agent_id
    assert col.index is True


def test_semantic_memory_has_required_columns():
    cols = {c.name for c in SemanticMemory.__table__.c}
    for required in ("id", "agent_id", "content", "embedding_json", "memory_type",
                     "access_count", "relevance_score", "created_at", "last_accessed_at"):
        assert required in cols
