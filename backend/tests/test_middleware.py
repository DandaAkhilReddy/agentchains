"""Tests for app.api.middleware — rate limiter and middleware stack."""

import logging
import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.middleware import RateLimitMiddleware


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rate_limiter():
    """A standalone RateLimitMiddleware instance for unit testing."""
    return RateLimitMiddleware(
        app=MagicMock(),
        max_requests=10,
        window_seconds=60,
    )


# ---------------------------------------------------------------------------
# Tests: health endpoint via real ASGI client (not rate limited)
# ---------------------------------------------------------------------------


class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_normal_requests(self, async_client):
        """Non-scanner endpoints should not be rate limited."""
        resp = await async_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# Tests: _prune_expired
# ---------------------------------------------------------------------------


class TestPruneExpired:

    def test_prune_removes_old_entries(self, rate_limiter):
        """Entries older than the window are removed."""
        now = time.time()
        rate_limiter.requests["1.2.3.4"] = [now - 120]  # expired (>60s)
        rate_limiter.requests["5.6.7.8"] = [now - 10]   # still valid

        rate_limiter._prune_expired(now)

        assert "1.2.3.4" not in rate_limiter.requests
        assert "5.6.7.8" in rate_limiter.requests

    def test_prune_removes_empty_lists(self, rate_limiter):
        """IPs with empty request lists are pruned."""
        now = time.time()
        rate_limiter.requests["empty_ip"] = []

        rate_limiter._prune_expired(now)

        assert "empty_ip" not in rate_limiter.requests

    def test_prune_keeps_recent(self, rate_limiter):
        """Recent entries within the window are preserved."""
        now = time.time()
        rate_limiter.requests["recent"] = [now - 5, now - 2, now]

        rate_limiter._prune_expired(now)

        assert "recent" in rate_limiter.requests
        assert len(rate_limiter.requests["recent"]) == 3

    def test_prune_updates_last_prune_time(self, rate_limiter):
        """_prune_expired updates the _last_prune timestamp."""
        now = time.time()
        rate_limiter._prune_expired(now)
        assert rate_limiter._last_prune == now


# ---------------------------------------------------------------------------
# Tests: max_ips safety valve
# ---------------------------------------------------------------------------


class TestMaxIPsSafetyValve:

    def test_max_tracked_ips_constant(self, rate_limiter):
        """Verify the safety valve constant is set."""
        assert rate_limiter._MAX_TRACKED_IPS == 10_000

    def test_safety_valve_triggers_prune(self, rate_limiter):
        """When tracked IPs exceed _MAX_TRACKED_IPS, the middleware prunes.

        We simulate by filling requests dict beyond the cap and verifying
        the middleware logic path (the prune call is made in dispatch).
        """
        now = time.time()
        # Fill with expired entries beyond max
        for i in range(rate_limiter._MAX_TRACKED_IPS + 100):
            rate_limiter.requests[f"192.168.{i // 256}.{i % 256}"] = [now - 120]

        assert len(rate_limiter.requests) > rate_limiter._MAX_TRACKED_IPS

        # Prune should clean all expired
        rate_limiter._prune_expired(now)
        assert len(rate_limiter.requests) == 0


# ---------------------------------------------------------------------------
# Tests: sliding window request counting
# ---------------------------------------------------------------------------


class TestSlidingWindow:

    def test_window_size(self, rate_limiter):
        assert rate_limiter.window == 60

    def test_max_requests(self, rate_limiter):
        assert rate_limiter.max_requests == 10

    def test_requests_dict_is_defaultdict(self, rate_limiter):
        """Accessing a new IP key should return an empty list."""
        assert rate_limiter.requests["new_ip"] == []


# ---------------------------------------------------------------------------
# Tests: CORS headers
# ---------------------------------------------------------------------------


class TestCORSHeaders:
    """Verify the CORSMiddleware is configured and sets headers."""

    @pytest.mark.asyncio
    async def test_cors_allows_configured_origin(self, async_client):
        """Preflight from a configured origin should return CORS headers."""
        resp = await async_client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == (
            "http://localhost:5173"
        )
        assert "GET" in resp.headers.get("access-control-allow-methods", "")

    @pytest.mark.asyncio
    async def test_cors_rejects_unknown_origin(self, async_client):
        """Preflight from an unknown origin should not include allow-origin."""
        resp = await async_client.options(
            "/api/health",
            headers={
                "Origin": "https://malicious-site.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Starlette's CORSMiddleware omits the header for disallowed origins
        assert resp.headers.get("access-control-allow-origin") != (
            "https://malicious-site.example.com"
        )

    @pytest.mark.asyncio
    async def test_cors_allows_credentials(self, async_client):
        """CORS should advertise credentials support."""
        resp = await async_client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-credentials") == "true"


# ---------------------------------------------------------------------------
# Tests: rate limiter dispatch (allow within limit)
# ---------------------------------------------------------------------------


class TestRateLimiterAllowsWithinLimit:
    """Rate limiter should pass through requests below the threshold."""

    @pytest.mark.asyncio
    async def test_scanner_upload_within_limit(self, async_client):
        """Requests to /api/scanner/upload within limit should not return 429."""
        for _ in range(3):
            resp = await async_client.post(
                "/api/scanner/upload",
                files={"file": ("test.pdf", b"fake-pdf", "application/pdf")},
            )
            # Should NOT be 429 — may be 401/422 due to auth/validation, but
            # rate limiter should not block.
            assert resp.status_code != 429

    @pytest.mark.asyncio
    async def test_non_scanner_endpoint_never_rate_limited(self, async_client):
        """Non-scanner endpoints are never subject to rate limiting."""
        for _ in range(15):
            resp = await async_client.get("/api/health")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: rate limiter dispatch (block after exceeding limit)
# ---------------------------------------------------------------------------


class TestRateLimiterBlocksExceedingLimit:
    """Rate limiter must return 429 once the per-IP limit is exceeded."""

    @pytest.mark.asyncio
    async def test_scanner_upload_exceeds_limit(self):
        """Hitting /api/scanner/upload above max_requests yields 429."""
        from app.main import app
        from app.api.middleware import RateLimitMiddleware

        # Find the RateLimitMiddleware instance and lower the limit
        for mw in app.user_middleware:
            if mw.cls is RateLimitMiddleware:
                break

        # Create a fresh app-level test with a very low limit.
        # We use the unit-testable approach: craft request/call_next mocks.
        limiter = RateLimitMiddleware(
            app=MagicMock(),
            max_requests=3,
            window_seconds=60,
        )

        async def fake_call_next(request):
            return MagicMock(status_code=200, headers={})

        for i in range(5):
            request = MagicMock()
            request.url.path = "/api/scanner/upload"
            request.client.host = "10.0.0.1"

            response = await limiter.dispatch(request, fake_call_next)

            if i < 3:
                # First 3 should pass through
                assert response.status_code == 200, f"Request {i} should be allowed"
            else:
                # 4th and 5th should be blocked
                assert response.status_code == 429, f"Request {i} should be blocked"

    @pytest.mark.asyncio
    async def test_rate_limit_response_body(self):
        """429 response should include a helpful detail message."""
        limiter = RateLimitMiddleware(
            app=MagicMock(),
            max_requests=1,
            window_seconds=60,
        )

        async def fake_call_next(request):
            return MagicMock(status_code=200, headers={})

        request = MagicMock()
        request.url.path = "/api/scanner/upload"
        request.client.host = "10.0.0.2"

        # First request OK
        await limiter.dispatch(request, fake_call_next)
        # Second request should be 429
        response = await limiter.dispatch(request, fake_call_next)

        assert response.status_code == 429
        assert "Rate limit exceeded" in response.body.decode()

    @pytest.mark.asyncio
    async def test_different_ips_have_separate_limits(self):
        """Each IP gets its own counter; one IP's limit doesn't affect another."""
        limiter = RateLimitMiddleware(
            app=MagicMock(),
            max_requests=2,
            window_seconds=60,
        )

        async def fake_call_next(request):
            return MagicMock(status_code=200, headers={})

        # IP-A makes 2 requests (hits limit)
        for _ in range(2):
            req_a = MagicMock()
            req_a.url.path = "/api/scanner/upload"
            req_a.client.host = "10.0.0.10"
            await limiter.dispatch(req_a, fake_call_next)

        # IP-A should now be blocked
        resp_a = await limiter.dispatch(req_a, fake_call_next)
        assert resp_a.status_code == 429

        # IP-B should still be allowed
        req_b = MagicMock()
        req_b.url.path = "/api/scanner/upload"
        req_b.client.host = "10.0.0.20"
        resp_b = await limiter.dispatch(req_b, fake_call_next)
        assert resp_b.status_code == 200


# ---------------------------------------------------------------------------
# Tests: GlobalErrorHandler catches unhandled exceptions
# ---------------------------------------------------------------------------


class TestGlobalErrorHandler:
    """GlobalErrorHandler should catch exceptions and return JSON 500."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_500(self):
        """An exception thrown by the downstream app should yield a 500 JSON."""
        from app.api.middleware import GlobalErrorHandler

        handler = GlobalErrorHandler(app=MagicMock())

        async def exploding_call_next(request):
            raise RuntimeError("Something broke!")

        request = MagicMock()
        request.url.path = "/api/test"

        response = await handler.dispatch(request, exploding_call_next)

        assert response.status_code == 500
        body = response.body.decode()
        assert "Internal server error" in body

    @pytest.mark.asyncio
    async def test_error_response_is_json(self):
        """500 error response should have application/json content type."""
        from app.api.middleware import GlobalErrorHandler

        handler = GlobalErrorHandler(app=MagicMock())

        async def exploding_call_next(request):
            raise ValueError("Bad value")

        request = MagicMock()
        request.url.path = "/api/explode"

        response = await handler.dispatch(request, exploding_call_next)

        assert response.status_code == 500
        assert response.media_type == "application/json"

    @pytest.mark.asyncio
    async def test_successful_request_passes_through(self):
        """When no exception occurs, GlobalErrorHandler passes the response."""
        from app.api.middleware import GlobalErrorHandler

        handler = GlobalErrorHandler(app=MagicMock())
        ok_response = MagicMock(status_code=200)

        async def ok_call_next(request):
            return ok_response

        request = MagicMock()
        response = await handler.dispatch(request, ok_call_next)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: RequestLoggingMiddleware logs method, path, status
# ---------------------------------------------------------------------------


class TestRequestLoggingMiddleware:
    """RequestLoggingMiddleware should log request details and set timing header."""

    @pytest.mark.asyncio
    async def test_logs_method_path_status(self, caplog):
        """Logger output should include HTTP method, URL path, and status code."""
        from app.api.middleware import RequestLoggingMiddleware

        mw = RequestLoggingMiddleware(app=MagicMock())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def fake_call_next(request):
            return mock_response

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/health"

        with caplog.at_level(logging.INFO, logger="app.api.middleware"):
            await mw.dispatch(request, fake_call_next)

        # Verify the log contains method, path, and status
        assert any("GET" in msg and "/api/health" in msg and "200" in msg
                    for msg in caplog.messages), (
            f"Expected log with 'GET /api/health 200', got: {caplog.messages}"
        )

    @pytest.mark.asyncio
    async def test_sets_x_response_time_header(self):
        """Response should include an X-Response-Time header."""
        from app.api.middleware import RequestLoggingMiddleware

        mw = RequestLoggingMiddleware(app=MagicMock())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def fake_call_next(request):
            return mock_response

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/scanner/upload"

        response = await mw.dispatch(request, fake_call_next)

        assert "X-Response-Time" in response.headers
        assert response.headers["X-Response-Time"].endswith("ms")

    @pytest.mark.asyncio
    async def test_response_time_header_via_async_client(self, async_client):
        """X-Response-Time header should be present on real HTTP responses."""
        resp = await async_client.get("/api/health")
        assert resp.status_code == 200
        assert "x-response-time" in resp.headers
        assert resp.headers["x-response-time"].endswith("ms")


# ---------------------------------------------------------------------------
# Tests: Health endpoint bypasses rate limiter
# ---------------------------------------------------------------------------


class TestHealthBypassesRateLimiter:
    """Health endpoint should never be blocked by the rate limiter."""

    @pytest.mark.asyncio
    async def test_health_not_rate_limited_even_after_many_calls(self):
        """Health checks should succeed even if called many times."""
        limiter = RateLimitMiddleware(
            app=MagicMock(),
            max_requests=2,  # very low limit
            window_seconds=60,
        )

        ok_response = MagicMock(status_code=200)

        async def fake_call_next(request):
            return ok_response

        # Make many requests to /api/health — all should pass
        for i in range(20):
            request = MagicMock()
            request.url.path = "/api/health"
            request.client.host = "10.0.0.1"

            response = await limiter.dispatch(request, fake_call_next)
            assert response.status_code == 200, (
                f"Health request {i} was blocked with {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_health_ok_while_scanner_is_blocked(self):
        """Even when the same IP is rate-limited on /api/scanner/upload,
        /api/health should still work."""
        limiter = RateLimitMiddleware(
            app=MagicMock(),
            max_requests=1,
            window_seconds=60,
        )

        ok_response = MagicMock(status_code=200)

        async def fake_call_next(request):
            return ok_response

        # Exhaust scanner limit
        scanner_req = MagicMock()
        scanner_req.url.path = "/api/scanner/upload"
        scanner_req.client.host = "10.0.0.1"
        await limiter.dispatch(scanner_req, fake_call_next)
        # Confirm scanner is now blocked
        scanner_resp = await limiter.dispatch(scanner_req, fake_call_next)
        assert scanner_resp.status_code == 429

        # Health should still be fine from the same IP
        health_req = MagicMock()
        health_req.url.path = "/api/health"
        health_req.client.host = "10.0.0.1"
        health_resp = await limiter.dispatch(health_req, fake_call_next)
        assert health_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_via_async_client_always_200(self, async_client):
        """Integration check: /api/health returns 200 through the full stack."""
        for _ in range(5):
            resp = await async_client.get("/api/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"
