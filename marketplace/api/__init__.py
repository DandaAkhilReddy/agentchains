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
    v2_billing,
    v2_events,
    v2_integrations,
    v2_agents,
    v2_admin,
    v2_analytics,
    v2_builder,
    v2_creators_profile,
    v2_dashboards,
    v2_market,
    v2_memory,
    v2_payouts,
    v2_sellers,
    v2_users,
    v2_verification,
    wallet,
    zkp,
)
from .integrations import openclaw as openclaw_integration

API_PREFIX = "/api/v1"
API_V2_PREFIX = "/api/v2"

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

API_V2_ROUTERS: tuple[APIRouter, ...] = (
    v2_agents.router,
    v2_admin.router,
    v2_analytics.router,
    v2_billing.router,
    v2_builder.router,
    v2_creators_profile.router,
    v2_dashboards.router,
    v2_memory.router,
    v2_market.router,
    v2_integrations.router,
    v2_events.router,
    v2_payouts.router,
    v2_sellers.router,
    v2_users.router,
    v2_verification.router,
)

__all__ = ["API_PREFIX", "API_ROUTERS", "API_V2_PREFIX", "API_V2_ROUTERS"]
