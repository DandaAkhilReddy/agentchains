"""API contract validation tests for the marketplace.

These tests verify that API responses conform to their expected contracts,
including required fields, data types, and registered API version prefixes.
Uses the async client fixture from conftest.py (httpx AsyncClient with
ASGI transport).
"""

import pytest

from marketplace.api.health import _VERSION as HEALTH_VERSION


# ---------------------------------------------------------------------------
# Health Contract Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_has_all_required_fields(client):
    """Health response must contain all required contract fields."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    required_fields = {"status", "version", "agents_count", "listings_count", "cache_stats"}
    missing = required_fields - set(data.keys())
    assert not missing, f"Health response missing fields: {missing}"


@pytest.mark.asyncio
async def test_health_status_is_healthy_string(client):
    """Health status field must be the string 'healthy'."""
    resp = await client.get("/api/v1/health")
    data = resp.json()
    assert data["status"] == "healthy"
    assert isinstance(data["status"], str)


@pytest.mark.asyncio
async def test_health_version_matches_app_version(client):
    """Health version field must match _VERSION from marketplace.api.health."""
    resp = await client.get("/api/v1/health")
    data = resp.json()
    assert data["version"] == HEALTH_VERSION, (
        f"Expected version '{HEALTH_VERSION}', got '{data['version']}'"
    )


@pytest.mark.asyncio
async def test_health_accessible_without_authentication(client):
    """Health endpoint should be accessible without any auth headers."""
    resp = await client.get(
        "/api/v1/health",
        headers={},  # explicitly no auth
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_cache_stats_sub_keys(client):
    """cache_stats must contain listings, content, and agents sub-keys."""
    resp = await client.get("/api/v1/health")
    data = resp.json()
    cache_stats = data["cache_stats"]
    for key in ("listings", "content", "agents"):
        assert key in cache_stats, f"cache_stats missing '{key}' sub-key"


# ---------------------------------------------------------------------------
# API Structure Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v1_health_returns_200(client):
    """/api/v1/health must return HTTP 200."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_v2_prefix_registered(client):
    """/api/v2 prefix must have at least one route registered."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    v2_paths = [p for p in paths if p.startswith("/api/v2")]
    assert len(v2_paths) > 0, "No /api/v2 routes registered"


@pytest.mark.asyncio
async def test_v3_prefix_registered(client):
    """/api/v3 prefix must have at least one route registered."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    v3_paths = [p for p in paths if p.startswith("/api/v3")]
    assert len(v3_paths) > 0, "No /api/v3 routes registered"


@pytest.mark.asyncio
async def test_v4_prefix_registered(client):
    """/api/v4 prefix must have at least one route registered."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    v4_paths = [p for p in paths if p.startswith("/api/v4")]
    assert len(v4_paths) > 0, "No /api/v4 routes registered"


@pytest.mark.asyncio
async def test_openapi_json_contract(client):
    """/openapi.json must return valid JSON with 'openapi' and 'paths' keys."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "openapi" in data, "Missing 'openapi' key in OpenAPI JSON"
    assert "paths" in data, "Missing 'paths' key in OpenAPI JSON"
