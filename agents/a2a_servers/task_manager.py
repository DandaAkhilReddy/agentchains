"""A2A Task Manager — in-memory task store with lifecycle management."""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class Task:
    """Represents an A2A task with lifecycle state management."""

    def __init__(self, task_id: str, skill_id: str, message: str):
        self.id = task_id
        self.skill_id = skill_id
        self.message = message
        self.state = TaskState.SUBMITTED
        self.artifacts: list[dict[str, Any]] = []
        self.error: str | None = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self._update_queue: asyncio.Queue[dict] = asyncio.Queue()

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "state": self.state.value,
            "skill_id": self.skill_id,
            "message": self.message,
            "artifacts": self.artifacts,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.error:
            result["error"] = self.error
        return result


class TaskManager:
    """In-memory task store with lifecycle management and streaming updates.

    Usage:
        manager = TaskManager()
        task = manager.create_task("search-skill", "Find Python tutorials")
        manager.update_state(task.id, TaskState.WORKING)
        manager.add_artifact(task.id, {"type": "text", "content": "Found 5 results"})
        manager.update_state(task.id, TaskState.COMPLETED)
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def create_task(self, skill_id: str, message: str) -> Task:
        """Create a new task in SUBMITTED state."""
        task_id = str(uuid.uuid4())
        task = Task(task_id=task_id, skill_id=skill_id, message=message)
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def update_state(self, task_id: str, new_state: TaskState, error: str | None = None) -> Task | None:
        """Update task state and notify subscribers."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        # Validate state transitions
        valid_transitions = {
            TaskState.SUBMITTED: {TaskState.WORKING, TaskState.CANCELED},
            TaskState.WORKING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.INPUT_REQUIRED, TaskState.CANCELED},
            TaskState.INPUT_REQUIRED: {TaskState.WORKING, TaskState.CANCELED},
        }
        allowed = valid_transitions.get(task.state, set())
        if new_state not in allowed:
            return None

        task.state = new_state
        task.updated_at = datetime.now(timezone.utc)
        if error:
            task.error = error

        # Push update to subscribers
        task._update_queue.put_nowait({
            "type": "state_change",
            "task_id": task.id,
            "state": new_state.value,
            "timestamp": task.updated_at.isoformat(),
        })

        return task

    def add_artifact(self, task_id: str, artifact: dict[str, Any]) -> Task | None:
        """Add an artifact to a task and notify subscribers."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.artifacts.append(artifact)
        task.updated_at = datetime.now(timezone.utc)

        task._update_queue.put_nowait({
            "type": "artifact",
            "task_id": task.id,
            "artifact": artifact,
            "timestamp": task.updated_at.isoformat(),
        })

        return task

    def cancel_task(self, task_id: str) -> Task | None:
        """Cancel a task if it's in a cancellable state."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        if task.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED):
            return None
        return self.update_state(task_id, TaskState.CANCELED)

    async def stream_updates(self, task_id: str):
        """Async generator that yields task updates for SSE streaming."""
        task = self._tasks.get(task_id)
        if not task:
            return

        while task.state not in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED):
            try:
                update = await asyncio.wait_for(task._update_queue.get(), timeout=30.0)
                yield update
            except asyncio.TimeoutError:
                yield {"type": "heartbeat", "task_id": task_id}

        # Drain remaining updates
        while not task._update_queue.empty():
            yield task._update_queue.get_nowait()

    def list_tasks(self, limit: int = 50) -> list[dict]:
        """List recent tasks."""
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        """Remove completed/failed/canceled tasks older than max_age_seconds."""
        now = datetime.now(timezone.utc)
        terminal_states = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}
        to_remove = []
        for task_id, task in self._tasks.items():
            if task.state in terminal_states:
                age = (now - task.updated_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(task_id)
        for task_id in to_remove:
            del self._tasks[task_id]
        return len(to_remove)
