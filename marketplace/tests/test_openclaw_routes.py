"""Integration tests for OpenClaw webhook API routes.

Tests hit the FastAPI endpoints through httpx AsyncClient.
"""

from unittest.mock import AsyncMock, patch

import pytest

from marketplace.core.auth import create_access_token
from marketplace.models.agent import RegisteredAgent
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_agent() -> tuple[str, str]:
    """Create an agent and return (agent_id, jwt)."""
    async with TestSession() as db:
        agent_id = _new_id()
        agent = RegisteredAgent(
            id=agent_id, name=f"oc-agent-{agent_id[:8]}",
            agent_type="both", public_key="ssh-rsa AAAA", status="active",
        )
        db.add(agent)
        await db.commit()
        jwt = create_access_token(agent_id, agent.name)
        return agent_id, jwt


# ---------------------------------------------------------------------------
# POST /integrations/openclaw/register-webhook
# ---------------------------------------------------------------------------

async def test_register_webhook_201(client):
    agent_id, jwt = await _setup_agent()

    resp = await client.post(
        "/api/v1/integrations/openclaw/register-webhook",
        json={
            "gateway_url": "https://example.com/hooks/agent",
            "bearer_token": "my-secret-token",
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == agent_id
    assert data["gateway_url"] == "https://example.com/hooks/agent"
    assert data["status"] == "active"
    assert "demand_spike" in data["event_types"]


async def test_register_webhook_custom_events(client):
    _, jwt = await _setup_agent()

    resp = await client.post(
        "/api/v1/integrations/openclaw/register-webhook",
        json={
            "gateway_url": "https://example.com/hooks/agent",
            "bearer_token": "tok",
            "event_types": ["listing_created"],
            "filters": {"categories": ["web_search"]},
        },
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_types"] == ["listing_created"]
    assert data["filters"]["categories"] == ["web_search"]


async def test_register_webhook_unauthenticated(client):
    resp = await client.post(
        "/api/v1/integrations/openclaw/register-webhook",
        json={
            "gateway_url": "https://example.com/hooks/agent",
            "bearer_token": "tok",
        },
    )
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /integrations/openclaw/webhooks
# ---------------------------------------------------------------------------

async def test_list_webhooks_empty(client):
    _, jwt = await _setup_agent()

    resp = await client.get(
        "/api/v1/integrations/openclaw/webhooks",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["webhooks"] == []
    assert data["count"] == 0


async def test_list_webhooks_after_register(client):
    _, jwt = await _setup_agent()

    # Register a webhook first
    await client.post(
        "/api/v1/integrations/openclaw/register-webhook",
        json={"gateway_url": "https://gw.com/hooks", "bearer_token": "tok"},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    resp = await client.get(
        "/api/v1/integrations/openclaw/webhooks",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


# ---------------------------------------------------------------------------
# DELETE /integrations/openclaw/webhooks/{id}
# ---------------------------------------------------------------------------

async def test_delete_webhook_success(client):
    _, jwt = await _setup_agent()

    # Register
    reg_resp = await client.post(
        "/api/v1/integrations/openclaw/register-webhook",
        json={"gateway_url": "https://gw.com/hooks", "bearer_token": "tok"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    webhook_id = reg_resp.json()["id"]

    # Delete
    del_resp = await client.delete(
        f"/api/v1/integrations/openclaw/webhooks/{webhook_id}",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


async def test_delete_webhook_not_found(client):
    _, jwt = await _setup_agent()

    resp = await client.delete(
        "/api/v1/integrations/openclaw/webhooks/nonexistent-id",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 404


async def test_delete_webhook_wrong_agent(client):
    agent1_id, jwt1 = await _setup_agent()
    _, jwt2 = await _setup_agent()

    # Agent 1 registers webhook
    reg_resp = await client.post(
        "/api/v1/integrations/openclaw/register-webhook",
        json={"gateway_url": "https://gw.com/hooks", "bearer_token": "tok"},
        headers={"Authorization": f"Bearer {jwt1}"},
    )
    webhook_id = reg_resp.json()["id"]

    # Agent 2 tries to delete → 404
    resp = await client.delete(
        f"/api/v1/integrations/openclaw/webhooks/{webhook_id}",
        headers={"Authorization": f"Bearer {jwt2}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /integrations/openclaw/webhooks/{id}/test
# ---------------------------------------------------------------------------

@patch("marketplace.services.openclaw_service.deliver_event", new_callable=AsyncMock)
async def test_test_webhook_endpoint(mock_deliver, client):
    mock_deliver.return_value = True
    _, jwt = await _setup_agent()

    reg_resp = await client.post(
        "/api/v1/integrations/openclaw/register-webhook",
        json={"gateway_url": "https://gw.com/hooks", "bearer_token": "tok"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    webhook_id = reg_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/integrations/openclaw/webhooks/{webhook_id}/test",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# GET /integrations/openclaw/status
# ---------------------------------------------------------------------------

async def test_status_not_connected(client):
    _, jwt = await _setup_agent()

    resp = await client.get(
        "/api/v1/integrations/openclaw/status",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False


async def test_status_connected_after_register(client):
    _, jwt = await _setup_agent()

    await client.post(
        "/api/v1/integrations/openclaw/register-webhook",
        json={"gateway_url": "https://gw.com/hooks", "bearer_token": "tok"},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    resp = await client.get(
        "/api/v1/integrations/openclaw/status",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    assert resp.json()["connected"] is True
    assert resp.json()["active_count"] == 1
