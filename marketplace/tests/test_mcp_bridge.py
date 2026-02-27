"""Tests for A2UI MCP bridge — MCP tool executions trigger UI updates.

Covers:
  - push_tool_execution_start: session active, session missing (tests 1-2)
  - push_tool_execution_result: progress + render, missing session (tests 3-4)
  - push_tool_execution_error: progress + notify, missing session (tests 5-6)
  - push_resource_read_result: render card, missing session (tests 7-8)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.a2ui.mcp_bridge import (
    push_tool_execution_start,
    push_tool_execution_result,
    push_tool_execution_error,
    push_resource_read_result,
)


def _mock_session():
    """Return a mock A2UISession object."""
    session = MagicMock()
    session.session_id = "test-sess"
    session.agent_id = "test-agent"
    return session


class TestPushToolExecutionStart:
    """Tests 1-2: tool execution start notifications."""

    # 1
    async def test_start_returns_task_id_when_session_active(self):
        """Should return a UUID task_id and push progress."""
        with (
            patch(
                "marketplace.a2ui.mcp_bridge.a2ui_session_manager"
            ) as mock_mgr,
            patch(
                "marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock
            ) as mock_progress,
        ):
            mock_mgr.get_session.return_value = _mock_session()

            task_id = await push_tool_execution_start(
                "sess-1", "search_tool", {"query": "test"}
            )

            assert task_id is not None
            assert len(task_id) == 36  # UUID format
            mock_progress.assert_called_once()
            call_kwargs = mock_progress.call_args
            assert call_kwargs[1]["progress_type"] == "indeterminate"
            assert "search_tool" in call_kwargs[1]["message"]

    # 2
    async def test_start_returns_none_when_session_missing(self):
        """Should return None if session does not exist."""
        with patch(
            "marketplace.a2ui.mcp_bridge.a2ui_session_manager"
        ) as mock_mgr:
            mock_mgr.get_session.return_value = None

            task_id = await push_tool_execution_start(
                "no-sess", "tool", {"arg": "val"}
            )

            assert task_id is None


class TestPushToolExecutionResult:
    """Tests 3-4: tool execution result rendering."""

    # 3
    async def test_result_pushes_progress_and_render(self):
        """Should complete progress and render tool result."""
        with (
            patch(
                "marketplace.a2ui.mcp_bridge.a2ui_session_manager"
            ) as mock_mgr,
            patch(
                "marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock
            ) as mock_progress,
            patch(
                "marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock
            ) as mock_render,
        ):
            mock_mgr.get_session.return_value = _mock_session()
            mock_render.return_value = "comp-id-1"

            component_id = await push_tool_execution_result(
                "sess-3", "task-3", "search_tool", {"results": [1, 2, 3]}
            )

            assert component_id == "comp-id-1"
            # Progress should be determinate at 1/1
            progress_kwargs = mock_progress.call_args
            assert progress_kwargs[1]["value"] == 1
            assert progress_kwargs[1]["total"] == 1
            assert "Completed" in progress_kwargs[1]["message"]
            # Render should be a code component
            render_args = mock_render.call_args
            assert render_args[0][1] == "code"
            assert render_args[0][2]["source"] == "mcp_tool"

    # 4
    async def test_result_returns_none_when_session_missing(self):
        """Should return None if session does not exist."""
        with patch(
            "marketplace.a2ui.mcp_bridge.a2ui_session_manager"
        ) as mock_mgr:
            mock_mgr.get_session.return_value = None

            result = await push_tool_execution_result(
                "no-sess", "task-x", "tool", {"data": "val"}
            )

            assert result is None


class TestPushToolExecutionError:
    """Tests 5-6: tool execution error notifications."""

    # 5
    async def test_error_pushes_progress_and_notify(self):
        """Should push failed progress and error notification."""
        with (
            patch(
                "marketplace.a2ui.mcp_bridge.a2ui_session_manager"
            ) as mock_mgr,
            patch(
                "marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock
            ) as mock_progress,
            patch(
                "marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock
            ) as mock_notify,
        ):
            mock_mgr.get_session.return_value = _mock_session()

            await push_tool_execution_error(
                "sess-5", "task-5", "broken_tool", "Connection refused"
            )

            # Progress should indicate failure
            progress_kwargs = mock_progress.call_args
            assert "Failed" in progress_kwargs[1]["message"]
            # Notify should be error level
            mock_notify.assert_called_once_with(
                "sess-5", "error", "Tool failed: broken_tool", "Connection refused"
            )

    # 6
    async def test_error_returns_none_when_session_missing(self):
        """Should return early (None) if session does not exist."""
        with patch(
            "marketplace.a2ui.mcp_bridge.a2ui_session_manager"
        ) as mock_mgr:
            mock_mgr.get_session.return_value = None

            # Should not raise
            result = await push_tool_execution_error(
                "no-sess", "task-x", "tool", "error msg"
            )

            assert result is None


class TestPushResourceReadResult:
    """Tests 7-8: MCP resource read rendering."""

    # 7
    async def test_resource_read_renders_card(self):
        """Should render a card component with resource data."""
        with (
            patch(
                "marketplace.a2ui.mcp_bridge.a2ui_session_manager"
            ) as mock_mgr,
            patch(
                "marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock
            ) as mock_render,
        ):
            mock_mgr.get_session.return_value = _mock_session()
            mock_render.return_value = "comp-7"

            component_id = await push_resource_read_result(
                "sess-7", "resource://agents/list", {"agents": ["a1"]}
            )

            assert component_id == "comp-7"
            render_args = mock_render.call_args
            assert render_args[0][1] == "card"
            data = render_args[0][2]
            assert "resource://agents/list" in data["title"]
            assert data["source"] == "mcp_resource"
            assert render_args[1]["metadata"]["mcp_resource_uri"] == "resource://agents/list"

    # 8
    async def test_resource_read_returns_none_when_session_missing(self):
        """Should return None if session does not exist."""
        with patch(
            "marketplace.a2ui.mcp_bridge.a2ui_session_manager"
        ) as mock_mgr:
            mock_mgr.get_session.return_value = None

            result = await push_resource_read_result(
                "no-sess", "resource://x", {"data": "val"}
            )

            assert result is None
