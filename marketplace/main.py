import asyncio
import json
import os
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


# WebSocket connection manager for live feed
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active:
                self.active.remove(ws)


ws_manager = ConnectionManager()


async def broadcast_event(event_type: str, data: dict):
    """Broadcast a typed event to all connected WebSocket clients and OpenClaw webhooks."""
    await ws_manager.broadcast({
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })
    # Dispatch to OpenClaw webhooks in background (fire-and-forget)
    asyncio.ensure_future(_dispatch_openclaw(event_type, data))


async def _dispatch_openclaw(event_type: str, data: dict):
    """Background task to deliver events to registered OpenClaw webhooks."""
    try:
        from marketplace.database import async_session
        from marketplace.services.openclaw_service import dispatch_to_openclaw_webhooks
        async with async_session() as db:
            await dispatch_to_openclaw_webhooks(db, event_type, data)
    except Exception:
        pass  # Don't let webhook failures affect the main flow


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Startup: create tables
    await init_db()

    # Start background demand aggregation (initial delay avoids lock contention at startup)
    async def _demand_loop():
        await asyncio.sleep(30)  # Wait 30s before first run
        while True:
            try:
                from marketplace.database import async_session
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
                pass
            await asyncio.sleep(300)  # Every 5 minutes

    task = asyncio.create_task(_demand_loop())

    # Start CDN hot cache decay background task
    from marketplace.services.cdn_service import cdn_decay_loop
    cdn_task = asyncio.create_task(cdn_decay_loop())

    # Start monthly payout background task
    async def _payout_loop():
        await asyncio.sleep(60)
        while True:
            try:
                now = datetime.now(timezone.utc)
                if now.day == settings.creator_payout_day:
                    from marketplace.services.payout_service import run_monthly_payout
                    async with async_session() as payout_db:
                        await run_monthly_payout(payout_db)
            except Exception:
                pass
            await asyncio.sleep(3600)  # Check hourly

    from marketplace.config import settings
    from marketplace.database import async_session
    payout_task = asyncio.create_task(_payout_loop())

    yield

    # Shutdown: cancel background tasks and dispose connection pool
    task.cancel()
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
        version="0.4.0",
        lifespan=lifespan,
    )

    # CORS — configurable via CORS_ORIGINS env var
    from marketplace.config import settings
    allowed_origins = [o.strip() for o in settings.cors_origins.split(",")]
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

    # Register routers
    from marketplace.api import (
        analytics,
        automatch,
        catalog,
        creators,
        discovery,
        express,
        health,
        listings,
        registry,
        reputation,
        routing,
        seller_api,
        transactions,
        verification,
        wallet,
        zkp,
    )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(registry.router, prefix="/api/v1")
    app.include_router(listings.router, prefix="/api/v1")
    app.include_router(discovery.router, prefix="/api/v1")
    app.include_router(transactions.router, prefix="/api/v1")
    app.include_router(verification.router, prefix="/api/v1")
    app.include_router(reputation.router, prefix="/api/v1")
    app.include_router(express.router, prefix="/api/v1")
    app.include_router(automatch.router, prefix="/api/v1")
    app.include_router(analytics.router, prefix="/api/v1")
    app.include_router(zkp.router, prefix="/api/v1")
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(seller_api.router, prefix="/api/v1")
    app.include_router(routing.router, prefix="/api/v1")
    app.include_router(wallet.router, prefix="/api/v1")
    app.include_router(creators.router, prefix="/api/v1")

    from marketplace.api import redemptions
    app.include_router(redemptions.router, prefix="/api/v1")

    from marketplace.api import audit, redemptions
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(redemptions.router, prefix="/api/v1")

    from marketplace.api.integrations import openclaw as openclaw_integration
    app.include_router(openclaw_integration.router, prefix="/api/v1")

    # MCP server routes
    if settings.mcp_enabled:
        from marketplace.mcp.server import router as mcp_router
        app.include_router(mcp_router)

    # WebSocket for live feed (JWT-authenticated)
    @app.websocket("/ws/feed")
    async def live_feed(ws: WebSocket, token: str = Query(None)):
        from marketplace.core.auth import decode_token
        if not token:
            await ws.close(code=4001, reason="Missing token query parameter")
            return
        try:
            decode_token(token)
        except Exception:
            await ws.close(code=4003, reason="Invalid or expired token")
            return

        await ws_manager.connect(ws)
        try:
            while True:
                # Keep connection alive, receive pings
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)

    # CDN stats endpoint
    @app.get("/api/v1/health/cdn")
    async def cdn_health():
        from marketplace.services.cdn_service import get_cdn_stats
        return get_cdn_stats()

    # Serve frontend static files (built React app)
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="static-assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve the React SPA for any non-API route."""
            # Check if it's a static file first
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            # Fallback to index.html for SPA routing
            return FileResponse(str(static_dir / "index.html"))
    else:
        @app.get("/")
        async def root():
            return {
                "name": "Agent-to-Agent Data Marketplace",
                "version": "0.4.0",
                "docs": "/docs",
                "health": "/api/v1/health",
                "mcp": "/mcp/health",
                "cdn": "/api/v1/health/cdn",
            }

    return app


app = create_app()
