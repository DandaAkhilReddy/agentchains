"""Tests that API router registry remains explicit and stable."""

from marketplace.api import (
    API_PREFIX,
    API_ROUTERS,
    API_V2_PREFIX,
    API_V2_ROUTERS,
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
    v2_admin,
    v2_analytics,
    v2_agents,
    v2_billing,
    v2_dashboards,
    v2_events,
    v2_integrations,
    v2_memory,
    v2_payouts,
    v2_sellers,
    v2_verification,
    wallet,
    zkp,
)
from marketplace.api.integrations import openclaw as openclaw_integration


def test_api_prefix_is_stable():
    assert API_PREFIX == "/api/v1"


def test_api_v2_prefix_is_stable():
    assert API_V2_PREFIX == "/api/v2"


def test_router_registry_order_and_membership():
    expected = (
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
    assert API_ROUTERS == expected


def test_v2_router_registry_order_and_membership():
    expected = (
        v2_agents.router,
        v2_admin.router,
        v2_analytics.router,
        v2_billing.router,
        v2_dashboards.router,
        v2_memory.router,
        v2_integrations.router,
        v2_events.router,
        v2_payouts.router,
        v2_sellers.router,
        v2_verification.router,
    )
    assert API_V2_ROUTERS == expected
