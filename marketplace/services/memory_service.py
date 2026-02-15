"""Managed memory snapshot import and verification for agent trust."""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.async_tasks import fire_and_forget
from marketplace.models.agent_trust import (
    MemorySnapshot,
    MemorySnapshotChunk,
    MemoryVerificationRun,
)
from marketplace.services.agent_trust_service import update_memory_stage

_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "system prompt",
    "<script",
    "javascript:",
    "rm -rf",
    "drop table",
    "prompt injection",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _json_load(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def _chunk(records: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    chunk_size = max(1, size)
    return [records[i : i + chunk_size] for i in range(0, len(records), chunk_size)]


def _merkle_root(chunk_hashes: list[str]) -> str:
    if not chunk_hashes:
        return _hash_text("")
    level = [value.replace("sha256:", "") for value in chunk_hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level: list[str] = []
        for idx in range(0, len(level), 2):
            merged = level[idx] + level[idx + 1]
            next_level.append(hashlib.sha256(merged.encode("utf-8")).hexdigest())
        level = next_level
    return f"sha256:{level[0]}"


def _canonicalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each memory record must be an object")
        packed = json.dumps(record, sort_keys=True, separators=(",", ":"))
        normalized.append(json.loads(packed))
    return normalized


def _record_has_reference(record: dict[str, Any]) -> bool:
    if any(key in record for key in ("id", "record_id", "source_id", "source")):
        return True
    return any(key in record for key in ("text", "content", "value"))


def _contains_injection(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in _INJECTION_PATTERNS)


def _serialize_snapshot(snapshot: MemorySnapshot) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot.id,
        "agent_id": snapshot.agent_id,
        "source_type": snapshot.source_type,
        "label": snapshot.label,
        "manifest": _json_load(snapshot.manifest_json, {}),
        "merkle_root": snapshot.merkle_root,
        "status": snapshot.status,
        "total_records": int(snapshot.total_records or 0),
        "total_chunks": int(snapshot.total_chunks or 0),
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "verified_at": snapshot.verified_at.isoformat() if snapshot.verified_at else None,
    }


async def import_snapshot(
    db: AsyncSession,
    *,
    agent_id: str,
    creator_id: str | None,
    source_type: str,
    label: str,
    records: list[dict[str, Any]],
    chunk_size: int = 100,
    source_metadata: dict[str, Any] | None = None,
    encrypted_blob_ref: str | None = None,
) -> dict[str, Any]:
    normalized_records = _canonicalize_records(records)
    if not normalized_records:
        raise ValueError("At least one memory record is required")

    chunks = _chunk(normalized_records, chunk_size)
    chunk_hashes: list[str] = []
    snapshot_id = str(uuid.uuid4())
    source_meta = source_metadata or {}
    for records_chunk in chunks:
        payload = json.dumps(records_chunk, sort_keys=True, separators=(",", ":"))
        chunk_hashes.append(_hash_text(payload))

    merkle_root = _merkle_root(chunk_hashes)
    manifest = {
        "schema_version": "memory-snapshot-v1",
        "record_count": len(normalized_records),
        "chunk_count": len(chunks),
        "chunk_size": max(1, chunk_size),
        "source_metadata": source_meta,
    }

    snapshot = MemorySnapshot(
        id=snapshot_id,
        agent_id=agent_id,
        creator_id=creator_id,
        source_type=source_type,
        label=label,
        manifest_json=json.dumps(manifest),
        merkle_root=merkle_root,
        encrypted_blob_ref=encrypted_blob_ref,
        status="imported",
        total_records=len(normalized_records),
        total_chunks=len(chunks),
    )
    db.add(snapshot)
    await db.flush()

    for idx, records_chunk in enumerate(chunks):
        payload = json.dumps(records_chunk, sort_keys=True, separators=(",", ":"))
        db.add(
            MemorySnapshotChunk(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                chunk_index=idx,
                chunk_hash=_hash_text(payload),
                chunk_payload=payload,
                record_count=len(records_chunk),
            )
        )

    initial_memory_score = 8 if source_meta else 5
    trust_profile = await update_memory_stage(
        db,
        agent_id=agent_id,
        snapshot_id=snapshot_id,
        status="imported",
        score=initial_memory_score,
        provenance={
            "merkle_root": merkle_root,
            "source_type": source_type,
            "verified": False,
        },
    )

    from marketplace.main import broadcast_event

    fire_and_forget(
        broadcast_event(
            "memory.snapshot.imported",
            {
                "agent_id": agent_id,
                "snapshot_id": snapshot_id,
                "merkle_root": merkle_root,
                "record_count": len(normalized_records),
            },
        ),
        task_name="broadcast_memory_snapshot_imported",
    )

    return {
        "snapshot": _serialize_snapshot(snapshot),
        "chunk_hashes": chunk_hashes,
        "trust_profile": trust_profile,
    }


async def verify_snapshot(
    db: AsyncSession,
    *,
    snapshot_id: str,
    agent_id: str,
    sample_size: int = 5,
) -> dict[str, Any]:
    snapshot_result = await db.execute(
        select(MemorySnapshot).where(MemorySnapshot.id == snapshot_id)
    )
    snapshot = snapshot_result.scalar_one_or_none()
    if snapshot is None:
        raise ValueError(f"Snapshot {snapshot_id} not found")
    if snapshot.agent_id != agent_id:
        raise PermissionError("Cannot verify a snapshot owned by another agent")

    chunks_result = await db.execute(
        select(MemorySnapshotChunk)
        .where(MemorySnapshotChunk.snapshot_id == snapshot_id)
        .order_by(MemorySnapshotChunk.chunk_index.asc())
    )
    chunks = list(chunks_result.scalars().all())
    if not chunks:
        raise ValueError("Snapshot has no chunks")

    stored_hashes: list[str] = []
    parsed_records: list[dict[str, Any]] = []
    integrity_ok = True
    mismatch_reason = ""
    for chunk in chunks:
        expected_hash = _hash_text(chunk.chunk_payload or "")
        if expected_hash != chunk.chunk_hash:
            integrity_ok = False
            mismatch_reason = f"chunk_hash_mismatch:{chunk.chunk_index}"
            break
        stored_hashes.append(chunk.chunk_hash)
        parsed = _json_load(chunk.chunk_payload, [])
        if isinstance(parsed, list):
            for record in parsed:
                if isinstance(record, dict):
                    parsed_records.append(record)

    if integrity_ok:
        computed_root = _merkle_root(stored_hashes)
        if computed_root != snapshot.merkle_root:
            integrity_ok = False
            mismatch_reason = "merkle_root_mismatch"
    else:
        computed_root = _merkle_root(stored_hashes)

    risk_text = json.dumps(parsed_records, sort_keys=True, default=str)
    safety_ok = not _contains_injection(risk_text)

    sampled_entries: list[dict[str, Any]] = []
    if parsed_records:
        sample_n = max(1, min(sample_size, len(parsed_records)))
        rand = random.Random(snapshot_id)
        sampled_indexes = sorted(rand.sample(range(len(parsed_records)), sample_n))
        sampled_entries = [parsed_records[idx] for idx in sampled_indexes]
        replay_ok = all(_record_has_reference(entry) for entry in sampled_entries)
    else:
        sample_n = 0
        replay_ok = False

    status = "verified"
    score = 20
    failure_reason = ""
    if not integrity_ok:
        status = "failed"
        score = 0
        failure_reason = mismatch_reason or "integrity_failed"
    elif not safety_ok:
        status = "quarantined"
        score = 0
        failure_reason = "safety_scan_failed"
    elif not replay_ok:
        status = "failed"
        score = 10
        failure_reason = "replay_sampling_failed"

    snapshot.status = status
    snapshot.verified_at = _utcnow() if status == "verified" else None

    run = MemoryVerificationRun(
        id=str(uuid.uuid4()),
        snapshot_id=snapshot_id,
        agent_id=agent_id,
        status=status,
        score=score,
        sampled_entries_json=json.dumps(sampled_entries),
        evidence_json=json.dumps(
            {
                "integrity_ok": integrity_ok,
                "safety_ok": safety_ok,
                "replay_ok": replay_ok,
                "computed_root": computed_root,
                "stored_root": snapshot.merkle_root,
                "failure_reason": failure_reason,
            }
        ),
    )
    db.add(run)
    await db.flush()

    trust_profile = await update_memory_stage(
        db,
        agent_id=agent_id,
        snapshot_id=snapshot_id,
        status=status,
        score=score,
        provenance={
            "merkle_root": snapshot.merkle_root,
            "verification_run_id": run.id,
            "sample_size": sample_n,
            "failure_reason": failure_reason,
            "verified": status == "verified",
        },
    )

    from marketplace.main import broadcast_event

    fire_and_forget(
        broadcast_event(
            "memory.snapshot.verified",
            {
                "agent_id": agent_id,
                "snapshot_id": snapshot_id,
                "status": status,
                "score": score,
                "verification_run_id": run.id,
            },
        ),
        task_name="broadcast_memory_snapshot_verified",
    )

    return {
        "snapshot": _serialize_snapshot(snapshot),
        "verification_run_id": run.id,
        "status": status,
        "score": score,
        "sampled_entries": sampled_entries,
        "trust_profile": trust_profile,
    }


async def get_snapshot(
    db: AsyncSession,
    *,
    snapshot_id: str,
    agent_id: str,
) -> dict[str, Any]:
    result = await db.execute(
        select(MemorySnapshot).where(
            MemorySnapshot.id == snapshot_id,
            MemorySnapshot.agent_id == agent_id,
        )
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise ValueError("Snapshot not found")
    return _serialize_snapshot(snapshot)
