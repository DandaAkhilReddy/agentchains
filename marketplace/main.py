import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, Response

from marketplace.core.async_tasks import fire_and_forget
from marketplace.database import init_db
from marketplace.models import *  # noqa: F403

APP_VERSION = "0.4.0"
logger = logging.getLogger(__name__)


# WebSocket connection manager for live feed
class ConnectionManager:
    MAX_CONNECTIONS = 1000

    def __init__(self):
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> bool:
        if len(self.active) >= self.MAX_CONNECTIONS:
            await ws.close(code=4029, reason="Too many connections")
            return False
        await ws.accept()
        self.active.add(ws)
        return True

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def broadcast(self, message: dict) -> None:
        data = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.discard(ws)


ws_manager = ConnectionManager()


class ScopedConnectionManager:
    """Connection manager that tracks agent ownership for private event routing."""

    MAX_CONNECTIONS = 2000

    def __init__(self):
        self.active: dict[WebSocket, dict[str, Any]] = {}

    async def connect(self, ws: WebSocket, *, stream_payload: dict[str, Any]) -> bool:
        if len(self.active) >= self.MAX_CONNECTIONS:
            await ws.close(code=4029, reason="Too many connections")
            return False
        await ws.accept()
        self.active[ws] = {
            "sub": stream_payload.get("sub"),
            "sub_type": stream_payload.get("sub_type", "agent"),
            "allowed_topics": set(stream_payload.get("allowed_topics", [])),
        }
        return True

    def disconnect(self, ws: WebSocket) -> None:
        self.active.pop(ws, None)

    async def broadcast_public(self, message: dict) -> None:
        data = json.dumps(message)
        dead: list[WebSocket] = []
        for ws, meta in self.active.items():
            topics = meta.get("allowed_topics", set())
            if topics and "public.market" not in topics:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_private_agent(self, message: dict, *, target_agent_ids: list[str]) -> None:
        if not target_agent_ids:
            return
        data = json.dumps(message)
        targets = set(target_agent_ids)
        dead: list[WebSocket] = []
        for ws, meta in self.active.items():
            if meta.get("sub_type") != "agent":
                continue
            topics = meta.get("allowed_topics", set())
            if topics and "private.agent" not in topics:
                continue
            if meta.get("sub") not in targets:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_private_admin(self, message: dict, *, target_creator_ids: list[str]) -> None:
        data = json.dumps(message)
        targets = set(target_creator_ids or [])
        dead: list[WebSocket] = []
        for ws, meta in self.active.items():
            if meta.get("sub_type") != "admin":
                continue
            topics = meta.get("allowed_topics", set())
            if topics and "private.admin" not in topics:
                continue
            if targets and meta.get("sub") not in targets:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_scoped_manager = ScopedConnectionManager()


async def broadcast_event(event_type: str, data: dict) -> None:
    """Broadcast a typed event to WebSocket clients and webhook subscribers."""
    from marketplace.services.event_subscription_service import (
        build_event_envelope,
        should_dispatch_event,
    )

    envelope = build_event_envelope(
        event_type,
        data,
        agent_id=data.get("agent_id"),
    )
    if not should_dispatch_event(envelope):
        return

    visibility = envelope.get("visibility", "private")
    if visibility == "public":
        await ws_manager.broadcast(envelope)
        await ws_scoped_manager.broadcast_public(envelope)
        # Legacy OpenClaw fan-out is restricted to public events only.
        fire_and_forget(
            _dispatch_openclaw(event_type, envelope.get("payload", data)),
            task_name="dispatch_openclaw",
        )
    else:
        topic = envelope.get("topic", "private.agent")
        if topic == "private.admin":
            await ws_scoped_manager.broadcast_private_admin(
                envelope,
                target_creator_ids=envelope.get("target_creator_ids", []),
            )
        else:
            await ws_scoped_manager.broadcast_private_agent(
                envelope,
                target_agent_ids=envelope.get("target_agent_ids", []),
            )

    # Dispatch to webhook integrations in background (fire-and-forget).
    fire_and_forget(
        _dispatch_event_subscriptions(envelope),
        task_name="dispatch_event_subscriptions",
    )


async def _dispatch_openclaw(event_type: str, data: dict) -> None:
    """Background task to deliver events to registered OpenClaw webhooks."""
    try:
        from marketplace.database import async_session
        from marketplace.services.openclaw_service import dispatch_to_openclaw_webhooks

        async with async_session() as db:
            await dispatch_to_openclaw_webhooks(db, event_type, data)
    except Exception:
        logger.exception("Background task error")


async def _dispatch_event_subscriptions(event: dict) -> None:
    """Background task to deliver events to generic signed webhook subscribers."""
    try:
        from marketplace.database import async_session
        from marketplace.services.event_subscription_service import (
            dispatch_event_to_subscriptions,
        )

        async with async_session() as db:
            await dispatch_event_to_subscriptions(db, event=event)
    except Exception:
        logger.exception("Background task error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: create tables
    await init_db()
    from marketplace.config import settings
    from marketplace.database import async_session

    # Start background demand aggregation (initial delay avoids lock contention at startup)
    async def _demand_loop() -> None:
        await asyncio.sleep(30)  # Wait 30s before first run
        while True:
            try:
                async with async_session() as db:
                    from marketplace.services import demand_service

                    signals = await demand_service.aggregate_demand(db)
                    opps = await demand_service.generate_opportunities(db)
                    # Broadcast high-velocity demand spikes
                    for s in signals:
                        if float(s.velocity or 0) > 10:
                            await broadcast_event("demand_spike", {
                                "query_pattern": s.query_pattern,
                                "velocity": float(s.velocity),
                                "category": s.category,
                            })
                    # Broadcast new high-urgency opportunities
                    for o in opps:
                        if float(o.urgency_score or 0) > 0.7:
                            await broadcast_event("opportunity_created", {
                                "id": o.id,
                                "query_pattern": o.query_pattern,
                                "estimated_revenue_usd": float(o.estimated_revenue_usdc),
                                "urgency_score": float(o.urgency_score),
                            })
            except Exception:
                logger.exception("Background task error")
            await asyncio.sleep(300)  # Every 5 minutes

    demand_task = asyncio.create_task(_demand_loop())

    # Start CDN hot cache decay background task
    from marketplace.services.cdn_service import cdn_decay_loop

    cdn_task = asyncio.create_task(cdn_decay_loop())

    # Start monthly payout background task
    async def _payout_loop() -> None:
        await asyncio.sleep(60)
        while True:
            try:
                now = datetime.now(timezone.utc)
                if now.day == settings.creator_payout_day:
                    from marketplace.services.payout_service import run_monthly_payout

                    async with async_session() as payout_db:
                        await run_monthly_payout(payout_db)
            except Exception:
                logger.exception("Background task error")
            await asyncio.sleep(3600)  # Check hourly

    payout_task = asyncio.create_task(_payout_loop())

    # Security artifact retention cleanup
    async def _security_retention_loop() -> None:
        await asyncio.sleep(120)
        while True:
            try:
                async with async_session() as security_db:
                    from marketplace.services.event_subscription_service import (
                        redact_old_webhook_deliveries,
                    )
                    from marketplace.services.memory_service import (
                        redact_old_memory_verification_evidence,
                    )

                    await redact_old_webhook_deliveries(
                        security_db,
                        retention_days=settings.security_event_retention_days,
                    )
                    await redact_old_memory_verification_evidence(
                        security_db,
                        retention_days=settings.security_event_retention_days,
                    )
            except Exception:
                logger.exception("Background task error")
            await asyncio.sleep(12 * 3600)

    security_retention_task = asyncio.create_task(_security_retention_loop())

    yield

    # Shutdown: cancel background tasks and dispose connection pool
    demand_task.cancel()
    cdn_task.cancel()
    payout_task.cancel()
    security_retention_task.cancel()

    from marketplace.database import dispose_engine

    await dispose_engine()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' wss: ws:; "
            "script-src 'self'"
        )
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent-to-Agent Data Marketplace",
        description="Trade cached computation results between AI agents",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    # CORS configurable via CORS_ORIGINS env var
    from marketplace.config import settings

    allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    from marketplace.core.rate_limit_middleware import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Register REST routers
    from marketplace.api import API_PREFIX, API_ROUTERS, API_V2_PREFIX, API_V2_ROUTERS

    for router in API_ROUTERS:
        app.include_router(router, prefix=API_PREFIX)

    for router in API_V2_ROUTERS:
        app.include_router(router, prefix=API_V2_PREFIX)

    # MCP server routes
    if settings.mcp_enabled:
        from marketplace.mcp.server import router as mcp_router

        app.include_router(mcp_router)

    # WebSocket for live feed (JWT-authenticated)
    @app.websocket("/ws/feed")
    async def live_feed(ws: WebSocket, token: str | None = Query(default=None)) -> None:
        from marketplace.core.auth import decode_token

        if not token:
            await ws.close(code=4001, reason="Missing token query parameter")
            return
        try:
            decode_token(token)
        except Exception:
            await ws.close(code=4003, reason="Invalid or expired token")
            return

        connected = await ws_manager.connect(ws)
        if not connected:
            return
        try:
            await ws.send_text(
                json.dumps(
                    {
                        "type": "deprecation_notice",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {
                            "endpoint": "/ws/feed",
                            "replacement": "/ws/v2/events",
                            "sunset": "2026-05-16T00:00:00Z",
                        },
                    }
                )
            )
            while True:
                # Keep connection alive, receive pings
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)

    @app.websocket("/ws/v2/events")
    async def live_feed_v2(ws: WebSocket, token: str | None = Query(default=None)) -> None:
        from marketplace.core.auth import decode_stream_token

        if not token:
            await ws.close(code=4001, reason="Missing token query parameter")
            return
        try:
            payload = decode_stream_token(token)
        except Exception:
            await ws.close(code=4003, reason="Invalid or expired stream token")
            return

        connected = await ws_scoped_manager.connect(ws, stream_payload=payload)
        if not connected:
            return
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_scoped_manager.disconnect(ws)

    # CDN stats endpoint
    @app.get(f"{API_PREFIX}/health/cdn")
    async def cdn_health() -> dict:
        from marketplace.services.cdn_service import get_cdn_stats

        return get_cdn_stats()

    # Serve frontend static files (built React app)
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="static-assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve the React SPA for any non-API route."""
            # Resolve and verify the path stays within static_dir (prevent traversal)
            file_path = (static_dir / full_path).resolve()
            if file_path.is_file() and str(file_path).startswith(str(static_dir.resolve())):
                return FileResponse(str(file_path))
            # Fallback to index.html for SPA routing
            return FileResponse(str(static_dir / "index.html"))
    else:
        @app.get("/")
        async def root() -> dict[str, str]:
            return {
                "name": "Agent-to-Agent Data Marketplace",
                "version": APP_VERSION,
                "docs": "/docs",
                "health": f"{API_PREFIX}/health",
                "mcp": "/mcp/health",
                "cdn": f"{API_PREFIX}/health/cdn",
            }

    return app


app = create_app()
