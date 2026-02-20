"""A2A Server — HTTP server implementing the Agent-to-Agent protocol.

Implements the A2A spec with JSON-RPC 2.0 message handling, SSE streaming
for long-running tasks, and .well-known/agent.json agent card endpoint.

Usage:
    from agents.a2a_servers.server import create_a2a_app

    app = create_a2a_app(
        name="My Agent",
        description="A marketplace agent",
        skills=[{"id": "search", "name": "Search", "description": "Search the web"}],
        task_handler=my_handler,
    )
    uvicorn.run(app, host="0.0.0.0", port=9000)
"""

import json
import logging
from typing import Any, Callable, Awaitable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agents.a2a_servers.agent_card import generate_agent_card
from agents.a2a_servers.task_manager import TaskManager, TaskState

logger = logging.getLogger(__name__)


# Type for the user-provided task handler
TaskHandler = Callable[[str, str, dict], Awaitable[dict]]


def create_a2a_app(
    name: str,
    description: str,
    skills: list[dict[str, Any]] | None = None,
    task_handler: TaskHandler | None = None,
    host: str = "0.0.0.0",
    port: int = 9000,
) -> FastAPI:
    """Create a FastAPI app implementing the A2A protocol.

    Args:
        name: Agent display name
        description: What this agent does
        skills: List of skill definitions
        task_handler: Async function(skill_id, message, params) → result dict
        host: Bind host
        port: Bind port

    Returns:
        FastAPI application ready to run with uvicorn
    """
    app = FastAPI(title=f"A2A: {name}", version="0.1.0")
    task_manager = TaskManager()
    base_url = f"http://{host}:{port}"

    agent_card = generate_agent_card(
        name=name,
        description=description,
        url=base_url,
        skills=skills or [],
    )

    # Default handler if none provided
    async def _default_handler(skill_id: str, message: str, params: dict) -> dict:
        return {
            "status": "completed",
            "message": f"Agent '{name}' received: {message}",
            "skill_id": skill_id,
        }

    handler = task_handler or _default_handler

    # ── Agent Card Endpoint ─────────────────────────────────

    @app.get("/.well-known/agent.json")
    async def get_agent_card():
        """Serve the A2A agent card for discovery."""
        return agent_card

    # ── JSON-RPC Endpoint ───────────────────────────────────

    @app.post("/")
    async def jsonrpc_handler(request: Request):
        """Handle A2A JSON-RPC 2.0 requests."""
        try:
            body = await request.json()
        except Exception:
            return _jsonrpc_error(None, -32700, "Parse error")

        method = body.get("method")
        params = body.get("params", {})
        rpc_id = body.get("id")

        if method == "tasks/send":
            return await _handle_send(rpc_id, params, handler, task_manager)
        elif method == "tasks/get":
            return _handle_get(rpc_id, params, task_manager)
        elif method == "tasks/cancel":
            return _handle_cancel(rpc_id, params, task_manager)
        elif method == "tasks/sendSubscribe":
            return await _handle_send_subscribe(rpc_id, params, handler, task_manager)
        else:
            return _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")

    return app


# ── JSON-RPC Handlers ───────────────────────────────────────────


async def _handle_send(
    rpc_id: Any,
    params: dict,
    handler: TaskHandler,
    task_manager: TaskManager,
) -> JSONResponse:
    """Handle tasks/send — create and execute a task."""
    skill_id = params.get("skill_id", "default")
    message_data = params.get("message", {})
    message_text = ""

    # Extract text from A2A message format
    parts = message_data.get("parts", [])
    for part in parts:
        if part.get("type") == "text":
            message_text = part.get("text", "")
            break
    if not message_text:
        message_text = message_data.get("text", str(message_data))

    task = task_manager.create_task(skill_id, message_text)
    task_manager.update_state(task.id, TaskState.WORKING)

    try:
        result = await handler(skill_id, message_text, params)
        task_manager.add_artifact(task.id, {
            "type": "text",
            "parts": [{"type": "text", "text": json.dumps(result)}],
        })
        task_manager.update_state(task.id, TaskState.COMPLETED)
    except Exception as e:
        logger.error("Task %s failed: %s", task.id, e)
        task_manager.update_state(task.id, TaskState.FAILED, error=str(e))

    return _jsonrpc_result(rpc_id, task.to_dict())


def _handle_get(
    rpc_id: Any,
    params: dict,
    task_manager: TaskManager,
) -> JSONResponse:
    """Handle tasks/get — retrieve task status."""
    task_id = params.get("id")
    if not task_id:
        return _jsonrpc_error(rpc_id, -32602, "Missing 'id' parameter")

    task = task_manager.get_task(task_id)
    if not task:
        return _jsonrpc_error(rpc_id, -32602, f"Task not found: {task_id}")

    return _jsonrpc_result(rpc_id, task.to_dict())


def _handle_cancel(
    rpc_id: Any,
    params: dict,
    task_manager: TaskManager,
) -> JSONResponse:
    """Handle tasks/cancel — cancel a running task."""
    task_id = params.get("id")
    if not task_id:
        return _jsonrpc_error(rpc_id, -32602, "Missing 'id' parameter")

    task = task_manager.cancel_task(task_id)
    if not task:
        return _jsonrpc_error(rpc_id, -32602, f"Cannot cancel task: {task_id}")

    return _jsonrpc_result(rpc_id, task.to_dict())


async def _handle_send_subscribe(
    rpc_id: Any,
    params: dict,
    handler: TaskHandler,
    task_manager: TaskManager,
) -> StreamingResponse:
    """Handle tasks/sendSubscribe — create task and stream updates via SSE."""
    skill_id = params.get("skill_id", "default")
    message_data = params.get("message", {})
    message_text = ""

    parts = message_data.get("parts", [])
    for part in parts:
        if part.get("type") == "text":
            message_text = part.get("text", "")
            break
    if not message_text:
        message_text = message_data.get("text", str(message_data))

    task = task_manager.create_task(skill_id, message_text)

    async def event_stream():
        # Start task execution
        task_manager.update_state(task.id, TaskState.WORKING)

        try:
            result = await handler(skill_id, message_text, params)
            task_manager.add_artifact(task.id, {
                "type": "text",
                "parts": [{"type": "text", "text": json.dumps(result)}],
            })
            task_manager.update_state(task.id, TaskState.COMPLETED)
        except Exception as e:
            task_manager.update_state(task.id, TaskState.FAILED, error=str(e))

        # Stream all updates
        async for update in task_manager.stream_updates(task.id):
            yield f"data: {json.dumps(update)}\n\n"

        # Final state
        final_task = task_manager.get_task(task.id)
        if final_task:
            yield f"data: {json.dumps(final_task.to_dict())}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── JSON-RPC Helpers ────────────────────────────────────────────


def _jsonrpc_result(rpc_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": rpc_id,
        "result": result,
    })


def _jsonrpc_error(rpc_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": code, "message": message},
        },
        status_code=200,  # JSON-RPC errors are always 200
    )
