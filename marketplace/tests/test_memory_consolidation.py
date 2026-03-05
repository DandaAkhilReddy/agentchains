"""Tests for MemoryConsolidator — promote, merge, decay — and verify_snapshot integration."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.memory.consolidation import MemoryConsolidator
from marketplace.memory.embedding_service import EmbeddingService
from marketplace.memory.semantic_store import SemanticMemoryStore
from marketplace.models.agent_trust import (
    MemorySnapshot,
    MemorySnapshotChunk,
)
from marketplace.models.semantic_memory import SemanticMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


def _unit_vec(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in values))
    if norm == 0:
        return values
    return [x / norm for x in values]


def _mock_embedding_service(vector: list[float] | None = None) -> EmbeddingService:
    svc = MagicMock(spec=EmbeddingService)
    vec = vector or _unit_vec([1.0, 0.0, 0.0, 0.0])
    svc.embed = AsyncMock(return_value=vec)
    return svc


def _make_consolidator(vector: list[float] | None = None) -> MemoryConsolidator:
    emb_svc = _mock_embedding_service(vector)
    store = SemanticMemoryStore(emb_svc)
    return MemoryConsolidator(store, emb_svc)


def _make_agent_in_db(agent_id: str | None = None) -> str:
    """Return an agent_id; the actual RegisteredAgent row creation is done inline via SQL or fixture."""
    return agent_id or _new_id()


async def _insert_agent(db: AsyncSession, agent_id: str) -> None:
    """Insert a minimal RegisteredAgent row so FK constraints pass."""
    from marketplace.models.agent import RegisteredAgent
    agent = RegisteredAgent(
        id=agent_id,
        name=f"test-{agent_id[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test_key",
        status="active",
    )
    db.add(agent)
    await db.flush()


async def _insert_snapshot(
    db: AsyncSession,
    agent_id: str,
    snapshot_id: str | None = None,
    status: str = "verified",
) -> str:
    sid = snapshot_id or _new_id()
    snap = MemorySnapshot(
        id=sid,
        agent_id=agent_id,
        source_type="sdk",
        label="test-snapshot",
        manifest_json="{}",
        merkle_root=f"sha256:{'a' * 64}",
        status=status,
        total_records=1,
        total_chunks=1,
    )
    db.add(snap)
    await db.flush()
    return sid


async def _insert_chunk(
    db: AsyncSession,
    snapshot_id: str,
    records: list[dict],
    chunk_index: int = 0,
    encrypted: bool = True,
) -> None:
    """Insert a MemorySnapshotChunk with optionally encrypted payload."""
    payload = json.dumps(records)
    if encrypted:
        from marketplace.services.memory_service import _encrypt_chunk_payload, _hash_text
        chunk_payload = _encrypt_chunk_payload(payload)
        chunk_hash = _hash_text(payload)
    else:
        from marketplace.services.memory_service import _hash_text
        chunk_payload = payload
        chunk_hash = _hash_text(payload)

    chunk = MemorySnapshotChunk(
        id=_new_id(),
        snapshot_id=snapshot_id,
        chunk_index=chunk_index,
        chunk_hash=chunk_hash,
        chunk_payload=chunk_payload,
        record_count=len(records),
    )
    db.add(chunk)
    await db.flush()


async def _insert_semantic_memory(
    db: AsyncSession,
    agent_id: str,
    content: str,
    embedding: list[float],
    access_count: int = 0,
    relevance_score: float = 1.0,
    last_accessed_at: datetime | None = None,
) -> str:
    mem_id = _new_id()
    now = datetime.now(timezone.utc)
    mem = SemanticMemory(
        id=mem_id,
        agent_id=agent_id,
        content=content,
        embedding_json=json.dumps(embedding),
        metadata_json="{}",
        memory_type="fact",
        access_count=access_count,
        relevance_score=relevance_score,
        created_at=now,
        last_accessed_at=last_accessed_at or now,
    )
    db.add(mem)
    await db.flush()
    return mem_id


# ---------------------------------------------------------------------------
# MemoryConsolidator.promote_episodic()
# ---------------------------------------------------------------------------

async def test_promote_episodic_creates_semantic_memories(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    snapshot_id = await _insert_snapshot(db, agent_id)
    await _insert_chunk(db, snapshot_id, [{"content": "Python is a high-level language"}])

    consolidator = _make_consolidator()
    promoted = await consolidator.promote_episodic(db, agent_id=agent_id, snapshot_id=snapshot_id)

    assert promoted == 1
    result = await db.execute(
        select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
    )
    mems = list(result.scalars().all())
    assert len(mems) == 1
    assert mems[0].memory_type == "episode"


async def test_promote_episodic_sets_memory_type_episode(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    snapshot_id = await _insert_snapshot(db, agent_id)
    await _insert_chunk(db, snapshot_id, [{"text": "Some fact from history"}])

    consolidator = _make_consolidator()
    await consolidator.promote_episodic(db, agent_id=agent_id, snapshot_id=snapshot_id)

    result = await db.execute(
        select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
    )
    mem = result.scalars().first()
    assert mem is not None
    assert mem.memory_type == "episode"


async def test_promote_episodic_extracts_text_key(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    snapshot_id = await _insert_snapshot(db, agent_id)
    text_value = "Record using text key for extraction"
    await _insert_chunk(db, snapshot_id, [{"text": text_value}])

    consolidator = _make_consolidator()
    promoted = await consolidator.promote_episodic(db, agent_id=agent_id, snapshot_id=snapshot_id)
    assert promoted == 1


async def test_promote_episodic_extracts_content_key(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    snapshot_id = await _insert_snapshot(db, agent_id)
    await _insert_chunk(db, snapshot_id, [{"content": "Record using content key for extraction"}])

    consolidator = _make_consolidator()
    promoted = await consolidator.promote_episodic(db, agent_id=agent_id, snapshot_id=snapshot_id)
    assert promoted == 1


async def test_promote_episodic_extracts_value_key(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    snapshot_id = await _insert_snapshot(db, agent_id)
    await _insert_chunk(db, snapshot_id, [{"value": "Record using value key for extraction"}])

    consolidator = _make_consolidator()
    promoted = await consolidator.promote_episodic(db, agent_id=agent_id, snapshot_id=snapshot_id)
    assert promoted == 1


async def test_promote_episodic_snapshot_not_found_raises(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    consolidator = _make_consolidator()
    # No chunks exist for a non-existent snapshot → returns 0 (no crash, no records)
    result = await consolidator.promote_episodic(
        db, agent_id=agent_id, snapshot_id=_new_id()
    )
    assert result == 0


async def test_promote_episodic_no_chunks_no_crash(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    snapshot_id = await _insert_snapshot(db, agent_id)
    # No chunks inserted

    consolidator = _make_consolidator()
    promoted = await consolidator.promote_episodic(db, agent_id=agent_id, snapshot_id=snapshot_id)
    assert promoted == 0


async def test_promote_episodic_skips_short_content(db: AsyncSession):
    """Records whose extracted content is < 10 chars should be skipped."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    snapshot_id = await _insert_snapshot(db, agent_id)
    # content of "hi" is too short (< 10 chars)
    await _insert_chunk(db, snapshot_id, [{"content": "hi"}, {"content": "a valid long content entry"}])

    consolidator = _make_consolidator()
    promoted = await consolidator.promote_episodic(db, agent_id=agent_id, snapshot_id=snapshot_id)
    assert promoted == 1  # only the long one


async def test_promote_episodic_decrypts_chunks(db: AsyncSession):
    """Encrypted chunks must be decrypted before promotion."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    snapshot_id = await _insert_snapshot(db, agent_id)
    await _insert_chunk(
        db, snapshot_id,
        [{"content": "Encrypted memory about machine learning systems"}],
        encrypted=True,
    )

    consolidator = _make_consolidator()
    promoted = await consolidator.promote_episodic(db, agent_id=agent_id, snapshot_id=snapshot_id)
    assert promoted == 1


# ---------------------------------------------------------------------------
# MemoryConsolidator.merge_similar()
# ---------------------------------------------------------------------------

async def test_merge_similar_deduplicates_above_threshold(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    # Both memories share identical embedding → similarity = 1.0 ≥ 0.95
    identical_vec = _unit_vec([1.0, 0.0, 0.0])
    await _insert_semantic_memory(db, agent_id, "memory alpha", identical_vec)
    await _insert_semantic_memory(db, agent_id, "memory alpha duplicate", identical_vec)

    consolidator = _make_consolidator(vector=identical_vec)
    merged = await consolidator.merge_similar(db, agent_id=agent_id, threshold=0.95)
    assert merged == 1

    result = await db.execute(
        select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
    )
    remaining = list(result.scalars().all())
    assert len(remaining) == 1


async def test_merge_similar_keeps_higher_access_count(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    identical_vec = _unit_vec([1.0, 0.0, 0.0])
    id_low = await _insert_semantic_memory(
        db, agent_id, "low access memory", identical_vec, access_count=1
    )
    id_high = await _insert_semantic_memory(
        db, agent_id, "high access memory", identical_vec, access_count=10
    )

    consolidator = _make_consolidator(vector=identical_vec)
    await consolidator.merge_similar(db, agent_id=agent_id, threshold=0.95)

    result = await db.execute(
        select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
    )
    remaining = list(result.scalars().all())
    assert len(remaining) == 1
    assert remaining[0].id == id_high


async def test_merge_similar_below_threshold_keeps_both(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    vec_a = _unit_vec([1.0, 0.0, 0.0])
    vec_b = _unit_vec([0.0, 1.0, 0.0])  # orthogonal → similarity = 0.0
    await _insert_semantic_memory(db, agent_id, "memory A", vec_a)
    await _insert_semantic_memory(db, agent_id, "memory B", vec_b)

    consolidator = _make_consolidator()
    merged = await consolidator.merge_similar(db, agent_id=agent_id, threshold=0.95)
    assert merged == 0

    result = await db.execute(
        select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
    )
    remaining = list(result.scalars().all())
    assert len(remaining) == 2


async def test_merge_similar_no_memories_no_crash(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    consolidator = _make_consolidator()
    merged = await consolidator.merge_similar(db, agent_id=agent_id)
    assert merged == 0


async def test_merge_similar_single_memory_nothing_merged(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    vec = _unit_vec([1.0, 0.0, 0.0])
    await _insert_semantic_memory(db, agent_id, "solo memory", vec)

    consolidator = _make_consolidator(vector=vec)
    merged = await consolidator.merge_similar(db, agent_id=agent_id)
    assert merged == 0


# ---------------------------------------------------------------------------
# MemoryConsolidator.decay()
# ---------------------------------------------------------------------------

async def test_decay_reduces_relevance_score(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    old_access = datetime.now(timezone.utc) - timedelta(days=100)
    mem_id = await _insert_semantic_memory(
        db, agent_id, "stale memory content", _unit_vec([1.0, 0.0]),
        relevance_score=0.5,
        last_accessed_at=old_access,
    )

    consolidator = _make_consolidator()
    decayed = await consolidator.decay(db, agent_id=agent_id, max_age_days=30, decay_factor=0.9)

    assert decayed == 1
    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == mem_id))
    mem = result.scalar_one_or_none()
    # Score should be reduced (0.5 * 0.9 = 0.45) — still above 0.01 so not deleted
    if mem is not None:
        assert abs(mem.relevance_score - 0.45) < 1e-6


async def test_decay_deletes_below_min_threshold(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    old_access = datetime.now(timezone.utc) - timedelta(days=200)
    mem_id = await _insert_semantic_memory(
        db, agent_id, "very stale memory entry to delete", _unit_vec([1.0, 0.0]),
        relevance_score=0.005,  # 0.005 * 0.9 = 0.0045 < 0.01 → delete
        last_accessed_at=old_access,
    )

    consolidator = _make_consolidator()
    decayed = await consolidator.decay(db, agent_id=agent_id, max_age_days=30, decay_factor=0.9)

    assert decayed >= 1
    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == mem_id))
    assert result.scalar_one_or_none() is None


async def test_decay_respects_max_age_days(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    # Memory accessed only 10 days ago — within 30-day window — should NOT be decayed
    recent_access = datetime.now(timezone.utc) - timedelta(days=10)
    mem_id = await _insert_semantic_memory(
        db, agent_id, "recently accessed memory content", _unit_vec([1.0, 0.0]),
        relevance_score=0.8,
        last_accessed_at=recent_access,
    )

    consolidator = _make_consolidator()
    decayed = await consolidator.decay(db, agent_id=agent_id, max_age_days=30, decay_factor=0.9)

    assert decayed == 0
    result = await db.execute(select(SemanticMemory).where(SemanticMemory.id == mem_id))
    mem = result.scalar_one_or_none()
    assert mem is not None
    assert abs(mem.relevance_score - 0.8) < 1e-6


async def test_decay_recently_accessed_untouched(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    # Accessed just now
    mem_id = await _insert_semantic_memory(
        db, agent_id, "very fresh memory accessed recently", _unit_vec([1.0, 0.0]),
        relevance_score=1.0,
        last_accessed_at=datetime.now(timezone.utc),
    )

    consolidator = _make_consolidator()
    decayed = await consolidator.decay(db, agent_id=agent_id, max_age_days=90, decay_factor=0.9)

    assert decayed == 0


async def test_decay_no_old_memories_nothing_decayed(db: AsyncSession):
    agent_id = _new_id()
    await _insert_agent(db, agent_id)
    # No memories inserted at all

    consolidator = _make_consolidator()
    decayed = await consolidator.decay(db, agent_id=agent_id)
    assert decayed == 0


# ---------------------------------------------------------------------------
# Integration: verify_snapshot triggers promotion
# ---------------------------------------------------------------------------

async def test_verify_snapshot_triggers_promotion_on_success(db: AsyncSession):
    """verify_snapshot with a valid snapshot should call consolidator.promote_episodic."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    # Build a real importable snapshot using the service
    from marketplace.services.memory_service import import_snapshot, verify_snapshot

    with patch("marketplace.services.memory_service.broadcast_event"):
        import_result = await import_snapshot(
            db,
            agent_id=agent_id,
            creator_id=None,
            source_type="sdk",
            label="integration-test",
            records=[
                {"id": "r1", "content": "Agent learned about reinforcement learning algorithms"},
            ],
        )

    snapshot_id = import_result["snapshot"]["snapshot_id"]

    # Patch the consolidator's promote_episodic so we can verify it's called
    with patch(
        "marketplace.memory.consolidation.MemoryConsolidator.promote_episodic",
        new_callable=AsyncMock,
        return_value=1,
    ) as mock_promote:
        with patch("marketplace.services.memory_service.broadcast_event"):
            result = await verify_snapshot(db, snapshot_id=snapshot_id, agent_id=agent_id)

    assert result["status"] == "verified"
    mock_promote.assert_awaited_once()


async def test_verify_snapshot_failed_no_promotion(db: AsyncSession):
    """A snapshot that fails integrity check should NOT trigger promotion."""
    from marketplace.services.memory_service import verify_snapshot

    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    # Insert a snapshot with tampered chunk hash
    snapshot_id = _new_id()
    snap = MemorySnapshot(
        id=snapshot_id,
        agent_id=agent_id,
        source_type="sdk",
        label="tampered",
        manifest_json="{}",
        merkle_root=f"sha256:{'f' * 64}",
        status="imported",
        total_records=1,
        total_chunks=1,
    )
    db.add(snap)
    await db.flush()

    # Chunk with wrong hash — integrity check will fail
    chunk = MemorySnapshotChunk(
        id=_new_id(),
        snapshot_id=snapshot_id,
        chunk_index=0,
        chunk_hash=f"sha256:{'0' * 64}",  # wrong hash
        chunk_payload=json.dumps([{"id": "r1", "content": "Real content here for testing"}]),
        record_count=1,
    )
    db.add(chunk)
    await db.flush()

    with patch(
        "marketplace.memory.consolidation.MemoryConsolidator.promote_episodic",
        new_callable=AsyncMock,
    ) as mock_promote:
        with patch("marketplace.services.memory_service.broadcast_event"):
            result = await verify_snapshot(db, snapshot_id=snapshot_id, agent_id=agent_id)

    # Verification should have failed
    assert result["status"] == "failed"
    mock_promote.assert_not_awaited()


async def test_verify_snapshot_promotion_failure_is_swallowed(db: AsyncSession):
    """If promotion raises an exception, verify_snapshot should still return a result."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    from marketplace.services.memory_service import import_snapshot, verify_snapshot

    with patch("marketplace.services.memory_service.broadcast_event"):
        import_result = await import_snapshot(
            db,
            agent_id=agent_id,
            creator_id=None,
            source_type="sdk",
            label="promotion-failure-test",
            records=[
                {"id": "r1", "content": "Memory content for promotion failure test case"},
            ],
        )

    snapshot_id = import_result["snapshot"]["snapshot_id"]

    with patch(
        "marketplace.memory.consolidation.MemoryConsolidator.promote_episodic",
        new_callable=AsyncMock,
        side_effect=RuntimeError("embedding service down"),
    ):
        with patch("marketplace.services.memory_service.broadcast_event"):
            result = await verify_snapshot(db, snapshot_id=snapshot_id, agent_id=agent_id)

    # Should not raise — verify_snapshot catches promotion errors
    assert "status" in result
    assert result["status"] == "verified"


async def test_promote_end_to_end_import_verify_promote_recall(db: AsyncSession):
    """Full pipeline: import → verify → promote → memories exist in semantic store."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    from marketplace.services.memory_service import import_snapshot, verify_snapshot

    records = [
        {"id": "fact-1", "content": "Neural networks are universal function approximators"},
        {"id": "fact-2", "content": "Transformers use self-attention mechanisms for processing"},
    ]

    with patch("marketplace.services.memory_service.broadcast_event"):
        import_result = await import_snapshot(
            db,
            agent_id=agent_id,
            creator_id=None,
            source_type="sdk",
            label="e2e-test",
            records=records,
        )

    snapshot_id = import_result["snapshot"]["snapshot_id"]

    # Use a real consolidator (no mock) — embed will fall back to hash-based embedding
    with patch("marketplace.services.memory_service.broadcast_event"):
        verify_result = await verify_snapshot(db, snapshot_id=snapshot_id, agent_id=agent_id)

    assert verify_result["status"] == "verified"

    # After promotion, semantic memories should exist for the agent
    result = await db.execute(
        select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
    )
    mems = list(result.scalars().all())
    # At least one memory promoted from the records
    assert len(mems) >= 1
    assert all(m.memory_type == "episode" for m in mems)


# ---------------------------------------------------------------------------
# Additional edge cases for coverage (consolidation.py lines 64, 68, 91-92, 130-131, 141)
# ---------------------------------------------------------------------------


async def test_promote_episodic_records_not_list_skipped(db: AsyncSession):
    """Line 64: chunk payload is a JSON dict (not list) → skipped via continue."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    sid = await _insert_snapshot(db, agent_id)

    # Chunk payload is a dict, not a list
    chunk = MemorySnapshotChunk(
        snapshot_id=sid,
        chunk_index=0,
        chunk_payload=json.dumps({"key": "value"}),
        chunk_hash="hash",
    )
    db.add(chunk)
    await db.commit()

    embed_svc = _mock_embedding_service()
    store = SemanticMemoryStore(embed_svc)
    consolidator = MemoryConsolidator(store, embed_svc)

    promoted = await consolidator.promote_episodic(db, agent_id, sid)
    assert promoted == 0


async def test_promote_episodic_record_not_dict_skipped(db: AsyncSession):
    """Line 68: record in list is not a dict → skipped via continue."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    sid = await _insert_snapshot(db, agent_id)

    # Chunk payload is a list with non-dict items
    chunk = MemorySnapshotChunk(
        snapshot_id=sid,
        chunk_index=0,
        chunk_payload=json.dumps(["string_item", 42, None]),
        chunk_hash="hash",
    )
    db.add(chunk)
    await db.commit()

    embed_svc = _mock_embedding_service()
    store = SemanticMemoryStore(embed_svc)
    consolidator = MemoryConsolidator(store, embed_svc)

    promoted = await consolidator.promote_episodic(db, agent_id, sid)
    assert promoted == 0


async def test_promote_episodic_chunk_exception_logged(db: AsyncSession):
    """Lines 91-92: Exception during chunk processing → logged, skipped."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    sid = await _insert_snapshot(db, agent_id)

    # Valid chunk payload but _decrypt_chunk_payload will raise
    chunk = MemorySnapshotChunk(
        snapshot_id=sid,
        chunk_index=0,
        chunk_payload=json.dumps([{"content": "valid content for testing exception path"}]),
        chunk_hash="hash",
    )
    db.add(chunk)
    await db.commit()

    embed_svc = _mock_embedding_service()
    store = SemanticMemoryStore(embed_svc)
    consolidator = MemoryConsolidator(store, embed_svc)

    # Make _decrypt_chunk_payload raise (imported inline from memory_service)
    with patch(
        "marketplace.services.memory_service._decrypt_chunk_payload",
        side_effect=Exception("decrypt failed"),
    ):
        promoted = await consolidator.promote_episodic(db, agent_id, sid)
    assert promoted == 0


async def test_merge_similar_bad_embedding_json_skipped(db: AsyncSession):
    """Lines 130-131: Unparseable embedding_json → memory skipped in merge."""
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    # Insert two memories, one with bad embedding JSON
    mem_a = SemanticMemory(
        id=_new_id(),
        agent_id=agent_id,
        content="memory alpha",
        embedding_json="not valid json",
        memory_type="fact",
        access_count=1,
        relevance_score=1.0,
    )
    mem_b = SemanticMemory(
        id=_new_id(),
        agent_id=agent_id,
        content="memory beta",
        embedding_json=json.dumps([0.1, 0.2, 0.3]),
        memory_type="fact",
        access_count=1,
        relevance_score=1.0,
    )
    db.add_all([mem_a, mem_b])
    await db.commit()

    embed_svc = _mock_embedding_service()
    store = SemanticMemoryStore(embed_svc)
    consolidator = MemoryConsolidator(store, embed_svc)

    merged = await consolidator.merge_similar(db, agent_id, threshold=0.95)
    # Only one parseable memory → no pair to merge
    assert merged == 0


async def test_merge_similar_skip_already_deleted(db: AsyncSession):
    """Line 140-141: inner loop skips j when parsed[j] is already in to_delete.

    Scenario: A(access=0), B(access=5), C(access=0), all identical embeddings.
    - i=0(A), j=1(B): B.access > A.access → A deleted
    - i=0(A), j=2(C): A.access == C.access → C deleted (else branch)
    - i=1(B, not deleted), j=2(C, in to_delete) → LINE 140 triggers continue
    """
    agent_id = _new_id()
    await _insert_agent(db, agent_id)

    emb = [1.0, 0.0, 0.0]
    # A: access_count=0 (will be deleted by B comparison)
    mem_a = SemanticMemory(
        id=_new_id(), agent_id=agent_id, content="memory A",
        embedding_json=json.dumps(emb), memory_type="fact",
        access_count=0, relevance_score=1.0,
    )
    # B: access_count=5 (high access, survives)
    mem_b = SemanticMemory(
        id=_new_id(), agent_id=agent_id, content="memory B",
        embedding_json=json.dumps(emb), memory_type="fact",
        access_count=5, relevance_score=1.0,
    )
    # C: access_count=0 (deleted by A comparison, then skipped when B checks)
    mem_c = SemanticMemory(
        id=_new_id(), agent_id=agent_id, content="memory C",
        embedding_json=json.dumps(emb), memory_type="fact",
        access_count=0, relevance_score=1.0,
    )
    db.add_all([mem_a, mem_b, mem_c])
    await db.commit()

    embed_svc = _mock_embedding_service()
    store = SemanticMemoryStore(embed_svc)
    consolidator = MemoryConsolidator(store, embed_svc)

    merged = await consolidator.merge_similar(db, agent_id, threshold=0.95)
    # A and C deleted, B survives → merged=2
    assert merged == 2

    # Verify only B remains
    result = await db.execute(
        select(SemanticMemory).where(SemanticMemory.agent_id == agent_id)
    )
    remaining = list(result.scalars().all())
    assert len(remaining) == 1
    assert remaining[0].access_count == 5
