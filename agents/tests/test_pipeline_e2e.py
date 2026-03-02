"""Tests for the Pipeline class with mocked A2A calls.

Because Pipeline uses httpx.AsyncClient internally to make real HTTP calls,
we test pipeline logic by mocking A2AClient.send_task with AsyncMock.
This lets us verify orchestration behaviour (step sequencing, transform_fn,
failure propagation, exception handling) without any real network I/O.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, call, patch

import pytest

from agents.common.pipeline import Pipeline, PipelineStep


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_AGENT_1 = "http://search-agent:9001"
_AGENT_2 = "http://sentiment-agent:9002"

_COMPLETED_TASK = {
    "id": "task-001",
    "state": "completed",
    "artifacts": [
        {"parts": [{"type": "text", "text": json.dumps({"result": "step-output"})}]}
    ],
}

_FAILED_TASK = {
    "id": "task-002",
    "state": "failed",
    "error": "downstream agent crashed",
    "artifacts": [],
}

_COMPLETED_NO_ARTIFACTS = {
    "id": "task-003",
    "state": "completed",
    "artifacts": [],
}


# ---------------------------------------------------------------------------
# TestPipelineWith2Steps — Happy path
# ---------------------------------------------------------------------------


class TestPipelineWith2Steps:
    """Two-step pipeline with mocked A2A calls."""

    async def test_execute_returns_completed_status(self) -> None:
        p = Pipeline("SearchPipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_COMPLETED_TASK,
        ):
            result = await p.execute('{"query": "python"}')

        assert result["status"] == "completed"

    async def test_execute_calls_both_agents(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        send_mock = AsyncMock(return_value=_COMPLETED_TASK)
        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            await p.execute("initial input")

        assert send_mock.call_count == 2

    async def test_execute_passes_initial_input_to_first_step(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        send_mock = AsyncMock(return_value=_COMPLETED_TASK)
        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            await p.execute("my initial query")

        first_call = send_mock.call_args_list[0]
        assert first_call[1]["message"] == "my initial query"

    async def test_execute_result_contains_two_steps(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_COMPLETED_TASK,
        ):
            result = await p.execute("input")

        assert len(result["steps"]) == 2

    async def test_execute_total_steps_is_2(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_COMPLETED_TASK,
        ):
            result = await p.execute("input")

        assert result["total_steps"] == 2

    async def test_execute_final_result_is_last_step_task(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_COMPLETED_TASK,
        ):
            result = await p.execute("input")

        assert result["final_result"] == _COMPLETED_TASK

    async def test_execute_step_records_have_agent_url(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_COMPLETED_TASK,
        ):
            result = await p.execute("input")

        urls = [s["agent_url"] for s in result["steps"]]
        assert _AGENT_1 in urls
        assert _AGENT_2 in urls

    async def test_execute_step_numbers_are_sequential(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_COMPLETED_TASK,
        ):
            result = await p.execute("input")

        step_nums = [s["step"] for s in result["steps"]]
        assert step_nums == [1, 2]


# ---------------------------------------------------------------------------
# TestPipelineFailureHandling
# ---------------------------------------------------------------------------


class TestPipelineFailureHandling:
    """Pipeline behaviour when a step returns a failed task or raises an exception."""

    async def test_failed_step_1_produces_failed_status(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_FAILED_TASK,
        ):
            result = await p.execute("input")

        assert result["status"] == "failed"

    async def test_failed_step_1_stops_before_step_2(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_FAILED_TASK,
        ):
            result = await p.execute("input")

        assert len(result["steps"]) == 1

    async def test_failed_step_records_failed_at_step_index(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_FAILED_TASK,
        ):
            result = await p.execute("input")

        assert result["failed_at_step"] == 1

    async def test_failed_step_propagates_error_message(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_FAILED_TASK,
        ):
            result = await p.execute("input")

        assert "downstream agent crashed" in result["error"]

    async def test_step_exception_produces_failed_status(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            side_effect=ConnectionError("refused"),
        ):
            result = await p.execute("input")

        assert result["status"] == "failed"

    async def test_step_exception_error_contains_message(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            side_effect=TimeoutError("request timed out"),
        ):
            result = await p.execute("input")

        assert "request timed out" in result["error"]

    async def test_step_exception_records_failed_at_step(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            result = await p.execute("input")

        assert result["failed_at_step"] == 1

    async def test_second_step_failure_after_first_success(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        send_mock = AsyncMock(side_effect=[_COMPLETED_TASK, _FAILED_TASK])
        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            result = await p.execute("input")

        assert result["status"] == "failed"
        assert result["failed_at_step"] == 2
        assert len(result["steps"]) == 2


# ---------------------------------------------------------------------------
# TestPipelineTransformFn
# ---------------------------------------------------------------------------


class TestPipelineTransformFn:
    """Verify transform_fn is applied between steps."""

    async def test_transform_fn_output_is_sent_to_next_step(self) -> None:
        """transform_fn on step 1 converts step-1's result to the message for step 2."""
        transform = lambda r: "transformed:" + r.get("state", "")

        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search", transform_fn=transform)
        p.add_step(_AGENT_2, "analyze-sentiment")

        send_mock = AsyncMock(return_value=_COMPLETED_TASK)
        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            await p.execute("initial")

        second_call = send_mock.call_args_list[1]
        assert second_call[1]["message"] == "transformed:completed"

    async def test_without_transform_fn_artifact_text_is_used(self) -> None:
        """Default inter-step transfer: extract text from first artifact part."""
        artifact_text = json.dumps({"result": "extracted from artifact"})
        task_with_artifact = {
            "id": "t1",
            "state": "completed",
            "artifacts": [{"parts": [{"type": "text", "text": artifact_text}]}],
        }

        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")  # no transform_fn
        p.add_step(_AGENT_2, "analyze-sentiment")

        send_mock = AsyncMock(return_value=task_with_artifact)
        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            await p.execute("first-input")

        second_call = send_mock.call_args_list[1]
        assert second_call[1]["message"] == artifact_text

    async def test_without_transform_fn_and_no_artifacts_uses_json_dumps(self) -> None:
        """If artifacts are empty, fall back to json.dumps of the task dict."""
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        send_mock = AsyncMock(return_value=_COMPLETED_NO_ARTIFACTS)
        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            await p.execute("first-input")

        second_call = send_mock.call_args_list[1]
        # The message should be a valid JSON string of the task dict
        parsed = json.loads(second_call[1]["message"])
        assert parsed["state"] == "completed"

    async def test_transform_fn_return_value_is_used_verbatim(self) -> None:
        transform = lambda _r: "constant-message"

        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search", transform_fn=transform)
        p.add_step(_AGENT_2, "analyze-sentiment")

        send_mock = AsyncMock(return_value=_COMPLETED_TASK)
        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            await p.execute("first-input")

        second_call = send_mock.call_args_list[1]
        assert second_call[1]["message"] == "constant-message"


# ---------------------------------------------------------------------------
# TestPipelineEdgeCases
# ---------------------------------------------------------------------------


class TestPipelineEdgeCases:
    """Edge cases: empty pipeline, single-step, custom names."""

    async def test_empty_pipeline_returns_failed_status(self) -> None:
        p = Pipeline("Empty")
        result = await p.execute("input")
        assert result["status"] == "failed"

    async def test_empty_pipeline_error_mentions_no_steps(self) -> None:
        p = Pipeline("Empty")
        result = await p.execute("input")
        assert "no steps" in result["error"].lower()

    async def test_single_step_pipeline_returns_completed(self) -> None:
        p = Pipeline("Single")
        p.add_step(_AGENT_1, "web-search")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_COMPLETED_TASK,
        ):
            result = await p.execute("query")

        assert result["status"] == "completed"

    async def test_step_name_appears_in_step_record(self) -> None:
        p = Pipeline("NamedPipe")
        p.add_step(_AGENT_1, "web-search", name="SearchStep")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=_COMPLETED_TASK,
        ):
            result = await p.execute("input")

        assert result["steps"][0]["name"] == "SearchStep"

    async def test_pipeline_uses_correct_skill_id_per_step(self) -> None:
        p = Pipeline("Pipe")
        p.add_step(_AGENT_1, "web-search")
        p.add_step(_AGENT_2, "analyze-sentiment")

        send_mock = AsyncMock(return_value=_COMPLETED_TASK)
        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            await p.execute("input")

        first_skill = send_mock.call_args_list[0][1]["skill_id"]
        second_skill = send_mock.call_args_list[1][1]["skill_id"]
        assert first_skill == "web-search"
        assert second_skill == "analyze-sentiment"
