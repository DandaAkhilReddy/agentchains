"""Tests for marketplace/api/v2_memory.py -- managed memory vault endpoints.

The memory service involves encryption and complex DB operations, so we mock
``memory_service`` at the service boundary.  Route-level auth and validation
run for real.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_MOCK_SNAPSHOT = {
    "snapshot_id": "snap-1",
    "agent_id": "agent-1",
    "source_type": "sdk",
    "label": "default",
    "manifest": {},
    "merkle_root": "sha256:abc123",
    "status": "imported",
    "total_records": 3,
    "total_chunks": 1,
    "created_at": "2026-01-01T00:00:00",
    "verified_at": None,
}

_MOCK_IMPORT_RESULT = {
    "snapshot": _MOCK_SNAPSHOT,
    "chunk_hashes": ["sha256:abc123"],
    "trust_profile": {"trust_status": "unverified", "trust_tier": "T0", "trust_score": 5},
}

_MOCK_VERIFY_RESULT = {
    "snapshot": {**_MOCK_SNAPSHOT, "status": "verified"},
    "verification_run_id": "run-1",
    "status": "verified",
    "score": 20,
    "sampled_entries": [{"id": "rec-1", "text": "hello"}],
    "trust_profile": {"trust_status": "verified", "trust_tier": "T1", "trust_score": 20},
}

MEMORY_PREFIX = "/api/v2/memory"


# ---------------------------------------------------------------------------
# POST /api/v2/memory/snapshots/import -- import memory snapshot
# ---------------------------------------------------------------------------

async def test_import_memory_snapshot_success(client, make_agent):
    """POST /snapshots/import creates a new snapshot."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_memory.memory_service.import_snapshot",
        new_callable=AsyncMock,
        return_value={**_MOCK_IMPORT_RESULT, "snapshot": {**_MOCK_SNAPSHOT, "agent_id": agent.id}},
    ):
        resp = await client.post(
            f"{MEMORY_PREFIX}/snapshots/import",
            headers=_agent_auth(token),
            json={
                "source_type": "sdk",
                "label": "test-import",
                "records": [{"id": "r1", "text": "hello world"}],
                "chunk_size": 100,
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "snapshot" in body
    assert "chunk_hashes" in body
    assert "trust_profile" in body


async def test_import_memory_snapshot_empty_records(client, make_agent):
    """POST /snapshots/import with empty records returns 400."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_memory.memory_service.import_snapshot",
        new_callable=AsyncMock,
        side_effect=ValueError("At least one memory record is required"),
    ):
        resp = await client.post(
            f"{MEMORY_PREFIX}/snapshots/import",
            headers=_agent_auth(token),
            json={
                "source_type": "sdk",
                "label": "empty",
                "records": [],
            },
        )
    assert resp.status_code == 400
    assert "record" in resp.json()["detail"].lower()


async def test_import_memory_snapshot_no_auth(client):
    """POST /snapshots/import without auth returns 401."""
    resp = await client.post(
        f"{MEMORY_PREFIX}/snapshots/import",
        json={
            "source_type": "sdk",
            "label": "test",
            "records": [{"id": "r1"}],
        },
    )
    assert resp.status_code == 401


async def test_import_memory_snapshot_with_metadata(client, make_agent):
    """POST /snapshots/import passes source_metadata and encrypted_blob_ref."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_memory.memory_service.import_snapshot",
        new_callable=AsyncMock,
        return_value=_MOCK_IMPORT_RESULT,
    ) as mock_import:
        resp = await client.post(
            f"{MEMORY_PREFIX}/snapshots/import",
            headers=_agent_auth(token),
            json={
                "source_type": "langchain",
                "label": "chat-history",
                "records": [{"id": "r1", "content": "test"}],
                "source_metadata": {"model": "gpt-4", "chain": "rag"},
                "encrypted_blob_ref": "blob:ref:123",
            },
        )
    assert resp.status_code == 201
    mock_import.assert_called_once()
    call_kwargs = mock_import.call_args.kwargs
    assert call_kwargs["source_type"] == "langchain"
    assert call_kwargs["source_metadata"] == {"model": "gpt-4", "chain": "rag"}
    assert call_kwargs["encrypted_blob_ref"] == "blob:ref:123"


async def test_import_memory_snapshot_validation_chunk_size(client, make_agent):
    """POST /snapshots/import rejects chunk_size outside [1, 1000]."""
    agent, token = await make_agent()

    # chunk_size too large (> 1000)
    resp = await client.post(
        f"{MEMORY_PREFIX}/snapshots/import",
        headers=_agent_auth(token),
        json={
            "source_type": "sdk",
            "label": "test",
            "records": [{"id": "r1"}],
            "chunk_size": 5000,
        },
    )
    assert resp.status_code == 422

    # chunk_size too small (< 1)
    resp = await client.post(
        f"{MEMORY_PREFIX}/snapshots/import",
        headers=_agent_auth(token),
        json={
            "source_type": "sdk",
            "label": "test",
            "records": [{"id": "r1"}],
            "chunk_size": 0,
        },
    )
    assert resp.status_code == 422


async def test_import_memory_snapshot_source_type_length(client, make_agent):
    """POST /snapshots/import rejects source_type shorter than min_length=2."""
    agent, token = await make_agent()

    resp = await client.post(
        f"{MEMORY_PREFIX}/snapshots/import",
        headers=_agent_auth(token),
        json={
            "source_type": "x",  # min_length=2
            "label": "test",
            "records": [{"id": "r1"}],
        },
    )
    assert resp.status_code == 422


async def test_import_memory_snapshot_creator_token_rejected(client, make_creator):
    """POST /snapshots/import rejects creator tokens (agent-only)."""
    _, creator_token = await make_creator()

    resp = await client.post(
        f"{MEMORY_PREFIX}/snapshots/import",
        headers=_agent_auth(creator_token),
        json={
            "source_type": "sdk",
            "label": "test",
            "records": [{"id": "r1"}],
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v2/memory/snapshots/{snapshot_id}/verify -- verify snapshot
# ---------------------------------------------------------------------------

async def test_verify_memory_snapshot_success(client, make_agent):
    """POST /snapshots/{id}/verify runs verification and returns result."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_memory.memory_service.verify_snapshot",
        new_callable=AsyncMock,
        return_value=_MOCK_VERIFY_RESULT,
    ):
        resp = await client.post(
            f"{MEMORY_PREFIX}/snapshots/{_new_id()}/verify",
            headers=_agent_auth(token),
            json={"sample_size": 5},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "verified"
    assert body["score"] == 20


async def test_verify_memory_snapshot_not_found(client, make_agent):
    """POST /snapshots/{id}/verify returns 404 for unknown snapshot."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_memory.memory_service.verify_snapshot",
        new_callable=AsyncMock,
        side_effect=ValueError("Snapshot snap-xxx not found"),
    ):
        resp = await client.post(
            f"{MEMORY_PREFIX}/snapshots/{_new_id()}/verify",
            headers=_agent_auth(token),
            json={"sample_size": 5},
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_verify_memory_snapshot_permission_denied(client, make_agent):
    """POST /snapshots/{id}/verify returns 403 for wrong agent."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_memory.memory_service.verify_snapshot",
        new_callable=AsyncMock,
        side_effect=PermissionError("Cannot verify a snapshot owned by another agent"),
    ):
        resp = await client.post(
            f"{MEMORY_PREFIX}/snapshots/{_new_id()}/verify",
            headers=_agent_auth(token),
            json={"sample_size": 5},
        )
    assert resp.status_code == 403
    assert "another agent" in resp.json()["detail"].lower()


async def test_verify_memory_snapshot_no_auth(client):
    """POST /snapshots/{id}/verify without auth returns 401."""
    resp = await client.post(
        f"{MEMORY_PREFIX}/snapshots/{_new_id()}/verify",
        json={"sample_size": 5},
    )
    assert resp.status_code == 401


async def test_verify_memory_snapshot_sample_size_validation(client, make_agent):
    """POST /snapshots/{id}/verify rejects sample_size outside [1, 100]."""
    agent, token = await make_agent()

    # sample_size too large (> 100)
    resp = await client.post(
        f"{MEMORY_PREFIX}/snapshots/{_new_id()}/verify",
        headers=_agent_auth(token),
        json={"sample_size": 200},
    )
    assert resp.status_code == 422

    # sample_size too small (< 1)
    resp = await client.post(
        f"{MEMORY_PREFIX}/snapshots/{_new_id()}/verify",
        headers=_agent_auth(token),
        json={"sample_size": 0},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v2/memory/snapshots/{snapshot_id} -- get snapshot details
# ---------------------------------------------------------------------------

async def test_get_memory_snapshot_success(client, make_agent):
    """GET /snapshots/{id} returns snapshot details."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_memory.memory_service.get_snapshot",
        new_callable=AsyncMock,
        return_value={**_MOCK_SNAPSHOT, "agent_id": agent.id},
    ):
        resp = await client.get(
            f"{MEMORY_PREFIX}/snapshots/{_new_id()}",
            headers=_agent_auth(token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent.id
    assert body["source_type"] == "sdk"
    assert body["status"] == "imported"


async def test_get_memory_snapshot_not_found(client, make_agent):
    """GET /snapshots/{id} returns 404 for unknown snapshot."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_memory.memory_service.get_snapshot",
        new_callable=AsyncMock,
        side_effect=ValueError("Snapshot not found"),
    ):
        resp = await client.get(
            f"{MEMORY_PREFIX}/snapshots/{_new_id()}",
            headers=_agent_auth(token),
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_get_memory_snapshot_no_auth(client):
    """GET /snapshots/{id} without auth returns 401."""
    resp = await client.get(f"{MEMORY_PREFIX}/snapshots/{_new_id()}")
    assert resp.status_code == 401


async def test_import_memory_snapshot_direct_function(db, make_agent):
    """Call import_memory_snapshot_v2 directly to cover lines 42-57."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from marketplace.api.v2_memory import import_memory_snapshot_v2, SnapshotImportRequest
    agent, _ = await make_agent()

    req = SnapshotImportRequest(
        source_type="sdk",
        label="direct-test",
        records=[{"id": "r1", "text": "hello"}],
        chunk_size=100,
        source_metadata={"key": "value"},
        encrypted_blob_ref="blob:ref:xyz",
    )

    mock_result = {
        "snapshot": {
            "snapshot_id": "snap-1",
            "agent_id": agent.id,
            "source_type": "sdk",
            "label": "direct-test",
            "manifest": {},
            "merkle_root": "sha256:abc",
            "status": "imported",
            "total_records": 1,
            "total_chunks": 1,
            "created_at": None,
            "verified_at": None,
        },
        "chunk_hashes": ["sha256:abc"],
        "trust_profile": {},
    }

    with patch(
        "marketplace.api.v2_memory.memory_service.import_snapshot",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mock_import:
        # Simulate the function with mocked dependencies
        with patch("marketplace.api.v2_memory.get_current_agent_id", return_value=agent.id):
            result = await import_memory_snapshot_v2(req, db, agent.id)
            assert result == mock_result
            call_kwargs = mock_import.call_args.kwargs
            assert call_kwargs["source_type"] == "sdk"
            assert call_kwargs["label"] == "direct-test"
            assert call_kwargs["source_metadata"] == {"key": "value"}
            assert call_kwargs["encrypted_blob_ref"] == "blob:ref:xyz"
