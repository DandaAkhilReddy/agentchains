"""High-level A2UI service for agents to interact with the UI.

Provides convenience functions that build JSON-RPC messages and send
them through the A2UI connection manager.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from marketplace.a2ui.connection_manager import a2ui_connection_manager
from marketplace.a2ui.session_manager import a2ui_session_manager
from marketplace.a2ui.security import sanitize_html, validate_payload_size


def _build_jsonrpc_notification(method: str, params: dict[str, Any]) -> dict:
    """Build a JSON-RPC 2.0 notification (no id, no response expected)."""
    return {"jsonrpc": "2.0", "method": method, "params": params}


async def push_render(
    session_id: str,
    component_type: str,
    data: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> str:
    """Push a UI component to the client.

    Returns the generated component_id.
    """
    if not validate_payload_size(data):
        raise ValueError("Payload exceeds maximum size (1 MB)")

    component_id = str(uuid.uuid4())
    session = a2ui_session_manager.get_session(session_id)
    if session:
        session.active_components.add(component_id)

    message = _build_jsonrpc_notification("ui.render", {
        "component_id": component_id,
        "component_type": component_type,
        "data": data,
        "metadata": metadata,
    })
    await a2ui_connection_manager.send_to_session(session_id, message)
    return component_id


async def push_update(
    session_id: str,
    component_id: str,
    operation: str,
    data: dict[str, Any],
) -> None:
    """Patch an existing UI component."""
    if operation not in ("replace", "merge", "append"):
        raise ValueError(f"Invalid operation: {operation}")
    if not validate_payload_size(data):
        raise ValueError("Payload exceeds maximum size (1 MB)")

    message = _build_jsonrpc_notification("ui.update", {
        "component_id": component_id,
        "operation": operation,
        "data": data,
    })
    await a2ui_connection_manager.send_to_session(session_id, message)


async def request_input(
    session_id: str,
    input_type: str,
    prompt: str,
    options: list[str] | None = None,
    validation: dict[str, Any] | None = None,
    timeout: float = 60,
) -> Any:
    """Request input from the user and await their response.

    Sends a ui.request_input message and waits for the user to respond
    via user.respond. Returns the user's value or raises asyncio.TimeoutError.
    """
    request_id = str(uuid.uuid4())
    future = a2ui_session_manager.set_pending_input(session_id, request_id)

    message = _build_jsonrpc_notification("ui.request_input", {
        "request_id": request_id,
        "input_type": input_type,
        "prompt": sanitize_html(prompt),
        "options": options,
        "validation": validation,
    })
    await a2ui_connection_manager.send_to_session(session_id, message)

    return await asyncio.wait_for(future, timeout=timeout)


async def request_confirm(
    session_id: str,
    title: str,
    description: str = "",
    severity: str = "info",
    timeout: float = 30,
) -> dict[str, Any]:
    """Request approval from the user and await their decision.

    Sends a ui.confirm message and waits for the user to respond
    via user.approve. Returns {"approved": bool, "reason": str | None}
    or raises asyncio.TimeoutError.
    """
    request_id = str(uuid.uuid4())
    future = a2ui_session_manager.set_pending_input(session_id, request_id)

    message = _build_jsonrpc_notification("ui.confirm", {
        "request_id": request_id,
        "title": sanitize_html(title),
        "description": sanitize_html(description),
        "severity": severity,
        "timeout_seconds": int(timeout),
    })
    await a2ui_connection_manager.send_to_session(session_id, message)

    return await asyncio.wait_for(future, timeout=timeout)


async def push_progress(
    session_id: str,
    task_id: str,
    progress_type: str,
    value: float | None = None,
    total: float | None = None,
    message: str | None = None,
) -> None:
    """Stream a progress update to the UI."""
    msg = _build_jsonrpc_notification("ui.progress", {
        "task_id": task_id,
        "progress_type": progress_type,
        "value": value,
        "total": total,
        "message": sanitize_html(message) if message else None,
    })
    await a2ui_connection_manager.send_to_session(session_id, msg)


async def push_navigate(
    session_id: str,
    url: str,
    new_tab: bool = False,
) -> None:
    """Redirect the user to a URL."""
    message = _build_jsonrpc_notification("ui.navigate", {
        "url": url,
        "new_tab": new_tab,
    })
    await a2ui_connection_manager.send_to_session(session_id, message)


async def push_notify(
    session_id: str,
    level: str,
    title: str,
    message: str | None = None,
    duration_ms: int = 5000,
) -> None:
    """Send a toast notification to the UI."""
    msg = _build_jsonrpc_notification("ui.notify", {
        "level": level,
        "title": sanitize_html(title),
        "message": sanitize_html(message) if message else None,
        "duration_ms": duration_ms,
    })
    await a2ui_connection_manager.send_to_session(session_id, msg)
