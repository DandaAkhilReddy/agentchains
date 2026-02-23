"""Comprehensive unit tests for A2UI bridge modules.

Covers:
- A2ABridge  (marketplace/a2ui/a2a_bridge.py)
- A2UIConnectionManager  (marketplace/a2ui/connection_manager.py)
- mcp_bridge functions  (marketplace/a2ui/mcp_bridge.py)

All tests use async def and unittest.mock.AsyncMock for WebSocket / service
mocks.  pytest-asyncio is configured in auto mode, so no @pytest.mark.asyncio
decorators are required.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# TestA2ABridgeInit — constructor behaviour
# ===========================================================================

class TestA2ABridgeInit:
    """Verify A2ABridge stores its session_id correctly on construction."""

    def test_stores_session_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-xyz")
        assert bridge._session_id == "sess-xyz"

    def test_stores_uuid_session_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        sid = str(uuid.uuid4())
        bridge = A2ABridge(sid)
        assert bridge._session_id == sid

    def test_stores_empty_string_session_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("")
        assert bridge._session_id == ""

    def test_independent_instances_have_separate_session_ids(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        b1 = A2ABridge("sess-1")
        b2 = A2ABridge("sess-2")
        assert b1._session_id != b2._session_id


# ===========================================================================
# TestA2ABridgeOnPipelineStart
# ===========================================================================

class TestA2ABridgeOnPipelineStart:
    """Tests for A2ABridge.on_pipeline_start."""

    async def test_calls_push_render_once(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-1")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-1", ["a", "b"])
            mock_render.assert_called_once()

    async def test_calls_push_progress_once(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-2")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_pipeline_start("pipe-2", ["x"])
            mock_progress.assert_called_once()

    async def test_render_receives_correct_session_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-3")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-3", ["step"])
            assert mock_render.call_args[0][0] == "sess-start-3"

    async def test_render_component_type_is_steps(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-4")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-4", ["one", "two"])
            assert mock_render.call_args[1]["component_type"] == "steps"

    async def test_render_data_contains_pipeline_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-5")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("my-pipe", ["s1"])
            data = mock_render.call_args[1]["data"]
            assert data["pipeline_id"] == "my-pipe"

    async def test_render_data_steps_all_have_pending_status(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-6")
        steps = ["extract", "transform", "load"]
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-etl", steps)
            rendered_steps = mock_render.call_args[1]["data"]["steps"]
            assert all(s["status"] == "pending" for s in rendered_steps)

    async def test_render_data_steps_names_match_input(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-7")
        steps = ["alpha", "beta", "gamma"]
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-abc", steps)
            rendered_names = [s["name"] for s in mock_render.call_args[1]["data"]["steps"]]
            assert rendered_names == steps

    async def test_render_data_current_step_is_zero(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-8")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-9", ["s"])
            assert mock_render.call_args[1]["data"]["current_step"] == 0

    async def test_render_metadata_source_is_a2a_pipeline(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-9")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-10", ["s"])
            assert mock_render.call_args[1]["metadata"]["source"] == "a2a_pipeline"

    async def test_progress_progress_type_is_indeterminate(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-10")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_pipeline_start("pipe-11", ["s"])
            assert mock_progress.call_args[1]["progress_type"] == "indeterminate"

    async def test_progress_task_id_matches_pipeline_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-11")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_pipeline_start("the-pipe", ["s"])
            assert mock_progress.call_args[1]["task_id"] == "the-pipe"

    async def test_progress_message_includes_step_count(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-12")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_pipeline_start("pipe-x", ["a", "b", "c", "d"])
            assert "4" in mock_progress.call_args[1]["message"]

    async def test_empty_steps_list_renders_zero_steps(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-13")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            await bridge.on_pipeline_start("pipe-empty", [])
            assert mock_render.call_args[1]["data"]["steps"] == []

    async def test_error_in_push_render_propagates(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-start-err")
        with patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render, \
             patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock):
            mock_render.side_effect = RuntimeError("ws closed")
            with pytest.raises(RuntimeError, match="ws closed"):
                await bridge.on_pipeline_start("pipe-err", ["s"])


# ===========================================================================
# TestA2ABridgeOnStepStart
# ===========================================================================

class TestA2ABridgeOnStepStart:
    """Tests for A2ABridge.on_step_start."""

    async def test_calls_push_progress_once(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-step-1")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_step_start("pipe-s", 0, "fetch")
            mock_progress.assert_called_once()

    async def test_progress_type_is_determinate(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-step-2")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_step_start("pipe-s", 1, "parse")
            assert mock_progress.call_args[1]["progress_type"] == "determinate"

    async def test_progress_value_matches_step_index(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-step-3")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_step_start("pipe-s", 3, "upload")
            assert mock_progress.call_args[1]["value"] == 3

    async def test_progress_task_id_matches_pipeline_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-step-4")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_step_start("my-pipeline", 0, "init")
            assert mock_progress.call_args[1]["task_id"] == "my-pipeline"

    async def test_progress_message_includes_step_name(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-step-5")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_step_start("pipe-s", 2, "validate_schema")
            assert "validate_schema" in mock_progress.call_args[1]["message"]

    async def test_session_id_forwarded_to_push_progress(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-step-6")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_step_start("pipe-s", 0, "s")
            assert mock_progress.call_args[0][0] == "sess-step-6"

    async def test_error_in_push_progress_propagates(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-step-err")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress:
            mock_progress.side_effect = ConnectionError("dropped")
            with pytest.raises(ConnectionError):
                await bridge.on_step_start("pipe-s", 0, "s")


# ===========================================================================
# TestA2ABridgeOnStepComplete
# ===========================================================================

class TestA2ABridgeOnStepComplete:
    """Tests for A2ABridge.on_step_complete."""

    async def test_calls_push_update_once(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sc-1")
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-c", 0, "fetch", {"ok": True})
            mock_update.assert_called_once()

    async def test_component_id_prefixed_with_pipeline(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sc-2")
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("my-pipe", 1, "parse", {})
            assert mock_update.call_args[1]["component_id"] == "pipeline-my-pipe"

    async def test_operation_is_merge(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sc-3")
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-c", 0, "s", "result")
            assert mock_update.call_args[1]["operation"] == "merge"

    async def test_step_status_is_completed(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sc-4")
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-c", 2, "load", "done")
            steps_data = mock_update.call_args[1]["data"]["steps"]
            assert steps_data[2]["status"] == "completed"

    async def test_result_preview_is_string_representation(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sc-5")
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-c", 0, "s", {"key": "val"})
            preview = mock_update.call_args[1]["data"]["steps"][0]["result_preview"]
            assert "key" in preview

    async def test_result_preview_truncated_to_200_chars(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sc-6")
        long_result = "X" * 500
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-c", 0, "s", long_result)
            preview = mock_update.call_args[1]["data"]["steps"][0]["result_preview"]
            assert len(preview) <= 200

    async def test_session_id_passed_to_push_update(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sc-7")
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-c", 0, "s", None)
            assert mock_update.call_args[0][0] == "sess-sc-7"

    async def test_none_result_converts_to_string(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sc-8")
        with patch("marketplace.services.a2ui_service.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-c", 0, "s", None)
            preview = mock_update.call_args[1]["data"]["steps"][0]["result_preview"]
            assert isinstance(preview, str)


# ===========================================================================
# TestA2ABridgeOnStepFailed
# ===========================================================================

class TestA2ABridgeOnStepFailed:
    """Tests for A2ABridge.on_step_failed."""

    async def test_calls_push_notify_once(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sf-1")
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-f", 0, "fetch", "timeout")
            mock_notify.assert_called_once()

    async def test_notify_level_is_error(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sf-2")
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-f", 0, "s", "err")
            assert mock_notify.call_args[1]["level"] == "error"

    async def test_notify_title_contains_step_name(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sf-3")
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-f", 1, "validate_data", "schema mismatch")
            assert "validate_data" in mock_notify.call_args[1]["title"]

    async def test_notify_message_matches_error_string(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sf-4")
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-f", 0, "s", "Connection refused")
            assert mock_notify.call_args[1]["message"] == "Connection refused"

    async def test_error_message_truncated_to_300_chars(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sf-5")
        long_error = "E" * 500
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-f", 0, "s", long_error)
            assert len(mock_notify.call_args[1]["message"]) <= 300

    async def test_session_id_passed_to_push_notify(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sf-6")
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-f", 0, "s", "err")
            assert mock_notify.call_args[0][0] == "sess-sf-6"

    async def test_error_in_push_notify_propagates(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-sf-err")
        with patch("marketplace.services.a2ui_service.push_notify", new_callable=AsyncMock) as mock_notify:
            mock_notify.side_effect = OSError("send failed")
            with pytest.raises(OSError):
                await bridge.on_step_failed("pipe-f", 0, "s", "err")


# ===========================================================================
# TestA2ABridgeOnPipelineComplete
# ===========================================================================

class TestA2ABridgeOnPipelineComplete:
    """Tests for A2ABridge.on_pipeline_complete."""

    async def test_calls_push_progress_and_push_render(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-1")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-done", "output")
            mock_progress.assert_called_once()
            mock_render.assert_called_once()

    async def test_progress_value_and_total_are_100(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-2")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock):
            await bridge.on_pipeline_complete("pipe-done", "result")
            kw = mock_progress.call_args[1]
            assert kw["value"] == 100
            assert kw["total"] == 100

    async def test_progress_message_is_pipeline_completed(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-3")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock):
            await bridge.on_pipeline_complete("pipe-done", {})
            assert mock_progress.call_args[1]["message"] == "Pipeline completed"

    async def test_render_component_type_is_card(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-4")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-done", "x")
            assert mock_render.call_args[1]["component_type"] == "card"

    async def test_render_data_title_is_pipeline_complete(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-5")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-done", "x")
            assert mock_render.call_args[1]["data"]["title"] == "Pipeline Complete"

    async def test_render_metadata_contains_pipeline_id(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-6")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("my-pipe-id", "x")
            assert mock_render.call_args[1]["metadata"]["pipeline_id"] == "my-pipe-id"

    async def test_none_result_renders_no_output(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-7")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-none", None)
            assert mock_render.call_args[1]["data"]["content"] == "No output"

    async def test_long_result_truncated_to_500_chars(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-8")
        huge = "R" * 1000
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-big", huge)
            content = mock_render.call_args[1]["data"]["content"]
            assert len(content) <= 500

    async def test_render_metadata_source_is_a2a_pipeline(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-pc-9")
        with patch("marketplace.services.a2ui_service.push_progress", new_callable=AsyncMock), \
             patch("marketplace.services.a2ui_service.push_render", new_callable=AsyncMock) as mock_render:
            await bridge.on_pipeline_complete("pipe-src", "data")
            assert mock_render.call_args[1]["metadata"]["source"] == "a2a_pipeline"


# ===========================================================================
# TestA2ABridgeRequestHumanApproval
# ===========================================================================

class TestA2ABridgeRequestHumanApproval:
    """Tests for A2ABridge.request_human_approval."""

    async def test_returns_true_when_confirmed(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-ha-1")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True
            result = await bridge.request_human_approval("pipe-ha", "deploy", "Deploy?")
            assert result is True

    async def test_returns_false_when_denied(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-ha-2")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = False
            result = await bridge.request_human_approval("pipe-ha", "delete", "Delete all?")
            assert result is False

    async def test_title_contains_step_name(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-ha-3")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True
            await bridge.request_human_approval("pipe-ha", "publish_release", "Publish?")
            assert "publish_release" in mock_confirm.call_args[1]["title"]

    async def test_description_forwarded_verbatim(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-ha-4")
        desc = "This action cannot be undone."
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True
            await bridge.request_human_approval("pipe-ha", "s", desc)
            assert mock_confirm.call_args[1]["description"] == desc

    async def test_severity_is_warning(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-ha-5")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True
            await bridge.request_human_approval("pipe-ha", "s", "desc")
            assert mock_confirm.call_args[1]["severity"] == "warning"

    async def test_timeout_is_120_seconds(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-ha-6")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True
            await bridge.request_human_approval("pipe-ha", "s", "desc")
            assert mock_confirm.call_args[1]["timeout"] == 120

    async def test_session_id_forwarded_to_request_confirm(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-ha-7")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True
            await bridge.request_human_approval("pipe-ha", "s", "d")
            assert mock_confirm.call_args[0][0] == "sess-ha-7"

    async def test_error_from_request_confirm_propagates(self):
        from marketplace.a2ui.a2a_bridge import A2ABridge

        bridge = A2ABridge("sess-ha-err")
        with patch("marketplace.services.a2ui_service.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.side_effect = TimeoutError("user did not respond")
            with pytest.raises(TimeoutError):
                await bridge.request_human_approval("pipe-ha", "s", "d")


# ===========================================================================
# TestA2UIConnectionManagerConnect
# ===========================================================================

class TestA2UIConnectionManagerConnect:
    """Tests for A2UIConnectionManager.connect."""

    def _make_manager(self):
        from marketplace.a2ui.connection_manager import A2UIConnectionManager
        return A2UIConnectionManager()

    def _make_ws(self):
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    async def test_connect_returns_true_on_success(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        result = await mgr.connect(ws, "sess-1", "agent-1")
        assert result is True

    async def test_connect_accepts_websocket(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-2", "agent-2")
        ws.accept.assert_called_once()

    async def test_connect_stores_session(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-3", "agent-3")
        assert "sess-3" in mgr._session_ws

    async def test_connect_maps_agent_to_session(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-4", "agent-4")
        assert "sess-4" in mgr._agent_sessions["agent-4"]

    async def test_connect_multiple_sessions_same_agent(self):
        mgr = self._make_manager()
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await mgr.connect(ws1, "sess-5a", "agent-5")
        await mgr.connect(ws2, "sess-5b", "agent-5")
        assert {"sess-5a", "sess-5b"} == mgr._agent_sessions["agent-5"]

    async def test_connect_rejects_when_at_max_connections(self):
        mgr = self._make_manager()
        mgr.MAX_CONNECTIONS = 2
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        ws3 = self._make_ws()
        await mgr.connect(ws1, "s1", "a1")
        await mgr.connect(ws2, "s2", "a2")
        result = await mgr.connect(ws3, "s3", "a3")
        assert result is False

    async def test_connect_closes_websocket_when_at_max_connections(self):
        mgr = self._make_manager()
        mgr.MAX_CONNECTIONS = 1
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await mgr.connect(ws1, "s1", "a1")
        await mgr.connect(ws2, "s2", "a2")
        ws2.close.assert_called_once_with(code=4029, reason="Too many A2UI connections")

    async def test_connect_does_not_store_rejected_session(self):
        mgr = self._make_manager()
        mgr.MAX_CONNECTIONS = 1
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await mgr.connect(ws1, "s1", "a1")
        await mgr.connect(ws2, "s2", "a2")
        assert "s2" not in mgr._session_ws


# ===========================================================================
# TestA2UIConnectionManagerDisconnect
# ===========================================================================

class TestA2UIConnectionManagerDisconnect:
    """Tests for A2UIConnectionManager.disconnect."""

    def _make_manager(self):
        from marketplace.a2ui.connection_manager import A2UIConnectionManager
        return A2UIConnectionManager()

    def _make_ws(self):
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    async def test_disconnect_removes_session(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-d1", "agent-d1")
        mgr.disconnect(ws)
        assert "sess-d1" not in mgr._session_ws

    async def test_disconnect_removes_agent_session_mapping(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-d2", "agent-d2")
        mgr.disconnect(ws)
        # agent entry should be removed when empty
        assert "agent-d2" not in mgr._agent_sessions

    async def test_disconnect_unknown_ws_is_noop(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        # Should not raise
        mgr.disconnect(ws)

    async def test_disconnect_keeps_other_sessions_for_agent(self):
        mgr = self._make_manager()
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await mgr.connect(ws1, "sess-d3a", "agent-d3")
        await mgr.connect(ws2, "sess-d3b", "agent-d3")
        mgr.disconnect(ws1)
        assert "agent-d3" in mgr._agent_sessions
        assert "sess-d3b" in mgr._agent_sessions["agent-d3"]

    async def test_disconnect_keeps_other_agent_mappings(self):
        mgr = self._make_manager()
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await mgr.connect(ws1, "sess-d4a", "agent-d4a")
        await mgr.connect(ws2, "sess-d4b", "agent-d4b")
        mgr.disconnect(ws1)
        assert "agent-d4b" in mgr._agent_sessions


# ===========================================================================
# TestA2UIConnectionManagerSendToSession
# ===========================================================================

class TestA2UIConnectionManagerSendToSession:
    """Tests for A2UIConnectionManager.send_to_session."""

    def _make_manager(self):
        from marketplace.a2ui.connection_manager import A2UIConnectionManager
        return A2UIConnectionManager()

    def _make_ws(self):
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    async def test_returns_true_when_session_exists(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-s1", "agent-s1")
        result = await mgr.send_to_session("sess-s1", {"method": "ping"})
        assert result is True

    async def test_returns_false_for_unknown_session(self):
        mgr = self._make_manager()
        result = await mgr.send_to_session("no-such-session", {"method": "ping"})
        assert result is False

    async def test_sends_json_encoded_message(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-s2", "agent-s2")
        msg = {"jsonrpc": "2.0", "method": "ui.render"}
        await mgr.send_to_session("sess-s2", msg)
        ws.send_text.assert_called_once_with(json.dumps(msg))

    async def test_returns_false_and_disconnects_on_send_error(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        ws.send_text.side_effect = RuntimeError("broken pipe")
        await mgr.connect(ws, "sess-s3", "agent-s3")
        result = await mgr.send_to_session("sess-s3", {"x": 1})
        assert result is False
        # Session should be cleaned up
        assert "sess-s3" not in mgr._session_ws

    async def test_send_to_session_with_nested_payload(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-s4", "agent-s4")
        complex_msg = {"a": [1, 2], "b": {"c": True}}
        await mgr.send_to_session("sess-s4", complex_msg)
        sent_text = ws.send_text.call_args[0][0]
        assert json.loads(sent_text) == complex_msg


# ===========================================================================
# TestA2UIConnectionManagerBroadcastToAgent
# ===========================================================================

class TestA2UIConnectionManagerBroadcastToAgent:
    """Tests for A2UIConnectionManager.broadcast_to_agent."""

    def _make_manager(self):
        from marketplace.a2ui.connection_manager import A2UIConnectionManager
        return A2UIConnectionManager()

    def _make_ws(self):
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    async def test_broadcasts_to_all_agent_sessions(self):
        mgr = self._make_manager()
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await mgr.connect(ws1, "sess-b1", "agent-b")
        await mgr.connect(ws2, "sess-b2", "agent-b")
        await mgr.broadcast_to_agent("agent-b", {"event": "tick"})
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    async def test_broadcast_to_unknown_agent_is_noop(self):
        mgr = self._make_manager()
        # Should not raise
        await mgr.broadcast_to_agent("no-agent", {"x": 1})

    async def test_broadcast_sends_json_encoded_message(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "sess-b3", "agent-b3")
        msg = {"method": "ui.notify"}
        await mgr.broadcast_to_agent("agent-b3", msg)
        ws.send_text.assert_called_once_with(json.dumps(msg))

    async def test_broadcast_skips_failed_sessions_and_disconnects(self):
        mgr = self._make_manager()
        ws_bad = self._make_ws()
        ws_good = self._make_ws()
        ws_bad.send_text.side_effect = OSError("closed")
        await mgr.connect(ws_bad, "sess-b4-bad", "agent-b4")
        await mgr.connect(ws_good, "sess-b4-good", "agent-b4")
        # Should not raise; bad session is cleaned up
        await mgr.broadcast_to_agent("agent-b4", {"x": 1})
        assert "sess-b4-bad" not in mgr._session_ws

    async def test_broadcast_only_sends_to_own_agent_sessions(self):
        mgr = self._make_manager()
        ws_a = self._make_ws()
        ws_b = self._make_ws()
        await mgr.connect(ws_a, "sess-c1", "agent-c1")
        await mgr.connect(ws_b, "sess-c2", "agent-c2")
        await mgr.broadcast_to_agent("agent-c1", {"msg": "hello"})
        ws_a.send_text.assert_called_once()
        ws_b.send_text.assert_not_called()

    async def test_singleton_is_a2ui_connection_manager_instance(self):
        from marketplace.a2ui.connection_manager import (
            a2ui_connection_manager,
            A2UIConnectionManager,
        )
        assert isinstance(a2ui_connection_manager, A2UIConnectionManager)


# ===========================================================================
# TestMCPBridgePushToolExecutionStart
# ===========================================================================

class TestMCPBridgePushToolExecutionStart:
    """Tests for marketplace.a2ui.mcp_bridge.push_tool_execution_start."""

    async def test_returns_uuid_task_id_when_session_exists(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            task_id = await push_tool_execution_start("sess-mcp-1", "read_file", {"path": "/tmp"})
            assert task_id is not None
            uuid.UUID(task_id)  # Must parse as valid UUID

    async def test_returns_none_when_session_missing(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            result = await push_tool_execution_start("no-sess", "tool", {})
            assert result is None

    async def test_calls_push_progress_with_indeterminate_type(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            await push_tool_execution_start("sess-mcp-2", "search", {"q": "test"})
            assert mock_progress.call_args[1]["progress_type"] == "indeterminate"

    async def test_progress_message_includes_tool_name(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            await push_tool_execution_start("sess-mcp-3", "my_special_tool", {})
            assert "my_special_tool" in mock_progress.call_args[1]["message"]

    async def test_push_progress_receives_session_id(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            await push_tool_execution_start("sess-mcp-4", "tool", {})
            assert mock_progress.call_args[0][0] == "sess-mcp-4"

    async def test_different_calls_return_different_task_ids(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            id1 = await push_tool_execution_start("sess-mcp-5", "tool", {})
            id2 = await push_tool_execution_start("sess-mcp-5", "tool", {})
            assert id1 != id2

    async def test_does_not_call_push_progress_when_no_session(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress:
            mock_mgr.get_session.return_value = None
            from marketplace.a2ui.mcp_bridge import push_tool_execution_start
            await push_tool_execution_start("no-sess", "tool", {})
            mock_progress.assert_not_called()


# ===========================================================================
# TestMCPBridgePushToolExecutionResult
# ===========================================================================

class TestMCPBridgePushToolExecutionResult:
    """Tests for marketplace.a2ui.mcp_bridge.push_tool_execution_result."""

    async def test_returns_component_id_from_push_render(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            mock_render.return_value = "comp-abc"
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            cid = await push_tool_execution_result("sess-r1", "task-1", "my_tool", {"out": "ok"})
            assert cid == "comp-abc"

    async def test_returns_none_when_session_missing(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            result = await push_tool_execution_result("no-sess", "t", "tool", {})
            assert result is None

    async def test_progress_value_and_total_are_1(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-r2", "task-2", "tool", {})
            kw = mock_progress.call_args[1]
            assert kw["value"] == 1
            assert kw["total"] == 1

    async def test_progress_message_contains_completed_and_tool_name(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-r3", "task-3", "run_query", {})
            msg = mock_progress.call_args[1]["message"]
            assert "Completed" in msg
            assert "run_query" in msg

    async def test_render_component_type_is_code(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-r4", "task-4", "exec", {"output": "42"})
            assert mock_render.call_args[0][1] == "code"

    async def test_render_data_source_is_mcp_tool(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-r5", "task-5", "tool", {})
            assert mock_render.call_args[0][2]["source"] == "mcp_tool"

    async def test_render_metadata_contains_mcp_tool_name(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-r6", "task-6", "my_tool", {})
            assert mock_render.call_args[1]["metadata"]["mcp_tool"] == "my_tool"

    async def test_render_metadata_contains_task_id(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-r7", "task-99", "tool", {})
            assert mock_render.call_args[1]["metadata"]["task_id"] == "task-99"

    async def test_render_data_title_includes_tool_name(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-r8", "task-8", "search_files", {})
            title = mock_render.call_args[0][2]["title"]
            assert "search_files" in title

    async def test_result_dict_passed_as_content(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            payload = {"rows": [1, 2, 3], "count": 3}
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("sess-r9", "task-9", "sql", payload)
            assert mock_render.call_args[0][2]["content"] == payload

    async def test_does_not_call_render_when_no_session(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = None
            from marketplace.a2ui.mcp_bridge import push_tool_execution_result
            await push_tool_execution_result("no-sess", "t", "tool", {})
            mock_render.assert_not_called()


# ===========================================================================
# TestMCPBridgePushToolExecutionError
# ===========================================================================

class TestMCPBridgePushToolExecutionError:
    """Tests for marketplace.a2ui.mcp_bridge.push_tool_execution_error."""

    async def test_noop_when_session_missing(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock) as mock_notify:
            mock_mgr.get_session.return_value = None
            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("no-sess", "task-e", "tool", "err")
            mock_progress.assert_not_called()
            mock_notify.assert_not_called()

    async def test_sends_determinate_progress_on_failure(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-e1", "task-e1", "my_tool", "timeout")
            kw = mock_progress.call_args[1]
            assert kw["progress_type"] == "determinate"
            assert kw["value"] == 1
            assert kw["total"] == 1

    async def test_progress_message_contains_failed_and_tool_name(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock) as mock_progress, \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock):
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-e2", "task-e2", "run_sql", "syntax error")
            msg = mock_progress.call_args[1]["message"]
            assert "Failed" in msg
            assert "run_sql" in msg

    async def test_sends_error_notification(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock) as mock_notify:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-e3", "task-e3", "api_call", "404 not found")
            mock_notify.assert_called_once()

    async def test_notification_level_is_error(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock) as mock_notify:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-e4", "task-e4", "tool", "err")
            assert mock_notify.call_args[0][1] == "error"

    async def test_notification_title_contains_tool_name(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock) as mock_notify:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-e5", "task-e5", "fetch_data", "err")
            title = mock_notify.call_args[0][2]
            assert "fetch_data" in title

    async def test_notification_body_is_error_string(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock) as mock_notify:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-e6", "task-e6", "tool", "connection refused")
            assert mock_notify.call_args[0][3] == "connection refused"

    async def test_session_id_forwarded_to_push_notify(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_progress", new_callable=AsyncMock), \
             patch("marketplace.a2ui.mcp_bridge.push_notify", new_callable=AsyncMock) as mock_notify:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_tool_execution_error
            await push_tool_execution_error("sess-e7", "task-e7", "tool", "err")
            assert mock_notify.call_args[0][0] == "sess-e7"


# ===========================================================================
# TestMCPBridgePushResourceReadResult
# ===========================================================================

class TestMCPBridgePushResourceReadResult:
    """Tests for marketplace.a2ui.mcp_bridge.push_resource_read_result."""

    async def test_returns_component_id_from_push_render(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            mock_render.return_value = "comp-res-99"
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            cid = await push_resource_read_result("sess-res-1", "file:///data.json", {"k": "v"})
            assert cid == "comp-res-99"

    async def test_returns_none_when_session_missing(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr:
            mock_mgr.get_session.return_value = None
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            result = await push_resource_read_result("no-sess", "file:///x", {})
            assert result is None

    async def test_render_component_type_is_card(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("sess-res-2", "db://tbl", {"row": 1})
            assert mock_render.call_args[0][1] == "card"

    async def test_render_data_source_is_mcp_resource(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("sess-res-3", "http://api/v1", {})
            assert mock_render.call_args[0][2]["source"] == "mcp_resource"

    async def test_render_data_title_includes_uri(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("sess-res-4", "sql://users/all", {})
            assert "sql://users/all" in mock_render.call_args[0][2]["title"]

    async def test_render_metadata_contains_resource_uri(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("sess-res-5", "db://schema/table", {"n": 5})
            assert mock_render.call_args[1]["metadata"]["mcp_resource_uri"] == "db://schema/table"

    async def test_content_dict_passed_through_unchanged(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            content = {"rows": [1, 2, 3], "total": 3}
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("sess-res-6", "sql://q", content)
            assert mock_render.call_args[0][2]["content"] == content

    async def test_session_id_forwarded_to_push_render(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("sess-res-7", "file:///log", {})
            assert mock_render.call_args[0][0] == "sess-res-7"

    async def test_does_not_call_push_render_when_no_session(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = None
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            await push_resource_read_result("no-sess", "file:///x", {})
            mock_render.assert_not_called()

    async def test_returns_push_render_return_value(self):
        with patch("marketplace.a2ui.mcp_bridge.a2ui_session_manager") as mock_mgr, \
             patch("marketplace.a2ui.mcp_bridge.push_render", new_callable=AsyncMock) as mock_render:
            mock_mgr.get_session.return_value = MagicMock()
            mock_render.return_value = "unique-component-id"
            from marketplace.a2ui.mcp_bridge import push_resource_read_result
            cid = await push_resource_read_result("sess-res-8", "uri://x", {})
            assert cid == "unique-component-id"
