"""Tests for marketplace/api/v2_compliance.py — GDPR compliance endpoints."""

from __future__ import annotations

import marketplace.api.v2_compliance as _compliance_mod
from marketplace.tests.conftest import TestSession, _new_id


COMPLIANCE_PREFIX = "/api/v2/compliance"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_compliance_stores() -> None:
    """Reset the module-level in-memory stores between tests."""
    _compliance_mod._export_jobs.clear()
    _compliance_mod._deletion_requests.clear()
    _compliance_mod._consent_records.clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Data export endpoints
# ===========================================================================


async def test_data_export_requires_auth(client):
    """POST /data-export without auth returns 401."""
    _clear_compliance_stores()
    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-export",
        json={"format": "json"},
    )
    assert resp.status_code == 401


async def test_data_export_happy_path(client, make_agent):
    """POST /data-export creates an export job and returns completed status."""
    _clear_compliance_stores()
    agent, token = await make_agent()

    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-export",
        headers=_auth(token),
        json={"format": "json"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["agent_id"] == agent.id
    assert body["format"] == "json"
    assert body["job_id"]
    assert body["download_url"] is not None


async def test_data_export_csv_format(client, make_agent):
    """POST /data-export with format=csv is accepted."""
    _clear_compliance_stores()
    agent, token = await make_agent()

    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-export",
        headers=_auth(token),
        json={"format": "csv", "include_transactions": False},
    )
    assert resp.status_code == 200
    assert resp.json()["format"] == "csv"


async def test_data_export_cannot_export_other_agent(client, make_agent):
    """POST /data-export for another agent returns 403."""
    _clear_compliance_stores()
    agent, token = await make_agent()

    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-export",
        headers=_auth(token),
        json={"agent_id": "some-other-agent-id"},
    )
    assert resp.status_code == 403
    assert "your own account" in resp.json()["detail"]


async def test_data_export_status_happy_path(client, make_agent):
    """GET /data-export/{job_id} returns the job status for the owner."""
    _clear_compliance_stores()
    agent, token = await make_agent()

    # Create export
    create_resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-export",
        headers=_auth(token),
        json={},
    )
    job_id = create_resp.json()["job_id"]

    # Query status
    resp = await client.get(
        f"{COMPLIANCE_PREFIX}/data-export/{job_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["status"] == "completed"


async def test_data_export_status_not_found(client, make_agent):
    """GET /data-export/{job_id} returns 404 for unknown job."""
    _clear_compliance_stores()
    _, token = await make_agent()

    resp = await client.get(
        f"{COMPLIANCE_PREFIX}/data-export/nonexistent-job",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_data_export_status_wrong_agent(client, make_agent):
    """GET /data-export/{job_id} returns 403 when queried by another agent."""
    _clear_compliance_stores()
    agent_a, token_a = await make_agent(name="agent-a")
    _, token_b = await make_agent(name="agent-b")

    # Agent A creates an export
    create_resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-export",
        headers=_auth(token_a),
        json={},
    )
    job_id = create_resp.json()["job_id"]

    # Agent B tries to read it
    resp = await client.get(
        f"{COMPLIANCE_PREFIX}/data-export/{job_id}",
        headers=_auth(token_b),
    )
    assert resp.status_code == 403


# ===========================================================================
# Data deletion endpoints
# ===========================================================================


async def test_data_deletion_requires_auth(client):
    """POST /data-deletion without auth returns 401."""
    _clear_compliance_stores()
    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-deletion",
        json={"reason": "user_request"},
    )
    assert resp.status_code == 401


async def test_data_deletion_happy_path(client, make_agent):
    """POST /data-deletion creates a pending deletion request."""
    _clear_compliance_stores()
    agent, token = await make_agent()

    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-deletion",
        headers=_auth(token),
        json={"reason": "user_request", "soft_delete": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["agent_id"] == agent.id
    assert body["reason"] == "user_request"
    assert body["soft_delete"] is True
    assert body["request_id"]


async def test_data_deletion_hard_delete(client, make_agent):
    """POST /data-deletion with soft_delete=false is accepted."""
    _clear_compliance_stores()
    agent, token = await make_agent()

    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-deletion",
        headers=_auth(token),
        json={"soft_delete": False},
    )
    assert resp.status_code == 200
    assert resp.json()["soft_delete"] is False


async def test_data_deletion_cannot_delete_other_agent(client, make_agent):
    """POST /data-deletion for another agent returns 403."""
    _clear_compliance_stores()
    _, token = await make_agent()

    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-deletion",
        headers=_auth(token),
        json={"agent_id": "someone-else"},
    )
    assert resp.status_code == 403
    assert "your own account" in resp.json()["detail"]


async def test_data_deletion_status_happy_path(client, make_agent):
    """GET /data-deletion/{request_id} returns the request status for the owner."""
    _clear_compliance_stores()
    agent, token = await make_agent()

    create_resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-deletion",
        headers=_auth(token),
        json={},
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.get(
        f"{COMPLIANCE_PREFIX}/data-deletion/{request_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["request_id"] == request_id


async def test_data_deletion_status_not_found(client, make_agent):
    """GET /data-deletion/{request_id} returns 404 for unknown request."""
    _clear_compliance_stores()
    _, token = await make_agent()

    resp = await client.get(
        f"{COMPLIANCE_PREFIX}/data-deletion/no-such-request",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_data_deletion_status_wrong_agent(client, make_agent):
    """GET /data-deletion/{request_id} returns 403 for non-owner."""
    _clear_compliance_stores()
    _, token_a = await make_agent(name="del-a")
    _, token_b = await make_agent(name="del-b")

    create_resp = await client.post(
        f"{COMPLIANCE_PREFIX}/data-deletion",
        headers=_auth(token_a),
        json={},
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.get(
        f"{COMPLIANCE_PREFIX}/data-deletion/{request_id}",
        headers=_auth(token_b),
    )
    assert resp.status_code == 403


# ===========================================================================
# Consent management endpoints
# ===========================================================================


async def test_consent_get_empty(client, make_agent):
    """GET /consent returns empty list when no records exist."""
    _clear_compliance_stores()
    _, token = await make_agent()

    resp = await client.get(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_consent_record_and_retrieve(client, make_agent):
    """POST /consent records consent, GET /consent retrieves it."""
    _clear_compliance_stores()
    agent, token = await make_agent()

    # Record consent
    resp = await client.post(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token),
        json={
            "consent_type": "data_processing",
            "granted": True,
            "purpose": "marketplace data processing",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["consent_type"] == "data_processing"
    assert body["granted"] is True
    assert body["agent_id"] == agent.id

    # Retrieve
    get_resp = await client.get(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token),
    )
    assert get_resp.status_code == 200
    records = get_resp.json()
    assert len(records) == 1
    assert records[0]["consent_type"] == "data_processing"


async def test_consent_upsert_same_type(client, make_agent):
    """POST /consent for the same consent_type updates existing record."""
    _clear_compliance_stores()
    _, token = await make_agent()

    # Grant consent
    resp1 = await client.post(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token),
        json={"consent_type": "marketing", "granted": True, "purpose": "emails"},
    )
    assert resp1.status_code == 200
    original_id = resp1.json()["id"]

    # Revoke same consent type
    resp2 = await client.post(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token),
        json={"consent_type": "marketing", "granted": False, "purpose": "opt-out"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == original_id  # same ID preserved
    assert resp2.json()["granted"] is False

    # Only one record exists
    get_resp = await client.get(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token),
    )
    assert len(get_resp.json()) == 1


async def test_consent_multiple_types(client, make_agent):
    """Multiple distinct consent_type records coexist."""
    _clear_compliance_stores()
    _, token = await make_agent()

    for ctype in ("data_processing", "marketing", "analytics"):
        resp = await client.post(
            f"{COMPLIANCE_PREFIX}/consent",
            headers=_auth(token),
            json={"consent_type": ctype, "granted": True},
        )
        assert resp.status_code == 200

    get_resp = await client.get(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token),
    )
    assert len(get_resp.json()) == 3


async def test_consent_requires_auth(client):
    """Consent endpoints require authentication."""
    _clear_compliance_stores()
    resp_get = await client.get(f"{COMPLIANCE_PREFIX}/consent")
    assert resp_get.status_code == 401

    resp_post = await client.post(
        f"{COMPLIANCE_PREFIX}/consent",
        json={"consent_type": "data_processing", "granted": True},
    )
    assert resp_post.status_code == 401


async def test_consent_isolated_between_agents(client, make_agent):
    """Consent records are isolated per agent."""
    _clear_compliance_stores()
    _, token_a = await make_agent(name="consent-a")
    _, token_b = await make_agent(name="consent-b")

    # Agent A records consent
    await client.post(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token_a),
        json={"consent_type": "marketing", "granted": True},
    )

    # Agent B should see empty
    resp_b = await client.get(
        f"{COMPLIANCE_PREFIX}/consent",
        headers=_auth(token_b),
    )
    assert resp_b.json() == []
