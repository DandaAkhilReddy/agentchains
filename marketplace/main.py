import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, Response

from marketplace.database import init_db
from marketplace.models import *  # noqa: ensure all models are imported for create_all

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


async def broadcast_event(event_type: str, data: dict) -> None:
    """Broadcast a typed event to all connected WebSocket clients and OpenClaw webhooks."""
    await ws_manager.broadcast({
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })
    # Dispatch to OpenClaw webhooks in background (fire-and-forget)
    asyncio.ensure_future(_dispatch_openclaw(event_type, data))


async def _dispatch_openclaw(event_type: str, data: dict) -> None:
    """Background task to deliver events to registered OpenClaw webhooks."""
    try:
        from marketplace.database import async_session
        from marketplace.services.openclaw_service import dispatch_to_openclaw_webhooks

        async with async_session() as db:
            await dispatch_to_openclaw_webhooks(db, event_type, data)
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
                                "estimated_revenue_usdc": float(o.estimated_revenue_usdc),
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

    yield

    # Shutdown: cancel background tasks and dispose connection pool
    demand_task.cancel()
    cdn_task.cancel()
    payout_task.cancel()

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
    from marketplace.api import API_PREFIX, API_ROUTERS

    for router in API_ROUTERS:
        app.include_router(router, prefix=API_PREFIX)

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
            while True:
                # Keep connection alive, receive pings
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)

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
