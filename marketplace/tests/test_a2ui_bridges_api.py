"""Comprehensive tests for A2UI bridges, service, models, and API routes.

Covers:
- A2ABridge (A2A pipeline events -> A2UI protocol)
- MCP Bridge (MCP tool execution -> A2UI protocol)
- A2UI Service (push_render, request_input, push_progress, etc.)
- A2UI Models (A2UISessionLog, A2UIConsentRecord)
- V4 A2UI API Routes (stream-token, sessions, health)
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# TestA2ABridge — A2A pipeline bridge to A2UI protocol
# ---------------------------------------------------------------------------

class TestA2ABridge:
    """Tests for marketplace.a2ui.a2a_bridge.A2ABridge."""

    def test_bridge_initialization_stores_session_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-abc-123")
        assert bridge._session_id == "sess-abc-123"

    def test_bridge_initialization_with_uuid_session(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        sid = str(uuid.uuid4())
        bridge = A2ABridge(session_id=sid)
        assert bridge._session_id == sid

    def test_bridge_initialization_with_empty_session_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="")
        assert bridge._session_id == ""

    @pytest.mark.asyncio
    async def test_on_pipeline_start_calls_push_render_and_push_progress(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-1")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_pipeline_start("pipe-1", ["step_a", "step_b"])

            mock_render.assert_called_once()
            call_kwargs = mock_render.call_args
            assert call_kwargs[0][0] == "sess-1"
            assert call_kwargs[1]["component_type"] == "steps"
            assert call_kwargs[1]["data"]["pipeline_id"] == "pipe-1"
            assert len(call_kwargs[1]["data"]["steps"]) == 2
            assert call_kwargs[1]["data"]["steps"][0]["status"] == "pending"
            assert call_kwargs[1]["metadata"]["source"] == "a2a_pipeline"

            mock_progress.assert_called_once()
            prog_kwargs = mock_progress.call_args
            assert prog_kwargs[0][0] == "sess-1"
            assert prog_kwargs[1]["task_id"] == "pipe-1"
            assert prog_kwargs[1]["progress_type"] == "indeterminate"

    @pytest.mark.asyncio
    async def test_on_pipeline_start_steps_data_structure(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-2")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-2", ["extract", "transform", "load"])

            data = mock_render.call_args[1]["data"]
            assert data["current_step"] == 0
            assert data["steps"][1]["name"] == "transform"
            assert all(s["status"] == "pending" for s in data["steps"])

    @pytest.mark.asyncio
    async def test_on_step_start_sends_determinate_progress(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-3")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_step_start("pipe-3", step_index=2, step_name="validate")

            mock_progress.assert_called_once()
            kw = mock_progress.call_args
            assert kw[0][0] == "sess-3"
            assert kw[1]["task_id"] == "pipe-3"
            assert kw[1]["progress_type"] == "determinate"
            assert kw[1]["value"] == 2
            assert "validate" in kw[1]["message"]

    @pytest.mark.asyncio
    async def test_on_step_complete_pushes_merge_update(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-4")
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-4", step_index=1, step_name="fetch", result={"key": "val"})

            mock_update.assert_called_once()
            kw = mock_update.call_args
            assert kw[0][0] == "sess-4"
            assert kw[1]["component_id"] == "pipeline-pipe-4"
            assert kw[1]["operation"] == "merge"
            assert 1 in kw[1]["data"]["steps"]
            assert kw[1]["data"]["steps"][1]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_on_step_complete_truncates_result_preview(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-5")
        long_result = "x" * 500
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-5", 0, "proc", long_result)

            data = mock_update.call_args[1]["data"]
            preview = data["steps"][0]["result_preview"]
            assert len(preview) <= 200

    @pytest.mark.asyncio
    async def test_on_step_failed_sends_error_notification(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-6")
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-6", 0, "download", "Connection timeout")

            mock_notify.assert_called_once()
            kw = mock_notify.call_args
            assert kw[0][0] == "sess-6"
            assert kw[1]["level"] == "error"
            assert "download" in kw[1]["title"]
            assert kw[1]["message"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_on_step_failed_truncates_long_error_message(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-7")
        long_error = "E" * 500
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-7", 0, "parse", long_error)

            msg = mock_notify.call_args[1]["message"]
            assert len(msg) <= 300

    @pytest.mark.asyncio
    async def test_on_pipeline_complete_sends_progress_and_render(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-8")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-8", {"summary": "done"})

            mock_progress.assert_called_once()
            pk = mock_progress.call_args[1]
            assert pk["value"] == 100
            assert pk["total"] == 100
            assert pk["message"] == "Pipeline completed"

            mock_render.assert_called_once()
            rk = mock_render.call_args
            assert rk[1]["component_type"] == "card"
            assert rk[1]["data"]["title"] == "Pipeline Complete"
            assert rk[1]["metadata"]["pipeline_id"] == "pipe-8"

    @pytest.mark.asyncio
    async def test_on_pipeline_complete_with_none_result(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-9")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-9", None)

            data = mock_render.call_args[1]["data"]
            assert data["content"] == "No output"

    @pytest.mark.asyncio
    async def test_on_pipeline_complete_truncates_long_result(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-10")
        huge_result = "R" * 1000
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-10", huge_result)

            content = mock_render.call_args[1]["data"]["content"]
            assert len(content) <= 500

    @pytest.mark.asyncio
    async def test_request_human_approval_calls_confirm(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-11")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True
            result = await bridge.request_human_approval("pipe-11", "deploy", "Deploy to production?")

            assert result is True
            mock_confirm.assert_called_once()
            kw = mock_confirm.call_args
            assert kw[0][0] == "sess-11"
            assert "deploy" in kw[1]["title"]
            assert kw[1]["description"] == "Deploy to production?"
            assert kw[1]["severity"] == "warning"
            assert kw[1]["timeout"] == 120

    @pytest.mark.asyncio
    async def test_request_human_approval_returns_false_when_denied(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-12")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = False
            result = await bridge.request_human_approval("pipe-12", "delete", "Delete all data?")
            assert result is False

    @pytest.mark.asyncio
    async def test_pipeline_start_message_includes_step_count(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge(session_id="sess-13")
        steps = ["a", "b", "c", "d", "e"]
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_pipeline_start("pipe-13", steps)

            msg = mock_progress.call_args[1]["message"]
            assert "5" in msg


# ---------------------------------------------------------------------------
# TestMCPBridge — MCP tool execution to A2UI protocol
# ---------------------------------------------------------------------------

class TestMCPBridge:
    """Tests for marketplace.a2ui.mcp_bridge functions."""

    @pytest.mark.asyncio
    async def test_push_tool_execution_start_returns_task_id(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()

            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            task_id = await push_tool_execution_start("sess-1", "read_file", {"path": "/tmp"})

            assert task_id is not None
            # Should be a valid UUID
            uuid.UUID(task_id)

    @pytest.mark.asyncio
    async def test_push_tool_execution_start_returns_none_for_missing_session(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None

            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            result = await push_tool_execution_start("no-sess", "tool", {})

            assert result is None

    @pytest.mark.asyncio
    async def test_push_tool_execution_start_sends_indeterminate_progress(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress:
            mock_mgr.get_session.return_value = MagicMock()

            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            await push_tool_execution_start("sess-2", "search", {"query": "test"})

            mock_progress.assert_called_once()
            kw = mock_progress.call_args
            assert kw[0][0] == "sess-2"
            assert kw[1]["progress_type"] == "indeterminate"
            assert "search" in kw[1]["message"]

    @pytest.mark.asyncio
    async def test_push_tool_execution_result_returns_component_id(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            mock_render.return_value = "comp-xyz"

            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            cid = await push_tool_execution_result("sess-3", "task-1", "read_file", {"data": "ok"})

            assert cid == "comp-xyz"

    @pytest.mark.asyncio
    async def test_push_tool_execution_result_returns_none_for_missing_session(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None

            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            result = await push_tool_execution_result("no-sess", "task-1", "tool", {})

            assert result is None

    @pytest.mark.asyncio
    async def test_push_tool_execution_result_completes_progress(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()

            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-4", "task-2", "search", {"results": []})

            mock_progress.assert_called_once()
            kw = mock_progress.call_args
            assert kw[1]["value"] == 1
            assert kw[1]["total"] == 1
            assert "Completed" in kw[1]["message"]

    @pytest.mark.asyncio
    async def test_push_tool_execution_result_renders_code_component(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()

            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-5", "task-3", "exec_code", {"output": "42"})

            mock_render.assert_called_once()
            args = mock_render.call_args
            assert args[0][1] == "code"
            assert args[0][2]["source"] == "mcp_tool"
            assert args[1]["metadata"]["mcp_tool"] == "exec_code"

    @pytest.mark.asyncio
    async def test_push_tool_execution_error_sends_notification(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock) as mock_notify:
            mock_mgr.get_session.return_value = MagicMock()

            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-6", "task-4", "run_sql", "syntax error")

            mock_notify.assert_called_once()
            assert mock_notify.call_args[0][1] == "error"
            assert "run_sql" in mock_notify.call_args[0][2]
            assert mock_notify.call_args[0][3] == "syntax error"

    @pytest.mark.asyncio
    async def test_push_tool_execution_error_noop_for_missing_session(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None

            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            # Should not raise
            await push_tool_execution_error("no-sess", "task-5", "tool", "err")

    @pytest.mark.asyncio
    async def test_push_tool_execution_error_completes_progress_as_failed(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()

            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-7", "task-6", "api_call", "timeout")

            mock_progress.assert_called_once()
            kw = mock_progress.call_args
            assert kw[1]["value"] == 1
            assert kw[1]["total"] == 1
            assert "Failed" in kw[1]["message"]

    @pytest.mark.asyncio
    async def test_push_resource_read_result_returns_component_id(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            mock_render.return_value = "comp-res-1"

            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            cid = await push_resource_read_result("sess-8", "file:///data.json", {"key": "val"})

            assert cid == "comp-res-1"

    @pytest.mark.asyncio
    async def test_push_resource_read_result_returns_none_for_missing_session(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None

            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            result = await push_resource_read_result("no-sess", "file:///x", {})

            assert result is None

    @pytest.mark.asyncio
    async def test_push_resource_read_result_renders_card_component(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()

            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("sess-9", "db://users/1", {"name": "Alice"})

            mock_render.assert_called_once()
            args = mock_render.call_args
            assert args[0][1] == "card"
            assert args[0][2]["source"] == "mcp_resource"
            assert "db://users/1" in args[0][2]["title"]
            assert args[1]["metadata"]["mcp_resource_uri"] == "db://users/1"

    @pytest.mark.asyncio
    async def test_push_resource_read_result_content_passthrough(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            content = {"rows": [1, 2, 3], "total": 3}

            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("sess-10", "sql://query", content)

            assert mock_render.call_args[0][2]["content"] == content

    @pytest.mark.asyncio
    async def test_push_tool_execution_result_metadata_has_task_id(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()

            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-11", "task-99", "my_tool", {})

            metadata = mock_render.call_args[1]["metadata"]
            assert metadata["task_id"] == "task-99"
            assert metadata["mcp_tool"] == "my_tool"


# ---------------------------------------------------------------------------
# TestA2UIService — High-level A2UI service functions
# ---------------------------------------------------------------------------

class TestA2UIService:
    """Tests for marketplace.services.a2ui_service functions."""

    def test_build_jsonrpc_notification_structure(self):
        from marketplace.services.a2ui_service import _build_jsonrpc_notification

        msg = _build_jsonrpc_notification("ui.render", {"foo": "bar"})
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "ui.render"
        assert msg["params"] == {"foo": "bar"}
        assert "id" not in msg

    def test_build_jsonrpc_notification_no_id_field(self):
        from marketplace.services.a2ui_service import _build_jsonrpc_notification

        msg = _build_jsonrpc_notification("ui.progress", {})
        assert "id" not in msg

    @pytest.mark.asyncio
    async def test_push_render_returns_component_id(self):
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=True), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn:
            mock_session = MagicMock()
            mock_session.active_components = set()
            mock_mgr.get_session.return_value = mock_session
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_render
            cid = await push_render("sess-1", "card", {"title": "Hello"})

            assert cid is not None
            uuid.UUID(cid)  # Must be valid UUID

    @pytest.mark.asyncio
    async def test_push_render_adds_to_active_components(self):
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=True), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn:
            active = set()
            mock_session = MagicMock()
            mock_session.active_components = active
            mock_mgr.get_session.return_value = mock_session
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_render
            cid = await push_render("sess-2", "steps", {"data": 1})

            assert cid in active

    @pytest.mark.asyncio
    async def test_push_render_raises_on_oversized_payload(self):
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=False), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager"), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager"):
            from marketplace.services.a2ui_service import push_render

            with pytest.raises(ValueError, match="maximum size"):
                await push_render("sess-3", "card", {"data": "huge"})

    @pytest.mark.asyncio
    async def test_push_render_sends_jsonrpc_message(self):
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=True), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn:
            mock_mgr.get_session.return_value = MagicMock(active_components=set())
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_render
            await push_render("sess-4", "table", {"rows": []}, metadata={"src": "test"})

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["jsonrpc"] == "2.0"
            assert sent["method"] == "ui.render"
            assert sent["params"]["component_type"] == "table"
            assert sent["params"]["metadata"]["src"] == "test"

    @pytest.mark.asyncio
    async def test_push_update_valid_operations(self):
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=True), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn:
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_update

            for op in ("replace", "merge", "append"):
                await push_update("sess-5", "comp-1", op, {"field": "value"})

            assert mock_conn.send_to_session.call_count == 3

    @pytest.mark.asyncio
    async def test_push_update_rejects_invalid_operation(self):
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=True), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager"):
            from marketplace.services.a2ui_service import push_update

            with pytest.raises(ValueError, match="Invalid operation"):
                await push_update("sess-6", "comp-1", "delete", {})

    @pytest.mark.asyncio
    async def test_push_update_rejects_oversized_payload(self):
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=False), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager"):
            from marketplace.services.a2ui_service import push_update

            with pytest.raises(ValueError, match="maximum size"):
                await push_update("sess-7", "comp-1", "merge", {"big": "data"})

    @pytest.mark.asyncio
    async def test_push_update_sends_correct_message(self):
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=True), \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn:
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_update
            await push_update("sess-8", "comp-2", "replace", {"text": "new"})

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["method"] == "ui.update"
            assert sent["params"]["component_id"] == "comp-2"
            assert sent["params"]["operation"] == "replace"

    @pytest.mark.asyncio
    async def test_request_input_sends_message_and_returns_future_result(self):
        with patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            future.set_result("user typed this")
            mock_mgr.set_pending_input.return_value = future
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import request_input
            result = await request_input("sess-9", "text", "Enter name:", timeout=5)

            assert result == "user typed this"
            mock_conn.send_to_session.assert_called_once()
            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["method"] == "ui.request_input"
            assert sent["params"]["input_type"] == "text"
            assert sent["params"]["prompt"] == "Enter name:"

    @pytest.mark.asyncio
    async def test_request_input_includes_options_and_validation(self):
        with patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            future.set_result("option_a")
            mock_mgr.set_pending_input.return_value = future
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import request_input
            await request_input(
                "sess-10", "select", "Choose:",
                options=["a", "b"], validation={"required": True}, timeout=10,
            )

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["params"]["options"] == ["a", "b"]
            assert sent["params"]["validation"] == {"required": True}

    @pytest.mark.asyncio
    async def test_request_input_timeout_raises(self):
        with patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            loop = asyncio.get_running_loop()
            future = loop.create_future()  # Never resolved
            mock_mgr.set_pending_input.return_value = future
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import request_input

            with pytest.raises(asyncio.TimeoutError):
                await request_input("sess-11", "text", "Quick:", timeout=0.01)

    @pytest.mark.asyncio
    async def test_request_confirm_sends_confirm_message(self):
        with patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            future.set_result({"approved": True, "reason": None})
            mock_mgr.set_pending_input.return_value = future
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import request_confirm
            result = await request_confirm("sess-12", "Delete item?", "Permanent action", severity="warning")

            assert result["approved"] is True
            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["method"] == "ui.confirm"
            assert sent["params"]["title"] == "Delete item?"
            assert sent["params"]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_request_confirm_timeout_raises(self):
        with patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            mock_mgr.set_pending_input.return_value = future
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import request_confirm

            with pytest.raises(asyncio.TimeoutError):
                await request_confirm("sess-13", "Approve?", timeout=0.01)

    @pytest.mark.asyncio
    async def test_push_progress_sends_correct_message(self):
        with patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_progress
            await push_progress("sess-14", "task-1", "determinate", value=50, total=100, message="Half done")

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["method"] == "ui.progress"
            assert sent["params"]["task_id"] == "task-1"
            assert sent["params"]["progress_type"] == "determinate"
            assert sent["params"]["value"] == 50
            assert sent["params"]["total"] == 100
            assert sent["params"]["message"] == "Half done"

    @pytest.mark.asyncio
    async def test_push_progress_with_none_message(self):
        with patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_progress
            await push_progress("sess-15", "task-2", "indeterminate")

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["params"]["message"] is None
            assert sent["params"]["value"] is None

    @pytest.mark.asyncio
    async def test_push_navigate_sends_url(self):
        with patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn:
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_navigate
            await push_navigate("sess-16", "https://example.com", new_tab=True)

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["method"] == "ui.navigate"
            assert sent["params"]["url"] == "https://example.com"
            assert sent["params"]["new_tab"] is True

    @pytest.mark.asyncio
    async def test_push_navigate_defaults_same_tab(self):
        with patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn:
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_navigate
            await push_navigate("sess-17", "/dashboard")

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["params"]["new_tab"] is False

    @pytest.mark.asyncio
    async def test_push_notify_sends_toast(self):
        with patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_notify
            await push_notify("sess-18", "success", "Saved!", "Your data was saved.", duration_ms=3000)

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["method"] == "ui.notify"
            assert sent["params"]["level"] == "success"
            assert sent["params"]["title"] == "Saved!"
            assert sent["params"]["message"] == "Your data was saved."
            assert sent["params"]["duration_ms"] == 3000

    @pytest.mark.asyncio
    async def test_push_notify_with_none_message(self):
        with patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_notify
            await push_notify("sess-19", "info", "Heads up")

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["params"]["message"] is None

    @pytest.mark.asyncio
    async def test_push_notify_default_duration(self):
        with patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_notify
            await push_notify("sess-20", "warning", "Watch out")

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["params"]["duration_ms"] == 5000

    @pytest.mark.asyncio
    async def test_push_render_with_no_session_still_sends(self):
        """When session is None, push_render should still send the message (no crash)."""
        with patch("marketplace.services.a2ui_service.validate_payload_size", return_value=True), \
             patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn:
            mock_mgr.get_session.return_value = None
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import push_render
            cid = await push_render("sess-21", "card", {"x": 1})

            assert cid is not None
            mock_conn.send_to_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_confirm_includes_timeout_seconds(self):
        with patch("marketplace.services.a2ui_service.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.services.a2ui_service.a2ui_connection_manager") as mock_conn, \
             patch("marketplace.services.a2ui_service.sanitize_html", side_effect=lambda x: x):
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            future.set_result({"approved": False})
            mock_mgr.set_pending_input.return_value = future
            mock_conn.send_to_session = AsyncMock()

            from marketplace.services.a2ui_service import request_confirm
            await request_confirm("sess-22", "OK?", timeout=45)

            sent = mock_conn.send_to_session.call_args[0][1]
            assert sent["params"]["timeout_seconds"] == 45


# ---------------------------------------------------------------------------
# TestA2UIModels — SQLAlchemy models for session logging and consent
# ---------------------------------------------------------------------------

class TestA2UIModels:
    """Tests for marketplace.models.a2ui_session models."""

    def test_session_log_table_name(self):
        from marketplace.models.a2ui_session import A2UISessionLog
        assert A2UISessionLog.__tablename__ == "a2ui_session_logs"

    def test_session_log_has_required_columns(self):
        from marketplace.models.a2ui_session import A2UISessionLog

        col_names = {c.name for c in A2UISessionLog.__table__.columns}
        expected = {"id", "agent_id", "user_id", "session_started_at",
                    "session_ended_at", "message_count", "components_rendered",
                    "inputs_requested", "created_at"}
        assert expected.issubset(col_names)

    def test_session_log_id_default_generates_uuid(self):
        from marketplace.models.a2ui_session import A2UISessionLog

        col = A2UISessionLog.__table__.c.id
        assert col.primary_key

    def test_session_log_agent_id_not_nullable(self):
        from marketplace.models.a2ui_session import A2UISessionLog

        col = A2UISessionLog.__table__.c.agent_id
        assert col.nullable is False

    def test_session_log_user_id_nullable(self):
        from marketplace.models.a2ui_session import A2UISessionLog

        col = A2UISessionLog.__table__.c.user_id
        assert col.nullable is True

    def test_session_log_message_count_default(self):
        from marketplace.models.a2ui_session import A2UISessionLog

        col = A2UISessionLog.__table__.c.message_count
        assert col.default.arg == 0

    def test_session_log_components_rendered_default(self):
        from marketplace.models.a2ui_session import A2UISessionLog

        col = A2UISessionLog.__table__.c.components_rendered
        assert col.default.arg == 0

    def test_consent_record_table_name(self):
        from marketplace.models.a2ui_session import A2UIConsentRecord
        assert A2UIConsentRecord.__tablename__ == "a2ui_consent_records"

    def test_consent_record_has_required_columns(self):
        from marketplace.models.a2ui_session import A2UIConsentRecord

        col_names = {c.name for c in A2UIConsentRecord.__table__.columns}
        expected = {"id", "session_id", "consent_type", "granted",
                    "granted_at", "revoked_at"}
        assert expected.issubset(col_names)

    def test_consent_record_session_id_foreign_key(self):
        from marketplace.models.a2ui_session import A2UIConsentRecord

        col = A2UIConsentRecord.__table__.c.session_id
        fk_targets = [fk.target_fullname for fk in col.foreign_keys]
        assert "a2ui_session_logs.id" in fk_targets

    def test_consent_record_granted_not_nullable(self):
        from marketplace.models.a2ui_session import A2UIConsentRecord

        col = A2UIConsentRecord.__table__.c.granted
        assert col.nullable is False

    def test_consent_record_revoked_at_nullable(self):
        from marketplace.models.a2ui_session import A2UIConsentRecord

        col = A2UIConsentRecord.__table__.c.revoked_at
        assert col.nullable is True

    def test_session_log_indexes_exist(self):
        from marketplace.models.a2ui_session import A2UISessionLog

        index_names = {idx.name for idx in A2UISessionLog.__table__.indexes}
        assert "idx_a2ui_sessions_agent" in index_names
        assert "idx_a2ui_sessions_user" in index_names

    def test_consent_record_index_exists(self):
        from marketplace.models.a2ui_session import A2UIConsentRecord

        index_names = {idx.name for idx in A2UIConsentRecord.__table__.indexes}
        assert "idx_a2ui_consent_session" in index_names

    def test_utcnow_returns_aware_datetime(self):
        from marketplace.models.a2ui_session import utcnow

        now = utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# TestV4A2UIRoutes — FastAPI router for A2UI v4 API
# ---------------------------------------------------------------------------

class TestV4A2UIRoutes:
    """Tests for marketplace.api.v4_a2ui route definitions."""

    def test_router_has_stream_token_endpoint(self):
        from marketplace.api.v4_a2ui import router

        paths = [r.path for r in router.routes]
        assert "/stream-token" in paths

    def test_router_has_sessions_list_endpoint(self):
        from marketplace.api.v4_a2ui import router

        paths = [r.path for r in router.routes]
        assert "/sessions" in paths

    def test_router_has_session_detail_endpoint(self):
        from marketplace.api.v4_a2ui import router

        paths = [r.path for r in router.routes]
        assert "/sessions/{session_id}" in paths

    def test_router_has_health_endpoint(self):
        from marketplace.api.v4_a2ui import router

        paths = [r.path for r in router.routes]
        assert "/health" in paths

    def test_router_tag_is_a2ui(self):
        from marketplace.api.v4_a2ui import router

        assert "a2ui" in router.tags

    def test_health_endpoint_is_get_method(self):
        from marketplace.api.v4_a2ui import router

        for route in router.routes:
            if getattr(route, "path", None) == "/health":
                assert "GET" in route.methods
                break
        else:
            pytest.fail("Health endpoint not found")

    def test_stream_token_endpoint_is_post_method(self):
        from marketplace.api.v4_a2ui import router

        for route in router.routes:
            if getattr(route, "path", None) == "/stream-token":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("Stream-token endpoint not found")

    def test_close_session_endpoint_is_delete_method(self):
        from marketplace.api.v4_a2ui import router

        for route in router.routes:
            if getattr(route, "path", None) == "/sessions/{session_id}":
                methods = getattr(route, "methods", set())
                if "DELETE" in methods:
                    break
        else:
            pytest.fail("DELETE sessions/{session_id} endpoint not found")
