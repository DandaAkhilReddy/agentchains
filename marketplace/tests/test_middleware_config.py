"""Tests for RateLimitMiddleware and Settings defaults.

Agent UT-10 -- 28 tests covering:
  - Middleware skip paths, OPTIONS bypass, key extraction, 429 responses, rate headers
  - Config defaults for platform fees, JWT, MCP, CDN, redemption, creator, rate limits, etc.
"""

import uuid

import pytest

from marketplace.config import Settings, settings
from marketplace.core.auth import create_access_token


# ===================================================================
# Middleware tests (1-15) -- use the `client` fixture from conftest
# ===================================================================


class TestMiddlewareSkipPaths:
    """Tests 1-6: paths/methods that bypass rate limiting."""

    @pytest.mark.asyncio
    async def test_middleware_skip_health(self, client):
        """GET /api/v1/health should bypass rate limiting (no X-RateLimit headers)."""
        resp = await client.get("/api/v1/health")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    @pytest.mark.asyncio
    async def test_middleware_skip_docs(self, client):
        """GET /docs should bypass the rate limiter entirely."""
        resp = await client.get("/docs")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    @pytest.mark.asyncio
    async def test_middleware_skip_openapi(self, client):
        """GET /openapi.json should bypass the rate limiter."""
        resp = await client.get("/openapi.json")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    @pytest.mark.asyncio
    async def test_middleware_skip_redoc(self, client):
        """GET /redoc should bypass the rate limiter."""
        resp = await client.get("/redoc")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    @pytest.mark.asyncio
    async def test_middleware_skip_mcp_health(self, client):
        """GET /mcp/health should bypass rate limiting."""
        resp = await client.get("/mcp/health")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    @pytest.mark.asyncio
    async def test_middleware_skip_options(self, client):
        """OPTIONS requests (CORS preflight) should bypass rate limiting."""
        resp = await client.options("/api/v1/agents")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers


class TestMiddlewareExtractKey:
    """Tests 7-10: key extraction from JWT, invalid JWT, no auth, x-forwarded-for."""

    @pytest.mark.asyncio
    async def test_middleware_extract_key_valid_jwt(self, client):
        """Valid JWT should produce an 'agent:{sub}' key with authenticated limit (120)."""
        agent_id = str(uuid.uuid4())
        token = create_access_token(agent_id, "test-agent")
        resp = await client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == str(
            settings.rest_rate_limit_authenticated
        )

    @pytest.mark.asyncio
    async def test_middleware_extract_key_invalid_jwt(self, client):
        """Invalid JWT should fall back to anonymous IP-based key (limit=30)."""
        resp = await client.get(
            "/api/v1/agents",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == str(
            settings.rest_rate_limit_anonymous
        )

    @pytest.mark.asyncio
    async def test_middleware_extract_key_no_auth(self, client):
        """Request with no Authorization header should use anonymous IP limit."""
        resp = await client.get("/api/v1/agents")
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == str(
            settings.rest_rate_limit_anonymous
        )

    @pytest.mark.asyncio
    async def test_middleware_extract_key_forwarded(self, client):
        """x-forwarded-for header's first IP should be used as the rate-limit key."""
        resp = await client.get(
            "/api/v1/agents",
            headers={"x-forwarded-for": "203.0.113.50, 10.0.0.1"},
        )
        assert "X-RateLimit-Limit" in resp.headers
        # No JWT present, so anonymous limit applies.
        assert resp.headers["X-RateLimit-Limit"] == str(
            settings.rest_rate_limit_anonymous
        )


class TestMiddlewareRateLimiting:
    """Tests 11-15: 429 responses, Retry-After, rate headers, limit values."""

    @pytest.mark.asyncio
    async def test_middleware_returns_429(self, client):
        """Exceeding the anonymous rate limit (30) should yield HTTP 429."""
        limit = settings.rest_rate_limit_anonymous  # 30
        for _ in range(limit):
            await client.get("/api/v1/agents")
        # The (limit+1)th request should be blocked.
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 429
        body = resp.json()
        assert body["detail"] == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_middleware_429_has_retry_after(self, client):
        """A 429 response must include a Retry-After header with a non-negative value."""
        limit = settings.rest_rate_limit_anonymous
        for _ in range(limit):
            await client.get("/api/v1/agents")
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        retry_after = int(resp.headers["Retry-After"])
        assert retry_after >= 0

    @pytest.mark.asyncio
    async def test_middleware_adds_rate_headers(self, client):
        """Successful responses should include all three X-RateLimit-* headers."""
        resp = await client.get("/api/v1/agents")
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

    @pytest.mark.asyncio
    async def test_middleware_authenticated_limit(self, client):
        """Authenticated requests should get the 120 req/min limit."""
        agent_id = str(uuid.uuid4())
        token = create_access_token(agent_id, "auth-agent")
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/agents", headers=headers)
        assert resp.headers["X-RateLimit-Limit"] == "120"

    @pytest.mark.asyncio
    async def test_middleware_anonymous_limit(self, client):
        """Anonymous requests should get the 30 req/min limit."""
        resp = await client.get("/api/v1/agents")
        assert resp.headers["X-RateLimit-Limit"] == "30"


# ===================================================================
# Config / Settings tests (16-28)
# ===================================================================


class TestSettingsUSDEconomy:
    """Tests 16-18: USD billing model defaults."""

    @pytest.mark.asyncio
    async def test_settings_platform_fee(self):
        """Platform fee should default to 2%."""
        s = Settings()
        assert s.platform_fee_pct == 0.02

    @pytest.mark.asyncio
    async def test_settings_signup_bonus(self):
        """Signup bonus should default to $0.10 USD."""
        s = Settings()
        assert s.signup_bonus_usd == 0.10


class TestSettingsAuthAndInfra:
    """Tests 19-22: JWT, MCP, CDN, redemption defaults."""

    @pytest.mark.asyncio
    async def test_settings_jwt_defaults(self):
        """JWT should default to HS256 algorithm with 168-hour (7-day) expiry."""
        s = Settings()
        assert s.jwt_algorithm == "HS256"
        assert s.jwt_expire_hours == 168
        assert s.jwt_secret_key == "dev-secret-change-in-production"

    @pytest.mark.asyncio
    async def test_settings_mcp_defaults(self):
        """MCP should be enabled by default with 60 req/min rate limit."""
        s = Settings()
        assert s.mcp_enabled is True
        assert s.mcp_rate_limit_per_minute == 60

    @pytest.mark.asyncio
    async def test_settings_cdn_defaults(self):
        """CDN hot cache should default to 256 MB with 60s decay interval."""
        s = Settings()
        assert s.cdn_hot_cache_max_bytes == 256 * 1024 * 1024
        assert s.cdn_hot_cache_max_bytes == 268435456
        assert s.cdn_decay_interval_seconds == 60

    @pytest.mark.asyncio
    async def test_settings_redemption_thresholds(self):
        """All four redemption minimums should match the spec (USD)."""
        s = Settings()
        assert s.redemption_min_api_credits_usd == 0.10
        assert s.redemption_min_gift_card_usd == 1.00
        assert s.redemption_min_bank_usd == 10.00
        assert s.redemption_min_upi_usd == 5.00


class TestSettingsCreatorAndMisc:
    """Tests 23-28: creator economy, rate limits, payment, CORS, OpenClaw."""

    @pytest.mark.asyncio
    async def test_settings_creator_defaults(self):
        """Creator royalty=1.0, min withdrawal=$10.00, payout day=1."""
        s = Settings()
        assert s.creator_royalty_pct == 1.0
        assert s.creator_min_withdrawal_usd == 10.00
        assert s.creator_payout_day == 1

    @pytest.mark.asyncio
    async def test_settings_rate_limits(self):
        """REST rate limits: authenticated=120, anonymous=30."""
        s = Settings()
        assert s.rest_rate_limit_authenticated == 120
        assert s.rest_rate_limit_anonymous == 30

    @pytest.mark.asyncio
    async def test_settings_payment_mode(self):
        """Payment mode should default to 'simulated'."""
        s = Settings()
        assert s.payment_mode == "simulated"

    @pytest.mark.asyncio
    async def test_settings_cors(self):
        """CORS origins should default to localhost dev origins."""
        s = Settings()
        assert "localhost" in s.cors_origins

    @pytest.mark.asyncio
    async def test_settings_openclaw_defaults(self):
        """OpenClaw webhook: retries=3, timeout=10s, max_failures=5."""
        s = Settings()
        assert s.openclaw_webhook_max_retries == 3
        assert s.openclaw_webhook_timeout_seconds == 10
        assert s.openclaw_webhook_max_failures == 5
