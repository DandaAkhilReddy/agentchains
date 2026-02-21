"""Federation handler — merges local MCP tools with federated tools from remote servers.

Extends the MCP server to support federated tool dispatch so agents can
transparently call tools hosted on remote MCP servers via namespace prefixes.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.mcp.tools import TOOL_DEFINITIONS, execute_tool
from marketplace.services.mcp_federation_service import discover_tools, route_tool_call

logger = logging.getLogger(__name__)


async def get_federated_tools(db: AsyncSession) -> list[dict]:
    """Merge local TOOL_DEFINITIONS with federated tools from active servers.

    Local tools are returned as-is. Federated tools get a namespace prefix
    (e.g. "weather.get_forecast") so the caller can distinguish them.
    """
    local_tools = list(TOOL_DEFINITIONS)

    try:
        federated = await discover_tools(db)
    except Exception as exc:
        logger.error("Failed to discover federated tools: %s", exc)
        federated = []

    all_tools = local_tools + federated
    logger.info(
        "Serving %d tools (%d local + %d federated)",
        len(all_tools),
        len(local_tools),
        len(federated),
    )
    return all_tools


async def handle_federated_tool_call(
    db: AsyncSession,
    tool_name: str,
    arguments: dict,
    agent_id: str,
) -> dict:
    """Route a tool call to either the local executor or a federated server.

    If the tool_name contains a dot (e.g. "weather.get_forecast"), it is
    treated as a namespaced federated tool and routed via the federation
    service. Otherwise it falls through to the local execute_tool handler.
    """
    if "." in tool_name:
        logger.info(
            "Routing federated tool call '%s' for agent '%s'",
            tool_name,
            agent_id,
        )
        return await route_tool_call(db, tool_name, arguments, agent_id)

    logger.info(
        "Executing local tool '%s' for agent '%s'",
        tool_name,
        agent_id,
    )
    return await execute_tool(tool_name, arguments, agent_id, db=db)


class FederationHandler:
    """Class wrapper for federation handler functions."""

    async def get_tools(self, db, **kwargs):
        return await get_federated_tools(db, **kwargs)

    async def handle_call(self, db, **kwargs):
        return await handle_federated_tool_call(db, **kwargs)
