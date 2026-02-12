"""Unit tests for the MCP (Model Context Protocol) layer.

Covers: SessionManager, MCP auth, JSON-RPC message handling, tool/resource definitions.
30 tests total — zero prior coverage in this area.
"""

import time
import uuid
from unittest.mock import patch

import pytest

from marketplace.core.auth import create_access_token
from marketplace.core.exceptions import UnauthorizedError
from marketplace.mcp.auth import validate_mcp_auth
from marketplace.mcp.resources import RESOURCE_DEFINITIONS
from marketplace.mcp.server import (
    MCP_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    _jsonrpc_error,
    _jsonrpc_response,
    handle_message,
)
from marketplace.mcp.session_manager import MCPSession, SessionManager
from marketplace.mcp.tools import TOOL_DEFINITIONS


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_jwt(agent_id: str = None, agent_name: str = "test-agent") -> str:
    """Create a valid JWT for testing."""
    agent_id = agent_id or str(uuid.uuid4())
    return create_access_token(agent_id, agent_name)


def _init_params_caps(token: str) -> dict:
    """Build initialize params with token in capabilities.auth.token."""
    return {"capabilities": {"auth": {"token": token}}}


def _init_params_meta(token: str) -> dict:
    """Build initialize params with token in meta.authorization (Bearer)."""
    return {"meta": {"authorization": f"Bearer {token}"}}


def _init_params_auth(token: str) -> dict:
    """Build initialize params with token in _auth."""
    return {"_auth": token}


# ═══════════════════════════════════════════════════════════════════════════════
# SessionManager tests (11)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionManager:
    """SessionManager lifecycle, rate limiting, and cleanup."""

    def test_create_session_returns_session_with_ids(self):
        """create_session returns MCPSession with session_id and agent_id set."""
        mgr = SessionManager()
        session = mgr.create_session("agent-42")

        assert isinstance(session, MCPSession)
        assert session.session_id is not None
        assert len(session.session_id) == 36  # UUID format
        assert session.agent_id == "agent-42"

    def test_two_sessions_get_different_ids(self):
        """Two calls to create_session produce distinct session IDs."""
        mgr = SessionManager()
        s1 = mgr.create_session("agent-a")
        s2 = mgr.create_session("agent-b")

        assert s1.session_id != s2.session_id

    def test_get_session_valid_id(self):
        """get_session with a valid ID returns the same session object."""
        mgr = SessionManager()
        created = mgr.create_session("agent-x")
        fetched = mgr.get_session(created.session_id)

        assert fetched is not None
        assert fetched.session_id == created.session_id
        assert fetched.agent_id == "agent-x"

    def test_get_session_invalid_id_returns_none(self):
        """get_session with a non-existent ID returns None."""
        mgr = SessionManager()
        assert mgr.get_session("no-such-session") is None

    def test_get_session_expired_returns_none(self):
        """get_session returns None for an expired session (past timeout)."""
        mgr = SessionManager(session_timeout=10)
        session = mgr.create_session("agent-expired")

        # Simulate time far beyond the timeout
        with patch("marketplace.mcp.session_manager.time") as mock_time:
            # creation happened at real time; now pretend monotonic is far in the future
            mock_time.monotonic.return_value = session.last_activity + 20
            result = mgr.get_session(session.session_id)

        assert result is None

    def test_check_rate_limit_within_limit_returns_true(self):
        """Requests within the rate limit return True."""
        mgr = SessionManager(rate_limit_per_minute=5)
        session = mgr.create_session("agent-rl")

        for _ in range(5):
            assert mgr.check_rate_limit(session) is True

    def test_check_rate_limit_exceeded_returns_false(self):
        """The request that exceeds the rate limit returns False."""
        mgr = SessionManager(rate_limit_per_minute=3)
        session = mgr.create_session("agent-rl2")

        for _ in range(3):
            mgr.check_rate_limit(session)

        # 4th request should exceed the limit
        assert mgr.check_rate_limit(session) is False

    def test_rate_limit_window_resets_after_60s(self):
        """After 60 seconds the rate-limit window resets and requests succeed again."""
        mgr = SessionManager(rate_limit_per_minute=2)
        session = mgr.create_session("agent-rl3")

        # Exhaust the limit
        mgr.check_rate_limit(session)
        mgr.check_rate_limit(session)
        assert mgr.check_rate_limit(session) is False

        # Advance window_start so next call sees > 60s elapsed
        session.window_start = session.window_start - 61

        # Now the window should reset and the request should succeed
        assert mgr.check_rate_limit(session) is True

    def test_close_session_makes_unretrievable(self):
        """close_session removes the session so get_session returns None."""
        mgr = SessionManager()
        session = mgr.create_session("agent-close")
        mgr.close_session(session.session_id)

        assert mgr.get_session(session.session_id) is None

    def test_cleanup_expired_removes_old_sessions(self):
        """cleanup_expired removes sessions whose last_activity exceeds timeout."""
        mgr = SessionManager(session_timeout=10)
        old = mgr.create_session("agent-old")
        _fresh = mgr.create_session("agent-fresh")

        # Make old session's last_activity far in the past
        old.last_activity = time.monotonic() - 20

        mgr.cleanup_expired()

        assert mgr.get_session(old.session_id) is None
        # fresh session should still be there (created just now)
        assert mgr.active_count == 1

    def test_active_count_matches_live_sessions(self):
        """active_count reflects the number of non-closed sessions."""
        mgr = SessionManager()
        assert mgr.active_count == 0

        s1 = mgr.create_session("a1")
        s2 = mgr.create_session("a2")
        _s3 = mgr.create_session("a3")
        assert mgr.active_count == 3

        mgr.close_session(s1.session_id)
        assert mgr.active_count == 2

        mgr.close_session(s2.session_id)
        assert mgr.active_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Auth tests (5)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMCPAuth:
    """validate_mcp_auth extracts JWT from three param locations."""

    def test_auth_via_capabilities(self):
        """Token in params.capabilities.auth.token is accepted."""
        agent_id = str(uuid.uuid4())
        token = create_access_token(agent_id, "caps-agent")
        params = _init_params_caps(token)

        result = validate_mcp_auth(params)
        assert result == agent_id

    def test_auth_via_meta_authorization(self):
        """Token in params.meta.authorization (Bearer <jwt>) is accepted."""
        agent_id = str(uuid.uuid4())
        token = create_access_token(agent_id, "meta-agent")
        params = _init_params_meta(token)

        result = validate_mcp_auth(params)
        assert result == agent_id

    def test_auth_via_underscore_auth(self):
        """Token in params._auth is accepted."""
        agent_id = str(uuid.uuid4())
        token = create_access_token(agent_id, "auth-agent")
        params = _init_params_auth(token)

        result = validate_mcp_auth(params)
        assert result == agent_id

    def test_missing_token_raises_unauthorized(self):
        """No token in any location raises UnauthorizedError."""
        with pytest.raises(UnauthorizedError):
            validate_mcp_auth({})

    def test_invalid_token_raises_unauthorized(self):
        """A garbage JWT raises UnauthorizedError."""
        params = {"_auth": "not.a.valid.jwt.token"}
        with pytest.raises(UnauthorizedError):
            validate_mcp_auth(params)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON-RPC handling tests (9)
# ═══════════════════════════════════════════════════════════════════════════════

class TestJSONRPCHandling:
    """handle_message dispatches JSON-RPC methods correctly."""

    @pytest.mark.asyncio
    async def test_initialize_returns_protocol_info(self):
        """initialize method returns protocolVersion, capabilities, serverInfo."""
        token = _make_jwt()
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": _init_params_caps(token),
        }
        resp = await handle_message(body)

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        result = resp["result"]
        assert result["protocolVersion"] == MCP_VERSION
        assert "capabilities" in result
        assert result["serverInfo"]["name"] == SERVER_NAME
        assert result["serverInfo"]["version"] == SERVER_VERSION
        assert "_session_id" in result

    @pytest.mark.asyncio
    async def test_tools_list_returns_definitions(self):
        """tools/list returns the tool definitions array."""
        # First initialize to get a session
        token = _make_jwt()
        init_resp = await handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": _init_params_auth(token),
        })
        sid = init_resp["result"]["_session_id"]

        resp = await handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"_session_id": sid}},
        )

        assert "result" in resp
        tools = resp["result"]["tools"]
        assert isinstance(tools, list)
        assert len(tools) == len(TOOL_DEFINITIONS)

    @pytest.mark.asyncio
    async def test_resources_list_returns_definitions(self):
        """resources/list returns the resource definitions array."""
        token = _make_jwt()
        init_resp = await handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": _init_params_auth(token),
        })
        sid = init_resp["result"]["_session_id"]

        resp = await handle_message(
            {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {"_session_id": sid}},
        )

        assert "result" in resp
        resources = resp["result"]["resources"]
        assert isinstance(resources, list)
        assert len(resources) == len(RESOURCE_DEFINITIONS)

    @pytest.mark.asyncio
    async def test_ping_returns_empty_result(self):
        """ping returns an empty dict result."""
        token = _make_jwt()
        init_resp = await handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": _init_params_auth(token),
        })
        sid = init_resp["result"]["_session_id"]

        resp = await handle_message(
            {"jsonrpc": "2.0", "id": 4, "method": "ping", "params": {"_session_id": sid}},
        )

        assert resp["result"] == {}

    @pytest.mark.asyncio
    async def test_notifications_initialized_returns_ack(self):
        """notifications/initialized returns acknowledged: True."""
        token = _make_jwt()
        init_resp = await handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": _init_params_auth(token),
        })
        sid = init_resp["result"]["_session_id"]

        resp = await handle_message(
            {"jsonrpc": "2.0", "id": 5, "method": "notifications/initialized",
             "params": {"_session_id": sid}},
        )

        assert resp["result"]["acknowledged"] is True

    @pytest.mark.asyncio
    async def test_unknown_method_returns_32601(self):
        """Unknown method returns JSON-RPC error -32601 (Method not found)."""
        token = _make_jwt()
        init_resp = await handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": _init_params_auth(token),
        })
        sid = init_resp["result"]["_session_id"]

        resp = await handle_message(
            {"jsonrpc": "2.0", "id": 6, "method": "bogus/method",
             "params": {"_session_id": sid}},
        )

        assert "error" in resp
        assert resp["error"]["code"] == -32601
        assert "bogus/method" in resp["error"]["message"]

    @pytest.mark.asyncio
    async def test_response_format_has_required_fields(self):
        """A successful response has jsonrpc, id, and result fields."""
        token = _make_jwt()
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 99, "method": "initialize",
            "params": _init_params_auth(token),
        })

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 99
        assert "result" in resp
        assert "error" not in resp

    @pytest.mark.asyncio
    async def test_error_format_has_required_fields(self):
        """An error response has jsonrpc, id, and error with code+message."""
        # Send a request with no session and a non-init method
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 77, "method": "tools/list", "params": {},
        })

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 77
        assert "error" in resp
        assert "result" not in resp
        assert "code" in resp["error"]
        assert "message" in resp["error"]
        assert isinstance(resp["error"]["code"], int)
        assert isinstance(resp["error"]["message"], str)

    @pytest.mark.asyncio
    async def test_non_init_method_without_session_returns_error(self):
        """Calling any non-initialize method without a session returns -32000."""
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 10, "method": "ping", "params": {},
        })

        assert "error" in resp
        assert resp["error"]["code"] == -32000
        assert "session" in resp["error"]["message"].lower() or "initialize" in resp["error"]["message"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tool / Resource definition tests (5)
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolResourceDefinitions:
    """Static validation of MCP tool and resource registries."""

    def test_tool_definitions_expected_count(self):
        """TOOL_DEFINITIONS has exactly 8 tools (per tools.py header comment)."""
        assert len(TOOL_DEFINITIONS) == 8

    def test_all_tools_have_required_fields(self):
        """Every tool has name, description, and inputSchema."""
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "inputSchema" in tool, f"Tool {tool['name']} missing 'inputSchema'"
            # inputSchema must be a dict with at least a "type" key
            assert isinstance(tool["inputSchema"], dict)
            assert "type" in tool["inputSchema"]

    def test_resource_definitions_expected_count(self):
        """RESOURCE_DEFINITIONS has exactly 5 resources."""
        assert len(RESOURCE_DEFINITIONS) == 5

    def test_all_resources_have_uri_and_name(self):
        """Every resource has uri and name fields."""
        for resource in RESOURCE_DEFINITIONS:
            assert "uri" in resource, f"Resource missing 'uri': {resource}"
            assert "name" in resource, f"Resource missing 'name': {resource}"
            assert resource["uri"].startswith("marketplace://")

    def test_tool_names_are_unique(self):
        """No duplicate tool names in the registry."""
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), f"Duplicate tool names found: {names}"
