"""MCP Federation Service — register, discover, and route tools across federated MCP servers."""

import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.mcp_server import MCPServerEntry

logger = logging.getLogger(__name__)


async def register_server(
    db: AsyncSession,
    name: str,
    base_url: str,
    namespace: str,
    description: str = "",
    auth_type: str = "none",
    auth_credential_ref: str = "",
    registered_by: str | None = None,
) -> MCPServerEntry:
    """Register a new federated MCP server."""
    server = MCPServerEntry(
        name=name,
        base_url=base_url.rstrip("/"),
        namespace=namespace,
        description=description,
        auth_type=auth_type,
        auth_credential_ref=auth_credential_ref,
        registered_by=registered_by,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    logger.info("Registered MCP server '%s' in namespace '%s'", name, namespace)
    return server


async def unregister_server(db: AsyncSession, server_id: str) -> bool:
    """Remove a federated MCP server by ID. Returns True if found and deleted."""
    result = await db.execute(
        select(MCPServerEntry).where(MCPServerEntry.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        return False
    await db.delete(server)
    await db.commit()
    logger.info("Unregistered MCP server '%s' (id=%s)", server.name, server_id)
    return True


async def list_servers(
    db: AsyncSession,
    namespace: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[MCPServerEntry]:
    """List federated MCP servers with optional filters."""
    query = select(MCPServerEntry)
    if namespace:
        query = query.where(MCPServerEntry.namespace == namespace)
    if status:
        query = query.where(MCPServerEntry.status == status)
    query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_server(db: AsyncSession, server_id: str) -> MCPServerEntry | None:
    """Get a single federated MCP server by ID."""
    result = await db.execute(
        select(MCPServerEntry).where(MCPServerEntry.id == server_id)
    )
    return result.scalar_one_or_none()


async def discover_tools(
    db: AsyncSession,
    namespace: str | None = None,
) -> list[dict]:
    """Aggregate tools from all active servers, prefixing each tool name with namespace.

    Returns a list of tool definition dicts ready for MCP tools/list responses.
    """
    query = select(MCPServerEntry).where(MCPServerEntry.status == "active")
    if namespace:
        query = query.where(MCPServerEntry.namespace == namespace)

    result = await db.execute(query)
    servers = list(result.scalars().all())

    tools: list[dict] = []
    for server in servers:
        try:
            cached_tools = json.loads(server.tools_json) if server.tools_json else []
        except json.JSONDecodeError:
            logger.warning("Invalid tools_json for server '%s'", server.name)
            cached_tools = []

        for tool in cached_tools:
            namespaced_tool = dict(tool)
            namespaced_tool["name"] = f"{server.namespace}.{tool['name']}"
            namespaced_tool["_server_id"] = server.id
            namespaced_tool["_namespace"] = server.namespace
            tools.append(namespaced_tool)

    return tools


def _build_auth_headers(server: MCPServerEntry) -> dict[str, str]:
    """Build authorization headers based on the server's auth_type."""
    if server.auth_type == "bearer" and server.auth_credential_ref:
        return {"Authorization": f"Bearer {server.auth_credential_ref}"}
    if server.auth_type == "api_key" and server.auth_credential_ref:
        return {"X-API-Key": server.auth_credential_ref}
    return {}


async def refresh_server_tools(db: AsyncSession, server_id: str) -> dict:
    """Call a server's tools/list endpoint, cache result in tools_json.

    Returns the parsed tools list or an error dict.
    """
    server = await get_server(db, server_id)
    if not server:
        return {"error": "Server not found", "server_id": server_id}

    url = f"{server.base_url}/tools/list"
    headers = _build_auth_headers(server)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json={}, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        tools = data.get("tools", data) if isinstance(data, dict) else data
        server.tools_json = json.dumps(tools)
        server.last_health_check = datetime.now(timezone.utc)
        server.health_score = 100
        server.status = "active"
        await db.commit()
        await db.refresh(server)
        logger.info("Refreshed %d tools from server '%s'", len(tools), server.name)
        return {"tools": tools, "count": len(tools)}

    except httpx.HTTPStatusError as exc:
        logger.error("HTTP error refreshing tools from '%s': %s", server.name, exc)
        await update_health_score(db, server_id, max(0, server.health_score - 20))
        return {"error": f"HTTP {exc.response.status_code}", "server_id": server_id}

    except (httpx.RequestError, Exception) as exc:
        logger.error("Error refreshing tools from '%s': %s", server.name, exc)
        await update_health_score(db, server_id, max(0, server.health_score - 30))
        return {"error": str(exc), "server_id": server_id}


async def route_tool_call(
    db: AsyncSession,
    namespaced_tool_name: str,
    arguments: dict,
    agent_id: str,
) -> dict:
    """Parse namespace from tool name, find the server, and forward a tools/call request.

    Tool name format: "namespace.tool_name" (e.g. "weather.get_forecast").
    """
    if "." not in namespaced_tool_name:
        return {"error": f"Invalid namespaced tool name: {namespaced_tool_name}"}

    namespace, tool_name = namespaced_tool_name.split(".", 1)

    result = await db.execute(
        select(MCPServerEntry).where(
            MCPServerEntry.namespace == namespace,
            MCPServerEntry.status == "active",
        )
    )
    servers = list(result.scalars().all())

    if not servers:
        return {"error": f"No active server found for namespace '{namespace}'"}

    # Pick the server with the highest health score
    server = max(servers, key=lambda s: s.health_score or 0)

    url = f"{server.base_url}/tools/call"
    headers = _build_auth_headers(server)
    payload = {
        "name": tool_name,
        "arguments": arguments,
        "meta": {"agent_id": agent_id},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            result_data = resp.json()

        logger.info(
            "Routed tool call '%s' to server '%s' for agent '%s'",
            namespaced_tool_name,
            server.name,
            agent_id,
        )
        return result_data

    except httpx.HTTPStatusError as exc:
        logger.error(
            "HTTP error routing '%s' to '%s': %s",
            namespaced_tool_name,
            server.name,
            exc,
        )
        await update_health_score(db, server.id, max(0, server.health_score - 10))
        return {"error": f"HTTP {exc.response.status_code}", "tool": namespaced_tool_name}

    except (httpx.RequestError, Exception) as exc:
        logger.error(
            "Error routing '%s' to '%s': %s",
            namespaced_tool_name,
            server.name,
            exc,
        )
        await update_health_score(db, server.id, max(0, server.health_score - 20))
        return {"error": str(exc), "tool": namespaced_tool_name}


async def update_health_score(db: AsyncSession, server_id: str, score: int) -> None:
    """Update the health score and last_health_check for a server."""
    result = await db.execute(
        select(MCPServerEntry).where(MCPServerEntry.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        return

    server.health_score = max(0, min(100, score))
    server.last_health_check = datetime.now(timezone.utc)

    # Degrade status if health drops too low
    if server.health_score <= 0:
        server.status = "inactive"
    elif server.health_score < 50:
        server.status = "degraded"
    else:
        server.status = "active"

    await db.commit()
