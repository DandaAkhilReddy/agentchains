"""Tests for health and readiness endpoints covering production mode and error paths."""

from unittest.mock import AsyncMock, patch

from marketplace.config import settings


async def test_health_dev_mode_full_response(client):
    """GET /api/v1/health in dev mode returns full response with counts and cache stats."""
    original = settings.environment
    try:
        object.__setattr__(settings, "environment", "development")
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "agents_count" in body
        assert "listings_count" in body
        assert "transactions_count" in body
        assert "cache_stats" in body
        assert "version" in body
    finally:
        object.__setattr__(settings, "environment", original)


async def test_health_production_mode_minimal(client):
    """GET /api/v1/health in production mode returns minimal response."""
    original = settings.environment
    try:
        object.__setattr__(settings, "environment", "production")
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["version"]
        assert "agents_count" not in body
        assert "cache_stats" not in body
    finally:
        object.__setattr__(settings, "environment", original)


async def test_health_production_mode_prod_alias(client):
    """GET /api/v1/health works with 'prod' alias."""
    original = settings.environment
    try:
        object.__setattr__(settings, "environment", "prod")
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "agents_count" not in body
    finally:
        object.__setattr__(settings, "environment", original)


async def test_health_readiness_probe_success(client):
    """GET /api/v1/health/ready returns ready when DB is connected."""
    resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["database"] == "connected"


async def test_health_check_function_dev_mode(db):
    """Call health_check function directly in dev mode to ensure coverage."""
    from marketplace.api.health import health_check
    original = settings.environment
    try:
        object.__setattr__(settings, "environment", "development")
        result = await health_check(db)
        assert result.status == "healthy"
        assert result.version
        assert result.agents_count >= 0
        assert result.listings_count >= 0
        assert result.transactions_count >= 0
    finally:
        object.__setattr__(settings, "environment", original)


async def test_health_check_function_prod_mode(db):
    """Call health_check function directly in production mode."""
    from marketplace.api.health import health_check
    original = settings.environment
    try:
        object.__setattr__(settings, "environment", "production")
        result = await health_check(db)
        assert isinstance(result, dict)
        assert result["status"] == "healthy"
        assert result["version"]
        assert "agents_count" not in result
    finally:
        object.__setattr__(settings, "environment", original)


async def test_readiness_check_function_success(db):
    """Call readiness_check function directly."""
    from marketplace.api.health import readiness_check
    result = await readiness_check(db)
    assert isinstance(result, dict)
    assert result["status"] == "ready"
    assert result["database"] == "connected"


async def test_health_check_function_prod_db_failure(db):
    """Production mode health check returns 503 when DB fails."""
    from unittest.mock import AsyncMock
    from marketplace.api.health import health_check
    original = settings.environment
    try:
        object.__setattr__(settings, "environment", "production")
        # Create a mock session that raises on execute
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB connection lost"))
        result = await health_check(mock_db)
        # Should return JSONResponse with 503
        assert result.status_code == 503
        import json
        body = json.loads(result.body.decode())
        assert body["status"] == "unhealthy"
    finally:
        object.__setattr__(settings, "environment", original)


async def test_readiness_check_function_db_failure(db):
    """Readiness check returns 503 when DB is unreachable."""
    from unittest.mock import AsyncMock
    from marketplace.api.health import readiness_check
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Connection refused"))
    result = await readiness_check(mock_db)
    assert result.status_code == 503
    import json
    body = json.loads(result.body.decode())
    assert body["status"] == "not_ready"
    assert body["database"] == "unavailable"
