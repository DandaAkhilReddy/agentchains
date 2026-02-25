"""Tests for marketplace/api/v2_creators_profile.py -- creator developer profile endpoints.

All endpoints hit the real FastAPI app via the ``client`` fixture.
Developer profiles are stored in the real in-memory SQLite database via
the dual_layer_service. No external services to mock.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# GET /api/v2/creators/me/developer-profile
# ===========================================================================


async def test_get_profile_creates_default_on_first_access(client, make_creator):
    """GET /me/developer-profile returns a default profile on first access."""
    _, token = await make_creator()

    resp = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "creator_id" in body
    assert body["bio"] == ""
    assert body["links"] == []
    assert body["specialties"] == []
    assert body["featured_flag"] is False
    assert "created_at" in body
    assert "updated_at" in body


async def test_get_profile_returns_same_data_on_repeat_call(client, make_creator):
    """GET /me/developer-profile returns consistent data across calls."""
    _, token = await make_creator()
    headers = _auth(token)

    resp1 = await client.get("/api/v2/creators/me/developer-profile", headers=headers)
    resp2 = await client.get("/api/v2/creators/me/developer-profile", headers=headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["creator_id"] == resp2.json()["creator_id"]


async def test_get_profile_rejects_missing_auth(client):
    """GET /me/developer-profile without auth returns 401."""
    resp = await client.get("/api/v2/creators/me/developer-profile")
    assert resp.status_code == 401


async def test_get_profile_rejects_invalid_token(client):
    """GET /me/developer-profile with invalid token returns 401."""
    resp = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers={"Authorization": "Bearer invalid-jwt-token"},
    )
    assert resp.status_code == 401


async def test_get_profile_rejects_agent_token(client, make_agent):
    """GET /me/developer-profile rejects agent tokens (creator-only)."""
    _, agent_token = await make_agent()
    resp = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers=_auth(agent_token),
    )
    assert resp.status_code == 401


# ===========================================================================
# PUT /api/v2/creators/me/developer-profile
# ===========================================================================


async def test_update_profile_happy_path(client, make_creator):
    """PUT /me/developer-profile updates all fields."""
    _, token = await make_creator()
    headers = _auth(token)

    payload = {
        "bio": "Expert in AI agent development",
        "links": ["https://github.com/testdev", "https://linkedin.com/in/testdev"],
        "specialties": ["python", "langchain", "fastapi"],
        "featured_flag": True,
    }
    resp = await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bio"] == "Expert in AI agent development"
    assert body["links"] == ["https://github.com/testdev", "https://linkedin.com/in/testdev"]
    assert body["specialties"] == ["python", "langchain", "fastapi"]
    assert body["featured_flag"] is True


async def test_update_profile_persists_across_reads(client, make_creator):
    """PUT /me/developer-profile persists data visible in subsequent GET."""
    _, token = await make_creator()
    headers = _auth(token)

    update_payload = {
        "bio": "Updated bio",
        "links": ["https://example.com"],
        "specialties": ["rust"],
        "featured_flag": False,
    }
    await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=headers,
        json=update_payload,
    )

    resp = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bio"] == "Updated bio"
    assert body["links"] == ["https://example.com"]
    assert body["specialties"] == ["rust"]


async def test_update_profile_with_empty_fields(client, make_creator):
    """PUT /me/developer-profile accepts empty fields."""
    _, token = await make_creator()
    headers = _auth(token)

    payload = {
        "bio": "",
        "links": [],
        "specialties": [],
        "featured_flag": False,
    }
    resp = await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bio"] == ""
    assert body["links"] == []
    assert body["specialties"] == []


async def test_update_profile_overwrite_previous(client, make_creator):
    """Second PUT fully replaces the first."""
    _, token = await make_creator()
    headers = _auth(token)

    first_payload = {
        "bio": "First bio",
        "links": ["https://first.com"],
        "specialties": ["alpha"],
        "featured_flag": True,
    }
    await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=headers,
        json=first_payload,
    )

    second_payload = {
        "bio": "Second bio",
        "links": [],
        "specialties": ["beta", "gamma"],
        "featured_flag": False,
    }
    resp = await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=headers,
        json=second_payload,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bio"] == "Second bio"
    assert body["links"] == []
    assert body["specialties"] == ["beta", "gamma"]
    assert body["featured_flag"] is False


async def test_update_profile_rejects_missing_auth(client):
    """PUT /me/developer-profile without auth returns 401."""
    resp = await client.put(
        "/api/v2/creators/me/developer-profile",
        json={"bio": "test", "links": [], "specialties": [], "featured_flag": False},
    )
    assert resp.status_code == 401


async def test_update_profile_rejects_agent_token(client, make_agent):
    """PUT /me/developer-profile rejects agent tokens (creator-only)."""
    _, agent_token = await make_agent()
    resp = await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=_auth(agent_token),
        json={"bio": "test", "links": [], "specialties": [], "featured_flag": False},
    )
    assert resp.status_code == 401


async def test_update_profile_validates_bio_max_length(client, make_creator):
    """PUT /me/developer-profile rejects bio exceeding max_length=5000."""
    _, token = await make_creator()
    headers = _auth(token)

    payload = {
        "bio": "x" * 5001,
        "links": [],
        "specialties": [],
        "featured_flag": False,
    }
    resp = await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 422


async def test_update_profile_isolation_between_creators(client, make_creator):
    """Two creators should have independent profiles."""
    _, token_a = await make_creator()
    _, token_b = await make_creator()

    await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=_auth(token_a),
        json={"bio": "Creator A", "links": [], "specialties": [], "featured_flag": True},
    )
    await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=_auth(token_b),
        json={"bio": "Creator B", "links": [], "specialties": [], "featured_flag": False},
    )

    resp_a = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers=_auth(token_a),
    )
    resp_b = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers=_auth(token_b),
    )
    assert resp_a.json()["bio"] == "Creator A"
    assert resp_a.json()["featured_flag"] is True
    assert resp_b.json()["bio"] == "Creator B"
    assert resp_b.json()["featured_flag"] is False
