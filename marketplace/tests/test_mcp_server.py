"""MCP server tests."""

from __future__ import annotations
import json
import uuid
from unittest.mock import patch, MagicMock
import pytest
from marketplace.core.auth import create_access_token
from marketplace.mcp.session_manager import session_manager
from marketplace.mcp.server import (
    MCP_VERSION, SERVER_NAME, SERVER_VERSION,
    _jsonrpc_response, _jsonrpc_error, handle_message,
)
from marketplace.mcp.tools import TOOL_DEFINITIONS
from marketplace.mcp.resources import RESOURCE_DEFINITIONS

def _jwt(aid=None):
    aid=aid or str(uuid.uuid4())
    return create_access_token(aid,"test-agent")

@pytest.fixture(autouse=True)
def _clear_sessions():
    session_manager._sessions.clear()
    yield
    session_manager._sessions.clear()

class TestJsonRpcHelpers:
    def test_response(self):
        r=_jsonrpc_response(1,{"ok":True})
        assert r["jsonrpc"]=="2.0" and r["id"]==1 and r["result"]=={"ok":True}
    def test_error(self):
        r=_jsonrpc_error(2,-32600,"Invalid")
        assert r["error"]["code"]==-32600 and r["error"]["message"]=="Invalid"

class TestHandleMessage:
    async def test_initialize(self):
        r=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        assert r["result"]["protocolVersion"]==MCP_VERSION
        assert r["result"]["serverInfo"]["name"]==SERVER_NAME
        assert "_session_id" in r["result"]

    async def test_tools_list(self):
        ir=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        sid=ir["result"]["_session_id"]
        r=await handle_message({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}},session_id=sid)
        assert len(r["result"]["tools"])==len(TOOL_DEFINITIONS)
    async def test_resources_list(self):
        ir=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        sid=ir["result"]["_session_id"]
        r=await handle_message({"jsonrpc":"2.0","id":3,"method":"resources/list","params":{}},session_id=sid)
        assert len(r["result"]["resources"])==len(RESOURCE_DEFINITIONS)

    async def test_ping(self):
        ir=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        sid=ir["result"]["_session_id"]
        r=await handle_message({"jsonrpc":"2.0","id":4,"method":"ping","params":{}},session_id=sid)
        assert r["result"]=={}

    async def test_notifications_initialized(self):
        ir=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        sid=ir["result"]["_session_id"]
        r=await handle_message({"jsonrpc":"2.0","id":5,"method":"notifications/initialized","params":{}},session_id=sid)
        assert r["result"]["acknowledged"] is True

    async def test_unknown_method(self):
        ir=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        sid=ir["result"]["_session_id"]
        r=await handle_message({"jsonrpc":"2.0","id":6,"method":"bogus/method","params":{}},session_id=sid)
        assert r["error"]["code"]==-32601

    async def test_no_session(self):
        r=await handle_message({"jsonrpc":"2.0","id":10,"method":"ping","params":{}})
        assert r["error"]["code"]==-32000

    async def test_rate_limit(self):
        ir=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        sid=ir["result"]["_session_id"]
        s=session_manager.get_session(sid)
        s.request_count=60
        r=await handle_message({"jsonrpc":"2.0","id":99,"method":"ping","params":{}},session_id=sid)
        assert "rate limit" in r["error"]["message"].lower()
    async def test_tools_call_discover(self, db):
        ir=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        sid=ir["result"]["_session_id"]
        r=await handle_message({"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"marketplace_discover","arguments":{"q":"test"}}},session_id=sid,db=db)
        assert "result" in r
        parsed=json.loads(r["result"]["content"][0]["text"])
        assert "listings" in parsed

    async def test_tools_call_unknown(self, db):
        ir=await handle_message({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}})
        sid=ir["result"]["_session_id"]
        r=await handle_message({"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"nope","arguments":{}}},session_id=sid,db=db)
        parsed=json.loads(r["result"]["content"][0]["text"])
        assert "error" in parsed

class TestMCPEndpoints:
    async def test_health(self, client):
        r=await client.get("/mcp/health")
        assert r.status_code==200
        assert r.json()["status"]=="ok"

    async def test_message_endpoint(self, client):
        body={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}}
        r=await client.post("/mcp/message",json=body)
        assert r.status_code==200
        assert "_session_id" in r.json()["result"]

    async def test_sse_endpoint(self, client):
        body={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"_auth":_jwt()}}
        r=await client.post("/mcp/sse",json=body)
        assert r.status_code==200
        assert "text/event-stream" in r.headers.get("content-type","")
