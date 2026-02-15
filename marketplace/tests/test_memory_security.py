"""Security tests for encrypted memory snapshots and retention redaction."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from marketplace.models.agent_trust import MemorySnapshotChunk, MemoryVerificationRun
from marketplace.services.memory_service import redact_old_memory_verification_evidence
from marketplace.tests.conftest import TestSession


def _creator_payload() -> dict:
    suffix = uuid.uuid4().hex[:8]
    return {
        "email": f"memory-sec-{suffix}@example.com",
        "password": "StrongPass123!",
        "display_name": f"MemorySec {suffix}",
        "country": "US",
    }


@pytest.mark.asyncio
async def test_memory_snapshot_chunk_payload_is_encrypted_at_rest(client):
    creator = await client.post("/api/v1/creators/register", json=_creator_payload())
    assert creator.status_code == 201
    creator_token = creator.json()["token"]

    onboard = await client.post(
        "/api/v2/agents/onboard",
        headers={"Authorization": f"Bearer {creator_token}"},
        json={
            "name": "memory-sec-agent",
            "description": "security test agent",
            "agent_type": "both",
            "public_key": "ssh-rsa AAAA_memory_security_key_placeholder_long",
            "capabilities": ["retrieval"],
            "a2a_endpoint": "https://agent.example.com",
        },
    )
    assert onboard.status_code == 201
    token = onboard.json()["agent_jwt_token"]

    imported = await client.post(
        "/api/v2/memory/snapshots/import",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_type": "sdk",
            "label": "encrypted-check",
            "chunk_size": 2,
            "records": [
                {"id": "r1", "content": "Alpha memory"},
                {"id": "r2", "content": "Beta memory"},
            ],
        },
    )
    assert imported.status_code == 201
    snapshot_id = imported.json()["snapshot"]["snapshot_id"]

    async with TestSession() as db:
        result = await db.execute(
            select(MemorySnapshotChunk).where(MemorySnapshotChunk.snapshot_id == snapshot_id)
        )
        chunk = result.scalars().first()
        assert chunk is not None
        assert (chunk.chunk_payload or "").startswith("enc:v1:")
        assert "Alpha memory" not in (chunk.chunk_payload or "")
        assert "Beta memory" not in (chunk.chunk_payload or "")


@pytest.mark.asyncio
async def test_old_memory_verification_evidence_is_redacted(client):
    creator = await client.post("/api/v1/creators/register", json=_creator_payload())
    assert creator.status_code == 201
    creator_token = creator.json()["token"]

    onboard = await client.post(
        "/api/v2/agents/onboard",
        headers={"Authorization": f"Bearer {creator_token}"},
        json={
            "name": "memory-redact-agent",
            "description": "security test agent",
            "agent_type": "both",
            "public_key": "ssh-rsa AAAA_memory_redaction_key_placeholder_long",
            "capabilities": ["retrieval"],
            "a2a_endpoint": "https://agent.example.com",
        },
    )
    assert onboard.status_code == 201
    token = onboard.json()["agent_jwt_token"]

    imported = await client.post(
        "/api/v2/memory/snapshots/import",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_type": "sdk",
            "label": "retention-check",
            "chunk_size": 1,
            "records": [
                {"id": "r1", "content": "Alpha memory", "source": "firecrawl"},
            ],
        },
    )
    assert imported.status_code == 201
    snapshot_id = imported.json()["snapshot"]["snapshot_id"]

    verified = await client.post(
        f"/api/v2/memory/snapshots/{snapshot_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
        json={"sample_size": 1},
    )
    assert verified.status_code == 200

    async with TestSession() as db:
        result = await db.execute(
            select(MemoryVerificationRun).where(MemoryVerificationRun.snapshot_id == snapshot_id)
        )
        run = result.scalars().first()
        assert run is not None
        run.created_at = datetime.now(timezone.utc) - timedelta(days=45)
        run.sampled_entries_json = '[{"id":"r1"}]'
        run.evidence_json = '{"detailed":true}'
        await db.commit()

        redacted = await redact_old_memory_verification_evidence(db, retention_days=30)
        assert redacted >= 1

        result = await db.execute(
            select(MemoryVerificationRun).where(MemoryVerificationRun.snapshot_id == snapshot_id)
        )
        run = result.scalars().first()
        assert run is not None
        assert run.sampled_entries_json == "[]"
        assert run.evidence_json == '{"redacted":true}'
