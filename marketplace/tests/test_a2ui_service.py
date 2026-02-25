"""Tests for a2ui_service — 25 tests covering all public functions and the A2UIService class.

All WebSocket interactions are mocked via the a2ui_connection_manager and
a2ui_session_manager singletons.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.services.a2ui_service import (
    A2UIService,
    _build_jsonrpc_notification,
    push_navigate,
    push_notify,
    push_progress,
    push_render,
    push_update,
    request_confirm,
    request_input,
)


# ---------------------------------------------------------------------------
# _build_jsonrpc_notification
# ---------------------------------------------------------------------------


class TestBuildJsonrpcNotification:

    def test_builds_valid_jsonrpc_notification(self):
        msg = _build_jsonrpc_notification("ui.render", {"component_id": "c1"})
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "ui.render"
        assert msg["params"] == {"component_id": "c1"}

    def test_notification_has_no_id_field(self):
        msg = _build_jsonrpc_notification("ui.update", {})
        assert "id" not in msg

    def test_params_are_passed_through(self):
        params = {"key": "value", "nested": {"a": 1}}
        msg = _build_jsonrpc_notification("test.method", params)
        assert msg["params"] is params


# ---------------------------------------------------------------------------
# push_render
# ---------------------------------------------------------------------------


class TestPushRender:

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    async def test_push_render_returns_component_id(self, mock_session_mgr, mock_conn_mgr):
        mock_session = MagicMock()
        mock_session.active_components = set()
        mock_session_mgr.get_session.return_value = mock_session
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        cid = await push_render("sess-1", "chart", {"title": "Revenue"})
        assert isinstance(cid, str)
        assert len(cid) > 0
        # Component ID should be added to session's active_components
        assert cid in mock_session.active_components

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    async def test_push_render_sends_correct_message(self, mock_session_mgr, mock_conn_mgr):
        mock_session_mgr.get_session.return_value = MagicMock(active_components=set())
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        await push_render("sess-1", "table", {"rows": []}, metadata={"source": "api"})

        call_args = mock_conn_mgr.send_to_session.call_args
        session_id = call_args[0][0]
        message = call_args[0][1]
        assert session_id == "sess-1"
        assert message["method"] == "ui.render"
        assert message["params"]["component_type"] == "table"
        assert message["params"]["data"] == {"rows": []}
        assert message["params"]["metadata"] == {"source": "api"}

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    @patch("marketplace.services.a2ui_service.validate_payload_size", return_value=False)
    async def test_push_render_rejects_oversized_payload(
        self, mock_validate, mock_session_mgr, mock_conn_mgr
    ):
        with pytest.raises(ValueError, match="maximum size"):
            await push_render("sess-1", "chart", {"huge": "data"})

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    async def test_push_render_handles_no_session(self, mock_session_mgr, mock_conn_mgr):
        """push_render works even if session is not found (component_id still returned)."""
        mock_session_mgr.get_session.return_value = None
        mock_conn_mgr.send_to_session = AsyncMock(return_value=False)

        cid = await push_render("missing-sess", "chart", {"data": 1})
        assert isinstance(cid, str)


# ---------------------------------------------------------------------------
# push_update
# ---------------------------------------------------------------------------


class TestPushUpdate:

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_push_update_sends_message(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        await push_update("sess-1", "comp-1", "replace", {"title": "New"})

        call_args = mock_conn_mgr.send_to_session.call_args
        message = call_args[0][1]
        assert message["method"] == "ui.update"
        assert message["params"]["component_id"] == "comp-1"
        assert message["params"]["operation"] == "replace"

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_push_update_rejects_invalid_operation(self, mock_conn_mgr):
        with pytest.raises(ValueError, match="Invalid operation"):
            await push_update("sess-1", "comp-1", "delete_all", {})

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_push_update_accepts_merge_operation(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)
        await push_update("sess-1", "comp-1", "merge", {"key": "value"})
        # Should not raise

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_push_update_accepts_append_operation(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)
        await push_update("sess-1", "comp-1", "append", {"row": [1, 2]})
        # Should not raise

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.validate_payload_size", return_value=False)
    async def test_push_update_rejects_oversized_payload(
        self, mock_validate, mock_conn_mgr
    ):
        with pytest.raises(ValueError, match="maximum size"):
            await push_update("sess-1", "comp-1", "replace", {"huge": "x" * 10000})


# ---------------------------------------------------------------------------
# request_input
# ---------------------------------------------------------------------------


class TestRequestInput:

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    async def test_request_input_sends_and_resolves(self, mock_session_mgr, mock_conn_mgr):
        """Simulates the user responding to an input request."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        mock_session_mgr.set_pending_input.return_value = future
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        # Resolve the future after a short delay
        async def _resolve():
            await asyncio.sleep(0.01)
            future.set_result("user-typed-value")

        asyncio.create_task(_resolve())
        result = await request_input("sess-1", "text", "Enter name:", timeout=5)
        assert result == "user-typed-value"

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    async def test_request_input_timeout(self, mock_session_mgr, mock_conn_mgr):
        """If user doesn't respond within timeout, asyncio.TimeoutError is raised."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        mock_session_mgr.set_pending_input.return_value = future
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        with pytest.raises(asyncio.TimeoutError):
            await request_input("sess-1", "text", "prompt", timeout=0.01)


# ---------------------------------------------------------------------------
# request_confirm
# ---------------------------------------------------------------------------


class TestRequestConfirm:

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    async def test_request_confirm_sends_and_resolves(self, mock_session_mgr, mock_conn_mgr):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        mock_session_mgr.set_pending_input.return_value = future
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        async def _resolve():
            await asyncio.sleep(0.01)
            future.set_result({"approved": True, "reason": None})

        asyncio.create_task(_resolve())
        result = await request_confirm("sess-1", "Delete data?", severity="warning", timeout=5)
        assert result["approved"] is True

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    async def test_request_confirm_timeout(self, mock_session_mgr, mock_conn_mgr):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        mock_session_mgr.set_pending_input.return_value = future
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        with pytest.raises(asyncio.TimeoutError):
            await request_confirm("sess-1", "Approve?", timeout=0.01)


# ---------------------------------------------------------------------------
# push_progress
# ---------------------------------------------------------------------------


class TestPushProgress:

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_push_progress_sends_message(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        await push_progress("sess-1", "task-1", "determinate", value=50, total=100, message="Half done")

        call_args = mock_conn_mgr.send_to_session.call_args
        message = call_args[0][1]
        assert message["method"] == "ui.progress"
        assert message["params"]["task_id"] == "task-1"
        assert message["params"]["progress_type"] == "determinate"
        assert message["params"]["value"] == 50
        assert message["params"]["total"] == 100


# ---------------------------------------------------------------------------
# push_navigate
# ---------------------------------------------------------------------------


class TestPushNavigate:

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_push_navigate_sends_url(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        await push_navigate("sess-1", "https://example.com", new_tab=True)

        call_args = mock_conn_mgr.send_to_session.call_args
        message = call_args[0][1]
        assert message["method"] == "ui.navigate"
        assert message["params"]["url"] == "https://example.com"
        assert message["params"]["new_tab"] is True

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_push_navigate_default_same_tab(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        await push_navigate("sess-1", "/dashboard")

        call_args = mock_conn_mgr.send_to_session.call_args
        message = call_args[0][1]
        assert message["params"]["new_tab"] is False


# ---------------------------------------------------------------------------
# push_notify
# ---------------------------------------------------------------------------


class TestPushNotify:

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_push_notify_sends_toast(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        await push_notify("sess-1", "success", "Done!", message="Task completed", duration_ms=3000)

        call_args = mock_conn_mgr.send_to_session.call_args
        message = call_args[0][1]
        assert message["method"] == "ui.notify"
        assert message["params"]["level"] == "success"
        assert message["params"]["duration_ms"] == 3000


# ---------------------------------------------------------------------------
# A2UIService class wrapper
# ---------------------------------------------------------------------------


class TestA2UIServiceClass:

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    @patch("marketplace.services.a2ui_service.a2ui_session_manager")
    async def test_render_delegates_to_push_render(self, mock_session_mgr, mock_conn_mgr):
        mock_session_mgr.get_session.return_value = MagicMock(active_components=set())
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        svc = A2UIService()
        cid = await svc.render("sess-1", component_type="chart", data={"x": 1})
        assert isinstance(cid, str)

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_update_delegates_to_push_update(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        svc = A2UIService()
        await svc.update("sess-1", component_id="c1", operation="merge", data={"k": "v"})
        mock_conn_mgr.send_to_session.assert_awaited_once()

    @patch("marketplace.services.a2ui_service.a2ui_connection_manager")
    async def test_notify_delegates_to_push_notify(self, mock_conn_mgr):
        mock_conn_mgr.send_to_session = AsyncMock(return_value=True)

        svc = A2UIService()
        await svc.notify("sess-1", level="info", title="Hello")
        mock_conn_mgr.send_to_session.assert_awaited_once()
