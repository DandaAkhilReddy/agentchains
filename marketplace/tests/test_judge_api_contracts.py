"""J-4 API Contracts Judge — 15 tests verifying HTTP error codes and response schemas.

Ensures that every endpoint returns the correct status code for error conditions
and that success responses conform to the documented API contract (field names,
types, pagination semantics, and error envelope format).

Uses shared conftest fixtures: client, db, seed_platform, make_agent,
make_token_account, make_listing, auth_header.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CDN_PATCH = "marketplace.services.express_service.cdn_get_content"
SAMPLE_CONTENT = b'{"data": "api contracts judge payload"}'

REGISTER_PAYLOAD = {
    "name": "contract-test-agent",
    "agent_type": "both",
    "public_key": "ssh-rsa AAAA_test_key",
}


async def _seed_platform():
    """Ensure platform treasury + TokenSupply exist for token tests."""
    from marketplace.models.token_account import TokenAccount, TokenSupply
    from sqlalchemy import select

    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id.is_(None))
        )
        if result.scalar_one_or_none() is None:
            db.add(TokenAccount(
                id=_new_id(), agent_id=None,
                balance=Decimal("0"), tier="platform",
            ))
            db.add(TokenSupply(id=1))
            await db.commit()


# ===================================================================
# 1. test_404_for_nonexistent_agent
# ===================================================================

@pytest.mark.asyncio
async def test_404_for_nonexistent_agent(client):
    """GET /api/v1/agents/<nonexistent-uuid> returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/agents/{fake_id}")
    assert resp.status_code == 404


# ===================================================================
# 2. test_404_for_nonexistent_listing
# ===================================================================

@pytest.mark.asyncio
async def test_404_for_nonexistent_listing(client):
    """GET /api/v1/listings/<nonexistent-uuid> returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/listings/{fake_id}")
    assert resp.status_code == 404


# ===================================================================
# 3. test_422_for_missing_required_fields
# ===================================================================

@pytest.mark.asyncio
async def test_422_for_missing_required_fields(client):
    """POST /api/v1/agents/register without the required 'name' field returns 422."""
    resp = await client.post("/api/v1/agents/register", json={
        # 'name' is missing
        "agent_type": "both",
        "public_key": "ssh-rsa AAAA_test_key",
    })
    assert resp.status_code == 422


# ===================================================================
# 4. test_422_for_invalid_agent_type
# ===================================================================

@pytest.mark.asyncio
async def test_422_for_invalid_agent_type(client):
    """POST /api/v1/agents/register with agent_type='invalid' returns 422."""
    resp = await client.post("/api/v1/agents/register", json={
        "name": "invalid-type-agent",
        "agent_type": "invalid",
        "public_key": "ssh-rsa AAAA_test_key",
    })
    assert resp.status_code == 422


# ===================================================================
# 5. test_401_for_missing_auth
# ===================================================================

@pytest.mark.asyncio
async def test_401_for_missing_auth(client, make_agent, make_listing):
    """Protected express-buy endpoint without Authorization header returns 401."""
    seller, _ = await make_agent(name="seller-auth-check")
    listing = await make_listing(seller.id, price_usdc=1.0)

    # No auth header — should get 401
    resp = await client.get(f"/api/v1/express/{listing.id}?payment_method=token")
    assert resp.status_code == 401


# ===================================================================
# 6. test_400_for_self_purchase
# ===================================================================

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_400_for_self_purchase(mock_cdn, client, make_agent, make_listing,
                                     make_token_account, auth_header):
    """Express buy where buyer == seller returns 400."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, seller_jwt = await make_agent(name="seller-self-contract")
    await make_token_account(seller.id, balance=50000)
    listing = await make_listing(seller.id, price_usdc=1.0)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers=auth_header(seller_jwt),
    )
    assert resp.status_code == 400
    assert "own listing" in resp.json()["detail"].lower()


# ===================================================================
# 7. test_402_for_insufficient_balance
# ===================================================================

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_402_for_insufficient_balance(mock_cdn, client, make_agent, make_listing,
                                            make_token_account, auth_header):
    """Express buy with zero ARD balance on a priced listing returns 402."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-bal-contract")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=10.0, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-bal-contract")
    await make_token_account(buyer.id, balance=0)  # zero balance

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers=auth_header(buyer_jwt),
    )
    assert resp.status_code == 402
    assert "insufficient" in resp.json()["detail"].lower()


# ===================================================================
# 8. test_register_response_schema
# ===================================================================

@pytest.mark.asyncio
async def test_register_response_schema(client):
    """POST /api/v1/agents/register response contains: id, name, jwt_token, agent_card_url, created_at."""
    resp = await client.post("/api/v1/agents/register", json={
        "name": f"schema-agent-{_new_id()[:8]}",
        "agent_type": "both",
        "public_key": "ssh-rsa AAAA_test_key",
    })
    assert resp.status_code == 201
    body = resp.json()

    # Required fields per AgentRegisterResponse schema
    assert "id" in body
    assert "name" in body
    assert "jwt_token" in body
    assert "agent_card_url" in body
    assert "created_at" in body

    # Type checks
    assert isinstance(body["id"], str)
    assert isinstance(body["name"], str)
    assert isinstance(body["jwt_token"], str)
    assert isinstance(body["agent_card_url"], str)
    assert isinstance(body["created_at"], str)
    assert len(body["id"]) > 0
    assert len(body["jwt_token"]) > 0


# ===================================================================
# 9. test_discover_response_schema
# ===================================================================

@pytest.mark.asyncio
async def test_discover_response_schema(client):
    """GET /api/v1/discover response contains: results (array), total, page, page_size."""
    resp = await client.get("/api/v1/discover")
    assert resp.status_code == 200
    body = resp.json()

    # Required fields per ListingListResponse schema
    assert "results" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body

    # Type checks
    assert isinstance(body["results"], list)
    assert isinstance(body["total"], int)
    assert isinstance(body["page"], int)
    assert isinstance(body["page_size"], int)

    # Sane defaults
    assert body["total"] >= 0
    assert body["page"] >= 1
    assert body["page_size"] >= 1


# ===================================================================
# 10. test_health_response_schema
# ===================================================================

@pytest.mark.asyncio
async def test_health_response_schema(client):
    """GET /api/v1/health response contains: status, agents_count, listings_count, cache_stats, version."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()

    # Required fields per HealthResponse schema
    assert "status" in body
    assert "agents_count" in body
    assert "listings_count" in body
    assert "cache_stats" in body
    assert "version" in body

    # Type checks
    assert isinstance(body["status"], str)
    assert isinstance(body["agents_count"], int)
    assert isinstance(body["listings_count"], int)
    assert isinstance(body["version"], str)
    assert isinstance(body["cache_stats"], dict)

    # Cache stats sub-keys
    stats = body["cache_stats"]
    assert "listings" in stats
    assert "content" in stats
    assert "agents" in stats


# ===================================================================
# 11. test_pagination_page_zero
# ===================================================================

@pytest.mark.asyncio
async def test_pagination_page_zero(client):
    """GET /api/v1/discover?page=0 returns 422 because page has ge=1 constraint."""
    resp = await client.get("/api/v1/discover", params={"page": 0})
    assert resp.status_code == 422


# ===================================================================
# 12. test_pagination_size_zero
# ===================================================================

@pytest.mark.asyncio
async def test_pagination_size_zero(client):
    """GET /api/v1/discover?page_size=0 returns 422 because page_size has ge=1 constraint."""
    resp = await client.get("/api/v1/discover", params={"page_size": 0})
    assert resp.status_code == 422


# ===================================================================
# 13. test_pagination_size_over_100
# ===================================================================

@pytest.mark.asyncio
async def test_pagination_size_over_100(client):
    """GET /api/v1/discover?page_size=101 returns 422 because page_size has le=100 constraint."""
    resp = await client.get("/api/v1/discover", params={"page_size": 101})
    assert resp.status_code == 422


# ===================================================================
# 14. test_express_buy_response_schema
# ===================================================================

@pytest.mark.asyncio
@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_response_schema(mock_cdn, client, make_agent, make_listing,
                                           make_token_account, auth_header):
    """Successful express buy response contains: transaction_id, content, content_hash, price_usdc, delivery_ms."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-schema-express")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-schema-express")
    await make_token_account(buyer.id, balance=50000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers=auth_header(buyer_jwt),
    )
    assert resp.status_code == 200
    body = resp.json()

    # Required fields per express buy contract
    assert "transaction_id" in body
    assert "content" in body
    assert "content_hash" in body
    assert "price_usdc" in body
    assert "delivery_ms" in body

    # Type checks
    assert isinstance(body["transaction_id"], str)
    assert isinstance(body["content"], str)
    assert isinstance(body["content_hash"], str)
    assert isinstance(body["price_usdc"], (int, float))
    assert isinstance(body["delivery_ms"], (int, float))

    # Delivery timing must be non-negative
    assert body["delivery_ms"] >= 0

    # Content hash matches listing
    assert body["content_hash"] == listing.content_hash

    # Transaction ID is a valid UUID
    uuid.UUID(body["transaction_id"])


# ===================================================================
# 15. test_error_response_format
# ===================================================================

@pytest.mark.asyncio
async def test_error_response_format(client):
    """Error responses conform to the {"detail": "..."} envelope format."""
    # 404 error — nonexistent agent
    fake_id = str(uuid.uuid4())
    resp_404 = await client.get(f"/api/v1/agents/{fake_id}")
    assert resp_404.status_code == 404
    body_404 = resp_404.json()
    assert "detail" in body_404
    assert isinstance(body_404["detail"], str)

    # 422 error — missing required fields
    resp_422 = await client.post("/api/v1/agents/register", json={})
    assert resp_422.status_code == 422
    body_422 = resp_422.json()
    assert "detail" in body_422

    # 401 error — express buy without auth
    resp_401 = await client.get(f"/api/v1/express/{fake_id}?payment_method=token")
    assert resp_401.status_code == 401
    body_401 = resp_401.json()
    assert "detail" in body_401
    assert isinstance(body_401["detail"], str)
