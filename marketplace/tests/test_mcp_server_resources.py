"""Comprehensive tests for:
  - marketplace/mcp/federation_handler.py
  - marketplace/mcp/resources.py
  - marketplace/mcp/server.py

Coverage breakdown:
  TestFederationHandlerModule      (14 tests) — get_federated_tools, handle_federated_tool_call, FederationHandler class
  TestResourceDefinitions          ( 7 tests) — RESOURCE_DEFINITIONS structure validation
  TestReadResourceCatalog          ( 4 tests) — read_resource for marketplace://catalog
  TestReadResourceListings         ( 4 tests) — read_resource for marketplace://listings/active
  TestReadResourceTrending         ( 3 tests) — read_resource for marketplace://trending
  TestReadResourceOpportunities    ( 4 tests) — read_resource for marketplace://opportunities
  TestReadResourceAgent            ( 5 tests) — read_resource for marketplace://agent/{id}
  TestReadResourceUnknown          ( 2 tests) — unknown URI handling
  TestReadResourceDbFallback       ( 2 tests) — db=None path uses async_session
  TestServerHelpers                ( 4 tests) — _jsonrpc_response, _jsonrpc_error, constants
  TestServerHandleMessage          (19 tests) — handle_message dispatch for all methods
  TestServerHTTPEndpoints          ( 6 tests) — /mcp/message, /mcp/sse, /mcp/health via HTTP client
"""

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import create_access_token
from marketplace.mcp.federation_handler import (
    FederationHandler,
    get_federated_tools,
    handle_federated_tool_call,
)
from marketplace.mcp.resources import RESOURCE_DEFINITIONS, read_resource
from marketplace.mcp.server import (
    MCP_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    _jsonrpc_error,
    _jsonrpc_response,
    handle_message,
)
from marketplace.mcp.tools import TOOL_DEFINITIONS


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


def _make_jwt(agent_id: str = None, agent_name: str = "test-agent") -> str:
    agent_id = agent_id or _new_id()
    return create_access_token(agent_id, agent_name)


def _init_body(token: str, msg_id: int = 1) -> dict:
    """Build a complete initialize JSON-RPC body using _auth location."""
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": "initialize",
        "params": {"_auth": token},
    }


async def _get_session_id(token: str) -> str:
    """Helper: run initialize and return the issued session_id."""
    resp = await handle_message(_init_body(token))
    return resp["result"]["_session_id"]


def _mock_db_result(items):
    """Return a mock SQLAlchemy execute result whose .scalars().all() returns items."""
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = items
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = items[0] if items else None
    return result


# ===========================================================================
# 1. TestFederationHandlerModule  (14 tests)
# ===========================================================================

class TestFederationHandlerModule:
    """Tests for marketplace.mcp.federation_handler module-level functions and class."""

    # -- get_federated_tools --

    async def test_get_federated_tools_always_includes_local(self):
        """Local TOOL_DEFINITIONS are always present in the merged result."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await get_federated_tools(db)
        local_names = {t["name"] for t in TOOL_DEFINITIONS}
        result_names = {t["name"] for t in tools}
        assert local_names.issubset(result_names)

    async def test_get_federated_tools_appends_remote_tools(self):
        """Remote federated tools are appended after local tools."""
        db = AsyncMock()
        remote = [{"name": "weather.forecast", "description": "Weather"}]
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=remote,
        ):
            tools = await get_federated_tools(db)
        names = [t["name"] for t in tools]
        assert "weather.forecast" in names

    async def test_get_federated_tools_total_count_is_sum(self):
        """Total count equals len(local) + len(remote)."""
        db = AsyncMock()
        remote = [
            {"name": "ns.a", "description": "a"},
            {"name": "ns.b", "description": "b"},
        ]
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=remote,
        ):
            tools = await get_federated_tools(db)
        assert len(tools) == len(TOOL_DEFINITIONS) + 2

    async def test_get_federated_tools_fallback_on_discovery_error(self):
        """If discover_tools raises, only local tools are returned (no propagation)."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network down"),
        ):
            tools = await get_federated_tools(db)
        assert len(tools) == len(TOOL_DEFINITIONS)

    async def test_get_federated_tools_empty_remote_returns_only_local(self):
        """Empty remote list means exactly the local tools are returned."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await get_federated_tools(db)
        assert len(tools) == len(TOOL_DEFINITIONS)

    async def test_get_federated_tools_namespace_prevents_collision(self):
        """Remote tools have namespace prefix so names don't collide with local ones."""
        db = AsyncMock()
        remote = [{"name": "ext.marketplace_discover", "description": "dup?"}]
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=remote,
        ):
            tools = await get_federated_tools(db)
        names = [t["name"] for t in tools]
        # Both the local and prefixed remote name should coexist
        assert "marketplace_discover" in names
        assert "ext.marketplace_discover" in names

    # -- handle_federated_tool_call --

    async def test_handle_federated_call_dotted_name_routes_to_federation(self):
        """Tool name with a dot triggers route_tool_call, not execute_tool."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"routed": True},
        ) as mock_route:
            result = await handle_federated_tool_call(
                db, "weather.forecast", {"city": "NYC"}, "agent-1"
            )
        assert result == {"routed": True}
        mock_route.assert_awaited_once_with(db, "weather.forecast", {"city": "NYC"}, "agent-1")

    async def test_handle_federated_call_no_dot_routes_to_local(self):
        """Tool name without a dot calls local execute_tool."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.execute_tool",
            new_callable=AsyncMock,
            return_value={"local": True},
        ) as mock_exec:
            result = await handle_federated_tool_call(
                db, "marketplace_discover", {"q": "test"}, "agent-2"
            )
        assert result == {"local": True}
        mock_exec.assert_awaited_once_with("marketplace_discover", {"q": "test"}, "agent-2", db=db)

    async def test_handle_federated_call_passes_db_to_local(self):
        """Local execute_tool receives the exact db session passed in."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.execute_tool",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_exec:
            await handle_federated_tool_call(db, "some_local", {}, "agent-3")
        _, kwargs = mock_exec.call_args
        assert kwargs.get("db") is db

    async def test_handle_federated_call_passes_agent_id_to_remote(self):
        """Agent ID is forwarded as the 4th positional arg to route_tool_call."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_route:
            await handle_federated_tool_call(db, "ns.tool", {}, "agent-xyz")
        mock_route.assert_awaited_once_with(db, "ns.tool", {}, "agent-xyz")

    async def test_handle_federated_call_error_dict_passed_through(self):
        """If route_tool_call returns an error dict, it is returned as-is."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"error": "server timeout"},
        ):
            result = await handle_federated_tool_call(db, "ns.fail", {}, "a")
        assert result["error"] == "server timeout"

    async def test_handle_federated_call_multi_dot_name_is_federated(self):
        """Names with multiple dots still route as federated."""
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"deep": True},
        ):
            result = await handle_federated_tool_call(db, "org.sub.tool", {}, "a")
        assert result == {"deep": True}

    async def test_handle_federated_call_arguments_forwarded_intact(self):
        """Arguments dict is forwarded without modification to route_tool_call."""
        db = AsyncMock()
        args = {"lat": 40.7, "lon": -74.0, "units": "metric"}
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"temp": 22},
        ) as mock_route:
            await handle_federated_tool_call(db, "weather.temp", args, "a")
        passed_args = mock_route.call_args[0][2]
        assert passed_args == args

    # -- FederationHandler class --

    async def test_federation_handler_get_tools_delegates(self):
        """FederationHandler.get_tools calls get_federated_tools with db."""
        handler = FederationHandler()
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await handler.get_tools(db)
        assert isinstance(tools, list)
        assert len(tools) >= len(TOOL_DEFINITIONS)

    async def test_federation_handler_handle_call_delegates(self):
        """FederationHandler.handle_call dispatches to handle_federated_tool_call."""
        handler = FederationHandler()
        db = AsyncMock()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"delegated": True},
        ):
            result = await handler.handle_call(
                db, tool_name="ns.something", arguments={}, agent_id="agent-h"
            )
        assert result == {"delegated": True}


# ===========================================================================
# 2. TestResourceDefinitions  (7 tests)
# ===========================================================================

class TestResourceDefinitions:
    """Static validation of RESOURCE_DEFINITIONS."""

    def test_resource_definitions_count(self):
        """RESOURCE_DEFINITIONS should contain exactly 5 resources."""
        assert len(RESOURCE_DEFINITIONS) == 5

    def test_all_resources_have_uri(self):
        """Every resource entry has a non-empty 'uri' field."""
        for res in RESOURCE_DEFINITIONS:
            assert "uri" in res and res["uri"], f"Missing uri in: {res}"

    def test_all_resources_have_name(self):
        """Every resource entry has a non-empty 'name' field."""
        for res in RESOURCE_DEFINITIONS:
            assert "name" in res and res["name"], f"Missing name in: {res}"

    def test_all_resources_have_description(self):
        """Every resource entry has a 'description' field."""
        for res in RESOURCE_DEFINITIONS:
            assert "description" in res, f"Missing description in: {res}"

    def test_all_resources_have_mime_type(self):
        """Every resource has mimeType set to application/json."""
        for res in RESOURCE_DEFINITIONS:
            assert res.get("mimeType") == "application/json", f"Wrong mimeType in: {res}"

    def test_all_uris_use_marketplace_scheme(self):
        """All URIs start with 'marketplace://'."""
        for res in RESOURCE_DEFINITIONS:
            assert res["uri"].startswith("marketplace://"), f"Bad URI: {res['uri']}"

    def test_resource_uris_are_unique(self):
        """No duplicate URIs in the definitions."""
        uris = [r["uri"] for r in RESOURCE_DEFINITIONS]
        assert len(uris) == len(set(uris)), f"Duplicate URIs found: {uris}"


# ===========================================================================
# 3. TestReadResourceCatalog  (4 tests)
# ===========================================================================

class TestReadResourceCatalog:
    """read_resource for marketplace://catalog."""

    async def test_catalog_returns_entries_and_total(self):
        """Catalog resource returns 'entries' list and 'total' count."""
        db = AsyncMock()
        mock_entry = MagicMock()
        mock_entry.id = _new_id()
        mock_entry.namespace = "web_search"
        mock_entry.topic = "python"
        mock_entry.agent_id = _new_id()
        mock_entry.quality_avg = Decimal("0.85")
        mock_entry.active_listings_count = 3

        with patch(
            "marketplace.services.catalog_service.search_catalog",
            new_callable=AsyncMock,
            return_value=([mock_entry], 1),
        ):
            result = await read_resource("marketplace://catalog", "agent-a", db=db)

        assert "entries" in result
        assert "total" in result
        assert result["total"] == 1
        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert entry["id"] == mock_entry.id
        assert entry["namespace"] == "web_search"
        assert entry["topic"] == "python"

    async def test_catalog_quality_avg_defaults_to_half_when_none(self):
        """If quality_avg is None, it defaults to 0.5."""
        db = AsyncMock()
        mock_entry = MagicMock()
        mock_entry.id = _new_id()
        mock_entry.namespace = "ns"
        mock_entry.topic = "t"
        mock_entry.agent_id = _new_id()
        mock_entry.quality_avg = None
        mock_entry.active_listings_count = 0

        with patch(
            "marketplace.services.catalog_service.search_catalog",
            new_callable=AsyncMock,
            return_value=([mock_entry], 1),
        ):
            result = await read_resource("marketplace://catalog", "agent-a", db=db)

        assert result["entries"][0]["quality_avg"] == 0.5

    async def test_catalog_empty_result(self):
        """Catalog resource handles empty result gracefully."""
        db = AsyncMock()
        with patch(
            "marketplace.services.catalog_service.search_catalog",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            result = await read_resource("marketplace://catalog", "agent-a", db=db)

        assert result["entries"] == []
        assert result["total"] == 0

    async def test_catalog_propagates_service_exception(self):
        """If search_catalog raises, the exception propagates out."""
        db = AsyncMock()
        with patch(
            "marketplace.services.catalog_service.search_catalog",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db failure"),
        ):
            with pytest.raises(RuntimeError, match="db failure"):
                await read_resource("marketplace://catalog", "agent-a", db=db)


# ===========================================================================
# 4. TestReadResourceListings  (4 tests)
# ===========================================================================

class TestReadResourceListings:
    """read_resource for marketplace://listings/active."""

    async def test_listings_returns_list_and_total(self):
        """Active listings resource returns 'listings' and 'total'."""
        db = AsyncMock()
        mock_listing = MagicMock()
        mock_listing.id = _new_id()
        mock_listing.title = "My Listing"
        mock_listing.category = "web_search"
        mock_listing.price_usdc = Decimal("1.50")
        mock_listing.quality_score = Decimal("0.90")
        mock_listing.seller_id = _new_id()

        with patch(
            "marketplace.services.listing_service.list_listings",
            new_callable=AsyncMock,
            return_value=([mock_listing], 1),
        ):
            result = await read_resource("marketplace://listings/active", "agent-b", db=db)

        assert "listings" in result
        assert "total" in result
        assert result["total"] == 1
        item = result["listings"][0]
        assert item["id"] == mock_listing.id
        assert item["title"] == "My Listing"
        assert item["price_usdc"] == 1.5
        assert item["seller_id"] == mock_listing.seller_id

    async def test_listings_quality_defaults_to_half_when_none(self):
        """quality_score=None in listing defaults to 0.5."""
        db = AsyncMock()
        mock_listing = MagicMock()
        mock_listing.id = _new_id()
        mock_listing.title = "T"
        mock_listing.category = "c"
        mock_listing.price_usdc = Decimal("0.10")
        mock_listing.quality_score = None
        mock_listing.seller_id = _new_id()

        with patch(
            "marketplace.services.listing_service.list_listings",
            new_callable=AsyncMock,
            return_value=([mock_listing], 1),
        ):
            result = await read_resource("marketplace://listings/active", "agent-b", db=db)

        assert result["listings"][0]["quality_score"] == 0.5

    async def test_listings_empty_result(self):
        """Empty listings handled gracefully."""
        db = AsyncMock()
        with patch(
            "marketplace.services.listing_service.list_listings",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            result = await read_resource("marketplace://listings/active", "agent-b", db=db)

        assert result["listings"] == []
        assert result["total"] == 0

    async def test_listings_propagates_service_exception(self):
        """If list_listings raises, the exception propagates out."""
        db = AsyncMock()
        with patch(
            "marketplace.services.listing_service.list_listings",
            new_callable=AsyncMock,
            side_effect=ValueError("bad query"),
        ):
            with pytest.raises(ValueError, match="bad query"):
                await read_resource("marketplace://listings/active", "agent-b", db=db)


# ===========================================================================
# 5. TestReadResourceTrending  (3 tests)
# ===========================================================================

class TestReadResourceTrending:
    """read_resource for marketplace://trending."""

    async def test_trending_returns_signals_key(self):
        """Trending resource returns a dict with 'signals' key."""
        db = AsyncMock()
        fake_signals = [{"pattern": "python", "score": 0.9}]
        with patch(
            "marketplace.services.demand_service.get_trending",
            new_callable=AsyncMock,
            return_value=fake_signals,
        ):
            result = await read_resource("marketplace://trending", "agent-c", db=db)

        assert "signals" in result
        assert result["signals"] == fake_signals

    async def test_trending_empty_signals(self):
        """Empty trending list is returned correctly."""
        db = AsyncMock()
        with patch(
            "marketplace.services.demand_service.get_trending",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await read_resource("marketplace://trending", "agent-c", db=db)

        assert result["signals"] == []

    async def test_trending_propagates_exception(self):
        """Exception from get_trending propagates out."""
        db = AsyncMock()
        with patch(
            "marketplace.services.demand_service.get_trending",
            new_callable=AsyncMock,
            side_effect=ConnectionError("cache miss"),
        ):
            with pytest.raises(ConnectionError):
                await read_resource("marketplace://trending", "agent-c", db=db)


# ===========================================================================
# 6. TestReadResourceOpportunities  (4 tests)
# ===========================================================================

class TestReadResourceOpportunities:
    """read_resource for marketplace://opportunities."""

    def _mock_opp(self, urgency: float = 0.9):
        opp = MagicMock()
        opp.id = _new_id()
        opp.query_pattern = "ml data"
        opp.estimated_revenue_usdc = Decimal("5.00")
        opp.urgency_score = Decimal(str(urgency))
        return opp

    async def test_opportunities_returns_list(self):
        """Opportunities resource returns a dict with 'opportunities' key."""
        db = AsyncMock()
        opp = self._mock_opp()
        db.execute = AsyncMock(return_value=_mock_db_result([opp]))

        result = await read_resource("marketplace://opportunities", "agent-d", db=db)

        assert "opportunities" in result
        assert len(result["opportunities"]) == 1
        item = result["opportunities"][0]
        assert item["id"] == opp.id
        assert item["query_pattern"] == "ml data"
        assert isinstance(item["estimated_revenue_usdc"], float)
        assert isinstance(item["urgency_score"], float)

    async def test_opportunities_empty_result(self):
        """Empty opportunities list is handled correctly."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([]))

        result = await read_resource("marketplace://opportunities", "agent-d", db=db)

        assert result["opportunities"] == []

    async def test_opportunities_multiple_results(self):
        """Multiple opportunity signals are all returned."""
        db = AsyncMock()
        opps = [self._mock_opp(urgency=0.9), self._mock_opp(urgency=0.5)]
        db.execute = AsyncMock(return_value=_mock_db_result(opps))

        result = await read_resource("marketplace://opportunities", "agent-d", db=db)

        assert len(result["opportunities"]) == 2

    async def test_opportunities_urgency_score_is_float(self):
        """urgency_score is cast to float in the response."""
        db = AsyncMock()
        opp = self._mock_opp(urgency=0.777)
        db.execute = AsyncMock(return_value=_mock_db_result([opp]))

        result = await read_resource("marketplace://opportunities", "agent-d", db=db)

        assert isinstance(result["opportunities"][0]["urgency_score"], float)


# ===========================================================================
# 7. TestReadResourceAgent  (5 tests)
# ===========================================================================

class TestReadResourceAgent:
    """read_resource for marketplace://agent/{agent_id}."""

    def _mock_agent(self, agent_id: str = None):
        agent = MagicMock()
        agent.id = agent_id or _new_id()
        agent.name = "Test Agent"
        agent.agent_type = "buyer"
        agent.status = "active"
        return agent

    def _mock_stats(self, agent_id: str):
        stats = MagicMock()
        stats.agent_id = agent_id
        stats.helpfulness_score = Decimal("0.92")
        stats.total_earned_usdc = Decimal("42.50")
        stats.unique_buyers_served = 7
        stats.primary_specialization = "web_search"
        return stats

    async def test_agent_profile_returns_full_data(self):
        """Agent profile returns id, name, agent_type, status, and stats."""
        db = AsyncMock()
        agent_id = _new_id()
        agent = self._mock_agent(agent_id)
        stats = self._mock_stats(agent_id)

        # First execute call → agent lookup, second → stats lookup
        db.execute = AsyncMock(
            side_effect=[
                _mock_db_result([agent]),
                _mock_db_result([stats]),
            ]
        )

        result = await read_resource(f"marketplace://agent/{agent_id}", "requester", db=db)

        assert result["id"] == agent_id
        assert result["name"] == "Test Agent"
        assert result["agent_type"] == "buyer"
        assert result["status"] == "active"
        assert result["stats"] is not None
        assert result["stats"]["helpfulness_score"] == pytest.approx(0.92)
        assert result["stats"]["total_earned_usdc"] == pytest.approx(42.5)
        assert result["stats"]["unique_buyers_served"] == 7
        assert result["stats"]["primary_specialization"] == "web_search"

    async def test_agent_profile_not_found_returns_error(self):
        """Missing agent returns {'error': 'Agent not found'}."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_result([]))

        result = await read_resource("marketplace://agent/nonexistent", "requester", db=db)

        assert "error" in result
        assert result["error"] == "Agent not found"

    async def test_agent_profile_no_stats_returns_null_stats(self):
        """Agent found but no stats → stats field is None."""
        db = AsyncMock()
        agent_id = _new_id()
        agent = self._mock_agent(agent_id)

        db.execute = AsyncMock(
            side_effect=[
                _mock_db_result([agent]),
                _mock_db_result([]),   # no stats row
            ]
        )

        result = await read_resource(f"marketplace://agent/{agent_id}", "requester", db=db)

        assert result["id"] == agent_id
        # When stats row is None the code short-circuits to None
        assert result["stats"] is None

    async def test_agent_profile_extracts_id_from_uri(self):
        """The agent_id is correctly parsed from the URI path."""
        db = AsyncMock()
        target_id = "agent-uuid-1234"
        agent = self._mock_agent(target_id)
        stats = self._mock_stats(target_id)

        db.execute = AsyncMock(
            side_effect=[
                _mock_db_result([agent]),
                _mock_db_result([stats]),
            ]
        )

        result = await read_resource(f"marketplace://agent/{target_id}", "req", db=db)

        assert result["id"] == target_id

    async def test_agent_profile_stats_scores_are_floats(self):
        """Stats scores are cast to float in the response."""
        db = AsyncMock()
        agent_id = _new_id()
        agent = self._mock_agent(agent_id)
        stats = self._mock_stats(agent_id)

        db.execute = AsyncMock(
            side_effect=[
                _mock_db_result([agent]),
                _mock_db_result([stats]),
            ]
        )

        result = await read_resource(f"marketplace://agent/{agent_id}", "req", db=db)

        assert isinstance(result["stats"]["helpfulness_score"], float)
        assert isinstance(result["stats"]["total_earned_usdc"], float)


# ===========================================================================
# 8. TestReadResourceUnknown  (2 tests)
# ===========================================================================

class TestReadResourceUnknown:
    """Unknown URI handling in read_resource."""

    async def test_unknown_uri_returns_error_dict(self):
        """Unrecognized URI returns {'error': 'Unknown resource: ...'}."""
        db = AsyncMock()
        result = await read_resource("marketplace://does-not-exist", "agent-e", db=db)
        assert "error" in result
        assert "Unknown resource" in result["error"]
        assert "marketplace://does-not-exist" in result["error"]

    async def test_unrelated_scheme_returns_error(self):
        """URIs with a completely different scheme also return error."""
        db = AsyncMock()
        result = await read_resource("http://example.com/data", "agent-e", db=db)
        assert "error" in result


# ===========================================================================
# 9. TestReadResourceDbFallback  (2 tests)
# ===========================================================================

class TestReadResourceDbFallback:
    """read_resource db=None path: falls back to async_session()."""

    async def test_catalog_db_none_uses_async_session(self):
        """With db=None, read_resource opens its own session via async_session."""
        mock_entry = MagicMock()
        mock_entry.id = _new_id()
        mock_entry.namespace = "ns"
        mock_entry.topic = "t"
        mock_entry.agent_id = _new_id()
        mock_entry.quality_avg = Decimal("0.5")
        mock_entry.active_listings_count = 1

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("marketplace.database.async_session", return_value=mock_session_ctx), \
             patch(
                 "marketplace.services.catalog_service.search_catalog",
                 new_callable=AsyncMock,
                 return_value=([mock_entry], 1),
             ):
            result = await read_resource("marketplace://catalog", "agent-f", db=None)

        assert "entries" in result

    async def test_unknown_uri_db_none_returns_error(self):
        """Unknown URI with db=None still returns error dict without crash."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("marketplace.database.async_session", return_value=mock_session_ctx):
            result = await read_resource("marketplace://bogus", "agent-f", db=None)

        assert "error" in result


# ===========================================================================
# 10. TestServerHelpers  (4 tests)
# ===========================================================================

class TestServerHelpers:
    """_jsonrpc_response, _jsonrpc_error, and protocol constants."""

    def test_jsonrpc_response_structure(self):
        """_jsonrpc_response wraps result with jsonrpc and id."""
        resp = _jsonrpc_response(42, {"ok": True})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 42
        assert resp["result"] == {"ok": True}
        assert "error" not in resp

    def test_jsonrpc_error_structure(self):
        """_jsonrpc_error wraps error code/message with jsonrpc and id."""
        err = _jsonrpc_error(99, -32600, "Invalid request")
        assert err["jsonrpc"] == "2.0"
        assert err["id"] == 99
        assert err["error"]["code"] == -32600
        assert err["error"]["message"] == "Invalid request"
        assert "result" not in err

    def test_mcp_version_constant(self):
        """MCP_VERSION is the expected protocol date string."""
        assert MCP_VERSION == "2024-11-05"

    def test_server_name_and_version_constants(self):
        """SERVER_NAME and SERVER_VERSION are non-empty strings."""
        assert isinstance(SERVER_NAME, str) and SERVER_NAME
        assert isinstance(SERVER_VERSION, str) and SERVER_VERSION


# ===========================================================================
# 11. TestServerHandleMessage  (19 tests)
# ===========================================================================

class TestServerHandleMessage:
    """handle_message JSON-RPC dispatch: all supported methods and error paths."""

    # -- initialize --

    async def test_initialize_success_returns_protocol_info(self):
        """Successful initialize returns protocolVersion, capabilities, serverInfo."""
        token = _make_jwt()
        resp = await handle_message(_init_body(token))

        assert resp["jsonrpc"] == "2.0"
        result = resp["result"]
        assert result["protocolVersion"] == MCP_VERSION
        assert result["serverInfo"]["name"] == SERVER_NAME
        assert result["serverInfo"]["version"] == SERVER_VERSION
        assert "_session_id" in result
        assert "_agent_id" in result

    async def test_initialize_capabilities_present(self):
        """Initialize result includes tools and resources capabilities."""
        token = _make_jwt()
        resp = await handle_message(_init_body(token))
        caps = resp["result"]["capabilities"]
        assert "tools" in caps
        assert "resources" in caps

    async def test_initialize_bad_token_returns_32000(self):
        """Invalid JWT during initialize returns -32000 error."""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"_auth": "not.a.real.token"},
        }
        resp = await handle_message(body)
        assert "error" in resp
        assert resp["error"]["code"] == -32000

    async def test_initialize_missing_auth_returns_error(self):
        """No auth params returns an error."""
        body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        resp = await handle_message(body)
        assert "error" in resp

    async def test_initialize_creates_unique_session_ids(self):
        """Two separate initialize calls produce different session IDs."""
        t1 = _make_jwt()
        t2 = _make_jwt()
        r1 = await handle_message(_init_body(t1, 1))
        r2 = await handle_message(_init_body(t2, 2))
        assert r1["result"]["_session_id"] != r2["result"]["_session_id"]

    # -- tools/list --

    async def test_tools_list_returns_all_definitions(self):
        """tools/list returns the full TOOL_DEFINITIONS list."""
        sid = await _get_session_id(_make_jwt())
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            "params": {},
        }, session_id=sid)
        assert "result" in resp
        tools = resp["result"]["tools"]
        assert isinstance(tools, list)
        assert len(tools) == len(TOOL_DEFINITIONS)

    async def test_tools_list_without_session_returns_error(self):
        """tools/list without a session returns -32000."""
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32000

    # -- tools/call --

    async def test_tools_call_success(self):
        """tools/call returns content with text field when tool succeeds."""
        sid = await _get_session_id(_make_jwt())
        with patch(
            "marketplace.mcp.server.execute_tool",
            new_callable=AsyncMock,
            return_value={"listings": [], "total": 0},
        ):
            resp = await handle_message({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {
                    "name": "marketplace_discover",
                    "arguments": {"q": "test"},
                },
            }, session_id=sid)
        assert "result" in resp
        content = resp["result"]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        parsed = json.loads(content[0]["text"])
        assert parsed["total"] == 0

    async def test_tools_call_exception_returns_32000(self):
        """tools/call that raises an exception returns -32000."""
        sid = await _get_session_id(_make_jwt())
        with patch(
            "marketplace.mcp.server.execute_tool",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            resp = await handle_message({
                "jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {
                    "name": "marketplace_discover",
                    "arguments": {},
                },
            }, session_id=sid)
        assert "error" in resp
        assert resp["error"]["code"] == -32000
        assert "Tool execution error" in resp["error"]["message"]

    # -- resources/list --

    async def test_resources_list_returns_all_definitions(self):
        """resources/list returns the full RESOURCE_DEFINITIONS list."""
        sid = await _get_session_id(_make_jwt())
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 5, "method": "resources/list",
            "params": {},
        }, session_id=sid)
        assert "result" in resp
        resources = resp["result"]["resources"]
        assert len(resources) == len(RESOURCE_DEFINITIONS)

    async def test_resources_list_without_session_returns_error(self):
        """resources/list without session returns -32000."""
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 5, "method": "resources/list", "params": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32000

    # -- resources/read --

    async def test_resources_read_success(self):
        """resources/read returns contents array with uri, mimeType, text."""
        sid = await _get_session_id(_make_jwt())
        with patch(
            "marketplace.mcp.server.read_resource",
            new_callable=AsyncMock,
            return_value={"signals": []},
        ):
            resp = await handle_message({
                "jsonrpc": "2.0", "id": 6, "method": "resources/read",
                "params": {
                    "uri": "marketplace://trending",
                },
            }, session_id=sid)
        assert "result" in resp
        contents = resp["result"]["contents"]
        assert isinstance(contents, list)
        assert len(contents) == 1
        c = contents[0]
        assert c["uri"] == "marketplace://trending"
        assert c["mimeType"] == "application/json"
        parsed = json.loads(c["text"])
        assert parsed["signals"] == []

    async def test_resources_read_exception_returns_32000(self):
        """resources/read that raises returns -32000."""
        sid = await _get_session_id(_make_jwt())
        with patch(
            "marketplace.mcp.server.read_resource",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db exploded"),
        ):
            resp = await handle_message({
                "jsonrpc": "2.0", "id": 7, "method": "resources/read",
                "params": {"uri": "marketplace://catalog"},
            }, session_id=sid)
        assert "error" in resp
        assert resp["error"]["code"] == -32000
        assert "Resource read error" in resp["error"]["message"]

    # -- ping --

    async def test_ping_returns_empty_result(self):
        """ping returns an empty result dict."""
        sid = await _get_session_id(_make_jwt())
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 8, "method": "ping",
            "params": {},
        }, session_id=sid)
        assert resp.get("result") == {}

    # -- notifications/initialized --

    async def test_notifications_initialized_returns_acknowledged(self):
        """notifications/initialized returns {'acknowledged': True}."""
        sid = await _get_session_id(_make_jwt())
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 9, "method": "notifications/initialized",
            "params": {},
        }, session_id=sid)
        assert resp["result"]["acknowledged"] is True

    # -- unknown method --

    async def test_unknown_method_returns_32601(self):
        """Unknown method returns -32601 Method not found."""
        sid = await _get_session_id(_make_jwt())
        resp = await handle_message({
            "jsonrpc": "2.0", "id": 10, "method": "totally/unknown",
            "params": {},
        }, session_id=sid)
        assert "error" in resp
        assert resp["error"]["code"] == -32601
        assert "totally/unknown" in resp["error"]["message"]

    # -- rate limit --

    async def test_rate_limit_exceeded_returns_32000(self):
        """Exceeding rate limit returns -32000 with rate limit message."""
        sid = await _get_session_id(_make_jwt())

        # Patch the session manager to always report rate limit exceeded
        with patch(
            "marketplace.mcp.server.session_manager.check_rate_limit",
            return_value=False,
        ):
            resp = await handle_message({
                "jsonrpc": "2.0", "id": 11, "method": "ping",
                "params": {},
            }, session_id=sid)
        assert "error" in resp
        assert resp["error"]["code"] == -32000
        assert "Rate limit" in resp["error"]["message"] or "rate limit" in resp["error"]["message"].lower()

    # -- session via header --

    async def test_session_id_via_header_parameter(self):
        """handle_message accepts session_id as a positional parameter (header simulation)."""
        token = _make_jwt()
        init_resp = await handle_message(_init_body(token))
        sid = init_resp["result"]["_session_id"]

        # Pass sid as the session_id positional argument
        resp = await handle_message(
            {"jsonrpc": "2.0", "id": 12, "method": "ping", "params": {}},
            session_id=sid,
        )
        assert "result" in resp
        assert resp["result"] == {}

    # -- message id types --

    async def test_string_message_id_preserved(self):
        """String message IDs are preserved in the response."""
        token = _make_jwt()
        resp = await handle_message({
            "jsonrpc": "2.0",
            "id": "req-abc",
            "method": "initialize",
            "params": {"_auth": token},
        })
        assert resp["id"] == "req-abc"

    async def test_null_message_id_preserved(self):
        """Null/None message ID is preserved in the response."""
        resp = await handle_message({
            "jsonrpc": "2.0",
            "id": None,
            "method": "tools/list",
            "params": {},
        })
        assert resp["id"] is None
        # Should be an error since no session, but the id must match
        assert "error" in resp


# ===========================================================================
# 12. TestServerHTTPEndpoints  (6 tests)
# ===========================================================================

class TestServerHTTPEndpoints:
    """HTTP endpoint tests using the FastAPI test client fixture."""

    async def test_health_endpoint_returns_ok(self, client):
        """GET /mcp/health returns status=ok with correct fields."""
        resp = await client.get("/mcp/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["protocol_version"] == MCP_VERSION
        assert data["server"] == SERVER_NAME
        assert "active_sessions" in data
        assert "tools_count" in data
        assert "resources_count" in data

    async def test_health_tools_count_matches_definitions(self, client):
        """Health endpoint reports the correct number of tools."""
        resp = await client.get("/mcp/health")
        data = resp.json()
        assert data["tools_count"] == len(TOOL_DEFINITIONS)

    async def test_health_resources_count_matches_definitions(self, client):
        """Health endpoint reports the correct number of resources."""
        resp = await client.get("/mcp/health")
        data = resp.json()
        assert data["resources_count"] == len(RESOURCE_DEFINITIONS)

    async def test_message_endpoint_initialize(self, client):
        """POST /mcp/message handles initialize and returns session info."""
        token = _make_jwt()
        payload = _init_body(token)
        resp = await client.post("/mcp/message", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "_session_id" in data["result"]

    async def test_message_endpoint_tools_list(self, client):
        """POST /mcp/message handles tools/list after session established."""
        token = _make_jwt()
        init_resp = await client.post("/mcp/message", json=_init_body(token))
        sid = init_resp.json()["result"]["_session_id"]

        resp = await client.post("/mcp/message", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            "params": {},
        }, headers={"X-MCP-Session-ID": sid})
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert len(data["result"]["tools"]) == len(TOOL_DEFINITIONS)

    async def test_sse_endpoint_returns_event_stream(self, client):
        """POST /mcp/sse returns text/event-stream content type with message event."""
        token = _make_jwt()
        payload = _init_body(token)
        resp = await client.post("/mcp/sse", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "event: message" in body
        assert "data:" in body
        # Parse the data line
        for line in body.splitlines():
            if line.startswith("data:"):
                parsed = json.loads(line[5:].strip())
                assert "result" in parsed
                break
