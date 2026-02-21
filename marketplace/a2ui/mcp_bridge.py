"""A2UI ↔ MCP bridge — MCP tool executions trigger UI updates.

When an MCP tool is called, this bridge can stream progress and
results to a connected A2UI session.
"""

from __future__ import annotations

import logging
from typing import Any

from marketplace.a2ui.session_manager import a2ui_session_manager
from marketplace.services.a2ui_service import (
    push_notify,
    push_progress,
    push_render,
)

logger = logging.getLogger(__name__)


async def push_tool_execution_start(
    session_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> str | None:
    """Notify the UI that an MCP tool execution has started.

    Returns a task_id for tracking progress.
    """
    session = a2ui_session_manager.get_session(session_id)
    if not session:
        return None

    import uuid

    task_id = str(uuid.uuid4())

    await push_progress(
        session_id,
        task_id=task_id,
        progress_type="indeterminate",
        message=f"Executing tool: {tool_name}",
    )

    return task_id


async def push_tool_execution_result(
    session_id: str,
    task_id: str,
    tool_name: str,
    result: dict[str, Any],
) -> str | None:
    """Render an MCP tool execution result as an A2UI component.

    Returns the component_id if session is active.
    """
    session = a2ui_session_manager.get_session(session_id)
    if not session:
        return None

    # Complete the progress
    await push_progress(
        session_id,
        task_id=task_id,
        progress_type="determinate",
        value=1,
        total=1,
        message=f"Completed: {tool_name}",
    )

    # Render the result
    data = {
        "title": f"Tool Result: {tool_name}",
        "content": result,
        "source": "mcp_tool",
    }
    return await push_render(
        session_id, "code", data,
        metadata={"mcp_tool": tool_name, "task_id": task_id},
    )


async def push_tool_execution_error(
    session_id: str,
    task_id: str,
    tool_name: str,
    error: str,
) -> None:
    """Notify the UI that an MCP tool execution failed."""
    session = a2ui_session_manager.get_session(session_id)
    if not session:
        return

    await push_progress(
        session_id,
        task_id=task_id,
        progress_type="determinate",
        value=1,
        total=1,
        message=f"Failed: {tool_name}",
    )

    await push_notify(session_id, "error", f"Tool failed: {tool_name}", error)


async def push_resource_read_result(
    session_id: str,
    uri: str,
    content: dict[str, Any],
) -> str | None:
    """Render an MCP resource read as an A2UI component."""
    session = a2ui_session_manager.get_session(session_id)
    if not session:
        return None

    data = {
        "title": f"Resource: {uri}",
        "content": content,
        "source": "mcp_resource",
    }
    return await push_render(
        session_id, "card", data,
        metadata={"mcp_resource_uri": uri},
    )
