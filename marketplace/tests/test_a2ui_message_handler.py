"""Tests for A2UI message handler, connection manager, and schemas.

Covers JSON-RPC dispatch, WebSocket connection lifecycle, and Pydantic
model validation for all A2UI message types.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from marketplace.a2ui import A2UI_VERSION
from marketplace.a2ui.connection_manager import A2UIConnectionManager
from marketplace.a2ui.message_handler import (
    SERVER_NAME,
    SERVER_VERSION,
    _jsonrpc_error,
    _jsonrpc_response,
    handle_a2ui_message,
)
from marketplace.a2ui.schemas import (
    A2UIComponentType,
    A2UIConfirmMessage,
    A2UIInitRequest,
    A2UIInitResponse,
    A2UIInputType,
    A2UINavigateMessage,
    A2UINotifyMessage,
    A2UIProgressMessage,
    A2UIProgressType,
    A2UIRenderMessage,
    A2UIRequestInputMessage,
    A2UIUpdateMessage,
    A2UIUserApproval,
    A2UIUserCancel,
    A2UIUserResponse,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def conn_manager():
    """Fresh connection manager for each test."""
    return A2UIConnectionManager()


def _make_ws(accept=True):
    """Create a mock WebSocket that tracks calls."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


# ══════════════════════════════════════════════════════════════════════
#  TestA2UIMessageHandler
# ══════════════════════════════════════════════════════════════════════


class TestA2UIMessageHandler:
    """JSON-RPC dispatch and method routing tests."""

    # ── helpers ──

    @staticmethod
    def _init_body(agent_id="agent-1", user_id="user-1", msg_id=1):
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "a2ui.init",
            "params": {"agent_id": agent_id, "user_id": user_id},
        }

    # ── a2ui.init ──

    @pytest.mark.asyncio
    async def test_init_returns_session_id(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock()
            session.session_id = "sess-123"
            mgr.create_session.return_value = session
            resp = await handle_a2ui_message(self._init_body())
        assert resp["result"]["session_id"] == "sess-123"

    @pytest.mark.asyncio
    async def test_init_returns_capabilities(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.create_session.return_value = session
            resp = await handle_a2ui_message(self._init_body())
        caps = resp["result"]["capabilities"]
        assert "card" in caps["components"]
        assert caps["streaming"] is True

    @pytest.mark.asyncio
    async def test_init_returns_version(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.create_session.return_value = session
            resp = await handle_a2ui_message(self._init_body())
        assert resp["result"]["version"] == A2UI_VERSION

    @pytest.mark.asyncio
    async def test_init_returns_server_info(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.create_session.return_value = session
            resp = await handle_a2ui_message(self._init_body())
        info = resp["result"]["serverInfo"]
        assert info["name"] == SERVER_NAME
        assert info["version"] == SERVER_VERSION

    @pytest.mark.asyncio
    async def test_init_missing_agent_id(self):
        body = {"jsonrpc": "2.0", "id": 1, "method": "a2ui.init", "params": {}}
        resp = await handle_a2ui_message(body)
        assert resp["error"]["code"] == -32602
        assert "agent_id" in resp["error"]["message"]

    @pytest.mark.asyncio
    async def test_init_with_client_info_and_capabilities(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.create_session.return_value = session
            body = self._init_body()
            body["params"]["client_info"] = {"name": "test-client"}
            body["params"]["capabilities"] = {"streaming": True}
            resp = await handle_a2ui_message(body)
        assert "error" not in resp

    # ── no session ──

    @pytest.mark.asyncio
    async def test_method_without_session_returns_error(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            mgr.get_session.return_value = None
            body = {"jsonrpc": "2.0", "id": 2, "method": "user.respond", "params": {}}
            resp = await handle_a2ui_message(body)
        assert resp["error"]["code"] == -32000
        assert "No active session" in resp["error"]["message"]

    @pytest.mark.asyncio
    async def test_session_resolved_from_params(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock()
            session.session_id = "from-params"
            session.pending_inputs = {}
            mgr.get_session.side_effect = lambda sid: session if sid == "from-params" else None
            mgr.check_rate_limit.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 3, "method": "user.cancel",
                "params": {"session_id": "from-params", "task_id": "t1"},
            }
            resp = await handle_a2ui_message(body)
        assert "error" not in resp

    # ── rate limit ──

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = False
            body = {
                "jsonrpc": "2.0", "id": 4, "method": "user.respond",
                "params": {"request_id": "r1", "value": "hello"},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["error"]["code"] == -32000
        assert "Rate limit" in resp["error"]["message"]

    # ── user.respond ──

    @pytest.mark.asyncio
    async def test_user_respond_success(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            mgr.resolve_pending_input.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 5, "method": "user.respond",
                "params": {"request_id": "r1", "value": "test-val"},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["result"]["acknowledged"] is True
        assert resp["result"]["request_id"] == "r1"

    @pytest.mark.asyncio
    async def test_user_respond_missing_request_id(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 6, "method": "user.respond",
                "params": {"value": "x"},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_user_respond_no_pending_input(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            mgr.resolve_pending_input.return_value = False
            body = {
                "jsonrpc": "2.0", "id": 7, "method": "user.respond",
                "params": {"request_id": "missing"},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["error"]["code"] == -32000
        assert "missing" in resp["error"]["message"]

    # ── user.approve ──

    @pytest.mark.asyncio
    async def test_user_approve_success(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            mgr.resolve_pending_input.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 8, "method": "user.approve",
                "params": {"request_id": "c1", "approved": True, "reason": "ok"},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["result"]["acknowledged"] is True

    @pytest.mark.asyncio
    async def test_user_approve_missing_request_id(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 9, "method": "user.approve",
                "params": {"approved": True},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_user_approve_not_resolved(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            mgr.resolve_pending_input.return_value = False
            body = {
                "jsonrpc": "2.0", "id": 10, "method": "user.approve",
                "params": {"request_id": "c1", "approved": False},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["error"]["code"] == -32000
        assert "pending confirmation" in resp["error"]["message"]

    # ── user.cancel ──

    @pytest.mark.asyncio
    async def test_user_cancel_success(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            future = asyncio.Future()
            session = MagicMock(session_id="s1")
            session.pending_inputs = {"t1": future}
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 11, "method": "user.cancel",
                "params": {"task_id": "t1"},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["result"]["cancelled"] is True
        assert resp["result"]["task_id"] == "t1"

    @pytest.mark.asyncio
    async def test_user_cancel_missing_task_id(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            session.pending_inputs = {}
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 12, "method": "user.cancel",
                "params": {},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_user_cancel_no_matching_future(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            session.pending_inputs = {}
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 13, "method": "user.cancel",
                "params": {"task_id": "nonexistent"},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["result"]["cancelled"] is False

    @pytest.mark.asyncio
    async def test_user_cancel_prefix_match(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            future = asyncio.Future()
            session = MagicMock(session_id="s1")
            session.pending_inputs = {"t1:sub": future}
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            body = {
                "jsonrpc": "2.0", "id": 14, "method": "user.cancel",
                "params": {"task_id": "t1"},
            }
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["result"]["cancelled"] is True

    # ── ping ──

    @pytest.mark.asyncio
    async def test_ping(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            body = {"jsonrpc": "2.0", "id": 15, "method": "ping", "params": {}}
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["result"] == {}

    # ── unknown method ──

    @pytest.mark.asyncio
    async def test_unknown_method(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.get_session.return_value = session
            mgr.check_rate_limit.return_value = True
            body = {"jsonrpc": "2.0", "id": 16, "method": "foo.bar", "params": {}}
            resp = await handle_a2ui_message(body, session_id="s1")
        assert resp["error"]["code"] == -32601
        assert "foo.bar" in resp["error"]["message"]

    # ── malformed / edge cases ──

    @pytest.mark.asyncio
    async def test_missing_method_field(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            mgr.get_session.return_value = None
            body = {"jsonrpc": "2.0", "id": 17}
            resp = await handle_a2ui_message(body)
        # empty method string -> no session -> error
        assert "error" in resp

    @pytest.mark.asyncio
    async def test_missing_id_field(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            session = MagicMock(session_id="s1")
            mgr.create_session.return_value = session
            body = {"jsonrpc": "2.0", "method": "a2ui.init", "params": {"agent_id": "a"}}
            resp = await handle_a2ui_message(body)
        assert resp["id"] is None  # id defaults to None from body.get("id")

    @pytest.mark.asyncio
    async def test_missing_params_field(self):
        with patch("marketplace.a2ui.message_handler.a2ui_session_manager") as mgr:
            mgr.get_session.return_value = None
            body = {"jsonrpc": "2.0", "id": 18, "method": "user.respond"}
            resp = await handle_a2ui_message(body)
        assert "error" in resp

    # ── helper functions ──

    def test_jsonrpc_response_format(self):
        resp = _jsonrpc_response(42, {"ok": True})
        assert resp == {"jsonrpc": "2.0", "id": 42, "result": {"ok": True}}

    def test_jsonrpc_error_format(self):
        resp = _jsonrpc_error(99, -32600, "bad request")
        assert resp == {
            "jsonrpc": "2.0",
            "id": 99,
            "error": {"code": -32600, "message": "bad request"},
        }

    def test_jsonrpc_response_with_none_id(self):
        resp = _jsonrpc_response(None, {})
        assert resp["id"] is None

    def test_jsonrpc_error_with_string_id(self):
        resp = _jsonrpc_error("abc", -32601, "not found")
        assert resp["id"] == "abc"


# ══════════════════════════════════════════════════════════════════════
#  TestA2UIConnectionManager
# ══════════════════════════════════════════════════════════════════════


class TestA2UIConnectionManager:
    """WebSocket connection lifecycle tests."""

    @pytest.mark.asyncio
    async def test_connect_accepts_ws(self, conn_manager):
        ws = _make_ws()
        result = await conn_manager.connect(ws, "sess-1", "agent-1")
        assert result is True
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_tracks_session(self, conn_manager):
        ws = _make_ws()
        await conn_manager.connect(ws, "sess-1", "agent-1")
        assert "sess-1" in conn_manager._session_ws

    @pytest.mark.asyncio
    async def test_connect_tracks_agent(self, conn_manager):
        ws = _make_ws()
        await conn_manager.connect(ws, "sess-1", "agent-1")
        assert "sess-1" in conn_manager._agent_sessions["agent-1"]

    @pytest.mark.asyncio
    async def test_connect_max_connections(self, conn_manager):
        conn_manager.MAX_CONNECTIONS = 2
        ws1, ws2, ws3 = _make_ws(), _make_ws(), _make_ws()
        await conn_manager.connect(ws1, "s1", "a1")
        await conn_manager.connect(ws2, "s2", "a1")
        result = await conn_manager.connect(ws3, "s3", "a1")
        assert result is False
        ws3.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_session(self, conn_manager):
        ws = _make_ws()
        await conn_manager.connect(ws, "sess-1", "agent-1")
        conn_manager.disconnect(ws)
        assert "sess-1" not in conn_manager._session_ws

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_agent(self, conn_manager):
        ws = _make_ws()
        await conn_manager.connect(ws, "sess-1", "agent-1")
        conn_manager.disconnect(ws)
        assert "agent-1" not in conn_manager._agent_sessions

    @pytest.mark.asyncio
    async def test_disconnect_unknown_ws_noop(self, conn_manager):
        ws = _make_ws()
        conn_manager.disconnect(ws)  # should not raise

    @pytest.mark.asyncio
    async def test_disconnect_preserves_other_sessions(self, conn_manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await conn_manager.connect(ws1, "s1", "agent-1")
        await conn_manager.connect(ws2, "s2", "agent-1")
        conn_manager.disconnect(ws1)
        assert "s2" in conn_manager._session_ws
        assert "s2" in conn_manager._agent_sessions["agent-1"]

    @pytest.mark.asyncio
    async def test_send_to_session_success(self, conn_manager):
        ws = _make_ws()
        await conn_manager.connect(ws, "sess-1", "agent-1")
        result = await conn_manager.send_to_session("sess-1", {"type": "test"})
        assert result is True
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent == {"type": "test"}

    @pytest.mark.asyncio
    async def test_send_to_session_unknown_session(self, conn_manager):
        result = await conn_manager.send_to_session("no-such", {"x": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_to_session_failure_disconnects(self, conn_manager):
        ws = _make_ws()
        ws.send_text.side_effect = RuntimeError("connection closed")
        await conn_manager.connect(ws, "sess-1", "agent-1")
        result = await conn_manager.send_to_session("sess-1", {"x": 1})
        assert result is False
        assert "sess-1" not in conn_manager._session_ws

    @pytest.mark.asyncio
    async def test_broadcast_to_agent(self, conn_manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await conn_manager.connect(ws1, "s1", "agent-1")
        await conn_manager.connect(ws2, "s2", "agent-1")
        await conn_manager.broadcast_to_agent("agent-1", {"msg": "hi"})
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_unknown_agent(self, conn_manager):
        # should not raise
        await conn_manager.broadcast_to_agent("nobody", {"msg": "hi"})

    @pytest.mark.asyncio
    async def test_broadcast_cleans_dead_connections(self, conn_manager):
        ws1 = _make_ws()
        ws2 = _make_ws()
        ws2.send_text.side_effect = RuntimeError("dead")
        await conn_manager.connect(ws1, "s1", "agent-1")
        await conn_manager.connect(ws2, "s2", "agent-1")
        await conn_manager.broadcast_to_agent("agent-1", {"x": 1})
        assert "s2" not in conn_manager._session_ws

    @pytest.mark.asyncio
    async def test_message_serialization_json(self, conn_manager):
        ws = _make_ws()
        await conn_manager.connect(ws, "s1", "a1")
        payload = {"nested": {"list": [1, 2, 3]}}
        await conn_manager.send_to_session("s1", payload)
        sent_text = ws.send_text.call_args[0][0]
        assert json.loads(sent_text) == payload

    @pytest.mark.asyncio
    async def test_multiple_agents_isolated(self, conn_manager):
        ws1, ws2 = _make_ws(), _make_ws()
        await conn_manager.connect(ws1, "s1", "agent-a")
        await conn_manager.connect(ws2, "s2", "agent-b")
        await conn_manager.broadcast_to_agent("agent-a", {"x": 1})
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_not_awaited()


# ══════════════════════════════════════════════════════════════════════
#  TestA2UISchemas
# ══════════════════════════════════════════════════════════════════════


class TestA2UISchemas:
    """Pydantic model validation tests for all A2UI schema types."""

    # ── Enums ──

    def test_component_type_values(self):
        expected = {"card", "table", "form", "chart", "markdown",
                    "code", "image", "alert", "steps"}
        assert {e.value for e in A2UIComponentType} == expected

    def test_progress_type_values(self):
        expected = {"determinate", "indeterminate", "streaming"}
        assert {e.value for e in A2UIProgressType} == expected

    def test_input_type_values(self):
        expected = {"text", "select", "number", "date", "file"}
        assert {e.value for e in A2UIInputType} == expected

    # ── A2UIRenderMessage ──

    def test_render_valid(self):
        msg = A2UIRenderMessage(component_id="c1", component_type="card", data={"k": "v"})
        assert msg.component_id == "c1"
        assert msg.component_type == A2UIComponentType.card

    def test_render_empty_component_id(self):
        with pytest.raises(ValidationError):
            A2UIRenderMessage(component_id="", component_type="card")

    def test_render_default_data(self):
        msg = A2UIRenderMessage(component_id="c1", component_type="table")
        assert msg.data == {}

    def test_render_metadata_optional(self):
        msg = A2UIRenderMessage(component_id="c1", component_type="table")
        assert msg.metadata is None

    def test_render_invalid_component_type(self):
        with pytest.raises(ValidationError):
            A2UIRenderMessage(component_id="c1", component_type="nonexistent")

    # ── A2UIUpdateMessage ──

    def test_update_valid(self):
        msg = A2UIUpdateMessage(component_id="c1", operation="replace", data={"a": 1})
        assert msg.operation == "replace"

    def test_update_merge_operation(self):
        msg = A2UIUpdateMessage(component_id="c1", operation="merge")
        assert msg.data == {}

    def test_update_append_operation(self):
        msg = A2UIUpdateMessage(component_id="c1", operation="append")
        assert msg.operation == "append"

    def test_update_invalid_operation(self):
        with pytest.raises(ValidationError):
            A2UIUpdateMessage(component_id="c1", operation="delete")

    def test_update_empty_component_id(self):
        with pytest.raises(ValidationError):
            A2UIUpdateMessage(component_id="", operation="replace")

    # ── A2UIRequestInputMessage ──

    def test_request_input_valid(self):
        msg = A2UIRequestInputMessage(
            request_id="r1", input_type="text", prompt="Enter name"
        )
        assert msg.input_type == A2UIInputType.text

    def test_request_input_with_options(self):
        msg = A2UIRequestInputMessage(
            request_id="r1", input_type="select", prompt="Pick one",
            options=["a", "b"],
        )
        assert msg.options == ["a", "b"]

    def test_request_input_empty_prompt(self):
        with pytest.raises(ValidationError):
            A2UIRequestInputMessage(request_id="r1", input_type="text", prompt="")

    def test_request_input_missing_prompt(self):
        with pytest.raises(ValidationError):
            A2UIRequestInputMessage(request_id="r1", input_type="text")

    def test_request_input_validation_optional(self):
        msg = A2UIRequestInputMessage(
            request_id="r1", input_type="number", prompt="Enter age",
            validation={"min": 0, "max": 150},
        )
        assert msg.validation == {"min": 0, "max": 150}

    # ── A2UIConfirmMessage ──

    def test_confirm_valid(self):
        msg = A2UIConfirmMessage(request_id="c1", title="Confirm?")
        assert msg.severity == "info"
        assert msg.timeout_seconds == 30

    def test_confirm_custom_severity(self):
        msg = A2UIConfirmMessage(request_id="c1", title="Danger!", severity="critical")
        assert msg.severity == "critical"

    def test_confirm_invalid_severity(self):
        with pytest.raises(ValidationError):
            A2UIConfirmMessage(request_id="c1", title="X", severity="fatal")

    def test_confirm_timeout_bounds(self):
        msg = A2UIConfirmMessage(request_id="c1", title="X", timeout_seconds=1)
        assert msg.timeout_seconds == 1
        msg2 = A2UIConfirmMessage(request_id="c1", title="X", timeout_seconds=300)
        assert msg2.timeout_seconds == 300

    def test_confirm_timeout_too_low(self):
        with pytest.raises(ValidationError):
            A2UIConfirmMessage(request_id="c1", title="X", timeout_seconds=0)

    def test_confirm_timeout_too_high(self):
        with pytest.raises(ValidationError):
            A2UIConfirmMessage(request_id="c1", title="X", timeout_seconds=301)

    def test_confirm_empty_title(self):
        with pytest.raises(ValidationError):
            A2UIConfirmMessage(request_id="c1", title="")

    # ── A2UIProgressMessage ──

    def test_progress_determinate(self):
        msg = A2UIProgressMessage(
            task_id="t1", progress_type="determinate", value=50, total=100,
        )
        assert msg.value == 50

    def test_progress_indeterminate(self):
        msg = A2UIProgressMessage(task_id="t1", progress_type="indeterminate")
        assert msg.value is None

    def test_progress_streaming(self):
        msg = A2UIProgressMessage(
            task_id="t1", progress_type="streaming", message="working...",
        )
        assert msg.message == "working..."

    def test_progress_invalid_type(self):
        with pytest.raises(ValidationError):
            A2UIProgressMessage(task_id="t1", progress_type="unknown")

    # ── A2UINavigateMessage ──

    def test_navigate_valid(self):
        msg = A2UINavigateMessage(url="https://example.com")
        assert msg.new_tab is False

    def test_navigate_new_tab(self):
        msg = A2UINavigateMessage(url="https://example.com", new_tab=True)
        assert msg.new_tab is True

    def test_navigate_empty_url(self):
        with pytest.raises(ValidationError):
            A2UINavigateMessage(url="")

    # ── A2UINotifyMessage ──

    def test_notify_defaults(self):
        msg = A2UINotifyMessage(title="Hello")
        assert msg.level == "info"
        assert msg.duration_ms == 5000
        assert msg.message is None

    def test_notify_all_levels(self):
        for level in ("info", "success", "warning", "error"):
            msg = A2UINotifyMessage(title="X", level=level)
            assert msg.level == level

    def test_notify_invalid_level(self):
        with pytest.raises(ValidationError):
            A2UINotifyMessage(title="X", level="debug")

    def test_notify_duration_zero(self):
        msg = A2UINotifyMessage(title="X", duration_ms=0)
        assert msg.duration_ms == 0

    def test_notify_duration_max(self):
        msg = A2UINotifyMessage(title="X", duration_ms=60000)
        assert msg.duration_ms == 60000

    def test_notify_duration_over_max(self):
        with pytest.raises(ValidationError):
            A2UINotifyMessage(title="X", duration_ms=60001)

    # ── A2UIInitRequest ──

    def test_init_request_defaults(self):
        msg = A2UIInitRequest()
        assert msg.client_info == {}
        assert msg.capabilities == {}

    def test_init_request_with_values(self):
        msg = A2UIInitRequest(
            client_info={"name": "web"}, capabilities={"streaming": True},
        )
        assert msg.client_info["name"] == "web"

    # ── A2UIInitResponse ──

    def test_init_response_valid(self):
        msg = A2UIInitResponse(session_id="s1", version="2026-02-20")
        assert msg.session_id == "s1"
        assert msg.capabilities == {}

    def test_init_response_with_caps(self):
        msg = A2UIInitResponse(
            session_id="s1", version="1.0",
            capabilities={"components": ["card"]},
        )
        assert "card" in msg.capabilities["components"]

    # ── A2UIUserResponse ──

    def test_user_response_valid(self):
        msg = A2UIUserResponse(request_id="r1", value="hello")
        assert msg.value == "hello"

    def test_user_response_none_value(self):
        msg = A2UIUserResponse(request_id="r1")
        assert msg.value is None

    def test_user_response_empty_request_id(self):
        with pytest.raises(ValidationError):
            A2UIUserResponse(request_id="")

    # ── A2UIUserApproval ──

    def test_user_approval_approved(self):
        msg = A2UIUserApproval(request_id="c1", approved=True)
        assert msg.approved is True
        assert msg.reason is None

    def test_user_approval_rejected_with_reason(self):
        msg = A2UIUserApproval(request_id="c1", approved=False, reason="not safe")
        assert msg.reason == "not safe"

    def test_user_approval_missing_approved(self):
        with pytest.raises(ValidationError):
            A2UIUserApproval(request_id="c1")

    # ── A2UIUserCancel ──

    def test_user_cancel_valid(self):
        msg = A2UIUserCancel(task_id="t1")
        assert msg.task_id == "t1"

    def test_user_cancel_empty_task_id(self):
        with pytest.raises(ValidationError):
            A2UIUserCancel(task_id="")

    def test_user_cancel_task_id_max_length(self):
        msg = A2UIUserCancel(task_id="x" * 100)
        assert len(msg.task_id) == 100

    def test_user_cancel_task_id_too_long(self):
        with pytest.raises(ValidationError):
            A2UIUserCancel(task_id="x" * 101)
