"""Utilities for safe fire-and-forget background task scheduling."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)
_PENDING_TASKS: set[asyncio.Task[Any]] = set()


def fire_and_forget(
    coro: Coroutine[Any, Any, Any], *, task_name: str | None = None
) -> asyncio.Task[Any] | None:
    """Schedule a coroutine and log unexpected failures.

    This helper keeps API handlers and services from having to repeat
    per-call `create_task` + callback error handling boilerplate.
    """
    try:
        task = asyncio.create_task(coro, name=task_name)
    except RuntimeError:
        # No running loop (e.g. during shutdown); silently skip best-effort work.
        return None
    _PENDING_TASKS.add(task)

    def _on_done(done_task: asyncio.Task[Any]) -> None:
        _PENDING_TASKS.discard(done_task)
        try:
            done_task.result()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Background task failed: %s", task_name or "unnamed task")

    task.add_done_callback(_on_done)
    return task


async def drain_background_tasks(timeout_seconds: float = 1.0) -> None:
    """Wait for in-flight fire-and-forget tasks to finish.

    Primarily used by tests to avoid teardown races where the event loop closes
    before best-effort background work has completed.
    """
    if not _PENDING_TASKS:
        return

    pending = {task for task in _PENDING_TASKS if not task.done()}
    if not pending:
        return

    _, still_pending = await asyncio.wait(pending, timeout=timeout_seconds)
    for task in still_pending:
        task.cancel()

    if still_pending:
        await asyncio.gather(*still_pending, return_exceptions=True)
