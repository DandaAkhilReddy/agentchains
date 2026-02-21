"""A2UI JSON-RPC 2.0 message handler.

Pattern follows marketplace/mcp/server.py handle_message with
method dispatch for a2ui.init, user.respond, user.approve, user.cancel.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.a2ui import A2UI_VERSION
from marketplace.a2ui.session_manager import a2ui_session_manager

# Protocol constants
SERVER_NAME = "agentchains-a2ui"
SERVER_VERSION = "0.1.0"


def _jsonrpc_response(id, result):
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _jsonrpc_error(id, code, message):
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


async def handle_a2ui_message(
    body: dict,
    session_id: str | None = None,
    db: AsyncSession | None = None,
) -> dict:
    """Process a JSON-RPC message and return the response."""
    method = body.get("method", "")
    params = body.get("params", {})
    msg_id = body.get("id")

    # ── a2ui.init ──
    if method == "a2ui.init":
        agent_id = params.get("agent_id")
        if not agent_id:
            return _jsonrpc_error(msg_id, -32602, "Missing agent_id in params")

        user_id = params.get("user_id")
        client_info = params.get("client_info", {})
        capabilities = params.get("capabilities", {})

        session = a2ui_session_manager.create_session(
            agent_id=agent_id,
            user_id=user_id,
            capabilities=capabilities,
        )
        return _jsonrpc_response(msg_id, {
            "session_id": session.session_id,
            "capabilities": {
                "components": ["card", "table", "form", "chart", "markdown",
                               "code", "image", "alert", "steps"],
                "input_types": ["text", "select", "number", "date", "file"],
                "streaming": True,
            },
            "version": A2UI_VERSION,
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        })

    # ── All other methods require a session ──
    session = None
    if session_id:
        session = a2ui_session_manager.get_session(session_id)
    if not session:
        # Try getting session from params
        sid = params.get("session_id", "")
        if sid:
            session = a2ui_session_manager.get_session(sid)
    if not session:
        return _jsonrpc_error(msg_id, -32000, "No active session. Call a2ui.init first.")

    # Rate limit check
    if not a2ui_session_manager.check_rate_limit(session):
        return _jsonrpc_error(msg_id, -32000, "Rate limit exceeded. Max 60 requests/minute.")

    # ── user.respond ──
    if method == "user.respond":
        request_id = params.get("request_id", "")
        value = params.get("value")
        if not request_id:
            return _jsonrpc_error(msg_id, -32602, "Missing request_id in params")
        resolved = a2ui_session_manager.resolve_pending_input(
            session.session_id, request_id, value,
        )
        if not resolved:
            return _jsonrpc_error(
                msg_id, -32000,
                f"No pending input for request_id: {request_id}",
            )
        return _jsonrpc_response(msg_id, {"acknowledged": True, "request_id": request_id})

    # ── user.approve ──
    elif method == "user.approve":
        request_id = params.get("request_id", "")
        approved = params.get("approved", False)
        reason = params.get("reason")
        if not request_id:
            return _jsonrpc_error(msg_id, -32602, "Missing request_id in params")
        result_value = {"approved": approved, "reason": reason}
        resolved = a2ui_session_manager.resolve_pending_input(
            session.session_id, request_id, result_value,
        )
        if not resolved:
            return _jsonrpc_error(
                msg_id, -32000,
                f"No pending confirmation for request_id: {request_id}",
            )
        return _jsonrpc_response(msg_id, {"acknowledged": True, "request_id": request_id})

    # ── user.cancel ──
    elif method == "user.cancel":
        task_id = params.get("task_id", "")
        if not task_id:
            return _jsonrpc_error(msg_id, -32602, "Missing task_id in params")
        # Cancel any pending input futures for this task
        cancelled = False
        for req_id, future in list(session.pending_inputs.items()):
            if req_id == task_id or req_id.startswith(f"{task_id}:"):
                if not future.done():
                    future.cancel()
                session.pending_inputs.pop(req_id, None)
                cancelled = True
        return _jsonrpc_response(msg_id, {
            "acknowledged": True,
            "task_id": task_id,
            "cancelled": cancelled,
        })

    # ── ping ──
    elif method == "ping":
        return _jsonrpc_response(msg_id, {})

    return _jsonrpc_error(msg_id, -32601, f"Method not found: {method}")


class A2UIMessageHandler:
    """Class wrapper for A2UI message handler functions."""

    async def handle(self, message, **kwargs):
        return await handle_a2ui_message(message, **kwargs)
