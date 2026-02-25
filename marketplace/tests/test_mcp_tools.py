"""MCP tools tests."""

from __future__ import annotations
import json
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from marketplace.mcp.tools import TOOL_DEFINITIONS, execute_tool

class TestToolDefinitions:
    def test_count(self): assert len(TOOL_DEFINITIONS)==11
    def test_all_have_name(self):
        for t in TOOL_DEFINITIONS: assert "name" in t
    def test_all_have_description(self):
        for t in TOOL_DEFINITIONS: assert "description" in t
    def test_all_have_schema(self):
        for t in TOOL_DEFINITIONS: assert "inputSchema" in t
    def test_unique_names(self):
        names=[t["name"] for t in TOOL_DEFINITIONS]
        assert len(names)==len(set(names))
    def test_schemas_are_objects(self):
        for t in TOOL_DEFINITIONS: assert t["inputSchema"]["type"]=="object"

class TestExecuteTool:
    async def test_unknown_tool(self, db):
        r=await execute_tool("nonexistent_tool",{},"agent-1",db=db)
        assert "error" in r
        assert "Unknown tool" in r["error"]

    async def test_discover_empty(self, db):
        r=await execute_tool("marketplace_discover",{"q":"test","page":1,"page_size":5},"a1",db=db)
        assert "listings" in r
        assert "total" in r

    async def test_reputation_not_found(self, db):
        r=await execute_tool("marketplace_reputation",{"agent_id":str(uuid.uuid4())},"a1",db=db)
        assert "error" in r
        assert "Agent not found" in r["error"]

    async def test_trending_empty(self, db):
        from unittest.mock import AsyncMock as AM
        with patch("marketplace.services.demand_service.get_trending", new_callable=AM, return_value=[]):
            r=await execute_tool("marketplace_trending",{"limit":5},"a1",db=db)
            assert "signals" in r

    async def test_sell_creates_listing(self, db, make_agent):
        agent, _=await make_agent()
        args={"title":"Test Data","category":"web_search","content":"test content data","price_usdc":0.5}
        r=await execute_tool("marketplace_sell",args,agent.id,db=db)
        assert "listing_id" in r
        assert "title" in r
        assert "content_hash" in r

    async def test_discover_tools_empty(self, db):
        r=await execute_tool("webmcp_discover_tools",{"q":"shopping"},"a1",db=db)
        assert "tools" in r
        assert "total" in r

    async def test_verify_execution_not_found(self, db):
        r=await execute_tool("webmcp_verify_execution",{"execution_id":str(uuid.uuid4())},"a1",db=db)
        assert "error" in r

    async def test_execute_without_db_creates_session(self):
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        with patch("marketplace.database.async_session", return_value=mock_cm):
            r=await execute_tool("nonexistent_tool",{},"a1",db=None)
            assert "error" in r
