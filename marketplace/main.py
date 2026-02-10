import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

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
    """Broadcast a typed event to all connected WebSocket clients.

    Called by services (listing, transaction, express) to push real-time updates.
    """
    await ws_manager.broadcast({
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Startup: create tables
    await init_db()

    # Start background demand aggregation
    async def _demand_loop():
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

    yield
    # Shutdown: nothing to clean up for SQLite


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent-to-Agent Data Marketplace",
        description="Trade cached computation results between AI agents",
        version="0.3.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from marketplace.api import (
        analytics,
        automatch,
        discovery,
        express,
        health,
        listings,
        registry,
        reputation,
        transactions,
        verification,
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

    # WebSocket for live feed
    @app.websocket("/ws/feed")
    async def live_feed(ws: WebSocket):
        await ws_manager.connect(ws)
        try:
            while True:
                # Keep connection alive, receive pings
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "Agent-to-Agent Data Marketplace",
            "version": "0.3.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
