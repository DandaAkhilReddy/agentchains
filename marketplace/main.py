import json
from contextlib import asynccontextmanager
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
        self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


ws_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Startup: create tables
    await init_db()
    yield
    # Shutdown: nothing to clean up for SQLite


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent-to-Agent Data Marketplace",
        description="Trade cached computation results between AI agents",
        version="0.1.0",
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
        discovery,
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
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
