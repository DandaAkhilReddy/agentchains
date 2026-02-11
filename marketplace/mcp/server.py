"""MCP protocol handler: JSON-RPC over SSE.

Implements the Model Context Protocol for agent-to-agent communication.
Supports: initialize, tools/list, tools/call, resources/list, resources/read.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from marketplace.mcp.auth import validate_mcp_auth
from marketplace.mcp.session_manager import session_manager
from marketplace.mcp.tools import TOOL_DEFINITIONS, execute_tool
from marketplace.mcp.resources import RESOURCE_DEFINITIONS, read_resource

router = APIRouter(prefix="/mcp", tags=["mcp"])

# Protocol constants
MCP_VERSION = "2024-11-05"
SERVER_NAME = "agentchains-marketplace"
SERVER_VERSION = "0.3.0"


def _jsonrpc_response(id, result):
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _jsonrpc_error(id, code, message):
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


async def handle_message(body: dict, session_id: str | None = None) -> dict:
    """Process a JSON-RPC message and return the response."""
    method = body.get("method", "")
    params = body.get("params", {})
    msg_id = body.get("id")

    # ── initialize ──
    if method == "initialize":
        try:
            agent_id = validate_mcp_auth(params)
        except Exception as e:
            return _jsonrpc_error(msg_id, -32000, str(e))

        session = session_manager.create_session(agent_id)
        return _jsonrpc_response(msg_id, {
            "protocolVersion": MCP_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            "_session_id": session.session_id,
            "_agent_id": agent_id,
        })

    # ── All other methods require a session ──
    session = None
    if session_id:
        session = session_manager.get_session(session_id)
    if not session:
        # Try getting session from params
        sid = params.get("_session_id", "")
        if sid:
            session = session_manager.get_session(sid)
    if not session:
        return _jsonrpc_error(msg_id, -32000, "No active session. Call initialize first.")

    # Rate limit check
    if not session_manager.check_rate_limit(session):
        return _jsonrpc_error(msg_id, -32000, "Rate limit exceeded. Max 60 requests/minute.")

    # ── tools/list ──
    if method == "tools/list":
        return _jsonrpc_response(msg_id, {"tools": TOOL_DEFINITIONS})

    # ── tools/call ──
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = await execute_tool(tool_name, arguments, session.agent_id)
            return _jsonrpc_response(msg_id, {
                "content": [{"type": "text", "text": json.dumps(result)}],
            })
        except Exception as e:
            return _jsonrpc_error(msg_id, -32000, f"Tool execution error: {str(e)}")

    # ── resources/list ──
    elif method == "resources/list":
        return _jsonrpc_response(msg_id, {"resources": RESOURCE_DEFINITIONS})

    # ── resources/read ──
    elif method == "resources/read":
        uri = params.get("uri", "")
        try:
            result = await read_resource(uri, session.agent_id)
            return _jsonrpc_response(msg_id, {
                "contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(result)}],
            })
        except Exception as e:
            return _jsonrpc_error(msg_id, -32000, f"Resource read error: {str(e)}")

    # ── ping ──
    elif method == "ping":
        return _jsonrpc_response(msg_id, {})

    # ── notifications/initialized ──
    elif method == "notifications/initialized":
        return _jsonrpc_response(msg_id, {"acknowledged": True})

    return _jsonrpc_error(msg_id, -32601, f"Method not found: {method}")


@router.post("/message")
async def mcp_message(request: Request):
    """Handle a single MCP JSON-RPC message."""
    body = await request.json()
    session_id = request.headers.get("X-MCP-Session-ID")
    response = await handle_message(body, session_id)
    return JSONResponse(content=response)


@router.post("/sse")
async def mcp_sse(request: Request):
    """SSE endpoint for MCP communication.

    Client sends JSON-RPC messages, server responds via SSE events.
    Pure StreamingResponse — no external SSE library needed.
    """
    body = await request.json()
    session_id = request.headers.get("X-MCP-Session-ID")

    async def event_stream():
        response = await handle_message(body, session_id)
        data = json.dumps(response)
        yield f"event: message\ndata: {data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/health")
async def mcp_health():
    """MCP server health check."""
    return {
        "status": "ok",
        "protocol_version": MCP_VERSION,
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "active_sessions": session_manager.active_count,
        "tools_count": len(TOOL_DEFINITIONS),
        "resources_count": len(RESOURCE_DEFINITIONS),
    }
