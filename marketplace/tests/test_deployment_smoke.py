"""Smoke tests for live marketplace deployments.

These tests only run when the MARKETPLACE_URL environment variable is set,
pointing to a live deployment. They use httpx sync client to validate
health, security headers, CORS policy, and documentation endpoints.
"""

import os

import httpx
import pytest

MARKETPLACE_URL = os.environ.get("MARKETPLACE_URL", "")
skip_no_url = pytest.mark.skipif(
    not MARKETPLACE_URL, reason="MARKETPLACE_URL not set"
)


@pytest.mark.smoke
@skip_no_url
def test_health_endpoint_returns_200():
    """Health endpoint should return HTTP 200."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


@pytest.mark.smoke
@skip_no_url
def test_health_response_has_status_healthy():
    """Health response JSON should contain status 'healthy'."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.smoke
@skip_no_url
def test_health_response_includes_version():
    """Health response should include a version field."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0


@pytest.mark.smoke
@skip_no_url
def test_health_response_includes_metrics():
    """Health response should include agents_count and listings_count metrics."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert "agents_count" in data, "Missing agents_count in health response"
        assert "listings_count" in data, "Missing listings_count in health response"
        assert isinstance(data["agents_count"], int)
        assert isinstance(data["listings_count"], int)


@pytest.mark.smoke
@skip_no_url
def test_mcp_health_returns_200():
    """MCP health endpoint should return HTTP 200."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/mcp/health")
        assert resp.status_code == 200


@pytest.mark.smoke
@skip_no_url
def test_security_header_x_content_type_options():
    """Response should include X-Content-Type-Options: nosniff header."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/api/v1/health")
        header_value = resp.headers.get("x-content-type-options")
        assert header_value is not None, "Missing X-Content-Type-Options header"
        assert header_value == "nosniff"


@pytest.mark.smoke
@skip_no_url
def test_security_header_x_frame_options():
    """Response should include X-Frame-Options header."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/api/v1/health")
        header_value = resp.headers.get("x-frame-options")
        assert header_value is not None, "Missing X-Frame-Options header"


@pytest.mark.smoke
@skip_no_url
def test_cors_rejects_unauthorized_origin():
    """CORS should not allow access from unauthorized origins."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get(
            "/api/v1/health",
            headers={"Origin": "https://evil.com"},
        )
        allow_origin = resp.headers.get("access-control-allow-origin")
        assert allow_origin is None or allow_origin != "https://evil.com", (
            "CORS should not allow https://evil.com"
        )


@pytest.mark.smoke
@skip_no_url
def test_openapi_docs_accessible():
    """OpenAPI docs page at /docs should return HTTP 200."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/docs")
        assert resp.status_code == 200


@pytest.mark.smoke
@skip_no_url
def test_openapi_json_accessible():
    """OpenAPI JSON at /openapi.json should return 200 with valid JSON."""
    with httpx.Client(base_url=MARKETPLACE_URL) as client:
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "openapi" in data, "Missing 'openapi' key in OpenAPI JSON"
