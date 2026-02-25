"""Tests for A2UI WebSocket connection manager.

Covers:
  - connect: accept, track, max connections (tests 1-5)
  - disconnect: cleanup session and agent mappings (tests 6-8)
  - send_to_session: success, missing session, send failure (tests 9-11)
  - broadcast_to_agent: multi-session, dead cleanup (tests 12-14)
  - MAX_CONNECTIONS_PER_AGENT enforcement (test 15)
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from marketplace.a2ui.connection_manager import A2UIConnectionManager


def _make_ws() -> MagicMock:
    """Create a mock WebSocket with async accept/close/send_text."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestConnect:
    """Tests 1-5: WebSocket connection acceptance and tracking."""

    # 1
    async def test_connect_accepts_websocket(self):
        """connect() should accept the websocket and return True."""
        mgr = A2UIConnectionManager()
        ws = _make_ws()

        result = await mgr.connect(ws, "sess-1", "agent-1")

        assert result is True
        ws.accept.assert_called_once()

    # 2
    async def test_connect_tracks_session(self):
        """After connect, the session should be retrievable."""
        mgr = A2UIConnectionManager()
        ws = _make_ws()

        await mgr.connect(ws, "sess-2", "agent-2")

        assert mgr._session_ws["sess-2"] is ws
        assert "sess-2" in mgr._agent_sessions["agent-2"]

    # 3
    async def test_connect_rejects_when_max_connections_reached(self):
        """connect() should reject when global MAX_CONNECTIONS is hit."""
        mgr = A2UIConnectionManager()
        mgr.MAX_CONNECTIONS = 2

        ws1 = _make_ws()
        ws2 = _make_ws()
        ws3 = _make_ws()

        await mgr.connect(ws1, "s1", "a1")
        await mgr.connect(ws2, "s2", "a1")
        result = await mgr.connect(ws3, "s3", "a1")

        assert result is False
        ws3.close.assert_called_once()
        assert ws3.close.call_args[1]["code"] == 4029

    # 4
    async def test_connect_multiple_agents(self):
        """Multiple agents should each get their own session sets."""
        mgr = A2UIConnectionManager()

        await mgr.connect(_make_ws(), "s1", "agent-a")
        await mgr.connect(_make_ws(), "s2", "agent-b")

        assert "s1" in mgr._agent_sessions["agent-a"]
        assert "s2" in mgr._agent_sessions["agent-b"]
        assert "s1" not in mgr._agent_sessions.get("agent-b", set())

    # 5
    async def test_connect_rejects_per_agent_limit(self):
        """connect() should reject when MAX_CONNECTIONS_PER_AGENT is hit."""
        mgr = A2UIConnectionManager()
        mgr.MAX_CONNECTIONS_PER_AGENT = 2

        await mgr.connect(_make_ws(), "s1", "agent-x")
        await mgr.connect(_make_ws(), "s2", "agent-x")
        ws_reject = _make_ws()
        result = await mgr.connect(ws_reject, "s3", "agent-x")

        assert result is False
        ws_reject.close.assert_called_once()


class TestDisconnect:
    """Tests 6-8: WebSocket disconnection and cleanup."""

    # 6
    async def test_disconnect_removes_session(self):
        """disconnect() should remove the session from tracking."""
        mgr = A2UIConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws, "sess-6", "agent-6")

        mgr.disconnect(ws)

        assert "sess-6" not in mgr._session_ws

    # 7
    async def test_disconnect_removes_from_agent_sessions(self):
        """disconnect() should remove session from agent mapping."""
        mgr = A2UIConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws, "sess-7", "agent-7")

        mgr.disconnect(ws)

        # Agent with no sessions should be cleaned up
        assert "agent-7" not in mgr._agent_sessions

    # 8
    async def test_disconnect_unknown_ws_is_noop(self):
        """disconnect() with an unknown WebSocket should not raise."""
        mgr = A2UIConnectionManager()
        unknown_ws = _make_ws()

        mgr.disconnect(unknown_ws)  # Should not raise

    # 8b
    async def test_disconnect_preserves_other_sessions_for_agent(self):
        """disconnect() should only remove the specific session, not all agent sessions."""
        mgr = A2UIConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect(ws1, "s1", "agent-8")
        await mgr.connect(ws2, "s2", "agent-8")

        mgr.disconnect(ws1)

        assert "s1" not in mgr._session_ws
        assert "s2" in mgr._session_ws
        assert "s2" in mgr._agent_sessions["agent-8"]
        assert "s1" not in mgr._agent_sessions["agent-8"]


class TestSendToSession:
    """Tests 9-11: sending JSON messages to specific sessions."""

    # 9
    async def test_send_to_session_success(self):
        """send_to_session should serialize and send JSON."""
        mgr = A2UIConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws, "sess-9", "agent-9")

        result = await mgr.send_to_session("sess-9", {"type": "test"})

        assert result is True
        ws.send_text.assert_called_once_with(json.dumps({"type": "test"}))

    # 10
    async def test_send_to_session_missing_returns_false(self):
        """send_to_session for nonexistent session should return False."""
        mgr = A2UIConnectionManager()

        result = await mgr.send_to_session("nonexistent", {"data": 1})

        assert result is False

    # 11
    async def test_send_to_session_failure_disconnects(self):
        """If send_text raises, the socket should be disconnected."""
        mgr = A2UIConnectionManager()
        ws = _make_ws()
        ws.send_text.side_effect = RuntimeError("broken pipe")
        await mgr.connect(ws, "sess-11", "agent-11")

        result = await mgr.send_to_session("sess-11", {"msg": "hello"})

        assert result is False
        assert "sess-11" not in mgr._session_ws


class TestBroadcastToAgent:
    """Tests 12-14: broadcasting to all sessions for an agent."""

    # 12
    async def test_broadcast_sends_to_all_agent_sessions(self):
        """broadcast_to_agent should send to every session for that agent."""
        mgr = A2UIConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect(ws1, "s1", "agent-12")
        await mgr.connect(ws2, "s2", "agent-12")

        await mgr.broadcast_to_agent("agent-12", {"event": "update"})

        expected = json.dumps({"event": "update"})
        ws1.send_text.assert_called_once_with(expected)
        ws2.send_text.assert_called_once_with(expected)

    # 13
    async def test_broadcast_to_unknown_agent_is_noop(self):
        """broadcast_to_agent for an unknown agent should not raise."""
        mgr = A2UIConnectionManager()
        await mgr.broadcast_to_agent("ghost-agent", {"test": True})  # Should not raise

    # 14
    async def test_broadcast_cleans_up_dead_sockets(self):
        """broadcast_to_agent should disconnect sockets that fail to send."""
        mgr = A2UIConnectionManager()
        ws_good = _make_ws()
        ws_bad = _make_ws()
        ws_bad.send_text.side_effect = RuntimeError("connection lost")

        await mgr.connect(ws_good, "s-good", "agent-14")
        await mgr.connect(ws_bad, "s-bad", "agent-14")

        await mgr.broadcast_to_agent("agent-14", {"data": "msg"})

        # Good socket should still be tracked
        assert "s-good" in mgr._session_ws
        # Bad socket should have been disconnected
        assert "s-bad" not in mgr._session_ws

    # 15
    async def test_broadcast_does_not_cross_agents(self):
        """broadcast_to_agent should not send to sessions of other agents."""
        mgr = A2UIConnectionManager()
        ws_a = _make_ws()
        ws_b = _make_ws()
        await mgr.connect(ws_a, "s-a", "agent-A")
        await mgr.connect(ws_b, "s-b", "agent-B")

        await mgr.broadcast_to_agent("agent-A", {"msg": "only-A"})

        ws_a.send_text.assert_called_once()
        ws_b.send_text.assert_not_called()
