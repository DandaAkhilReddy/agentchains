"""Tests that API router registry remains explicit and stable."""

from marketplace.api import (
    API_PREFIX,
    API_ROUTERS,
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
from marketplace.api.integrations import openclaw as openclaw_integration


def test_api_prefix_is_stable():
    assert API_PREFIX == "/api/v1"


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
