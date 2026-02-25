"""Tests for A2UI-to-A2A bridge — pipeline UI notification layer.

Covers:
  - on_pipeline_start sends steps component + indeterminate progress (tests 1-2)
  - on_step_start sends determinate progress (test 3)
  - on_step_complete sends merge update (test 4)
  - on_step_failed sends error notification (test 5)
  - on_pipeline_complete sends final progress + card render (tests 6-7)
  - request_human_approval delegates to request_confirm (test 8)
  - None/empty result edge cases (tests 9-10)
"""

from unittest.mock import AsyncMock, patch

import pytest

from marketplace.a2ui.a2a_bridge import A2ABridge

# The bridge uses lazy imports from marketplace.services.a2ui_service inside each
# method, so we patch at the service module level.
_SVC = "marketplace.services.a2ui_service"


class TestA2ABridgePipelineStart:
    """Tests 1-2: on_pipeline_start pushes steps component and progress."""

    # 1
    async def test_pipeline_start_pushes_steps_component(self):
        """on_pipeline_start should call push_render with steps component."""
        bridge = A2ABridge(session_id="sess-1")
        with (
            patch(f"{_SVC}.push_render", new_callable=AsyncMock) as mock_render,
            patch(f"{_SVC}.push_progress", new_callable=AsyncMock),
        ):
            await bridge.on_pipeline_start("pipe-1", ["step_a", "step_b"])

            mock_render.assert_called_once()
            args, kwargs = mock_render.call_args
            assert args[0] == "sess-1"
            assert kwargs["component_type"] == "steps"
            data = kwargs["data"]
            assert data["pipeline_id"] == "pipe-1"
            assert len(data["steps"]) == 2
            assert data["steps"][0] == {"name": "step_a", "status": "pending"}
            assert data["current_step"] == 0

    # 2
    async def test_pipeline_start_pushes_indeterminate_progress(self):
        """on_pipeline_start should push indeterminate progress with step count."""
        bridge = A2ABridge(session_id="sess-2")
        with (
            patch(f"{_SVC}.push_render", new_callable=AsyncMock),
            patch(f"{_SVC}.push_progress", new_callable=AsyncMock) as mock_progress,
        ):
            await bridge.on_pipeline_start("pipe-2", ["a", "b", "c"])

            mock_progress.assert_called_once()
            args, kwargs = mock_progress.call_args
            assert args[0] == "sess-2"
            assert kwargs["task_id"] == "pipe-2"
            assert kwargs["progress_type"] == "indeterminate"
            assert "3 steps" in kwargs["message"]


class TestA2ABridgeStepStart:
    """Test 3: on_step_start sends determinate progress."""

    # 3
    async def test_step_start_pushes_determinate_progress(self):
        """on_step_start should push determinate progress with step index."""
        bridge = A2ABridge(session_id="sess-3")
        with patch(f"{_SVC}.push_progress", new_callable=AsyncMock) as mock_progress:
            await bridge.on_step_start("pipe-3", 1, "fetch_data")

            mock_progress.assert_called_once()
            args, kwargs = mock_progress.call_args
            assert kwargs["task_id"] == "pipe-3"
            assert kwargs["progress_type"] == "determinate"
            assert kwargs["value"] == 1
            assert "fetch_data" in kwargs["message"]


class TestA2ABridgeStepComplete:
    """Test 4: on_step_complete sends merge update."""

    # 4
    async def test_step_complete_pushes_merge_update(self):
        """on_step_complete should push a merge update with completed status."""
        bridge = A2ABridge(session_id="sess-4")
        with patch(f"{_SVC}.push_update", new_callable=AsyncMock) as mock_update:
            await bridge.on_step_complete("pipe-4", 0, "analyze", {"score": 0.9})

            mock_update.assert_called_once()
            args, kwargs = mock_update.call_args
            assert args[0] == "sess-4"
            assert kwargs["component_id"] == "pipeline-pipe-4"
            assert kwargs["operation"] == "merge"
            step_data = kwargs["data"]["steps"][0]
            assert step_data["status"] == "completed"
            assert "score" in step_data["result_preview"]


class TestA2ABridgeStepFailed:
    """Test 5: on_step_failed sends error notification."""

    # 5
    async def test_step_failed_pushes_error_notify(self):
        """on_step_failed should push an error notification."""
        bridge = A2ABridge(session_id="sess-5")
        with patch(f"{_SVC}.push_notify", new_callable=AsyncMock) as mock_notify:
            await bridge.on_step_failed("pipe-5", 2, "validate", "Timeout exceeded")

            mock_notify.assert_called_once()
            args, kwargs = mock_notify.call_args
            assert args[0] == "sess-5"
            assert kwargs["level"] == "error"
            assert "validate" in kwargs["title"]
            assert "Timeout exceeded" in kwargs["message"]


class TestA2ABridgePipelineComplete:
    """Tests 6-7: on_pipeline_complete sends progress=100 and card."""

    # 6
    async def test_pipeline_complete_pushes_final_progress(self):
        """on_pipeline_complete should push progress at 100/100."""
        bridge = A2ABridge(session_id="sess-6")
        with (
            patch(f"{_SVC}.push_progress", new_callable=AsyncMock) as mock_progress,
            patch(f"{_SVC}.push_render", new_callable=AsyncMock),
        ):
            await bridge.on_pipeline_complete("pipe-6", {"done": True})

            mock_progress.assert_called_once()
            args, kwargs = mock_progress.call_args
            assert kwargs["value"] == 100
            assert kwargs["total"] == 100
            assert "completed" in kwargs["message"].lower()

    # 7
    async def test_pipeline_complete_renders_card(self):
        """on_pipeline_complete should render a card with the result."""
        bridge = A2ABridge(session_id="sess-7")
        with (
            patch(f"{_SVC}.push_progress", new_callable=AsyncMock),
            patch(f"{_SVC}.push_render", new_callable=AsyncMock) as mock_render,
        ):
            await bridge.on_pipeline_complete("pipe-7", {"answer": 42})

            mock_render.assert_called_once()
            args, kwargs = mock_render.call_args
            assert kwargs["component_type"] == "card"
            assert "Pipeline Complete" in kwargs["data"]["title"]
            assert "42" in kwargs["data"]["content"]


class TestA2ABridgeHumanApproval:
    """Test 8: request_human_approval delegates to request_confirm."""

    # 8
    async def test_request_human_approval_delegates(self):
        """request_human_approval should call request_confirm and return its result."""
        bridge = A2ABridge(session_id="sess-8")
        with patch(f"{_SVC}.request_confirm", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True

            result = await bridge.request_human_approval(
                "pipe-8", "deploy", "Deploy to production?"
            )

            assert result is True
            mock_confirm.assert_called_once()
            args, kwargs = mock_confirm.call_args
            assert args[0] == "sess-8"
            assert "deploy" in kwargs["title"].lower()
            assert kwargs["severity"] == "warning"
            assert kwargs["timeout"] == 120


class TestA2ABridgeEdgeCases:
    """Tests 9-12: edge cases with None/empty results."""

    # 9
    async def test_pipeline_complete_with_none_result(self):
        """on_pipeline_complete should handle None result gracefully."""
        bridge = A2ABridge(session_id="sess-9")
        with (
            patch(f"{_SVC}.push_progress", new_callable=AsyncMock),
            patch(f"{_SVC}.push_render", new_callable=AsyncMock) as mock_render,
        ):
            await bridge.on_pipeline_complete("pipe-9", None)

            args, kwargs = mock_render.call_args
            assert kwargs["data"]["content"] == "No output"

    # 10
    async def test_step_complete_truncates_long_result(self):
        """on_step_complete should truncate result_preview to 200 chars."""
        bridge = A2ABridge(session_id="sess-10")
        with patch(f"{_SVC}.push_update", new_callable=AsyncMock) as mock_update:
            long_result = "x" * 500
            await bridge.on_step_complete("pipe-10", 0, "big_step", long_result)

            args, kwargs = mock_update.call_args
            preview = kwargs["data"]["steps"][0]["result_preview"]
            assert len(preview) <= 200

    # 11
    async def test_step_failed_truncates_long_error(self):
        """on_step_failed should truncate error to 300 chars."""
        bridge = A2ABridge(session_id="sess-11")
        with patch(f"{_SVC}.push_notify", new_callable=AsyncMock) as mock_notify:
            long_error = "E" * 500
            await bridge.on_step_failed("pipe-11", 0, "fail_step", long_error)

            args, kwargs = mock_notify.call_args
            assert len(kwargs["message"]) <= 300

    # 12
    async def test_session_id_passed_through_all_methods(self):
        """Session ID should propagate to every service call."""
        bridge = A2ABridge(session_id="unique-sess-id")
        with (
            patch(f"{_SVC}.push_render", new_callable=AsyncMock) as mock_render,
            patch(f"{_SVC}.push_progress", new_callable=AsyncMock) as mock_progress,
        ):
            await bridge.on_pipeline_start("p", ["s1"])
            assert mock_render.call_args[0][0] == "unique-sess-id"
            assert mock_progress.call_args[0][0] == "unique-sess-id"
