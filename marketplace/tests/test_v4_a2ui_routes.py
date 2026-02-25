"""Tests for marketplace/api/v4_a2ui.py -- A2UI stream tokens, sessions, and health.

All endpoints hit the real FastAPI app via the ``client`` fixture.
Sessions are created directly via the session manager for testing.
No external services to mock.
"""

from __future__ import annotations

from marketplace.a2ui.session_manager import A2UISession, a2ui_session_manager
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_test_session(agent_id: str, user_id: str | None = None) -> A2UISession:
    """Create a session directly in the session manager for testing."""
    return a2ui_session_manager.create_session(
        agent_id=agent_id,
        user_id=user_id,
        capabilities={"render": True},
    )


# ---------------------------------------------------------------------------
# POST /api/v4/stream-token -- generate stream token
# ---------------------------------------------------------------------------

async def test_generate_stream_token_success(client, make_agent):
    """POST /stream-token returns a valid stream token for the agent."""
    agent, token = await make_agent()

    resp = await client.post(
        "/api/v4/stream-token",
        headers=_agent_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent.id
    assert "stream_token" in body
    assert body["stream_token"]
    assert "expires_in_seconds" in body
    assert body["expires_in_seconds"] > 0
    assert "expires_at" in body
    assert body["ws_url"] == "/ws/v4/a2ui"


async def test_generate_stream_token_no_auth(client):
    """POST /stream-token without auth returns 401."""
    resp = await client.post("/api/v4/stream-token")
    assert resp.status_code == 401


async def test_generate_stream_token_invalid_auth(client):
    """POST /stream-token with invalid token returns 401."""
    resp = await client.post(
        "/api/v4/stream-token",
        headers={"Authorization": "Bearer invalid-token-garbage"},
    )
    assert resp.status_code == 401


async def test_generate_stream_token_creator_token_rejected(client, make_creator):
    """POST /stream-token rejects creator tokens (agent-only)."""
    _, creator_token = await make_creator()

    resp = await client.post(
        "/api/v4/stream-token",
        headers=_agent_auth(creator_token),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v4/sessions -- list sessions for authenticated agent
# ---------------------------------------------------------------------------

async def test_list_sessions_empty(client, make_agent):
    """GET /sessions returns empty list when no sessions exist."""
    agent, token = await make_agent()

    resp = await client.get(
        "/api/v4/sessions",
        headers=_agent_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sessions"] == []
    assert body["total"] == 0


async def test_list_sessions_with_data(client, make_agent):
    """GET /sessions returns sessions for the authenticated agent."""
    agent, token = await make_agent()

    session = _create_test_session(agent.id, user_id="user-1")

    try:
        resp = await client.get(
            "/api/v4/sessions",
            headers=_agent_auth(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["sessions"]) == 1
        assert body["sessions"][0]["session_id"] == session.session_id
        assert body["sessions"][0]["agent_id"] == agent.id
        assert body["sessions"][0]["user_id"] == "user-1"
    finally:
        a2ui_session_manager.close_session(session.session_id)


async def test_list_sessions_filters_by_agent(client, make_agent):
    """An agent should only see its own sessions, not other agents' sessions."""
    agent_a, token_a = await make_agent(name="agent-a")
    agent_b, _ = await make_agent(name="agent-b")

    session_a = _create_test_session(agent_a.id)
    session_b = _create_test_session(agent_b.id)

    try:
        resp = await client.get(
            "/api/v4/sessions",
            headers=_agent_auth(token_a),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        session_ids = [s["session_id"] for s in body["sessions"]]
        assert session_a.session_id in session_ids
        assert session_b.session_id not in session_ids
    finally:
        a2ui_session_manager.close_session(session_a.session_id)
        a2ui_session_manager.close_session(session_b.session_id)


async def test_list_sessions_no_auth(client):
    """GET /sessions without auth returns 401."""
    resp = await client.get("/api/v4/sessions")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v4/sessions/{session_id} -- get single session
# ---------------------------------------------------------------------------

async def test_get_session_success(client, make_agent):
    """GET /sessions/{id} returns session details for the owning agent."""
    agent, token = await make_agent()
    session = _create_test_session(agent.id, user_id="user-2")

    try:
        resp = await client.get(
            f"/api/v4/sessions/{session.session_id}",
            headers=_agent_auth(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == session.session_id
        assert body["agent_id"] == agent.id
        assert body["user_id"] == "user-2"
        assert "capabilities" in body
        assert "active_components" in body
        assert "pending_inputs" in body
        assert "request_count" in body
    finally:
        a2ui_session_manager.close_session(session.session_id)


async def test_get_session_not_found(client, make_agent):
    """GET /sessions/{id} returns 404 for nonexistent session."""
    agent, token = await make_agent()

    resp = await client.get(
        f"/api/v4/sessions/{_new_id()}",
        headers=_agent_auth(token),
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_get_session_wrong_agent(client, make_agent):
    """Agent A cannot view Agent B's session."""
    agent_a, token_a = await make_agent(name="agent-a")
    agent_b, _ = await make_agent(name="agent-b")
    session_b = _create_test_session(agent_b.id)

    try:
        resp = await client.get(
            f"/api/v4/sessions/{session_b.session_id}",
            headers=_agent_auth(token_a),
        )
        assert resp.status_code == 403
        assert "not authorised" in resp.json()["detail"].lower()
    finally:
        a2ui_session_manager.close_session(session_b.session_id)


async def test_get_session_no_auth(client):
    """GET /sessions/{id} without auth returns 401."""
    resp = await client.get(f"/api/v4/sessions/{_new_id()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/v4/sessions/{session_id} -- close session
# ---------------------------------------------------------------------------

async def test_close_session_success(client, make_agent):
    """DELETE /sessions/{id} closes the session."""
    agent, token = await make_agent()
    session = _create_test_session(agent.id)

    resp = await client.delete(
        f"/api/v4/sessions/{session.session_id}",
        headers=_agent_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "closed"
    assert body["session_id"] == session.session_id

    assert a2ui_session_manager.get_session(session.session_id) is None


async def test_close_session_not_found(client, make_agent):
    """DELETE /sessions/{id} for nonexistent session returns 404."""
    agent, token = await make_agent()

    resp = await client.delete(
        f"/api/v4/sessions/{_new_id()}",
        headers=_agent_auth(token),
    )
    assert resp.status_code == 404


async def test_close_session_wrong_agent(client, make_agent):
    """Agent A cannot close Agent B's session."""
    agent_a, token_a = await make_agent(name="agent-a")
    agent_b, _ = await make_agent(name="agent-b")
    session_b = _create_test_session(agent_b.id)

    try:
        resp = await client.delete(
            f"/api/v4/sessions/{session_b.session_id}",
            headers=_agent_auth(token_a),
        )
        assert resp.status_code == 403
        assert "not authorised" in resp.json()["detail"].lower()
    finally:
        a2ui_session_manager.close_session(session_b.session_id)


async def test_close_session_no_auth(client):
    """DELETE /sessions/{id} without auth returns 401."""
    resp = await client.delete(f"/api/v4/sessions/{_new_id()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v4/health -- A2UI health check (public)
# ---------------------------------------------------------------------------

async def test_a2ui_health_check(client):
    """GET /health returns protocol health information."""
    resp = await client.get("/api/v4/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["protocol"] == "a2ui"
    assert body["version"] == "2026-02-20"
    assert body["ws_path"] == "/ws/v4/a2ui"
    assert "active_sessions" in body
    assert isinstance(body["active_sessions"], int)


async def test_a2ui_health_no_auth_required(client):
    """Health check should be accessible without authentication."""
    resp = await client.get("/api/v4/health")
    assert resp.status_code == 200
