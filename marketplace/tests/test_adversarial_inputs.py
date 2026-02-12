"""Adversarial and malicious input tests across the marketplace API.

15 tests covering:
- Unicode / emoji / CJK / RTL / special characters
- Null bytes, SQL injection, XSS payloads
- Extremely long strings, negative/zero prices
- Deeply nested JSON, empty strings, large content
- CRLF injection in headers

Invariant: the app must NEVER return a 500.  It should either succeed
gracefully or return a proper validation error (400/401/422).
"""

import uuid

import pytest

from marketplace.core.auth import create_access_token
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_agent_via_api(client, *, name: str = None, agent_type: str = "both"):
    """Register an agent via the API and return the full JSON response."""
    payload = {
        "name": name or f"adv-agent-{uuid.uuid4().hex[:8]}",
        "agent_type": agent_type,
        "public_key": "ssh-rsa AAAA_adversarial_test_key_placeholder",
        "capabilities": ["web_search"],
    }
    return await client.post("/api/v1/agents/register", json=payload)


async def _make_auth_agent(client):
    """Register an agent and return (agent_json, auth_headers)."""
    resp = await _register_agent_via_api(client)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data, _auth(data["jwt_token"])


# ---------------------------------------------------------------------------
# 1. Unicode emoji in agent name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unicode_emoji_in_agent_name(client):
    """Emoji characters in agent name should succeed or return 422, never 500."""
    resp = await _register_agent_via_api(client, name="rocket-agent-\U0001f680\U0001f525")
    assert resp.status_code != 500
    # Should either register successfully or reject with validation error
    assert resp.status_code in (201, 400, 422)


# ---------------------------------------------------------------------------
# 2. CJK characters in listing title
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cjk_characters_in_listing_title(client):
    """Chinese/Japanese/Korean characters in listing title should not crash."""
    agent, headers = await _make_auth_agent(client)

    resp = await client.post(
        "/api/v1/listings",
        headers=headers,
        json={
            "title": "\u4e2d\u6587\u6d4b\u8bd5 \u65e5\u672c\u8a9e \ud55c\uad6d\uc5b4",
            "description": "\u8fd9\u662f\u4e00\u4e2a\u6d4b\u8bd5\u5217\u8868",
            "category": "web_search",
            "content": "CJK content payload",
            "price_usdc": 1.0,
        },
    )
    assert resp.status_code != 500
    assert resp.status_code in (201, 400, 422)


# ---------------------------------------------------------------------------
# 3. RTL text in description
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rtl_text_in_description(client):
    """Arabic and Hebrew right-to-left text should not crash the API."""
    agent, headers = await _make_auth_agent(client)

    resp = await client.post(
        "/api/v1/listings",
        headers=headers,
        json={
            "title": "RTL test listing",
            "description": "\u0645\u0631\u062d\u0628\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645 \u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd",
            "category": "web_search",
            "content": "RTL description test content",
            "price_usdc": 2.0,
        },
    )
    assert resp.status_code != 500
    assert resp.status_code in (201, 400, 422)


# ---------------------------------------------------------------------------
# 4. Null bytes in search query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_null_bytes_in_search_query(client):
    """Null bytes embedded in the search query must not cause a 500."""
    resp = await client.get("/api/v1/discover", params={"q": "test\x00evil"})
    assert resp.status_code != 500
    # Should return results (possibly empty) or a 400/422
    assert resp.status_code in (200, 400, 422)


# ---------------------------------------------------------------------------
# 5. SQL injection in search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sql_injection_in_search(client):
    """Classic SQL injection payload in discover query must be handled safely."""
    resp = await client.get("/api/v1/discover", params={"q": "'; DROP TABLE agents;--"})
    assert resp.status_code != 500
    assert resp.status_code in (200, 400, 422)

    # Verify the app still works after the injection attempt
    health = await client.get("/api/v1/health")
    assert health.status_code == 200


# ---------------------------------------------------------------------------
# 6. HTML/script XSS in listing title
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_html_script_in_title(client):
    """XSS script tags in a listing title must not cause a 500."""
    agent, headers = await _make_auth_agent(client)

    resp = await client.post(
        "/api/v1/listings",
        headers=headers,
        json={
            "title": "<script>alert('xss')</script>",
            "description": '<img src=x onerror="alert(1)">',
            "category": "web_search",
            "content": "xss test content",
            "price_usdc": 1.0,
        },
    )
    assert resp.status_code != 500
    # The app may store it verbatim (output encoding is the frontend's job)
    # or reject it — both are acceptable
    assert resp.status_code in (201, 400, 422)


# ---------------------------------------------------------------------------
# 7. Extremely long agent name (10 000 chars)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extremely_long_agent_name(client):
    """A 10 000-character name should be rejected by max_length=100 validator."""
    long_name = "A" * 10_000
    resp = await _register_agent_via_api(client, name=long_name)
    assert resp.status_code != 500
    assert resp.status_code == 422  # Pydantic max_length=100 enforcement


# ---------------------------------------------------------------------------
# 8. Extremely long email (1 000 chars)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extremely_long_email(client):
    """A 1 000-character email should be rejected by max_length=255 validator."""
    long_email = "a" * 990 + "@test.com"  # 999 chars total
    resp = await client.post(
        "/api/v1/creators/register",
        json={
            "email": long_email,
            "password": "securepass123",
            "display_name": "Long Email Creator",
        },
    )
    assert resp.status_code != 500
    assert resp.status_code == 422  # Exceeds max_length=255


# ---------------------------------------------------------------------------
# 9. Negative price in listing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_negative_price_in_listing(client):
    """price_usdc=-1 should be rejected by gt=0 validator."""
    agent, headers = await _make_auth_agent(client)

    resp = await client.post(
        "/api/v1/listings",
        headers=headers,
        json={
            "title": "Negative price listing",
            "category": "web_search",
            "content": "test content",
            "price_usdc": -1,
        },
    )
    assert resp.status_code != 500
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 10. Zero price in listing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_price_in_listing(client):
    """price_usdc=0 should be rejected by gt=0 validator (strict greater-than)."""
    agent, headers = await _make_auth_agent(client)

    resp = await client.post(
        "/api/v1/listings",
        headers=headers,
        json={
            "title": "Zero price listing",
            "category": "web_search",
            "content": "test content",
            "price_usdc": 0,
        },
    )
    assert resp.status_code != 500
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 11. Special characters in search query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_special_chars_in_search(client):
    """Special punctuation in the discover query must not crash the API."""
    resp = await client.get("/api/v1/discover", params={"q": "!@#$%^&*()"})
    assert resp.status_code != 500
    assert resp.status_code in (200, 400, 422)


# ---------------------------------------------------------------------------
# 12. Deeply nested JSON payload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deeply_nested_json_payload(client):
    """Deeply nested JSON in the request body should not cause a stack overflow."""
    agent, headers = await _make_auth_agent(client)

    # Build a 50-level deep nested dict
    nested = {"key": "leaf"}
    for _ in range(50):
        nested = {"nested": nested}

    resp = await client.post(
        "/api/v1/listings",
        headers=headers,
        json={
            "title": "Deep nesting test",
            "category": "web_search",
            "content": "deep content",
            "price_usdc": 1.0,
            "metadata": nested,
        },
    )
    assert resp.status_code != 500
    # May succeed (metadata is an arbitrary dict) or be rejected
    assert resp.status_code in (201, 400, 413, 422)


# ---------------------------------------------------------------------------
# 13. Empty string fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_string_fields(client):
    """All-empty-string fields should trigger validation errors, not crashes."""
    agent, headers = await _make_auth_agent(client)

    # Agent registration with empty name (min_length=1)
    # NOTE: we send the payload directly because the helper uses `name or ...`
    # which would replace "" with a generated name.
    resp_agent = await client.post(
        "/api/v1/agents/register",
        json={
            "name": "",
            "agent_type": "both",
            "public_key": "ssh-rsa AAAA_adversarial_test_key_placeholder",
            "capabilities": [],
        },
    )
    assert resp_agent.status_code != 500
    assert resp_agent.status_code == 422

    # Listing with empty title (min_length=1)
    resp_listing = await client.post(
        "/api/v1/listings",
        headers=headers,
        json={
            "title": "",
            "category": "",
            "content": "",
            "price_usdc": 1.0,
        },
    )
    assert resp_listing.status_code != 500
    assert resp_listing.status_code == 422

    # Creator registration with empty password (min_length=8)
    resp_creator = await client.post(
        "/api/v1/creators/register",
        json={
            "email": "",
            "password": "",
            "display_name": "",
        },
    )
    assert resp_creator.status_code != 500
    assert resp_creator.status_code == 422


# ---------------------------------------------------------------------------
# 14. Very large content (100 KB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_very_large_content(client):
    """100 KB of content in a listing should not crash the API."""
    agent, headers = await _make_auth_agent(client)

    large_content = "X" * (100 * 1024)  # 100 KB

    resp = await client.post(
        "/api/v1/listings",
        headers=headers,
        json={
            "title": "Large content listing",
            "category": "web_search",
            "content": large_content,
            "price_usdc": 5.0,
        },
    )
    assert resp.status_code != 500
    # Should either succeed or reject with a size limit error
    assert resp.status_code in (201, 400, 413, 422)


# ---------------------------------------------------------------------------
# 15. CRLF injection in Authorization header
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crlf_injection_in_header(client):
    """CRLF characters in the Authorization header must not cause a 500."""
    # Attempt CRLF injection to add extra headers
    malicious_token = "Bearer fake_token\r\nX-Injected: evil"

    resp = await client.get(
        "/api/v1/listings",
        headers={"Authorization": malicious_token},
    )
    assert resp.status_code != 500
    # Should be 200 (listings list is public) or 401 (bad auth parse)
    assert resp.status_code in (200, 400, 401, 422)
