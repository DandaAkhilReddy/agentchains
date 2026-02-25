"""Tests for marketplace/api/v2_verification.py — Trust verification endpoints."""

from __future__ import annotations

from marketplace.tests.conftest import TestSession, _new_id


VERIFICATION_PREFIX = "/api/v2/verification"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# GET /api/v2/verification/listings/{listing_id}
# ===========================================================================


async def test_get_listing_trust_state_happy_path(client, make_agent, make_listing):
    """GET /listings/{listing_id} returns trust payload for an existing listing."""
    agent, _ = await make_agent()
    listing = await make_listing(seller_id=agent.id, price_usdc=5.0)

    resp = await client.get(f"{VERIFICATION_PREFIX}/listings/{listing.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["listing_id"] == listing.id
    assert "trust_status" in body
    assert "trust_score" in body
    assert "verification_summary" in body
    assert "provenance" in body


async def test_get_listing_trust_state_not_found(client):
    """GET /listings/{listing_id} returns 404 for nonexistent listing."""
    resp = await client.get(f"{VERIFICATION_PREFIX}/listings/nonexistent-id")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


async def test_get_listing_trust_state_no_auth_required(client, make_agent, make_listing):
    """GET /listings/{listing_id} does not require authentication."""
    agent, _ = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    # No auth header — should still succeed
    resp = await client.get(f"{VERIFICATION_PREFIX}/listings/{listing.id}")
    assert resp.status_code == 200


async def test_get_listing_trust_state_defaults(client, make_agent, make_listing):
    """GET /listings/{listing_id} returns default trust state for unverified listing."""
    agent, _ = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.get(f"{VERIFICATION_PREFIX}/listings/{listing.id}")
    body = resp.json()
    # Newly created listings should be pending or have default trust status
    assert body["trust_status"] in ("pending_verification", "verification_failed", None)
    assert isinstance(body["trust_score"], int)


# ===========================================================================
# POST /api/v2/verification/listings/{listing_id}/run
# ===========================================================================


async def test_run_verification_requires_auth(client, make_agent, make_listing):
    """POST /listings/{listing_id}/run without auth returns 401."""
    agent, _ = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.post(f"{VERIFICATION_PREFIX}/listings/{listing.id}/run")
    assert resp.status_code == 401


async def test_run_verification_happy_path(client, make_agent, make_listing):
    """POST /listings/{listing_id}/run by the seller runs verification."""
    agent, token = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/run",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["listing_id"] == listing.id
    assert "trust_status" in body
    assert "trust_score" in body
    assert "job_id" in body


async def test_run_verification_not_seller_returns_403(client, make_agent, make_listing):
    """POST /listings/{listing_id}/run by a non-seller returns 403."""
    seller, _ = await make_agent(name="ver-seller")
    _, other_token = await make_agent(name="ver-other")
    listing = await make_listing(seller_id=seller.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/run",
        headers=_auth(other_token),
    )
    assert resp.status_code == 403
    assert "seller" in resp.json()["detail"].lower()


async def test_run_verification_listing_not_found(client, make_agent):
    """POST /listings/{listing_id}/run for nonexistent listing returns 404."""
    _, token = await make_agent()

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/nonexistent-listing/run",
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_run_verification_returns_stage_results(client, make_agent, make_listing):
    """POST /listings/{listing_id}/run returns verification summary with stages."""
    agent, token = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/run",
        headers=_auth(token),
    )
    body = resp.json()
    # Verification summary should contain stage results
    summary = body.get("verification_summary", {})
    if summary:
        assert "stages" in summary or "status" in summary


# ===========================================================================
# POST /api/v2/verification/listings/{listing_id}/receipts
# ===========================================================================


async def test_add_receipt_requires_auth(client, make_agent, make_listing):
    """POST /listings/{listing_id}/receipts without auth returns 401."""
    agent, _ = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/receipts",
        json={
            "provider": "firecrawl",
            "source_query": "python data",
            "seller_signature": "sig12345678",
        },
    )
    assert resp.status_code == 401


async def test_add_receipt_happy_path(client, make_agent, make_listing):
    """POST /listings/{listing_id}/receipts by the seller succeeds."""
    agent, token = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/receipts",
        headers=_auth(token),
        json={
            "provider": "firecrawl",
            "source_query": "python tutorials",
            "seller_signature": "seller_sig_12345678",
            "response_hash": f"sha256:{'a' * 64}",
            "request_payload": {"url": "https://example.com"},
            "headers": {"X-Api-Key": "redacted"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "receipt_id" in body
    assert "verification" in body
    assert body["verification"]["listing_id"] == listing.id


async def test_add_receipt_not_seller_returns_403(client, make_agent, make_listing):
    """POST /listings/{listing_id}/receipts by non-seller returns 403."""
    seller, _ = await make_agent(name="receipt-seller")
    _, other_token = await make_agent(name="receipt-other")
    listing = await make_listing(seller_id=seller.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/receipts",
        headers=_auth(other_token),
        json={
            "provider": "firecrawl",
            "source_query": "test",
            "seller_signature": "sig12345678",
        },
    )
    assert resp.status_code == 403


async def test_add_receipt_listing_not_found(client, make_agent):
    """POST /listings/{listing_id}/receipts for nonexistent listing returns 404."""
    _, token = await make_agent()

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/nonexistent-listing/receipts",
        headers=_auth(token),
        json={
            "provider": "firecrawl",
            "source_query": "test",
            "seller_signature": "sig12345678",
        },
    )
    assert resp.status_code == 404


async def test_add_receipt_invalid_provider(client, make_agent, make_listing):
    """POST /listings/{listing_id}/receipts with unsupported provider returns 400."""
    agent, token = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/receipts",
        headers=_auth(token),
        json={
            "provider": "unsupported_provider",
            "source_query": "test",
            "seller_signature": "sig12345678",
        },
    )
    assert resp.status_code == 400
    assert "provider" in resp.json()["detail"].lower()


async def test_add_receipt_missing_required_fields(client, make_agent, make_listing):
    """POST /listings/{listing_id}/receipts with missing fields returns 422."""
    agent, token = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    # Missing provider
    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/receipts",
        headers=_auth(token),
        json={
            "source_query": "test",
            "seller_signature": "sig12345678",
        },
    )
    assert resp.status_code == 422


async def test_add_receipt_short_signature_rejected(client, make_agent, make_listing):
    """POST /listings/{listing_id}/receipts with signature < 8 chars returns 422."""
    agent, token = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/receipts",
        headers=_auth(token),
        json={
            "provider": "firecrawl",
            "source_query": "test",
            "seller_signature": "short",
        },
    )
    assert resp.status_code == 422


async def test_add_receipt_triggers_re_verification(client, make_agent, make_listing):
    """POST /listings/{listing_id}/receipts re-runs verification after adding receipt."""
    agent, token = await make_agent()
    listing = await make_listing(seller_id=agent.id)

    resp = await client.post(
        f"{VERIFICATION_PREFIX}/listings/{listing.id}/receipts",
        headers=_auth(token),
        json={
            "provider": "serpapi",
            "source_query": "AI marketplace data",
            "seller_signature": "sig_abcdefgh",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    verification = body["verification"]
    assert "trust_status" in verification
    assert "trust_score" in verification
    assert "job_id" in verification


async def test_add_receipt_with_all_allowed_providers(client, make_agent, make_listing):
    """POST /listings/{listing_id}/receipts accepts all allowed providers."""
    allowed_providers = [
        "firecrawl", "serpapi", "browserbase",
        "openapi", "custom_api", "manual_upload",
    ]

    for provider in allowed_providers:
        agent, token = await make_agent(name=f"prov-{provider[:6]}-{_new_id()[:4]}")
        listing = await make_listing(seller_id=agent.id)

        resp = await client.post(
            f"{VERIFICATION_PREFIX}/listings/{listing.id}/receipts",
            headers=_auth(token),
            json={
                "provider": provider,
                "source_query": f"test query for {provider}",
                "seller_signature": f"sig_{provider}_12345",
            },
        )
        assert resp.status_code == 200, f"Provider {provider} rejected unexpectedly"
