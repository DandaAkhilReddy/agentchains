"""Tests for marketplace.core.async_tasks — fire-and-forget and drain utilities.

Covers:
- fire_and_forget: task scheduling, callback cleanup, error logging, no-loop handling
- drain_background_tasks: waiting for pending tasks, timeout cancellation, empty set
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch

import pytest

from marketplace.core.async_tasks import (
    _PENDING_TASKS,
    drain_background_tasks,
    fire_and_forget,
)


# ---------------------------------------------------------------------------
# fire_and_forget
# ---------------------------------------------------------------------------


class TestFireAndForget:
    """Background task scheduling."""

    async def test_schedules_coroutine_and_returns_task(self) -> None:
        async def noop() -> None:
            pass

        task = fire_and_forget(noop(), task_name="test-noop")
        assert task is not None
        assert isinstance(task, asyncio.Task)
        await task  # let it finish

    async def test_task_added_to_pending_set(self) -> None:
        async def slow() -> None:
            await asyncio.sleep(0.05)

        initial_count = len(_PENDING_TASKS)
        task = fire_and_forget(slow(), task_name="test-pending")
        assert task in _PENDING_TASKS
        await task
        # After completion, callback removes it from _PENDING_TASKS
        await asyncio.sleep(0.01)  # allow callback to run
        assert task not in _PENDING_TASKS

    async def test_task_removed_from_pending_on_completion(self) -> None:
        async def quick() -> str:
            return "done"

        task = fire_and_forget(quick(), task_name="test-remove")
        assert task is not None
        await task
        await asyncio.sleep(0.01)
        assert task not in _PENDING_TASKS

    async def test_failed_task_logged_and_removed(self, caplog: pytest.LogCaptureFixture) -> None:
        async def failing() -> None:
            raise RuntimeError("intentional failure")

        with caplog.at_level(logging.ERROR, logger="marketplace.core.async_tasks"):
            task = fire_and_forget(failing(), task_name="test-fail")
            assert task is not None
            # Wait for completion + callback
            await asyncio.sleep(0.1)

        assert task not in _PENDING_TASKS
        assert "Background task failed" in caplog.text
        assert "test-fail" in caplog.text

    async def test_cancelled_task_does_not_log_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def eternal() -> None:
            await asyncio.sleep(999)

        with caplog.at_level(logging.ERROR, logger="marketplace.core.async_tasks"):
            task = fire_and_forget(eternal(), task_name="test-cancel")
            assert task is not None
            task.cancel()
            await asyncio.sleep(0.05)

        # CancelledError should NOT produce an error log
        assert "Background task failed" not in caplog.text

    async def test_task_name_assigned(self) -> None:
        async def noop() -> None:
            pass

        task = fire_and_forget(noop(), task_name="my-custom-name")
        assert task is not None
        assert task.get_name() == "my-custom-name"
        await task

    async def test_none_task_name_still_works(self) -> None:
        async def noop() -> None:
            pass

        task = fire_and_forget(noop())
        assert task is not None
        await task

    def test_returns_none_when_no_event_loop(self) -> None:
        """When called outside an async context (no running loop), returns None."""
        async def noop() -> None:
            pass

        # Create a coroutine but don't run it in an event loop context
        coro = noop()
        with patch(
            "marketplace.core.async_tasks.asyncio.create_task",
            side_effect=RuntimeError("no running event loop"),
        ):
            result = fire_and_forget(coro)
        assert result is None


# ---------------------------------------------------------------------------
# drain_background_tasks
# ---------------------------------------------------------------------------


class TestDrainBackgroundTasks:
    """Graceful shutdown for in-flight tasks."""

    async def test_drain_with_no_pending_tasks(self) -> None:
        """Should return immediately when no tasks are pending."""
        # Clear any leftover tasks
        _PENDING_TASKS.clear()
        await drain_background_tasks(timeout_seconds=0.1)  # should not raise

    async def test_drain_waits_for_running_tasks(self) -> None:
        completed = False

        async def slow() -> None:
            nonlocal completed
            await asyncio.sleep(0.05)
            completed = True

        fire_and_forget(slow(), task_name="drain-test")
        await drain_background_tasks(timeout_seconds=2.0)
        assert completed is True

    async def test_drain_cancels_tasks_after_timeout(self) -> None:
        async def very_slow() -> None:
            await asyncio.sleep(999)

        task = fire_and_forget(very_slow(), task_name="timeout-test")
        assert task is not None

        await drain_background_tasks(timeout_seconds=0.05)
        # Task should be cancelled after timeout
        assert task.cancelled() or task.done()

    async def test_drain_handles_already_done_tasks(self) -> None:
        async def instant() -> None:
            pass

        task = fire_and_forget(instant(), task_name="already-done")
        assert task is not None
        await asyncio.sleep(0.05)  # let it finish
        # Now drain — pending set may still reference it
        await drain_background_tasks(timeout_seconds=0.1)

    async def test_drain_multiple_tasks(self) -> None:
        results: list[int] = []

        async def worker(n: int) -> None:
            await asyncio.sleep(0.02)
            results.append(n)

        for i in range(5):
            fire_and_forget(worker(i), task_name=f"multi-{i}")

        await drain_background_tasks(timeout_seconds=2.0)
        assert len(results) == 5
