"""Comprehensive tests for a2ui_service and admin_dashboard_service.

Tests cover:
- a2ui_service: push_render, push_update, request_input, request_confirm,
  push_progress, push_navigate, push_notify, A2UIService class
- admin_dashboard_service: get_admin_overview, get_admin_finance,
  get_admin_usage, list_admin_agents, list_security_events, list_pending_payouts
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.a2ui.session_manager import A2UISession, A2UISessionManager
from marketplace.services import a2ui_service, admin_dashboard_service


# =============================================================================
# Helpers
# =============================================================================

def _new_id() -> str:
    return str(uuid.uuid4())


def _make_session_manager_with_session(session_id: str, agent_id: str = "agent-1") -> tuple[A2UISessionManager, A2UISession]:
    """Create a fresh session manager with one active session."""
    mgr = A2UISessionManager()
    session = mgr.create_session(agent_id=agent_id)
    # Override the auto-generated session_id so callers can reference it
    old_id = session.session_id
    mgr._sessions.pop(old_id)
    session.session_id = session_id
    mgr._sessions[session_id] = session
    return mgr, session


# =============================================================================
# a2ui_service._build_jsonrpc_notification
# =============================================================================

class TestBuildJsonrpcNotification:
    """Unit tests for the private _build_jsonrpc_notification helper."""

    def test_returns_correct_structure(self):
        msg = a2ui_service._build_jsonrpc_notification("ui.render", {"key": "value"})
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "ui.render"
        assert msg["params"] == {"key": "value"}

    def test_no_id_field(self):
        """Notifications must not have an id field (JSON-RPC spec)."""
        msg = a2ui_service._build_jsonrpc_notification("ui.test", {})
        assert "id" not in msg

    def test_empty_params(self):
        msg = a2ui_service._build_jsonrpc_notification("ui.navigate", {})
        assert msg["params"] == {}

    def test_nested_params(self):
        params = {"a": {"b": [1, 2, 3]}}
        msg = a2ui_service._build_jsonrpc_notification("ui.test", params)
        assert msg["params"]["a"]["b"] == [1, 2, 3]


# =============================================================================
# a2ui_service.push_render
# =============================================================================

class TestPushRender:

    async def test_push_render_happy_path(self):
        """push_render sends a ui.render message and returns a UUID component_id."""
        session_id = "sess-render-1"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        mock_sm = MagicMock()
        mock_session = MagicMock()
        mock_session.active_components = set()
        mock_sm.get_session.return_value = mock_session

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm):

            component_id = await a2ui_service.push_render(
                session_id,
                component_type="card",
                data={"title": "Hello"},
                metadata={"source": "test"},
            )

        assert isinstance(component_id, str)
        uuid.UUID(component_id)  # Must be a valid UUID
        mock_cm.send_to_session.assert_awaited_once()
        call_args = mock_cm.send_to_session.call_args
        sent_msg = call_args[0][1]
        assert sent_msg["method"] == "ui.render"
        assert sent_msg["params"]["component_id"] == component_id
        assert sent_msg["params"]["component_type"] == "card"
        assert sent_msg["params"]["data"] == {"title": "Hello"}
        assert sent_msg["params"]["metadata"] == {"source": "test"}

    async def test_push_render_adds_component_to_active_session(self):
        """push_render tracks the component_id in the session's active_components."""
        session_id = "sess-render-2"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        active_set: set[str] = set()
        mock_sm = MagicMock()
        mock_session = MagicMock()
        mock_session.active_components = active_set
        mock_sm.get_session.return_value = mock_session

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm):

            cid = await a2ui_service.push_render(session_id, component_type="text", data={"msg": "hi"})

        assert cid in active_set

    async def test_push_render_no_session_still_sends(self):
        """When session is not found, push_render still sends the message."""
        session_id = "sess-render-no-session"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=False)

        mock_sm = MagicMock()
        mock_sm.get_session.return_value = None  # Session not found

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm):

            cid = await a2ui_service.push_render(session_id, component_type="text", data={"x": 1})

        assert cid is not None
        mock_cm.send_to_session.assert_awaited_once()

    async def test_push_render_oversized_payload_raises(self):
        """push_render raises ValueError when payload exceeds 1 MB."""
        session_id = "sess-render-large"
        large_data = {"payload": "x" * (1024 * 1024 + 100)}

        with pytest.raises(ValueError, match="Payload exceeds maximum size"):
            await a2ui_service.push_render(session_id, component_type="card", data=large_data)

    async def test_push_render_metadata_none_is_allowed(self):
        """push_render works with metadata=None (default)."""
        session_id = "sess-render-3"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)
        mock_sm = MagicMock()
        mock_sm.get_session.return_value = None

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm):

            cid = await a2ui_service.push_render(session_id, component_type="list", data={"items": []})

        sent_msg = mock_cm.send_to_session.call_args[0][1]
        assert sent_msg["params"]["metadata"] is None


# =============================================================================
# a2ui_service.push_update
# =============================================================================

class TestPushUpdate:

    async def test_push_update_replace_operation(self):
        """push_update with 'replace' operation sends ui.update message."""
        session_id = "sess-update-1"
        component_id = _new_id()
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_update(session_id, component_id, "replace", {"value": 42})

        mock_cm.send_to_session.assert_awaited_once()
        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["method"] == "ui.update"
        assert msg["params"]["component_id"] == component_id
        assert msg["params"]["operation"] == "replace"
        assert msg["params"]["data"] == {"value": 42}

    async def test_push_update_merge_operation(self):
        """push_update with 'merge' operation sends the correct message."""
        session_id = "sess-update-2"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_update(session_id, "comp-1", "merge", {"key": "new_val"})

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["params"]["operation"] == "merge"

    async def test_push_update_append_operation(self):
        """push_update with 'append' operation sends the correct message."""
        session_id = "sess-update-3"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_update(session_id, "comp-1", "append", {"item": "x"})

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["params"]["operation"] == "append"

    async def test_push_update_invalid_operation_raises(self):
        """push_update raises ValueError for an unknown operation."""
        with pytest.raises(ValueError, match="Invalid operation"):
            await a2ui_service.push_update("sess-x", "comp-x", "delete", {})

    async def test_push_update_oversized_payload_raises(self):
        """push_update raises ValueError when data exceeds 1 MB."""
        large_data = {"payload": "y" * (1024 * 1024 + 100)}
        with pytest.raises(ValueError, match="Payload exceeds maximum size"):
            await a2ui_service.push_update("sess-x", "comp-x", "replace", large_data)


# =============================================================================
# a2ui_service.request_input
# =============================================================================

class TestRequestInput:

    async def test_request_input_returns_user_value(self):
        """request_input resolves when the future is set with a user value."""
        session_id = "sess-input-1"
        expected_value = "user_answer_42"
        future = asyncio.get_event_loop().create_future()
        future.set_result(expected_value)

        mock_sm = MagicMock()
        mock_sm.set_pending_input.return_value = future
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):

            result = await a2ui_service.request_input(
                session_id,
                input_type="text",
                prompt="What is your name?",
                timeout=5.0,
            )

        assert result == expected_value

    async def test_request_input_sends_correct_message(self):
        """request_input sends a ui.request_input JSON-RPC notification."""
        session_id = "sess-input-2"
        future = asyncio.get_event_loop().create_future()
        future.set_result("done")

        mock_sm = MagicMock()
        mock_sm.set_pending_input.return_value = future
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):

            await a2ui_service.request_input(
                session_id,
                input_type="select",
                prompt="Pick one",
                options=["A", "B"],
                validation={"min_length": 1},
                timeout=5.0,
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["method"] == "ui.request_input"
        assert msg["params"]["input_type"] == "select"
        assert msg["params"]["options"] == ["A", "B"]
        assert msg["params"]["validation"] == {"min_length": 1}
        assert "request_id" in msg["params"]

    async def test_request_input_sanitizes_prompt(self):
        """request_input sanitizes HTML in the prompt before sending."""
        session_id = "sess-input-3"
        future = asyncio.get_event_loop().create_future()
        future.set_result("ok")

        mock_sm = MagicMock()
        mock_sm.set_pending_input.return_value = future
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):

            await a2ui_service.request_input(
                session_id,
                input_type="text",
                prompt="<script>alert('xss')</script>Enter name",
                timeout=5.0,
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        prompt = msg["params"]["prompt"]
        assert "<script>" not in prompt
        assert "alert" in prompt  # Content text preserved after tag strip

    async def test_request_input_timeout_raises(self):
        """request_input raises asyncio.TimeoutError when the future is not resolved."""
        session_id = "sess-input-4"
        future = asyncio.get_event_loop().create_future()
        # Do NOT resolve the future — simulates no user response

        mock_sm = MagicMock()
        mock_sm.set_pending_input.return_value = future
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):

            with pytest.raises(asyncio.TimeoutError):
                await a2ui_service.request_input(
                    session_id,
                    input_type="text",
                    prompt="Enter something",
                    timeout=0.05,  # Very short timeout
                )


# =============================================================================
# a2ui_service.request_confirm
# =============================================================================

class TestRequestConfirm:

    async def test_request_confirm_approved(self):
        """request_confirm resolves with an approval dict."""
        session_id = "sess-confirm-1"
        approval_result = {"approved": True, "reason": None}
        future = asyncio.get_event_loop().create_future()
        future.set_result(approval_result)

        mock_sm = MagicMock()
        mock_sm.set_pending_input.return_value = future
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):

            result = await a2ui_service.request_confirm(
                session_id,
                title="Confirm purchase",
                description="Are you sure?",
                timeout=5.0,
            )

        assert result["approved"] is True

    async def test_request_confirm_sends_correct_message(self):
        """request_confirm sends a ui.confirm JSON-RPC notification with correct params."""
        session_id = "sess-confirm-2"
        future = asyncio.get_event_loop().create_future()
        future.set_result({"approved": False, "reason": "No"})

        mock_sm = MagicMock()
        mock_sm.set_pending_input.return_value = future
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):

            await a2ui_service.request_confirm(
                session_id,
                title="Delete agent",
                description="This is irreversible",
                severity="danger",
                timeout=5.0,
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["method"] == "ui.confirm"
        params = msg["params"]
        assert params["severity"] == "danger"
        assert "timeout_seconds" in params
        assert isinstance(params["timeout_seconds"], int)
        assert "request_id" in params

    async def test_request_confirm_sanitizes_title_and_description(self):
        """request_confirm sanitizes HTML in title and description."""
        session_id = "sess-confirm-3"
        future = asyncio.get_event_loop().create_future()
        future.set_result({"approved": True, "reason": None})

        mock_sm = MagicMock()
        mock_sm.set_pending_input.return_value = future
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):

            await a2ui_service.request_confirm(
                session_id,
                title="<b>Bold Title</b>",
                description="<img src=x onerror=alert(1)>Description",
                timeout=5.0,
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        assert "<b>" not in msg["params"]["title"]
        assert "<img" not in msg["params"]["description"]

    async def test_request_confirm_timeout_raises(self):
        """request_confirm raises asyncio.TimeoutError when user never responds."""
        session_id = "sess-confirm-4"
        future = asyncio.get_event_loop().create_future()

        mock_sm = MagicMock()
        mock_sm.set_pending_input.return_value = future
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):

            with pytest.raises(asyncio.TimeoutError):
                await a2ui_service.request_confirm(
                    session_id,
                    title="Confirm",
                    timeout=0.05,
                )


# =============================================================================
# a2ui_service.push_progress
# =============================================================================

class TestPushProgress:

    async def test_push_progress_sends_ui_progress(self):
        """push_progress sends a ui.progress notification."""
        session_id = "sess-progress-1"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_progress(
                session_id,
                task_id="task-1",
                progress_type="percent",
                value=50.0,
                total=100.0,
                message="Half done",
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["method"] == "ui.progress"
        params = msg["params"]
        assert params["task_id"] == "task-1"
        assert params["progress_type"] == "percent"
        assert params["value"] == 50.0
        assert params["total"] == 100.0
        assert "Half done" in params["message"]

    async def test_push_progress_no_message(self):
        """push_progress handles message=None without error."""
        session_id = "sess-progress-2"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_progress(
                session_id,
                task_id="task-2",
                progress_type="indeterminate",
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["params"]["message"] is None

    async def test_push_progress_sanitizes_message(self):
        """push_progress sanitizes HTML in the message field."""
        session_id = "sess-progress-3"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_progress(
                session_id,
                task_id="task-3",
                progress_type="percent",
                message="<script>hack()</script>Processing",
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        assert "<script>" not in msg["params"]["message"]


# =============================================================================
# a2ui_service.push_navigate
# =============================================================================

class TestPushNavigate:

    async def test_push_navigate_sends_ui_navigate(self):
        """push_navigate sends a ui.navigate message with url and new_tab."""
        session_id = "sess-nav-1"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_navigate(session_id, url="https://example.com", new_tab=True)

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["method"] == "ui.navigate"
        assert msg["params"]["url"] == "https://example.com"
        assert msg["params"]["new_tab"] is True

    async def test_push_navigate_default_same_tab(self):
        """push_navigate defaults new_tab to False."""
        session_id = "sess-nav-2"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_navigate(session_id, url="https://app.example.com/page")

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["params"]["new_tab"] is False

    async def test_push_navigate_calls_correct_session(self):
        """push_navigate passes the correct session_id to the connection manager."""
        session_id = "sess-nav-specific"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_navigate(session_id, url="https://x.com")

        call_session_id = mock_cm.send_to_session.call_args[0][0]
        assert call_session_id == session_id


# =============================================================================
# a2ui_service.push_notify
# =============================================================================

class TestPushNotify:

    async def test_push_notify_sends_ui_notify(self):
        """push_notify sends a ui.notify message with all required fields."""
        session_id = "sess-notify-1"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_notify(
                session_id,
                level="success",
                title="Done!",
                message="Your order is complete.",
                duration_ms=3000,
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["method"] == "ui.notify"
        assert msg["params"]["level"] == "success"
        assert "Done" in msg["params"]["title"]
        assert msg["params"]["duration_ms"] == 3000

    async def test_push_notify_no_message(self):
        """push_notify handles message=None (body-less notification)."""
        session_id = "sess-notify-2"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_notify(session_id, level="info", title="Info")

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["params"]["message"] is None

    async def test_push_notify_sanitizes_title_and_message(self):
        """push_notify strips HTML from title and message."""
        session_id = "sess-notify-3"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_notify(
                session_id,
                level="warning",
                title="<marquee>Alert</marquee>",
                message="<a href='evil'>click</a> here",
            )

        msg = mock_cm.send_to_session.call_args[0][1]
        assert "<marquee>" not in msg["params"]["title"]
        assert "<a " not in msg["params"]["message"]

    async def test_push_notify_default_duration(self):
        """push_notify defaults duration_ms to 5000."""
        session_id = "sess-notify-4"
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await a2ui_service.push_notify(session_id, level="error", title="Oops")

        msg = mock_cm.send_to_session.call_args[0][1]
        assert msg["params"]["duration_ms"] == 5000


# =============================================================================
# a2ui_service.A2UIService class
# =============================================================================

class TestA2UIServiceClass:

    async def test_render_delegates_to_push_render(self):
        """A2UIService.render() delegates to push_render and returns component_id."""
        svc = a2ui_service.A2UIService()
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)
        mock_sm = MagicMock()
        mock_sm.get_session.return_value = None

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager", mock_sm):

            cid = await svc.render("sess-1", component_type="card", data={"x": 1})

        assert cid is not None

    async def test_update_delegates_to_push_update(self):
        """A2UIService.update() delegates to push_update."""
        svc = a2ui_service.A2UIService()
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await svc.update("sess-1", component_id="comp-1", operation="replace", data={"v": 1})

        mock_cm.send_to_session.assert_awaited_once()

    async def test_notify_delegates_to_push_notify(self):
        """A2UIService.notify() delegates to push_notify."""
        svc = a2ui_service.A2UIService()
        mock_cm = AsyncMock()
        mock_cm.send_to_session = AsyncMock(return_value=True)

        with patch("marketplace.services.a2ui_service.a2ui_connection_manager", mock_cm):
            await svc.notify("sess-1", level="info", title="Hello")

        mock_cm.send_to_session.assert_awaited_once()


# =============================================================================
# admin_dashboard_service.get_admin_overview
# =============================================================================

class TestGetAdminOverview:

    async def test_overview_empty_db(self, db: AsyncSession):
        """get_admin_overview returns zero counts on a fresh database."""
        result = await admin_dashboard_service.get_admin_overview(db)

        assert result["total_agents"] == 0
        assert result["active_agents"] == 0
        assert result["total_listings"] == 0
        assert result["active_listings"] == 0
        assert result["total_transactions"] == 0
        assert result["completed_transactions"] == 0
        assert result["platform_volume_usd"] == 0.0
        assert result["trust_weighted_revenue_usd"] == 0.0
        assert "environment" in result
        assert "updated_at" in result

    async def test_overview_counts_agents(self, db: AsyncSession, make_agent):
        """get_admin_overview reflects the correct agent counts."""
        await make_agent(name="agent-a")
        await make_agent(name="agent-b")
        result = await admin_dashboard_service.get_admin_overview(db)
        assert result["total_agents"] == 2
        assert result["active_agents"] == 2

    async def test_overview_counts_listings(self, db: AsyncSession, make_agent, make_listing):
        """get_admin_overview reflects the correct listing counts."""
        agent, _ = await make_agent()
        await make_listing(agent.id, status="active")
        await make_listing(agent.id, status="active")
        result = await admin_dashboard_service.get_admin_overview(db)
        assert result["total_listings"] == 2
        assert result["active_listings"] == 2

    async def test_overview_platform_volume_from_completed_txs(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_overview sums amount_usdc from completed transactions."""
        seller, _ = await make_agent(name="seller")
        buyer, _ = await make_agent(name="buyer")
        listing = await make_listing(seller.id, price_usdc=10.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0, status="completed")
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

        result = await admin_dashboard_service.get_admin_overview(db)
        assert result["platform_volume_usd"] == pytest.approx(15.0, abs=1e-5)
        assert result["completed_transactions"] == 2

    async def test_overview_excludes_pending_transactions(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_overview does not count pending transactions in volume."""
        seller, _ = await make_agent()
        buyer, _ = await make_agent()
        listing = await make_listing(seller.id, price_usdc=100.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=100.0, status="pending")

        result = await admin_dashboard_service.get_admin_overview(db)
        assert result["platform_volume_usd"] == 0.0
        assert result["completed_transactions"] == 0

    async def test_overview_trust_weighted_revenue_verified_secure(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """Trust-weighted revenue applies weight=1.0 for verified_secure_data listings."""
        from marketplace.models.listing import DataListing
        from sqlalchemy import select

        seller, _ = await make_agent()
        buyer, _ = await make_agent()
        listing = await make_listing(seller.id, price_usdc=20.0)

        # Update trust_status on listing
        result = await db.execute(select(DataListing).where(DataListing.id == listing.id))
        db_listing = result.scalar_one()
        db_listing.trust_status = "verified_secure_data"
        db.add(db_listing)
        await db.commit()

        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=20.0, status="completed")

        overview = await admin_dashboard_service.get_admin_overview(db)
        # Weight 1.0 for verified_secure_data => trust_weighted == platform_volume
        assert overview["trust_weighted_revenue_usd"] == pytest.approx(20.0, abs=1e-5)

    async def test_overview_returns_environment_field(self, db: AsyncSession):
        """get_admin_overview includes the environment from settings."""
        result = await admin_dashboard_service.get_admin_overview(db)
        assert isinstance(result["environment"], str)
        assert len(result["environment"]) > 0


# =============================================================================
# admin_dashboard_service.get_admin_finance
# =============================================================================

class TestGetAdminFinance:

    async def test_finance_empty_db(self, db: AsyncSession):
        """get_admin_finance returns zero values on a fresh database."""
        result = await admin_dashboard_service.get_admin_finance(db)

        assert result["platform_volume_usd"] == 0.0
        assert result["completed_transaction_count"] == 0
        assert result["consumer_orders_count"] == 0
        assert result["platform_fee_volume_usd"] == 0.0
        assert result["payout_pending_count"] == 0
        assert result["payout_pending_usd"] == 0.0
        assert result["payout_processing_count"] == 0
        assert result["payout_processing_usd"] == 0.0
        assert result["top_sellers_by_revenue"] == []
        assert "updated_at" in result

    async def test_finance_platform_volume(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_finance sums completed transaction amounts correctly."""
        seller, _ = await make_agent()
        buyer, _ = await make_agent()
        listing = await make_listing(seller.id, price_usdc=30.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=30.0, status="completed")
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=20.0, status="completed")

        result = await admin_dashboard_service.get_admin_finance(db)
        assert result["platform_volume_usd"] == pytest.approx(50.0, abs=1e-5)
        assert result["completed_transaction_count"] == 2

    async def test_finance_top_sellers_ranking(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_finance ranks sellers by revenue descending."""
        buyer, _ = await make_agent(name="buyer")
        seller_a, _ = await make_agent(name="seller-a")
        seller_b, _ = await make_agent(name="seller-b")

        listing_a = await make_listing(seller_a.id, price_usdc=100.0)
        listing_b = await make_listing(seller_b.id, price_usdc=50.0)

        await make_transaction(buyer.id, seller_a.id, listing_a.id, amount_usdc=100.0, status="completed")
        await make_transaction(buyer.id, seller_b.id, listing_b.id, amount_usdc=50.0, status="completed")

        result = await admin_dashboard_service.get_admin_finance(db)
        sellers = result["top_sellers_by_revenue"]
        assert len(sellers) == 2
        # Highest earner should be first
        assert sellers[0]["money_received_usd"] >= sellers[1]["money_received_usd"]
        assert sellers[0]["agent_id"] == seller_a.id

    async def test_finance_top_sellers_includes_name(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_finance populates agent_name for top sellers."""
        buyer, _ = await make_agent(name="buyer-agent")
        seller, _ = await make_agent(name="named-seller")
        listing = await make_listing(seller.id, price_usdc=10.0)
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=10.0, status="completed")

        result = await admin_dashboard_service.get_admin_finance(db)
        sellers = result["top_sellers_by_revenue"]
        assert any(s["agent_name"] == "named-seller" for s in sellers)

    async def test_finance_pending_payouts(self, db: AsyncSession, make_creator):
        """get_admin_finance counts pending redemption requests."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()

        req1 = RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="api_credits",
            amount_usd=D("25.0"),
            status="pending",
        )
        req2 = RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="bank_withdrawal",
            amount_usd=D("15.5"),
            status="pending",
        )
        db.add(req1)
        db.add(req2)
        await db.commit()

        result = await admin_dashboard_service.get_admin_finance(db)
        assert result["payout_pending_count"] == 2
        assert result["payout_pending_usd"] == pytest.approx(40.5, abs=1e-4)

    async def test_finance_processing_payouts(self, db: AsyncSession, make_creator):
        """get_admin_finance counts processing redemption requests separately."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()
        req = RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="upi",
            amount_usd=D("50.0"),
            status="processing",
        )
        db.add(req)
        await db.commit()

        result = await admin_dashboard_service.get_admin_finance(db)
        assert result["payout_processing_count"] == 1
        assert result["payout_processing_usd"] == pytest.approx(50.0, abs=1e-5)

    async def test_finance_platform_fees(self, db: AsyncSession, make_agent, make_listing, make_transaction):
        """get_admin_finance aggregates platform fee totals."""
        from marketplace.models.dual_layer import PlatformFee
        from decimal import Decimal as D

        seller, _ = await make_agent()
        buyer, _ = await make_agent()
        listing = await make_listing(seller.id, price_usdc=100.0)
        tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=100.0, status="completed")

        fee = PlatformFee(
            id=_new_id(),
            tx_id=tx.id,
            gross_usd=D("100.0"),
            fee_usd=D("5.0"),
            payout_usd=D("95.0"),
        )
        db.add(fee)
        await db.commit()

        result = await admin_dashboard_service.get_admin_finance(db)
        assert result["platform_fee_volume_usd"] == pytest.approx(5.0, abs=1e-5)


# =============================================================================
# admin_dashboard_service.get_admin_usage
# =============================================================================

class TestGetAdminUsage:

    async def test_usage_empty_db(self, db: AsyncSession):
        """get_admin_usage returns zeroes on a fresh database."""
        result = await admin_dashboard_service.get_admin_usage(db)

        assert result["info_used_count"] == 0
        assert result["data_served_bytes"] == 0
        assert result["unique_buyers_count"] == 0
        assert result["unique_sellers_count"] == 0
        assert result["money_saved_for_others_usd"] == 0.0
        assert result["category_breakdown"] == []
        assert "updated_at" in result

    async def test_usage_counts_info_used(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_usage counts all completed transactions as info_used_count."""
        seller, _ = await make_agent()
        buyer, _ = await make_agent()
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id, status="completed")
        await make_transaction(buyer.id, seller.id, listing.id, status="completed")

        result = await admin_dashboard_service.get_admin_usage(db)
        assert result["info_used_count"] == 2

    async def test_usage_data_served_bytes(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_usage sums content_size bytes from matched listings."""
        seller, _ = await make_agent()
        buyer, _ = await make_agent()
        listing = await make_listing(seller.id, content_size=5000)
        await make_transaction(buyer.id, seller.id, listing.id, status="completed")

        result = await admin_dashboard_service.get_admin_usage(db)
        assert result["data_served_bytes"] == 5000

    async def test_usage_unique_buyers_and_sellers(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_usage counts distinct buyer and seller IDs."""
        seller1, _ = await make_agent(name="s1")
        seller2, _ = await make_agent(name="s2")
        buyer1, _ = await make_agent(name="b1")
        buyer2, _ = await make_agent(name="b2")

        listing1 = await make_listing(seller1.id)
        listing2 = await make_listing(seller2.id)

        await make_transaction(buyer1.id, seller1.id, listing1.id, status="completed")
        await make_transaction(buyer2.id, seller2.id, listing2.id, status="completed")
        # buyer1 buys again from seller1 — should not double-count
        await make_transaction(buyer1.id, seller1.id, listing1.id, status="completed")

        result = await admin_dashboard_service.get_admin_usage(db)
        assert result["unique_buyers_count"] == 2
        assert result["unique_sellers_count"] == 2

    async def test_usage_category_breakdown(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_usage groups transactions by listing category."""
        seller, _ = await make_agent()
        buyer, _ = await make_agent()

        listing_ws = await make_listing(seller.id, category="web_search", price_usdc=5.0)
        listing_ml = await make_listing(seller.id, category="ml_models", price_usdc=10.0)

        await make_transaction(buyer.id, seller.id, listing_ws.id, amount_usdc=5.0, status="completed")
        await make_transaction(buyer.id, seller.id, listing_ml.id, amount_usdc=10.0, status="completed")

        result = await admin_dashboard_service.get_admin_usage(db)
        cats = {row["category"]: row for row in result["category_breakdown"]}

        assert "web_search" in cats
        assert "ml_models" in cats
        assert cats["web_search"]["usage_count"] == 1
        assert cats["ml_models"]["usage_count"] == 1

    async def test_usage_category_breakdown_sorted_by_usage(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """get_admin_usage sorts category_breakdown by usage_count descending."""
        seller, _ = await make_agent()
        buyer, _ = await make_agent()

        listing_ws = await make_listing(seller.id, category="web_search")
        listing_ml = await make_listing(seller.id, category="ml_models")

        # web_search used 3x, ml_models used 1x
        for _ in range(3):
            await make_transaction(buyer.id, seller.id, listing_ws.id, status="completed")
        await make_transaction(buyer.id, seller.id, listing_ml.id, status="completed")

        result = await admin_dashboard_service.get_admin_usage(db)
        breakdown = result["category_breakdown"]
        assert breakdown[0]["category"] == "web_search"
        assert breakdown[0]["usage_count"] == 3


# =============================================================================
# admin_dashboard_service.list_admin_agents
# =============================================================================

class TestListAdminAgents:

    async def test_list_agents_empty(self, db: AsyncSession):
        """list_admin_agents returns empty entries on a fresh database."""
        result = await admin_dashboard_service.list_admin_agents(db)
        assert result["total"] == 0
        assert result["page"] == 1
        assert result["page_size"] == 20
        assert result["entries"] == []

    async def test_list_agents_basic(self, db: AsyncSession, make_agent):
        """list_admin_agents returns entries for existing agents."""
        agent_a, _ = await make_agent(name="agent-alpha")
        agent_b, _ = await make_agent(name="agent-beta")

        result = await admin_dashboard_service.list_admin_agents(db)
        assert result["total"] == 2
        assert len(result["entries"]) == 2

    async def test_list_agents_entry_fields(self, db: AsyncSession, make_agent):
        """list_admin_agents entries contain all required fields."""
        await make_agent(name="test-agent")
        result = await admin_dashboard_service.list_admin_agents(db)
        entry = result["entries"][0]
        required_fields = [
            "agent_id", "agent_name", "status", "trust_status",
            "trust_tier", "trust_score", "money_received_usd",
            "info_used_count", "other_agents_served_count", "data_served_bytes",
        ]
        for field in required_fields:
            assert field in entry, f"Missing field: {field}"

    async def test_list_agents_filter_by_status(self, db: AsyncSession, make_agent):
        """list_admin_agents filters by status correctly."""
        from marketplace.models.agent import RegisteredAgent

        agent_active, _ = await make_agent(name="active-agent")
        agent_inactive, _ = await make_agent(name="inactive-agent")

        # Manually set one agent to inactive
        from sqlalchemy import select
        result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent_inactive.id)
        )
        db_agent = result.scalar_one()
        db_agent.status = "inactive"
        db.add(db_agent)
        await db.commit()

        result = await admin_dashboard_service.list_admin_agents(db, status="active")
        assert result["total"] == 1
        assert result["entries"][0]["status"] == "active"

    async def test_list_agents_pagination(self, db: AsyncSession, make_agent):
        """list_admin_agents respects page and page_size parameters."""
        for i in range(5):
            await make_agent(name=f"agent-{i}")

        page1 = await admin_dashboard_service.list_admin_agents(db, page=1, page_size=2)
        page2 = await admin_dashboard_service.list_admin_agents(db, page=2, page_size=2)

        assert page1["total"] == 5
        assert len(page1["entries"]) == 2
        assert len(page2["entries"]) == 2
        # Pages should not overlap
        ids_p1 = {e["agent_id"] for e in page1["entries"]}
        ids_p2 = {e["agent_id"] for e in page2["entries"]}
        assert ids_p1.isdisjoint(ids_p2)

    async def test_list_agents_trust_profile_used_when_present(
        self, db: AsyncSession, make_agent
    ):
        """list_admin_agents uses AgentTrustProfile data when it exists."""
        from marketplace.models.agent_trust import AgentTrustProfile

        agent, _ = await make_agent(name="trusted-agent")
        trust = AgentTrustProfile(
            id=_new_id(),
            agent_id=agent.id,
            trust_status="verified_secure_data",
            trust_tier="T3",
            trust_score=90,
        )
        db.add(trust)
        await db.commit()

        result = await admin_dashboard_service.list_admin_agents(db)
        entry = result["entries"][0]
        assert entry["trust_status"] == "verified_secure_data"
        assert entry["trust_tier"] == "T3"
        assert entry["trust_score"] == 90


# =============================================================================
# admin_dashboard_service.list_security_events
# =============================================================================

class TestListSecurityEvents:

    async def test_security_events_empty(self, db: AsyncSession):
        """list_security_events returns empty on a fresh database."""
        result = await admin_dashboard_service.list_security_events(db)
        assert result["total"] == 0
        assert result["events"] == []
        assert result["page"] == 1
        assert result["page_size"] == 50

    async def test_security_events_basic(self, db: AsyncSession):
        """list_security_events returns all audit log entries."""
        from marketplace.models.audit_log import AuditLog
        from datetime import datetime, timezone

        log1 = AuditLog(
            id=_new_id(),
            event_type="login_failed",
            severity="warning",
            agent_id="agent-1",
        )
        log2 = AuditLog(
            id=_new_id(),
            event_type="rate_limit_exceeded",
            severity="info",
        )
        db.add(log1)
        db.add(log2)
        await db.commit()

        result = await admin_dashboard_service.list_security_events(db)
        assert result["total"] == 2
        assert len(result["events"]) == 2

    async def test_security_events_entry_fields(self, db: AsyncSession):
        """list_security_events entries contain all required fields."""
        from marketplace.models.audit_log import AuditLog

        db.add(AuditLog(
            id=_new_id(),
            event_type="test_event",
            severity="info",
            agent_id="agent-x",
            ip_address="127.0.0.1",
            details="{}",
        ))
        await db.commit()

        result = await admin_dashboard_service.list_security_events(db)
        event = result["events"][0]
        for field in ["id", "event_type", "severity", "agent_id", "creator_id", "ip_address", "details", "created_at"]:
            assert field in event, f"Missing field: {field}"

    async def test_security_events_filter_by_severity(self, db: AsyncSession):
        """list_security_events filters by severity correctly."""
        from marketplace.models.audit_log import AuditLog

        db.add(AuditLog(id=_new_id(), event_type="e1", severity="critical"))
        db.add(AuditLog(id=_new_id(), event_type="e2", severity="info"))
        db.add(AuditLog(id=_new_id(), event_type="e3", severity="critical"))
        await db.commit()

        result = await admin_dashboard_service.list_security_events(db, severity="critical")
        assert result["total"] == 2
        assert all(e["severity"] == "critical" for e in result["events"])

    async def test_security_events_filter_by_event_type(self, db: AsyncSession):
        """list_security_events filters by event_type correctly."""
        from marketplace.models.audit_log import AuditLog

        db.add(AuditLog(id=_new_id(), event_type="login_failed", severity="warning"))
        db.add(AuditLog(id=_new_id(), event_type="payment_failed", severity="warning"))
        db.add(AuditLog(id=_new_id(), event_type="login_failed", severity="info"))
        await db.commit()

        result = await admin_dashboard_service.list_security_events(db, event_type="login_failed")
        assert result["total"] == 2
        assert all(e["event_type"] == "login_failed" for e in result["events"])

    async def test_security_events_pagination(self, db: AsyncSession):
        """list_security_events respects page and page_size parameters."""
        from marketplace.models.audit_log import AuditLog

        for i in range(10):
            db.add(AuditLog(id=_new_id(), event_type=f"event-{i}", severity="info"))
        await db.commit()

        page1 = await admin_dashboard_service.list_security_events(db, page=1, page_size=4)
        page2 = await admin_dashboard_service.list_security_events(db, page=2, page_size=4)

        assert page1["total"] == 10
        assert len(page1["events"]) == 4
        assert len(page2["events"]) == 4

        ids_p1 = {e["id"] for e in page1["events"]}
        ids_p2 = {e["id"] for e in page2["events"]}
        assert ids_p1.isdisjoint(ids_p2)

    async def test_security_events_details_parsed_as_dict(self, db: AsyncSession):
        """list_security_events parses JSON details into a dict."""
        import json
        from marketplace.models.audit_log import AuditLog

        details = json.dumps({"action": "blocked", "count": 5})
        db.add(AuditLog(
            id=_new_id(),
            event_type="suspicious_activity",
            severity="warning",
            details=details,
        ))
        await db.commit()

        result = await admin_dashboard_service.list_security_events(db)
        event = result["events"][0]
        assert isinstance(event["details"], dict)
        assert event["details"]["action"] == "blocked"
        assert event["details"]["count"] == 5

    async def test_security_events_combined_filters(self, db: AsyncSession):
        """list_security_events correctly combines severity and event_type filters."""
        from marketplace.models.audit_log import AuditLog

        db.add(AuditLog(id=_new_id(), event_type="login_failed", severity="critical"))
        db.add(AuditLog(id=_new_id(), event_type="login_failed", severity="info"))
        db.add(AuditLog(id=_new_id(), event_type="payment_failed", severity="critical"))
        await db.commit()

        result = await admin_dashboard_service.list_security_events(
            db, severity="critical", event_type="login_failed"
        )
        assert result["total"] == 1
        assert result["events"][0]["event_type"] == "login_failed"
        assert result["events"][0]["severity"] == "critical"


# =============================================================================
# admin_dashboard_service.list_pending_payouts
# =============================================================================

class TestListPendingPayouts:

    async def test_pending_payouts_empty(self, db: AsyncSession):
        """list_pending_payouts returns zero count on a fresh database."""
        result = await admin_dashboard_service.list_pending_payouts(db)
        assert result["count"] == 0
        assert result["total_pending_usd"] == 0.0
        assert result["requests"] == []

    async def test_pending_payouts_basic(self, db: AsyncSession, make_creator):
        """list_pending_payouts returns all pending redemption requests."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()
        req = RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="api_credits",
            amount_usd=D("10.0"),
            status="pending",
        )
        db.add(req)
        await db.commit()

        result = await admin_dashboard_service.list_pending_payouts(db)
        assert result["count"] == 1
        assert result["total_pending_usd"] == pytest.approx(10.0, abs=1e-5)

    async def test_pending_payouts_total_sum(self, db: AsyncSession, make_creator):
        """list_pending_payouts sums all pending request amounts."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()
        for amount in ["20.0", "15.5", "9.25"]:
            db.add(RedemptionRequest(
                id=_new_id(),
                creator_id=creator.id,
                redemption_type="bank_withdrawal",
                amount_usd=D(amount),
                status="pending",
            ))
        await db.commit()

        result = await admin_dashboard_service.list_pending_payouts(db)
        assert result["count"] == 3
        assert result["total_pending_usd"] == pytest.approx(44.75, abs=1e-4)

    async def test_pending_payouts_excludes_non_pending(self, db: AsyncSession, make_creator):
        """list_pending_payouts excludes completed and processing requests."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()
        db.add(RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="upi",
            amount_usd=D("50.0"),
            status="completed",
        ))
        db.add(RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="upi",
            amount_usd=D("30.0"),
            status="processing",
        ))
        db.add(RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="api_credits",
            amount_usd=D("5.0"),
            status="pending",
        ))
        await db.commit()

        result = await admin_dashboard_service.list_pending_payouts(db)
        assert result["count"] == 1
        assert result["total_pending_usd"] == pytest.approx(5.0, abs=1e-5)

    async def test_pending_payouts_request_fields(self, db: AsyncSession, make_creator):
        """list_pending_payouts request entries have all required fields."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()
        db.add(RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="gift_card",
            amount_usd=D("25.0"),
            currency="USD",
            status="pending",
        ))
        await db.commit()

        result = await admin_dashboard_service.list_pending_payouts(db)
        req = result["requests"][0]
        for field in ["id", "creator_id", "redemption_type", "amount_usd", "currency", "status", "created_at"]:
            assert field in req, f"Missing field: {field}"

    async def test_pending_payouts_respects_limit(self, db: AsyncSession, make_creator):
        """list_pending_payouts respects the limit parameter."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()
        for i in range(10):
            db.add(RedemptionRequest(
                id=_new_id(),
                creator_id=creator.id,
                redemption_type="api_credits",
                amount_usd=D("1.0"),
                status="pending",
            ))
        await db.commit()

        result = await admin_dashboard_service.list_pending_payouts(db, limit=3)
        assert result["count"] == 3

    async def test_pending_payouts_limit_capped_at_500(self, db: AsyncSession, make_creator):
        """list_pending_payouts caps the limit at 500 (max 1, min with 500)."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()
        # Create 5 requests; request limit=1000 — should be capped at 500 internally
        for i in range(5):
            db.add(RedemptionRequest(
                id=_new_id(),
                creator_id=creator.id,
                redemption_type="bank_withdrawal",
                amount_usd=D("1.0"),
                status="pending",
            ))
        await db.commit()

        # limit=1000 should not crash; capped internally to 500
        result = await admin_dashboard_service.list_pending_payouts(db, limit=1000)
        assert result["count"] == 5  # Only 5 exist, so all returned

    async def test_pending_payouts_created_at_is_isoformat_or_none(
        self, db: AsyncSession, make_creator
    ):
        """list_pending_payouts serializes created_at as ISO string or None."""
        from marketplace.models.redemption import RedemptionRequest
        from decimal import Decimal as D

        creator, _ = await make_creator()
        db.add(RedemptionRequest(
            id=_new_id(),
            creator_id=creator.id,
            redemption_type="api_credits",
            amount_usd=D("5.0"),
            status="pending",
        ))
        await db.commit()

        result = await admin_dashboard_service.list_pending_payouts(db)
        created_at = result["requests"][0]["created_at"]
        # Should be an ISO-format string or None
        assert created_at is None or isinstance(created_at, str)
