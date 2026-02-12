"""Negative-path coverage tests: Pydantic validation 422s, 404s, 403s, and creator errors.

Exercises exact field constraints from listing.py and agent.py schemas,
ownership checks in listing_service and registry routes, and creator
auth error flows. Every test targets a single negative code path.
"""

import uuid

import pytest


# ---------------------------------------------------------------------------
# Helper: valid payloads (mutated per test to trigger one violation)
# ---------------------------------------------------------------------------

def _valid_listing_payload(**overrides) -> dict:
    """Return a valid ListingCreateRequest payload, then apply overrides."""
    base = {
        "title": "Valid Listing Title",
        "description": "A valid listing",
        "category": "web_search",
        "content": "dGVzdCBjb250ZW50",  # base64 encoded
        "price_usdc": 5.0,
        "metadata": {},
        "tags": ["test"],
        "quality_score": 0.8,
    }
    base.update(overrides)
    return base


def _valid_agent_payload(**overrides) -> dict:
    """Return a valid AgentRegisterRequest payload, then apply overrides."""
    base = {
        "name": f"neg-test-agent-{uuid.uuid4().hex[:8]}",
        "description": "Test agent for negative path",
        "agent_type": "seller",
        "public_key": "ssh-rsa AAAA_negative_test_key_placeholder",
        "wallet_address": "",
        "capabilities": [],
        "a2a_endpoint": "",
    }
    base.update(overrides)
    return base


# ===========================================================================
# SECTION 1 — Listing validation 422s (8 tests)
# ===========================================================================

@pytest.mark.asyncio
async def test_listing_invalid_category_422(client, make_agent, auth_header):
    """POST /listings with category='invalid_type' must return 422.

    Schema: category is constrained by pattern
    ^(web_search|code_analysis|document_summary|api_response|computation)$
    """
    agent, token = await make_agent()
    payload = _valid_listing_payload(category="invalid_type")

    resp = await client.post(
        "/api/v1/listings", headers=auth_header(token), json=payload,
    )

    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_listing_negative_price_422(client, make_agent, auth_header):
    """POST /listings with price_usdc=-1.0 must return 422.

    Schema: price_usdc = Field(..., gt=0, le=1000) — strictly greater than 0.
    """
    agent, token = await make_agent()
    payload = _valid_listing_payload(price_usdc=-1.0)

    resp = await client.post(
        "/api/v1/listings", headers=auth_header(token), json=payload,
    )

    assert resp.status_code == 422
    body = resp.json()
    # Pydantic v2 puts validation errors in detail
    assert "detail" in body


@pytest.mark.asyncio
async def test_listing_empty_title_422(client, make_agent, auth_header):
    """POST /listings with title='' must return 422.

    Schema: title = Field(..., min_length=1, max_length=255)
    """
    agent, token = await make_agent()
    payload = _valid_listing_payload(title="")

    resp = await client.post(
        "/api/v1/listings", headers=auth_header(token), json=payload,
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_listing_empty_content_422(client, make_agent, auth_header):
    """POST /listings with content='' must return 422.

    Schema: content = Field(..., min_length=1)
    """
    agent, token = await make_agent()
    payload = _valid_listing_payload(content="")

    resp = await client.post(
        "/api/v1/listings", headers=auth_header(token), json=payload,
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_listing_quality_above_one_422(client, make_agent, auth_header):
    """POST /listings with quality_score=1.5 must return 422.

    Schema: quality_score = Field(default=0.5, ge=0, le=1)
    """
    agent, token = await make_agent()
    payload = _valid_listing_payload(quality_score=1.5)

    resp = await client.post(
        "/api/v1/listings", headers=auth_header(token), json=payload,
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_listing_quality_below_zero_422(client, make_agent, auth_header):
    """POST /listings with quality_score=-0.1 must return 422.

    Schema: quality_score = Field(default=0.5, ge=0, le=1)
    """
    agent, token = await make_agent()
    payload = _valid_listing_payload(quality_score=-0.1)

    resp = await client.post(
        "/api/v1/listings", headers=auth_header(token), json=payload,
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_listing_missing_required_fields_422(client, make_agent, auth_header):
    """POST /listings with empty JSON body must return 422.

    Schema requires: title, category, content, price_usdc (all Field(...)).
    """
    agent, token = await make_agent()

    resp = await client.post(
        "/api/v1/listings", headers=auth_header(token), json={},
    )

    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    # At minimum, the error should reference missing fields
    errors = body["detail"]
    assert isinstance(errors, list)
    assert len(errors) >= 1


@pytest.mark.asyncio
async def test_listing_extra_unknown_field_ignored(client, make_agent, auth_header):
    """POST /listings with an unknown extra field should NOT return 422.

    Pydantic BaseModel by default ignores extra fields (no forbid config).
    The request should succeed (201) with the extra field silently dropped.
    """
    agent, token = await make_agent()
    payload = _valid_listing_payload(totally_unknown_field="should_be_ignored")

    resp = await client.post(
        "/api/v1/listings", headers=auth_header(token), json=payload,
    )

    # Should succeed, not fail with 422
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    # The extra field should not appear in the response
    assert "totally_unknown_field" not in body


# ===========================================================================
# SECTION 2 — Agent validation 422s (3 tests)
# ===========================================================================

@pytest.mark.asyncio
async def test_agent_invalid_type_422(client):
    """POST /agents/register with agent_type='hacker' must return 422.

    Schema: agent_type = Field(..., pattern="^(seller|buyer|both)$")
    """
    payload = _valid_agent_payload(agent_type="hacker")

    resp = await client.post("/api/v1/agents/register", json=payload)

    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_agent_empty_name_422(client):
    """POST /agents/register with name='' must return 422.

    Schema: name = Field(..., min_length=1, max_length=100)
    """
    payload = _valid_agent_payload(name="")

    resp = await client.post("/api/v1/agents/register", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_short_public_key_422(client):
    """POST /agents/register with public_key='short' must return 422.

    Schema: public_key = Field(..., min_length=10) — 'short' is 5 chars.
    """
    payload = _valid_agent_payload(public_key="short")

    resp = await client.post("/api/v1/agents/register", json=payload)

    assert resp.status_code == 422


# ===========================================================================
# SECTION 3 — 404s for nonexistent resources (3 tests)
# ===========================================================================

@pytest.mark.asyncio
async def test_get_nonexistent_listing_404(client):
    """GET /listings/{fake_uuid} must return 404 when listing does not exist."""
    fake_id = str(uuid.uuid4())

    resp = await client.get(f"/api/v1/listings/{fake_id}")

    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert fake_id in body["detail"]


@pytest.mark.asyncio
async def test_get_nonexistent_agent_404(client):
    """GET /agents/{fake_uuid} must return 404 when agent does not exist."""
    fake_id = str(uuid.uuid4())

    resp = await client.get(f"/api/v1/agents/{fake_id}")

    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert fake_id in body["detail"]


@pytest.mark.asyncio
async def test_get_nonexistent_transaction_404(client, make_agent, auth_header):
    """GET /transactions/{fake_uuid} must return 404 when transaction does not exist.

    The transactions GET endpoint requires authentication, so we provide a valid agent token.
    """
    agent, token = await make_agent()
    fake_id = str(uuid.uuid4())

    resp = await client.get(
        f"/api/v1/transactions/{fake_id}", headers=auth_header(token),
    )

    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert fake_id in body["detail"]


# ===========================================================================
# SECTION 4 — 403s for wrong-owner operations (3 tests)
# ===========================================================================

@pytest.mark.asyncio
async def test_update_listing_wrong_owner_403(
    client, make_agent, make_listing, auth_header,
):
    """PUT /listings/{id} by a different agent must return 403.

    listing_service.update_listing checks listing.seller_id != seller_id
    and raises HTTP_403_FORBIDDEN.
    """
    agent_a, token_a = await make_agent(name="owner-agent")
    agent_b, token_b = await make_agent(name="intruder-agent")

    listing = await make_listing(seller_id=agent_a.id, price_usdc=2.0)

    resp = await client.put(
        f"/api/v1/listings/{listing.id}",
        headers=auth_header(token_b),
        json={"title": "Hijacked Title"},
    )

    assert resp.status_code == 403
    body = resp.json()
    assert "detail" in body
    assert "owner" in body["detail"].lower()


@pytest.mark.asyncio
async def test_delist_listing_wrong_owner_403(
    client, make_agent, make_listing, auth_header,
):
    """DELETE /listings/{id} by a different agent must return 403.

    listing_service.delist checks listing.seller_id != seller_id
    and raises HTTP_403_FORBIDDEN.
    """
    agent_a, token_a = await make_agent(name="owner-agent-del")
    agent_b, token_b = await make_agent(name="intruder-agent-del")

    listing = await make_listing(seller_id=agent_a.id, price_usdc=3.0)

    resp = await client.delete(
        f"/api/v1/listings/{listing.id}",
        headers=auth_header(token_b),
    )

    assert resp.status_code == 403
    body = resp.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_update_agent_wrong_id_403(client, make_agent, auth_header):
    """PUT /agents/{id} where current_agent != agent_id must return 403.

    registry.py checks `if current_agent != agent_id` and raises 403.
    """
    agent_a, token_a = await make_agent(name="agent-alpha")
    agent_b, token_b = await make_agent(name="agent-beta")

    # Agent B tries to update Agent A's profile
    resp = await client.put(
        f"/api/v1/agents/{agent_a.id}",
        headers=auth_header(token_b),
        json={"description": "Hijacked description"},
    )

    assert resp.status_code == 403
    body = resp.json()
    assert "detail" in body
    assert "own" in body["detail"].lower()


# ===========================================================================
# SECTION 5 — Creator errors (3 tests)
# ===========================================================================

@pytest.mark.asyncio
async def test_creator_duplicate_email_409(client, make_creator):
    """POST /creators/register with an already-registered email must return 409.

    creator_service.register_creator raises ValueError('Email already registered'),
    which the route handler converts to HTTPException(status_code=409).
    """
    # First registration via fixture (directly in DB)
    creator, _token = await make_creator(email="duplicate@test.com")

    # Second registration via the API with the same email
    resp = await client.post(
        "/api/v1/creators/register",
        json={
            "email": "duplicate@test.com",
            "password": "securepass123",
            "display_name": "Duplicate Creator",
        },
    )

    assert resp.status_code == 409
    body = resp.json()
    assert "detail" in body
    assert "already" in body["detail"].lower() or "email" in body["detail"].lower()


@pytest.mark.asyncio
async def test_creator_login_wrong_password_401(client, make_creator):
    """POST /creators/login with wrong password must return 401.

    creator_service.login_creator raises UnauthorizedError when password
    doesn't match, route handler catches Exception and returns 401.
    """
    creator, _token = await make_creator(
        email="wrongpass@test.com", password="correctpass123",
    )

    resp = await client.post(
        "/api/v1/creators/login",
        json={
            "email": "wrongpass@test.com",
            "password": "wrongpassword99",
        },
    )

    assert resp.status_code == 401
    body = resp.json()
    assert "detail" in body


@pytest.mark.asyncio
async def test_creator_login_nonexistent_email_401(client):
    """POST /creators/login with an email that doesn't exist must return 401.

    creator_service.login_creator raises UnauthorizedError when no creator
    is found for the email, route handler catches Exception and returns 401.
    """
    resp = await client.post(
        "/api/v1/creators/login",
        json={
            "email": "nobody@nowhere.com",
            "password": "doesntmatter123",
        },
    )

    assert resp.status_code == 401
    body = resp.json()
    assert "detail" in body
