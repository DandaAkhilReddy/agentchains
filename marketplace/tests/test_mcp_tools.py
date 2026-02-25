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

    async def test_express_buy(self, db, make_agent):
        from unittest.mock import AsyncMock as AM, MagicMock
        agent, _ = await make_agent()
        mock_resp = MagicMock()
        mock_resp.body = b'{"transaction_id": "tx1", "content": "data"}'
        with patch("marketplace.services.express_service.express_buy",
                   new_callable=AM, return_value=mock_resp):
            r = await execute_tool(
                "marketplace_express_buy",
                {"listing_id": "lst-1"},
                agent.id,
                db=db,
            )
            assert "transaction_id" in r

    async def test_auto_match(self, db, make_agent):
        from unittest.mock import AsyncMock as AM
        agent, _ = await make_agent()
        with patch("marketplace.services.match_service.auto_match",
                   new_callable=AM,
                   return_value={"matches": [], "total": 0}):
            r = await execute_tool(
                "marketplace_auto_match",
                {"description": "weather data"},
                agent.id,
                db=db,
            )
            assert "matches" in r

    async def test_register_catalog(self, db, make_agent):
        from unittest.mock import AsyncMock as AM, MagicMock
        agent, _ = await make_agent()
        mock_entry = MagicMock()
        mock_entry.id = 1
        mock_entry.namespace = "web_search.python"
        mock_entry.topic = "search"
        with patch("marketplace.services.catalog_service.register_catalog_entry",
                   new_callable=AM, return_value=mock_entry):
            r = await execute_tool(
                "marketplace_register_catalog",
                {"namespace": "web_search.python", "topic": "search"},
                agent.id,
                db=db,
            )
            assert "entry_id" in r
            assert r["namespace"] == "web_search.python"

    async def test_reputation_found(self, db, make_agent):
        from unittest.mock import MagicMock
        agent, _ = await make_agent()
        # Create an AgentStats record
        from marketplace.models.agent_stats import AgentStats
        from decimal import Decimal
        stats = AgentStats(
            agent_id=agent.id,
            helpfulness_score=Decimal("0.95"),
            total_earned_usdc=Decimal("100.00"),
            unique_buyers_served=5,
            primary_specialization="web_search",
        )
        db.add(stats)
        await db.commit()
        r = await execute_tool(
            "marketplace_reputation",
            {"agent_id": agent.id},
            agent.id,
            db=db,
        )
        assert "helpfulness_score" in r
        assert r["agent_id"] == agent.id

    async def test_verify_zkp(self, db, make_agent):
        from unittest.mock import AsyncMock as AM
        agent, _ = await make_agent()
        with patch("marketplace.services.zkp_service.verify_listing",
                   new_callable=AM,
                   return_value={"valid": True, "proofs": []}):
            r = await execute_tool(
                "marketplace_verify_zkp",
                {"listing_id": "lst-1"},
                agent.id,
                db=db,
            )
            assert "valid" in r

    async def test_webmcp_execute_action(self, db, make_agent):
        from unittest.mock import AsyncMock as AM
        agent, _ = await make_agent()
        with patch("marketplace.services.action_executor.execute_action",
                   new_callable=AM,
                   return_value={"execution_id": "exec-1", "status": "completed"}):
            r = await execute_tool(
                "webmcp_execute_action",
                {"action_id": "act-1"},
                agent.id,
                db=db,
            )
            assert "execution_id" in r

    async def test_webmcp_verify_execution_with_proof(self, db, make_agent):
        from unittest.mock import AsyncMock as AM
        agent, _ = await make_agent()
        mock_execution = {
            "id": "exec-1",
            "proof_of_execution": {"hash": "abc", "timestamp": "2024-01-01"},
        }
        mock_proof_result = {"valid": True, "claims": {"data_delivered": True}}
        with patch("marketplace.services.action_executor.get_execution",
                   new_callable=AM, return_value=mock_execution),              patch("marketplace.services.proof_of_execution_service.verify_proof",
                   return_value=mock_proof_result):
            r = await execute_tool(
                "webmcp_verify_execution",
                {"execution_id": "exec-1"},
                agent.id,
                db=db,
            )
            assert r["verified"] is True
            assert "claims" in r

    async def test_webmcp_verify_execution_no_proof(self, db, make_agent):
        from unittest.mock import AsyncMock as AM
        agent, _ = await make_agent()
        mock_execution = {"id": "exec-1", "proof_of_execution": None}
        with patch("marketplace.services.action_executor.get_execution",
                   new_callable=AM, return_value=mock_execution):
            r = await execute_tool(
                "webmcp_verify_execution",
                {"execution_id": "exec-1"},
                agent.id,
                db=db,
            )
            assert r["verified"] is False
            assert "error" in r

