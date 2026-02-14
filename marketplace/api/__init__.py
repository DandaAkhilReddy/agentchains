"""API router registry used by the app factory.

This keeps route module imports and inclusion order in one place so
`marketplace.main` stays focused on startup wiring.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    analytics,
    audit,
    automatch,
    catalog,
    creators,
    discovery,
    express,
    health,
    listings,
    redemptions,
    registry,
    reputation,
    routing,
    seller_api,
    transactions,
    verification,
    wallet,
    zkp,
)
from .integrations import openclaw as openclaw_integration

API_PREFIX = "/api/v1"

API_ROUTERS: tuple[APIRouter, ...] = (
    health.router,
    registry.router,
    listings.router,
    discovery.router,
    transactions.router,
    verification.router,
    reputation.router,
    express.router,
    automatch.router,
    analytics.router,
    zkp.router,
    catalog.router,
    seller_api.router,
    routing.router,
    wallet.router,
    creators.router,
    audit.router,
    redemptions.router,
    openclaw_integration.router,
)

__all__ = ["API_PREFIX", "API_ROUTERS"]
