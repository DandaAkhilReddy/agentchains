"""MCP Federation v3 API — server registration, tool aggregation, and federated tool/resource calls."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import get_current_agent_id
from marketplace.database import get_db
from marketplace.services import mcp_federation_service

router = APIRouter(prefix="/federation", tags=["mcp-federation"])


# ── Helpers ────────────────────────────────────────────────────────


def _server_to_dict(srv) -> dict:
    """Serialise an MCPServerEntry ORM instance to a plain dict."""
    return {
        "id": srv.id,
        "name": srv.name,
        "base_url": srv.base_url,
        "namespace": srv.namespace,
        "description": srv.description,
        "status": srv.status,
        "health_score": srv.health_score,
        "auth_type": srv.auth_type,
        "last_health_check": srv.last_health_check.isoformat() if srv.last_health_check else None,
        "registered_by": srv.registered_by,
        "created_at": srv.created_at.isoformat() if srv.created_at else None,
        "updated_at": srv.updated_at.isoformat() if srv.updated_at else None,
    }


# ── Request Models ─────────────────────────────────────────────────


class ServerRegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1, max_length=500)
    namespace: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    auth_type: str = Field(default="none", pattern="^(none|bearer|api_key)$")
    auth_credential_ref: str = ""


class ServerUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    namespace: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    auth_type: str | None = Field(default=None, pattern="^(none|bearer|api_key)$")
    auth_credential_ref: str | None = None


class ToolCallRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, description="Namespaced tool name, e.g. 'weather.get_forecast'")
    arguments: dict = Field(default_factory=dict)


class ResourceReadRequest(BaseModel):
    uri: str = Field(..., min_length=1, description="Resource URI to read from a federated server")


# ── Server CRUD Endpoints ──────────────────────────────────────────


@router.post("/servers", status_code=201)
async def register_server(
    req: ServerRegisterRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Register a new federated MCP server."""
    server = await mcp_federation_service.register_server(
        db,
        name=req.name,
        base_url=req.base_url,
        namespace=req.namespace,
        description=req.description,
        auth_type=req.auth_type,
        auth_credential_ref=req.auth_credential_ref,
        registered_by=agent_id,
    )
    return _server_to_dict(server)


@router.get("/servers")
async def list_servers(
    namespace: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List registered federated MCP servers with optional filters."""
    servers = await mcp_federation_service.list_servers(
        db, namespace=namespace, status=status, limit=limit,
    )
    return {
        "servers": [_server_to_dict(s) for s in servers],
        "total": len(servers),
    }


@router.get("/servers/{server_id}")
async def get_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Get details for a single federated MCP server."""
    server = await mcp_federation_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return _server_to_dict(server)


@router.put("/servers/{server_id}")
async def update_server(
    server_id: str,
    req: ServerUpdateRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Update configuration for a federated MCP server."""
    server = await mcp_federation_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if req.name is not None:
        server.name = req.name
    if req.base_url is not None:
        server.base_url = req.base_url.rstrip("/")
    if req.namespace is not None:
        server.namespace = req.namespace
    if req.description is not None:
        server.description = req.description
    if req.auth_type is not None:
        server.auth_type = req.auth_type
    if req.auth_credential_ref is not None:
        server.auth_credential_ref = req.auth_credential_ref

    await db.commit()
    await db.refresh(server)
    return _server_to_dict(server)


@router.delete("/servers/{server_id}")
async def unregister_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Unregister (delete) a federated MCP server."""
    deleted = await mcp_federation_service.unregister_server(db, server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Server not found")
    return {"detail": "Server unregistered", "server_id": server_id}


# ── Server Operations ──────────────────────────────────────────────


@router.post("/servers/{server_id}/health")
async def trigger_health_check(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Trigger a health check for a specific federated server.

    Attempts to refresh tools; if successful the server is marked healthy.
    """
    server = await mcp_federation_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    result = await mcp_federation_service.refresh_server_tools(db, server_id)
    if "error" in result:
        # Update health score to reflect a failed check
        await mcp_federation_service.update_health_score(
            db, server_id, max(0, server.health_score - 20),
        )
        return {
            "server_id": server_id,
            "healthy": False,
            "error": result["error"],
            "health_score": max(0, server.health_score - 20),
        }

    return {
        "server_id": server_id,
        "healthy": True,
        "tools_count": result.get("count", 0),
        "health_score": 100,
    }


@router.post("/servers/{server_id}/refresh")
async def refresh_server_tools(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Refresh the cached tool list from a federated server."""
    server = await mcp_federation_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    result = await mcp_federation_service.refresh_server_tools(db, server_id)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])

    return {
        "server_id": server_id,
        "tools_refreshed": result.get("count", 0),
        "tools": result.get("tools", []),
    }


# ── Aggregated Tool Endpoints ──────────────────────────────────────


@router.get("/tools")
async def list_federated_tools(
    namespace: str | None = None,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List all aggregated tools from all federated MCP servers."""
    tools = await mcp_federation_service.discover_tools(db, namespace=namespace)
    return {
        "tools": tools,
        "total": len(tools),
    }


@router.post("/tools/call")
async def call_federated_tool(
    req: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Call a federated tool by its namespaced name (e.g. 'weather.get_forecast')."""
    result = await mcp_federation_service.route_tool_call(
        db,
        namespaced_tool_name=req.tool_name,
        arguments=req.arguments,
        agent_id=agent_id,
    )
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result


# ── Aggregated Resource Endpoints ──────────────────────────────────


@router.get("/resources")
async def list_federated_resources(
    namespace: str | None = None,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """List all aggregated resources from federated MCP servers.

    Reads each active server's cached resources_json and prefixes
    resource URIs with the server namespace.
    """
    from sqlalchemy import select
    from marketplace.models.mcp_server import MCPServerEntry

    query = select(MCPServerEntry).where(MCPServerEntry.status == "active")
    if namespace:
        query = query.where(MCPServerEntry.namespace == namespace)

    result = await db.execute(query)
    servers = list(result.scalars().all())

    resources: list[dict] = []
    for server in servers:
        try:
            cached = json.loads(server.resources_json) if server.resources_json else []
        except json.JSONDecodeError:
            cached = []

        for resource in cached:
            namespaced = dict(resource)
            namespaced["_server_id"] = server.id
            namespaced["_namespace"] = server.namespace
            resources.append(namespaced)

    return {
        "resources": resources,
        "total": len(resources),
    }


@router.post("/resources/read")
async def read_federated_resource(
    req: ResourceReadRequest,
    db: AsyncSession = Depends(get_db),
    agent_id: str = Depends(get_current_agent_id),
):
    """Read a resource from a federated MCP server by URI.

    The URI should include the namespace prefix so the router can
    identify the correct backend server (e.g. 'weather://forecasts/today').
    Falls back to trying all active servers if no namespace match.
    """
    from sqlalchemy import select
    from marketplace.models.mcp_server import MCPServerEntry
    import httpx

    # Try to extract namespace from the URI scheme (e.g. "weather://...")
    uri = req.uri
    namespace = None
    if "://" in uri:
        namespace = uri.split("://", 1)[0]

    query = select(MCPServerEntry).where(MCPServerEntry.status == "active")
    if namespace:
        query = query.where(MCPServerEntry.namespace == namespace)

    result = await db.execute(query)
    servers = list(result.scalars().all())

    if not servers:
        raise HTTPException(status_code=404, detail="No active server found for resource URI")

    # Try servers in order of health score
    servers.sort(key=lambda s: s.health_score or 0, reverse=True)

    for server in servers:
        url = f"{server.base_url}/resources/read"
        headers = mcp_federation_service._build_auth_headers(server)
        payload = {"uri": uri, "meta": {"agent_id": agent_id}}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError):
            continue

    raise HTTPException(
        status_code=502,
        detail="Failed to read resource from any federated server",
    )


# ── Federation Health Overview ─────────────────────────────────────


@router.get("/health")
async def federation_health_overview(
    db: AsyncSession = Depends(get_db),
):
    """Federation health overview: server count, healthy count, total tool count.

    This endpoint does not require authentication.
    """
    servers = await mcp_federation_service.list_servers(db, limit=1000)
    healthy = [s for s in servers if s.status == "active" and s.health_score >= 50]

    total_tools = 0
    for server in servers:
        try:
            tools = json.loads(server.tools_json) if server.tools_json else []
            total_tools += len(tools)
        except json.JSONDecodeError:
            pass

    return {
        "server_count": len(servers),
        "healthy_count": len(healthy),
        "degraded_count": len([s for s in servers if s.status == "degraded"]),
        "inactive_count": len([s for s in servers if s.status == "inactive"]),
        "total_tool_count": total_tools,
    }
