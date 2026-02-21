"""MCP Federation health monitor — background health checks.

Periodically pings federated MCP servers and updates their health scores.
Runs as a background task in the FastAPI lifespan.
"""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

_HEALTH_INTERVAL_SECONDS = 30
_HEALTH_TIMEOUT_SECONDS = 5


async def health_check_loop(interval: int = _HEALTH_INTERVAL_SECONDS) -> None:
    """Background loop that checks health of all federated MCP servers."""
    await asyncio.sleep(15)  # Initial delay to let app start
    logger.info("MCP health monitor started (interval=%ds)", interval)

    while True:
        try:
            await _run_health_checks()
        except Exception:
            logger.exception("MCP health check loop error")
        await asyncio.sleep(interval)


async def _run_health_checks() -> None:
    """Check health of all active federated MCP servers."""
    from marketplace.database import async_session
    from marketplace.models.mcp_server import MCPServerEntry

    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(MCPServerEntry).where(
                MCPServerEntry.status.in_(["active", "degraded"])
            )
        )
        servers = result.scalars().all()

    if not servers:
        return

    async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT_SECONDS) as client:
        tasks = [_check_server(client, s) for s in servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Update health scores in DB
    from marketplace.database import async_session as get_session
    from datetime import datetime, timezone

    async with get_session() as db:
        for server, result in zip(servers, results):
            if isinstance(result, Exception):
                new_score = max(0, (server.health_score or 100) - 20)
                new_status = "degraded" if new_score > 0 else "inactive"
                logger.warning(
                    "MCP server %s health check failed: %s (score=%d)",
                    server.name, result, new_score,
                )
            else:
                latency_ms, is_healthy = result
                if is_healthy:
                    new_score = min(100, (server.health_score or 50) + 10)
                    new_status = "active"
                else:
                    new_score = max(0, (server.health_score or 100) - 15)
                    new_status = "degraded" if new_score > 20 else "inactive"

            server.health_score = new_score
            server.status = new_status
            server.last_health_check = datetime.now(timezone.utc)
            db.add(server)

        await db.commit()


async def _check_server(
    client: httpx.AsyncClient, server
) -> tuple[float, bool]:
    """Ping a single MCP server and return (latency_ms, is_healthy)."""
    health_url = f"{server.base_url.rstrip('/')}/mcp/health"
    start = time.monotonic()

    try:
        resp = await client.get(health_url)
        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            return latency_ms, data.get("status") == "ok"
        return latency_ms, False

    except httpx.TimeoutException:
        latency_ms = (time.monotonic() - start) * 1000
        raise Exception(f"Timeout after {latency_ms:.0f}ms")
    except httpx.ConnectError as e:
        raise Exception(f"Connection failed: {e}")


class MCPHealthMonitor:
    """Class wrapper for MCP health monitor functions."""

    async def run_loop(self, db, **kwargs):
        return await health_check_loop(db, **kwargs)
