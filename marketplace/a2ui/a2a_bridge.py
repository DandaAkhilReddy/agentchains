"""A2UI-to-A2A bridge — Agent-driven UI updates in A2A pipelines.

Allows A2A pipeline steps to push UI components, request user input,
and stream progress through the A2UI protocol.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class A2ABridge:
    """Bridge A2A pipeline events to A2UI protocol for real-time UI updates."""

    def __init__(self, session_id: str):
        self._session_id = session_id

    async def on_pipeline_start(self, pipeline_id: str, steps: list[str]) -> None:
        """Notify UI that an A2A pipeline has started."""
        from marketplace.services.a2ui_service import push_render, push_progress

        await push_render(
            self._session_id,
            component_type="steps",
            data={
                "pipeline_id": pipeline_id,
                "steps": [{"name": s, "status": "pending"} for s in steps],
                "current_step": 0,
            },
            metadata={"source": "a2a_pipeline"},
        )
        await push_progress(
            self._session_id,
            task_id=pipeline_id,
            progress_type="indeterminate",
            message=f"Starting pipeline with {len(steps)} steps...",
        )

    async def on_step_start(self, pipeline_id: str, step_index: int, step_name: str) -> None:
        """Notify UI that a pipeline step has started."""
        from marketplace.services.a2ui_service import push_progress

        await push_progress(
            self._session_id,
            task_id=pipeline_id,
            progress_type="determinate",
            value=step_index,
            message=f"Running: {step_name}",
        )

    async def on_step_complete(
        self, pipeline_id: str, step_index: int, step_name: str, result: Any
    ) -> None:
        """Notify UI that a pipeline step completed."""
        from marketplace.services.a2ui_service import push_update

        await push_update(
            self._session_id,
            component_id=f"pipeline-{pipeline_id}",
            operation="merge",
            data={
                "steps": {step_index: {"status": "completed", "result_preview": str(result)[:200]}},
            },
        )

    async def on_step_failed(
        self, pipeline_id: str, step_index: int, step_name: str, error: str
    ) -> None:
        """Notify UI that a pipeline step failed."""
        from marketplace.services.a2ui_service import push_notify

        await push_notify(
            self._session_id,
            level="error",
            title=f"Step failed: {step_name}",
            message=error[:300],
        )

    async def on_pipeline_complete(self, pipeline_id: str, result: Any) -> None:
        """Notify UI that the pipeline completed."""
        from marketplace.services.a2ui_service import push_progress, push_render

        await push_progress(
            self._session_id,
            task_id=pipeline_id,
            progress_type="determinate",
            value=100,
            total=100,
            message="Pipeline completed",
        )
        await push_render(
            self._session_id,
            component_type="card",
            data={
                "title": "Pipeline Complete",
                "content": str(result)[:500] if result else "No output",
            },
            metadata={"source": "a2a_pipeline", "pipeline_id": pipeline_id},
        )

    async def request_human_approval(
        self, pipeline_id: str, step_name: str, description: str
    ) -> bool:
        """Request human approval before proceeding with a pipeline step."""
        from marketplace.services.a2ui_service import request_confirm

        return await request_confirm(
            self._session_id,
            title=f"Approval required: {step_name}",
            description=description,
            severity="warning",
            timeout=120,
        )
