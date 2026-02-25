"""Tests for MCP federation handler -- federated tool merging and call routing.

Mocks the underlying federation service and local tool executor.
"""

from unittest.mock import AsyncMock, patch

import pytest

from marketplace.mcp.federation_handler import (
    FederationHandler,
    get_federated_tools,
    handle_federated_tool_call,
)
from marketplace.mcp.tools import TOOL_DEFINITIONS


# ---------------------------------------------------------------------------
# get_federated_tools
# ---------------------------------------------------------------------------


class TestGetFederatedTools:
    async def test_returns_local_tools_when_no_federation(self, db):
        """With no active federated servers, should return only local tools."""
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await get_federated_tools(db)

        assert len(tools) == len(TOOL_DEFINITIONS)
        local_names = {t["name"] for t in TOOL_DEFINITIONS}
        returned_names = {t["name"] for t in tools}
        assert local_names == returned_names

    async def test_merges_federated_tools(self, db):
        """Federated tools should be appended to local tools."""
        federated = [
            {"name": "weather.get_forecast", "description": "Get weather forecast"},
            {"name": "weather.get_current", "description": "Get current weather"},
        ]
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=federated,
        ):
            tools = await get_federated_tools(db)

        assert len(tools) == len(TOOL_DEFINITIONS) + 2
        names = {t["name"] for t in tools}
        assert "weather.get_forecast" in names
        assert "weather.get_current" in names

    async def test_returns_local_tools_on_discovery_failure(self, db):
        """If discovery raises an exception, should still return local tools."""
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ):
            tools = await get_federated_tools(db)

        assert len(tools) == len(TOOL_DEFINITIONS)

    async def test_local_tools_not_mutated(self, db):
        """Original TOOL_DEFINITIONS should not be modified."""
        original_len = len(TOOL_DEFINITIONS)
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[{"name": "ns.tool", "description": "extra"}],
        ):
            await get_federated_tools(db)

        assert len(TOOL_DEFINITIONS) == original_len


# ---------------------------------------------------------------------------
# handle_federated_tool_call
# ---------------------------------------------------------------------------


class TestHandleFederatedToolCall:
    async def test_routes_dotted_name_to_federation(self, db):
        """Tool names with dots should be routed to the federation service."""
        expected_result = {"data": "weather result"}
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value=expected_result,
        ) as mock_route:
            result = await handle_federated_tool_call(
                db, "weather.get_forecast", {"city": "NYC"}, "agent-1"
            )

        assert result == expected_result
        mock_route.assert_awaited_once_with(
            db, "weather.get_forecast", {"city": "NYC"}, "agent-1"
        )

    async def test_routes_local_tool_to_executor(self, db):
        """Tool names without dots should be routed to the local executor."""
        expected_result = {"listings": [], "total": 0}
        with patch(
            "marketplace.mcp.federation_handler.execute_tool",
            new_callable=AsyncMock,
            return_value=expected_result,
        ) as mock_exec:
            result = await handle_federated_tool_call(
                db, "marketplace_discover", {"q": "test"}, "agent-1"
            )

        assert result == expected_result
        mock_exec.assert_awaited_once_with(
            "marketplace_discover", {"q": "test"}, "agent-1", db=db
        )

    async def test_local_tool_with_all_local_names(self, db):
        """All local tool names should route through execute_tool, not route_tool_call."""
        for tool_def in TOOL_DEFINITIONS:
            name = tool_def["name"]
            # Local tools should not contain dots
            assert "." not in name

            with patch(
                "marketplace.mcp.federation_handler.execute_tool",
                new_callable=AsyncMock,
                return_value={"ok": True},
            ) as mock_exec:
                await handle_federated_tool_call(db, name, {}, "agent-1")
                mock_exec.assert_awaited_once()

    async def test_multi_dot_namespace(self, db):
        """Multi-segment namespace (e.g. org.weather.get_temp) should still route federated."""
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"temp": 72},
        ) as mock_route:
            result = await handle_federated_tool_call(
                db, "org.weather.get_temp", {}, "agent-1"
            )

        assert result == {"temp": 72}
        mock_route.assert_awaited_once()

    async def test_empty_arguments(self, db):
        """Empty arguments should be passed through correctly."""
        with patch(
            "marketplace.mcp.federation_handler.execute_tool",
            new_callable=AsyncMock,
            return_value={"signals": []},
        ):
            result = await handle_federated_tool_call(
                db, "marketplace_trending", {}, "agent-1"
            )
        assert "signals" in result


# ---------------------------------------------------------------------------
# FederationHandler class wrapper
# ---------------------------------------------------------------------------


class TestFederationHandlerClass:
    async def test_get_tools_delegates(self, db):
        handler = FederationHandler()
        with patch(
            "marketplace.mcp.federation_handler.discover_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await handler.get_tools(db)
        assert isinstance(tools, list)
        assert len(tools) == len(TOOL_DEFINITIONS)

    async def test_handle_call_delegates_local(self, db):
        handler = FederationHandler()
        with patch(
            "marketplace.mcp.federation_handler.execute_tool",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            result = await handler.handle_call(
                db, tool_name="marketplace_discover", arguments={}, agent_id="a1"
            )
        assert result == {"ok": True}

    async def test_handle_call_delegates_federated(self, db):
        handler = FederationHandler()
        with patch(
            "marketplace.mcp.federation_handler.route_tool_call",
            new_callable=AsyncMock,
            return_value={"result": "remote"},
        ):
            result = await handler.handle_call(
                db, tool_name="ns.tool", arguments={"x": 1}, agent_id="a1"
            )
        assert result == {"result": "remote"}
