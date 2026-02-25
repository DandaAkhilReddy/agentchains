"""Tests for marketplace/api/v2_dashboards.py — role-specific dashboard endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _creator_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_MOCK_AGENT_DASHBOARD = {
    "agent_id": "agent-1",
    "money_received_usd": 100.0,
    "money_spent_usd": 20.0,
    "info_used_count": 15,
    "other_agents_served_count": 3,
    "data_served_bytes": 1024,
    "savings": {
        "money_saved_for_others_usd": 50.0,
        "fresh_cost_estimate_total_usd": 75.0,
    },
    "trust_status": "verified_secure_data",
    "trust_tier": "T2",
    "trust_score": 80,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

_MOCK_CREATOR_DASHBOARD = {
    "creator_id": "creator-1",
    "creator_balance_usd": 250.0,
    "creator_total_earned_usd": 500.0,
    "total_agent_earnings_usd": 300.0,
    "total_agent_spent_usd": 50.0,
    "creator_gross_revenue_usd": 400.0,
    "creator_platform_fees_usd": 40.0,
    "creator_net_revenue_usd": 360.0,
    "creator_pending_payout_usd": 100.0,
    "total_agents": 5,
    "active_agents": 3,
    "money_saved_for_others_usd": 200.0,
    "data_served_bytes": 2048,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

_MOCK_PUBLIC_DASHBOARD = {
    "agent_id": "agent-1",
    "agent_name": "TestAgent",
    "money_received_usd": 100.0,
    "info_used_count": 15,
    "other_agents_served_count": 3,
    "data_served_bytes": 1024,
    "money_saved_for_others_usd": 50.0,
    "trust_status": "verified_secure_data",
    "trust_tier": "T2",
    "trust_score": 80,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


# ---------------------------------------------------------------------------
# GET /api/v2/dashboards/agent/me — authenticated agent dashboard
# ---------------------------------------------------------------------------

async def test_dashboard_agent_me_success(client, make_agent):
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_dashboards.dashboard_service.get_agent_dashboard",
        new_callable=AsyncMock,
        return_value={**_MOCK_AGENT_DASHBOARD, "agent_id": agent.id},
    ):
        resp = await client.get(
            "/api/v2/dashboards/agent/me",
            headers=_agent_auth(token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent.id
    assert "money_received_usd" in body
    assert "savings" in body


async def test_dashboard_agent_me_no_auth(client):
    resp = await client.get("/api/v2/dashboards/agent/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/dashboards/creator/me — authenticated creator dashboard
# ---------------------------------------------------------------------------

async def test_dashboard_creator_me_success(client, make_creator):
    creator, token = await make_creator()

    with patch(
        "marketplace.api.v2_dashboards.dashboard_service.get_creator_dashboard_v2",
        new_callable=AsyncMock,
        return_value={**_MOCK_CREATOR_DASHBOARD, "creator_id": creator.id},
    ):
        resp = await client.get(
            "/api/v2/dashboards/creator/me",
            headers=_creator_auth(token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["creator_id"] == creator.id
    assert "creator_balance_usd" in body
    assert "total_agents" in body


async def test_dashboard_creator_me_no_auth(client):
    resp = await client.get("/api/v2/dashboards/creator/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v2/dashboards/agent/{agent_id}/public — public agent dashboard
# ---------------------------------------------------------------------------

async def test_dashboard_agent_public_success(client, make_agent):
    agent, _ = await make_agent()

    with patch(
        "marketplace.api.v2_dashboards.dashboard_service.get_agent_public_dashboard",
        new_callable=AsyncMock,
        return_value={**_MOCK_PUBLIC_DASHBOARD, "agent_id": agent.id},
    ):
        resp = await client.get(f"/api/v2/dashboards/agent/{agent.id}/public")
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent.id
    assert "agent_name" in body
    assert "trust_status" in body


async def test_dashboard_agent_public_not_found(client):
    with patch(
        "marketplace.api.v2_dashboards.dashboard_service.get_agent_public_dashboard",
        new_callable=AsyncMock,
        side_effect=ValueError("Agent not found"),
    ):
        resp = await client.get(f"/api/v2/dashboards/agent/{_new_id()}/public")
    assert resp.status_code == 404


async def test_dashboard_agent_public_no_auth_required(client, make_agent):
    """Public dashboard should not require authentication."""
    agent, _ = await make_agent()

    with patch(
        "marketplace.api.v2_dashboards.dashboard_service.get_agent_public_dashboard",
        new_callable=AsyncMock,
        return_value={**_MOCK_PUBLIC_DASHBOARD, "agent_id": agent.id},
    ):
        resp = await client.get(f"/api/v2/dashboards/agent/{agent.id}/public")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v2/dashboards/agent/{agent_id} — private agent dashboard
# ---------------------------------------------------------------------------

async def test_dashboard_agent_private_same_agent(client, make_agent):
    """Agent can view its own private dashboard."""
    agent, token = await make_agent()

    with patch(
        "marketplace.api.v2_dashboards.dashboard_service.get_agent_dashboard",
        new_callable=AsyncMock,
        return_value={**_MOCK_AGENT_DASHBOARD, "agent_id": agent.id},
    ):
        resp = await client.get(
            f"/api/v2/dashboards/agent/{agent.id}",
            headers=_agent_auth(token),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent.id


async def test_dashboard_agent_private_no_auth(client, make_agent):
    """No auth header should return 401."""
    agent, _ = await make_agent()

    resp = await client.get(f"/api/v2/dashboards/agent/{agent.id}")
    assert resp.status_code == 401


async def test_dashboard_agent_private_different_agent_no_creator(client, make_agent):
    """Agent A cannot view Agent B's private dashboard without creator auth."""
    agent_a, token_a = await make_agent(name="agent-a")
    agent_b, _ = await make_agent(name="agent-b")

    resp = await client.get(
        f"/api/v2/dashboards/agent/{agent_b.id}",
        headers=_agent_auth(token_a),
    )
    # Agent A is not agent B, and agent A's token is not a creator token
    assert resp.status_code == 401


async def test_dashboard_agent_private_creator_owns_agent(client, make_agent, make_creator, db):
    """Creator who owns the agent should be able to view the dashboard."""
    from marketplace.models.agent import RegisteredAgent

    creator, creator_token = await make_creator()
    agent, _ = await make_agent()

    # Assign creator_id to the agent
    result = await db.execute(
        __import__("sqlalchemy").select(RegisteredAgent).where(RegisteredAgent.id == agent.id)
    )
    agent_row = result.scalar_one()
    agent_row.creator_id = creator.id
    await db.commit()

    with patch(
        "marketplace.api.v2_dashboards.dashboard_service.get_agent_dashboard",
        new_callable=AsyncMock,
        return_value={**_MOCK_AGENT_DASHBOARD, "agent_id": agent.id},
    ):
        resp = await client.get(
            f"/api/v2/dashboards/agent/{agent.id}",
            headers=_creator_auth(creator_token),
        )
    assert resp.status_code == 200


async def test_dashboard_agent_private_admin_creator(client, make_agent, make_creator):
    """Admin creator can view any agent's private dashboard."""
    creator, creator_token = await make_creator()
    agent, _ = await make_agent()

    with patch(
        "marketplace.api.v2_dashboards._admin_creator_ids",
        return_value={creator.id},
    ), patch(
        "marketplace.api.v2_dashboards.dashboard_service.get_agent_dashboard",
        new_callable=AsyncMock,
        return_value={**_MOCK_AGENT_DASHBOARD, "agent_id": agent.id},
    ):
        resp = await client.get(
            f"/api/v2/dashboards/agent/{agent.id}",
            headers=_creator_auth(creator_token),
        )
    assert resp.status_code == 200


async def test_dashboard_agent_private_creator_not_owner(client, make_agent, make_creator):
    """Creator who does not own the agent and is not admin gets 403."""
    creator, creator_token = await make_creator()
    agent, _ = await make_agent()

    with patch(
        "marketplace.api.v2_dashboards._admin_creator_ids",
        return_value=set(),
    ):
        resp = await client.get(
            f"/api/v2/dashboards/agent/{agent.id}",
            headers=_creator_auth(creator_token),
        )
    assert resp.status_code == 403


async def test_dashboard_agent_private_agent_not_found(client, make_creator):
    """Accessing dashboard for a non-existent agent returns 404."""
    creator, creator_token = await make_creator()

    resp = await client.get(
        f"/api/v2/dashboards/agent/{_new_id()}",
        headers=_creator_auth(creator_token),
    )
    assert resp.status_code == 404
