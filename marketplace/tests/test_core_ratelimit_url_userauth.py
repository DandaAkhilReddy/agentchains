"""Comprehensive tests for three core modules:

  - marketplace.core.rate_limit_middleware  (RateLimitMiddleware)
  - marketplace.core.url_validation         (validate_url, is_disallowed_ip, resolve_host_ips)
  - marketplace.core.user_auth              (create_user_token, get_current_user_id, optional_user_id)

All tests are async def test_* functions.
pytest-asyncio is configured in auto mode -- no explicit mark needed.
"""

from __future__ import annotations

import ipaddress
import socket
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from jose import jwt

from marketplace.config import settings
from marketplace.core.auth import create_access_token
from marketplace.core.exceptions import UnauthorizedError
from marketplace.core.user_auth import (
    create_user_token,
    get_current_user_id,
    optional_user_id,
)
from marketplace.core.url_validation import (
    is_disallowed_ip,
    resolve_host_ips,
    validate_url,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _make_user_token(user_id: str = None, email: str = "user@test.com") -> str:
    """Build a valid user JWT."""
    user_id = user_id or str(uuid.uuid4())
    return create_user_token(user_id, email)


def _make_expired_user_token(user_id: str = "u-expired", email: str = "x@test.com") -> str:
    """Build a user JWT that has already expired."""
    payload = {
        "sub": user_id,
        "email": email,
        "type": "user",
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ===========================================================================
# RateLimitMiddleware -- integration tests via the `client` fixture
# ===========================================================================


class TestRateLimitMiddlewareSkipPaths:
    """Paths/methods that must bypass rate limiting entirely."""

    async def test_skip_health_endpoint(self, client):
        """GET /api/v1/health bypasses the rate limiter (no X-RateLimit headers)."""
        resp = await client.get("/api/v1/health")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    async def test_skip_docs_endpoint(self, client):
        """GET /docs returns a non-429 response without rate-limit headers."""
        resp = await client.get("/docs")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    async def test_skip_openapi_json(self, client):
        """GET /openapi.json is served without being rate-limited."""
        resp = await client.get("/openapi.json")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    async def test_skip_redoc(self, client):
        """GET /redoc is served without being rate-limited."""
        resp = await client.get("/redoc")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    async def test_skip_mcp_health(self, client):
        """GET /mcp/health bypasses rate limiting."""
        resp = await client.get("/mcp/health")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers

    async def test_skip_options_preflight(self, client):
        """OPTIONS (CORS preflight) bypasses rate limiting regardless of path."""
        resp = await client.options("/api/v1/agents")
        assert resp.status_code != 429
        assert "X-RateLimit-Limit" not in resp.headers


class TestRateLimitMiddlewareKeyExtraction:
    """Key extraction: valid JWT -> agent key, invalid/absent -> IP key."""

    async def test_valid_jwt_yields_authenticated_limit(self, client):
        """A valid Bearer JWT should produce the authenticated limit (120)."""
        agent_id = str(uuid.uuid4())
        token = create_access_token(agent_id, "test-agent")
        resp = await client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == str(settings.rest_rate_limit_authenticated)

    async def test_invalid_jwt_falls_back_to_anonymous_limit(self, client):
        """A malformed Bearer token should fall back to the anonymous IP limit (30)."""
        resp = await client.get(
            "/api/v1/agents",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == str(settings.rest_rate_limit_anonymous)

    async def test_no_auth_header_uses_anonymous_limit(self, client):
        """No Authorization header -> anonymous IP-based rate limit."""
        resp = await client.get("/api/v1/agents")
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == str(settings.rest_rate_limit_anonymous)

    async def test_x_forwarded_for_accepted_from_trusted_proxy(self, client):
        """X-Forwarded-For should be respected (anonymous limit still applies without JWT)."""
        resp = await client.get(
            "/api/v1/agents",
            headers={"x-forwarded-for": "203.0.113.55, 10.0.0.1"},
        )
        # No JWT, so the anonymous limit applies; we just confirm headers exist.
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == str(settings.rest_rate_limit_anonymous)

    async def test_user_token_jwt_accepted_as_authenticated(self, client):
        """A valid user JWT is also a valid Bearer token recognised by the middleware."""
        user_id = str(uuid.uuid4())
        token = _make_user_token(user_id)
        resp = await client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"},
        )
        # user tokens have 'sub', so they decode fine and yield authenticated limit
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == str(settings.rest_rate_limit_authenticated)


class TestRateLimitMiddlewareEnforcement:
    """Rate-limit enforcement: 429 responses, headers, Retry-After."""

    async def test_rate_limit_returns_correct_headers_on_normal_request(self, client):
        """Each non-skipped response must contain all three X-RateLimit headers."""
        resp = await client.get("/api/v1/agents")
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

    async def test_remaining_decrements_across_requests(self, client):
        """X-RateLimit-Remaining should decrease with each successive request."""
        resp1 = await client.get("/api/v1/agents")
        resp2 = await client.get("/api/v1/agents")
        remaining1 = int(resp1.headers["X-RateLimit-Remaining"])
        remaining2 = int(resp2.headers["X-RateLimit-Remaining"])
        assert remaining2 < remaining1

    async def test_exceeding_limit_returns_429(self, client):
        """After exhausting the anonymous limit, the next request must return 429."""
        limit = settings.rest_rate_limit_anonymous  # default 30
        for _ in range(limit):
            await client.get("/api/v1/agents")
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 429

    async def test_429_response_body_detail(self, client):
        """A 429 response body must contain 'detail' and 'retry_after'."""
        limit = settings.rest_rate_limit_anonymous
        for _ in range(limit):
            await client.get("/api/v1/agents")
        resp = await client.get("/api/v1/agents")
        body = resp.json()
        assert body["detail"] == "Rate limit exceeded"
        assert "retry_after" in body
        assert isinstance(body["retry_after"], int)
        assert body["retry_after"] >= 0

    async def test_429_has_retry_after_header(self, client):
        """A 429 response must include a Retry-After header."""
        limit = settings.rest_rate_limit_anonymous
        for _ in range(limit):
            await client.get("/api/v1/agents")
        resp = await client.get("/api/v1/agents")
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) >= 0

    async def test_authenticated_limit_is_higher_than_anonymous(self, client):
        """Authenticated requests get a higher limit than anonymous ones."""
        agent_id = str(uuid.uuid4())
        token = create_access_token(agent_id, "test-agent")
        resp = await client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {token}"},
        )
        auth_limit = int(resp.headers["X-RateLimit-Limit"])
        resp2 = await client.get("/api/v1/agents")  # different key (IP), no auth
        anon_limit = int(resp2.headers["X-RateLimit-Limit"])
        assert auth_limit > anon_limit

    async def test_rate_reset_header_is_non_negative(self, client):
        """X-RateLimit-Reset must always be a non-negative integer."""
        resp = await client.get("/api/v1/agents")
        reset = int(resp.headers["X-RateLimit-Reset"])
        assert reset >= 0


# ===========================================================================
# url_validation.py -- pure-function tests (no DB needed)
# ===========================================================================


class TestIsDisallowedIp:
    """is_disallowed_ip should return True for private/reserved ranges."""

    async def test_loopback_ipv4_is_disallowed(self):
        """127.0.0.1 (loopback) must be disallowed."""
        assert is_disallowed_ip(ipaddress.ip_address("127.0.0.1")) is True

    async def test_loopback_ipv6_is_disallowed(self):
        """::1 (IPv6 loopback) must be disallowed."""
        assert is_disallowed_ip(ipaddress.ip_address("::1")) is True

    async def test_private_10_network_is_disallowed(self):
        """10.x.x.x addresses belong to private RFC 1918 space."""
        assert is_disallowed_ip(ipaddress.ip_address("10.0.0.1")) is True

    async def test_private_172_network_is_disallowed(self):
        """172.16.x.x – 172.31.x.x is private RFC 1918 space."""
        assert is_disallowed_ip(ipaddress.ip_address("172.16.0.1")) is True

    async def test_private_192168_network_is_disallowed(self):
        """192.168.x.x is private RFC 1918 space."""
        assert is_disallowed_ip(ipaddress.ip_address("192.168.1.1")) is True

    async def test_link_local_is_disallowed(self):
        """169.254.x.x (APIPA / link-local) must be disallowed."""
        assert is_disallowed_ip(ipaddress.ip_address("169.254.1.1")) is True

    async def test_multicast_is_disallowed(self):
        """224.x.x.x (multicast) must be disallowed."""
        assert is_disallowed_ip(ipaddress.ip_address("224.0.0.1")) is True

    async def test_public_ip_is_allowed(self):
        """A genuine public routable IP must NOT be flagged as disallowed."""
        assert is_disallowed_ip(ipaddress.ip_address("8.8.8.8")) is False

    async def test_another_public_ip_is_allowed(self):
        """203.0.113.x (TEST-NET-3 documentation range) behaves as public."""
        # 203.0.113.x is in the documentation range (reserved), but it is not
        # loopback / link-local / private RFC-1918 / multicast.  The function
        # checks is_reserved, so 203.0.113.1 may be flagged.  We use a real
        # world public address instead.
        assert is_disallowed_ip(ipaddress.ip_address("1.1.1.1")) is False


class TestResolveHostIps:
    """resolve_host_ips must resolve hostnames or raise ValueError."""

    async def test_resolves_localhost_to_127(self):
        """localhost should resolve to 127.0.0.1 or ::1."""
        ips = resolve_host_ips("localhost")
        str_ips = [str(ip) for ip in ips]
        assert any(s in {"127.0.0.1", "::1"} for s in str_ips)

    async def test_resolves_known_public_host(self):
        """A resolvable public hostname returns at least one IP address."""
        # We mock socket.getaddrinfo to avoid network calls in CI
        fake_results = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        with patch("socket.getaddrinfo", return_value=fake_results):
            ips = resolve_host_ips("example.com")
        assert len(ips) >= 1
        assert all(isinstance(ip, (ipaddress.IPv4Address, ipaddress.IPv6Address)) for ip in ips)

    async def test_unresolvable_host_raises_value_error(self):
        """A non-existent hostname must raise ValueError."""
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("NXDOMAIN")):
            with pytest.raises(ValueError, match="Unable to resolve host"):
                resolve_host_ips("this-hostname-does-not-exist.invalid")

    async def test_empty_result_raises_value_error(self):
        """If getaddrinfo returns an empty list, ValueError must be raised."""
        with patch("socket.getaddrinfo", return_value=[]):
            with pytest.raises(ValueError, match="No routable IP addresses found"):
                resolve_host_ips("example.com")


class TestValidateUrl:
    """validate_url: scheme checks, host checks, SSRF protection."""

    # --- Happy paths ----------------------------------------------------------

    async def test_valid_http_url_accepted(self):
        """A well-formed http:// URL is accepted in non-production environments."""
        result = validate_url("http://example.com/path")
        assert result.startswith("http://example.com")

    async def test_valid_https_url_accepted(self):
        """A well-formed https:// URL is always accepted."""
        result = validate_url("https://example.com/callback")
        assert result.startswith("https://example.com")

    async def test_url_path_is_normalized(self):
        """A URL without a path gets '/' appended."""
        result = validate_url("https://example.com")
        assert result == "https://example.com/"

    async def test_query_string_preserved(self):
        """Query parameters must be preserved in the normalized URL."""
        result = validate_url("https://example.com/cb?foo=bar")
        assert "foo=bar" in result

    async def test_fragment_stripped(self):
        """URL fragments should be stripped from the normalized output."""
        result = validate_url("https://example.com/page#section")
        assert "#section" not in result

    async def test_whitespace_trimmed(self):
        """Leading/trailing whitespace around the URL must be trimmed."""
        result = validate_url("  https://example.com/  ")
        assert result.startswith("https://example.com")

    # --- Scheme errors --------------------------------------------------------

    async def test_ftp_scheme_rejected(self):
        """ftp:// URLs must raise ValueError."""
        with pytest.raises(ValueError, match="http or https"):
            validate_url("ftp://example.com/file")

    async def test_empty_url_rejected(self):
        """An empty string must raise ValueError."""
        with pytest.raises(ValueError):
            validate_url("")

    async def test_file_scheme_rejected(self):
        """file:// URLs (potential SSRF via filesystem) must be rejected."""
        with pytest.raises(ValueError, match="http or https"):
            validate_url("file:///etc/passwd")

    # --- Host errors ----------------------------------------------------------

    async def test_no_host_rejected(self):
        """A URL with no host (e.g. just a path) must raise ValueError."""
        with pytest.raises(ValueError, match="valid host"):
            validate_url("https:///no-host")

    # --- Private IP SSRF protection -------------------------------------------

    async def test_loopback_literal_ip_rejected(self):
        """http://127.0.0.1/... is an SSRF risk and must be rejected."""
        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://127.0.0.1/admin")

    async def test_private_192168_literal_ip_rejected(self):
        """http://192.168.x.x/... must be rejected as a private address."""
        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://192.168.1.10/secret")

    async def test_private_10_literal_ip_rejected(self):
        """http://10.x.x.x/... must be rejected as a private address."""
        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://10.0.0.1/internal")

    async def test_private_172_literal_ip_rejected(self):
        """http://172.16.x.x/... (RFC 1918) must be rejected."""
        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://172.16.0.1/internal")

    async def test_link_local_literal_ip_rejected(self):
        """http://169.254.x.x/... (APIPA) must be rejected."""
        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://169.254.169.254/metadata")

    # --- Production-only restrictions -----------------------------------------

    async def test_https_required_in_prod(self):
        """In production, http:// must raise ValueError when require_https_in_prod=True."""
        with patch("marketplace.core.url_validation.settings") as mock_settings:
            mock_settings.environment = "production"
            with pytest.raises(ValueError, match="HTTPS is required in production"):
                validate_url("http://example.com/", require_https_in_prod=True)

    async def test_https_not_required_if_flag_disabled(self):
        """With require_https_in_prod=False, http is allowed even in production."""
        with patch("marketplace.core.url_validation.settings") as mock_settings:
            mock_settings.environment = "production"
            # Must also patch socket to avoid real DNS in CI
            fake_results = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
            with patch("socket.getaddrinfo", return_value=fake_results):
                result = validate_url("http://example.com/", require_https_in_prod=False)
        assert result.startswith("http://example.com")

    async def test_localhost_blocked_in_prod(self):
        """In production, 'localhost' as a hostname must be rejected."""
        with patch("marketplace.core.url_validation.settings") as mock_settings:
            mock_settings.environment = "production"
            with pytest.raises(ValueError, match="Localhost URLs are not allowed in production"):
                validate_url("https://localhost/admin")

    async def test_127_0_0_1_blocked_in_prod(self):
        """In production, 127.0.0.1 literal is rejected (localhost check fires first)."""
        with patch("marketplace.core.url_validation.settings") as mock_settings:
            mock_settings.environment = "production"
            with pytest.raises(ValueError):
                validate_url("https://127.0.0.1/admin")

    async def test_hostname_resolving_to_private_ip_rejected_in_prod(self):
        """In production, a hostname resolving to a private IP must be rejected."""
        fake_results = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0))]
        with patch("marketplace.core.url_validation.settings") as mock_settings:
            mock_settings.environment = "production"
            with patch("socket.getaddrinfo", return_value=fake_results):
                with pytest.raises(ValueError, match="private or reserved"):
                    validate_url("https://internal.corp.example.com/api")

    async def test_hostname_resolving_to_public_ip_accepted_in_prod(self):
        """In production, a hostname resolving to a public IP is accepted."""
        fake_results = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        with patch("marketplace.core.url_validation.settings") as mock_settings:
            mock_settings.environment = "production"
            with patch("socket.getaddrinfo", return_value=fake_results):
                result = validate_url("https://example.com/callback")
        assert result.startswith("https://example.com")

    async def test_dev_environment_skips_dns_resolution(self):
        """In non-production, hostnames are NOT resolved (only literal IPs checked)."""
        # Should not raise even if getaddrinfo would fail, because resolution is skipped.
        with patch("socket.getaddrinfo", side_effect=AssertionError("Should not be called")):
            result = validate_url("https://somehost.internal/cb")
        assert "somehost.internal" in result


# ===========================================================================
# user_auth.py -- create_user_token
# ===========================================================================


class TestCreateUserToken:
    """create_user_token must produce valid JWTs with the correct claims."""

    async def test_returns_non_empty_string(self):
        """create_user_token returns a non-empty string."""
        token = create_user_token("user-1", "a@b.com")
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_payload_has_type_user(self):
        """Token payload must contain type='user'."""
        token = create_user_token("user-2", "c@d.com")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["type"] == "user"

    async def test_payload_has_correct_sub(self):
        """Token 'sub' claim must match the provided user_id."""
        uid = str(uuid.uuid4())
        token = create_user_token(uid, "test@example.com")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == uid

    async def test_payload_has_correct_email(self):
        """Token 'email' claim must match the provided email."""
        token = create_user_token("u-abc", "foo@bar.com")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["email"] == "foo@bar.com"

    async def test_payload_has_jti(self):
        """Token must have a 'jti' claim that is a valid UUID."""
        token = create_user_token("u-jti", "jti@test.com")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert "jti" in payload
        uuid.UUID(payload["jti"])  # raises ValueError if not a valid UUID

    async def test_each_token_has_unique_jti(self):
        """Two tokens for the same user must have different jti values."""
        t1 = create_user_token("u-same", "same@test.com")
        t2 = create_user_token("u-same", "same@test.com")
        p1 = jwt.decode(t1, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        p2 = jwt.decode(t2, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert p1["jti"] != p2["jti"]

    async def test_token_expiry_is_in_the_future(self):
        """Token exp must be in the future (at least 1 hour away)."""
        token = create_user_token("u-exp", "exp@test.com")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp_dt > datetime.now(timezone.utc) + timedelta(hours=1)

    async def test_payload_has_iat(self):
        """Token must have an 'iat' (issued at) claim."""
        token = create_user_token("u-iat", "iat@test.com")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert "iat" in payload


# ===========================================================================
# user_auth.py -- get_current_user_id
# ===========================================================================


class TestGetCurrentUserId:
    """get_current_user_id: correct extraction, all error paths."""

    async def test_valid_bearer_token_returns_user_id(self):
        """A valid user Bearer token must return the correct user_id."""
        uid = str(uuid.uuid4())
        token = _make_user_token(uid)
        result = get_current_user_id(f"Bearer {token}")
        assert result == uid

    async def test_missing_header_raises_unauthorized(self):
        """None authorization header must raise UnauthorizedError."""
        with pytest.raises(UnauthorizedError, match="Missing Authorization header"):
            get_current_user_id(None)

    async def test_empty_string_raises_unauthorized(self):
        """Empty string authorization header must raise UnauthorizedError."""
        with pytest.raises(UnauthorizedError):
            get_current_user_id("")

    async def test_missing_bearer_prefix_raises(self):
        """Authorization without 'Bearer' prefix must raise UnauthorizedError."""
        token = _make_user_token()
        with pytest.raises(UnauthorizedError, match="Bearer <token>"):
            get_current_user_id(f"Token {token}")

    async def test_three_part_header_raises(self):
        """Authorization header with extra whitespace-separated parts must raise."""
        token = _make_user_token()
        with pytest.raises(UnauthorizedError, match="Bearer <token>"):
            get_current_user_id(f"Bearer {token} extra")

    async def test_expired_token_raises(self):
        """An expired user token must raise UnauthorizedError."""
        token = _make_expired_user_token()
        with pytest.raises(UnauthorizedError, match="Invalid token"):
            get_current_user_id(f"Bearer {token}")

    async def test_garbage_token_raises(self):
        """A completely invalid token string must raise UnauthorizedError."""
        with pytest.raises(UnauthorizedError, match="Invalid token"):
            get_current_user_id("Bearer this.is.garbage")

    async def test_agent_token_rejected(self):
        """An agent JWT (type != 'user') must raise UnauthorizedError."""
        agent_token = create_access_token("agent-1", "NotAUser")
        with pytest.raises(UnauthorizedError, match="Not a user token"):
            get_current_user_id(f"Bearer {agent_token}")

    async def test_token_signed_with_wrong_secret_raises(self):
        """A token signed with a different secret must raise UnauthorizedError."""
        payload = {
            "sub": "u-hacker",
            "email": "h@evil.com",
            "type": "user",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        bad_token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.jwt_algorithm)
        with pytest.raises(UnauthorizedError, match="Invalid token"):
            get_current_user_id(f"Bearer {bad_token}")

    async def test_token_missing_sub_raises(self):
        """A user token without a 'sub' claim must raise UnauthorizedError."""
        payload = {
            "email": "nosub@test.com",
            "type": "user",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(UnauthorizedError, match="Token missing subject"):
            get_current_user_id(f"Bearer {token}")


# ===========================================================================
# user_auth.py -- optional_user_id
# ===========================================================================


class TestOptionalUserId:
    """optional_user_id: must return user_id or None, never raise."""

    async def test_returns_none_when_no_header(self):
        """None authorization header must return None (no exception)."""
        result = optional_user_id(None)
        assert result is None

    async def test_returns_none_for_invalid_token(self):
        """An invalid Bearer token must return None instead of raising."""
        result = optional_user_id("Bearer not.a.real.token")
        assert result is None

    async def test_returns_none_for_expired_token(self):
        """An expired user token must silently return None."""
        token = _make_expired_user_token()
        result = optional_user_id(f"Bearer {token}")
        assert result is None

    async def test_returns_none_for_agent_token(self):
        """An agent token (wrong type) must silently return None."""
        agent_token = create_access_token("agent-99", "SomeBot")
        result = optional_user_id(f"Bearer {agent_token}")
        assert result is None

    async def test_returns_user_id_for_valid_token(self):
        """A valid user Bearer token must return the correct user_id."""
        uid = str(uuid.uuid4())
        token = _make_user_token(uid)
        result = optional_user_id(f"Bearer {token}")
        assert result == uid

    async def test_returns_none_for_empty_string(self):
        """An empty string authorization header must return None."""
        result = optional_user_id("")
        assert result is None

    async def test_returns_none_for_garbage_header(self):
        """A completely garbage authorization value must return None."""
        result = optional_user_id("this-is-not-a-bearer-token")
        assert result is None
