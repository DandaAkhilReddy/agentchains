"""Tests for security audit fixes — webhook signature enforcement, OAuth2 auth,
PKCE S256-only, HTML sanitization, and Redis TLS settings.
"""

import hashlib
import hmac
import json
import re
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.config import settings


# ===========================================================================
# 1. Webhook Signature Enforcement
# ===========================================================================

class TestStripeWebhookSignatureEnforcement:
    """Verify Stripe webhook rejects requests with missing signature in live mode."""

    async def test_stripe_missing_signature_returns_401_in_live_mode(self, client):
        """When Stripe service is NOT simulated, omitting the Stripe-Signature
        header must return 401, not silently accept the payload."""
        with patch(
            "marketplace.api.webhooks.StripePaymentService"
        ) as MockStripe:
            mock_service = MagicMock()
            mock_service._simulated = False  # live mode
            MockStripe.return_value = mock_service

            resp = await client.post(
                "/webhooks/stripe",
                content=json.dumps({"type": "payment_intent.succeeded"}).encode(),
                headers={"Content-Type": "application/json"},
                # No Stripe-Signature header
            )
            assert resp.status_code == 401
            assert "Missing" in resp.json()["error"]

    async def test_stripe_with_signature_proceeds_to_verification(self, client):
        """When a signature header IS provided in live mode, it should be verified."""
        with patch(
            "marketplace.api.webhooks.StripePaymentService"
        ) as MockStripe:
            mock_service = MagicMock()
            mock_service._simulated = False
            mock_service.verify_webhook_signature.return_value = None  # invalid sig
            MockStripe.return_value = mock_service

            resp = await client.post(
                "/webhooks/stripe",
                content=json.dumps({"type": "payment_intent.succeeded"}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=badsig",
                },
            )
            assert resp.status_code == 400
            assert "Invalid webhook signature" in resp.json()["error"]

    async def test_stripe_simulated_mode_skips_signature(self, client):
        """In simulated mode, signature verification is skipped (dev convenience)."""
        with patch(
            "marketplace.api.webhooks.StripePaymentService"
        ) as MockStripe:
            mock_service = MagicMock()
            mock_service._simulated = True
            MockStripe.return_value = mock_service

            resp = await client.post(
                "/webhooks/stripe",
                content=json.dumps({"type": "payment_intent.succeeded", "data": {"id": "pi_test"}}).encode(),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 200


class TestRazorpayWebhookSignatureEnforcement:
    """Verify Razorpay webhook rejects requests with missing signature when secret is configured."""

    async def test_razorpay_missing_signature_returns_401_when_secret_configured(self, client):
        """When razorpay_key_secret is configured, omitting X-Razorpay-Signature
        must return 401."""
        with patch.object(settings, "razorpay_key_secret", "test_secret"):
            resp = await client.post(
                "/webhooks/razorpay",
                content=json.dumps({"event": "payment.captured"}).encode(),
                headers={"Content-Type": "application/json"},
                # No X-Razorpay-Signature header
            )
            assert resp.status_code == 401
            assert "Missing" in resp.json()["error"]

    async def test_razorpay_invalid_signature_returns_400(self, client):
        """When a signature IS provided but is wrong, return 400."""
        with patch.object(settings, "razorpay_key_secret", "test_secret"):
            resp = await client.post(
                "/webhooks/razorpay",
                content=json.dumps({"event": "payment.captured"}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-Razorpay-Signature": "invalidsignature",
                },
            )
            assert resp.status_code == 400
            assert "Invalid webhook signature" in resp.json()["error"]

    async def test_razorpay_valid_signature_accepted(self, client):
        """A correctly signed Razorpay payload should be accepted."""
        secret = "test_secret"
        payload = json.dumps({"event": "payment.captured", "payload": {}}).encode()
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        with patch.object(settings, "razorpay_key_secret", secret):
            resp = await client.post(
                "/webhooks/razorpay",
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Razorpay-Signature": sig,
                },
            )
            assert resp.status_code == 200

    async def test_razorpay_no_secret_allows_unsigned(self, client):
        """When razorpay_key_secret is empty, unsigned requests are accepted (dev mode)."""
        with patch.object(settings, "razorpay_key_secret", ""):
            resp = await client.post(
                "/webhooks/razorpay",
                content=json.dumps({"event": "payment.captured", "payload": {}}).encode(),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 200


# ===========================================================================
# 2. OAuth2 /authorize Authentication Requirement
# ===========================================================================

class TestOAuth2AuthorizeAuth:
    """Verify that /authorize requires authentication for user_id."""

    async def test_authorize_without_auth_or_user_id_returns_401(self, client):
        """Calling /authorize without auth token or user_id must return 401."""
        resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": "test-client",
                "redirect_uri": "https://example.com/callback",
            },
        )
        assert resp.status_code == 401

    async def test_authorize_with_valid_token_uses_token_user(self, client):
        """A valid Bearer token should provide the user_id from the token's sub claim."""
        from marketplace.core.auth import create_access_token

        # We need a registered client for this to work. The test may return 400
        # (invalid client) but should NOT return 401 since auth succeeded.
        token = create_access_token("user-from-token", "test-user")
        resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": "nonexistent-client",
                "redirect_uri": "https://example.com/callback",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        # Should fail with 400 (invalid client) not 401 (auth failure)
        assert resp.status_code == 400

    async def test_authorize_with_user_id_param_in_dev_mode(self, client):
        """In non-production, user_id query param is accepted as fallback."""
        with patch.object(settings, "environment", "development"):
            resp = await client.get(
                "/oauth2/authorize",
                params={
                    "client_id": "nonexistent-client",
                    "redirect_uri": "https://example.com/callback",
                    "user_id": "test-user",
                },
            )
            # Should fail with 400 (invalid client) not 401
            assert resp.status_code == 400

    async def test_authorize_with_user_id_param_in_prod_returns_401(self, client):
        """In production, user_id query param without auth token must return 401."""
        with patch.object(settings, "environment", "production"):
            resp = await client.get(
                "/oauth2/authorize",
                params={
                    "client_id": "test-client",
                    "redirect_uri": "https://example.com/callback",
                    "user_id": "attacker-controlled",
                },
            )
            assert resp.status_code == 401

    async def test_authorize_with_invalid_token_returns_401(self, client):
        """An invalid/expired Bearer token must return 401."""
        resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": "test-client",
                "redirect_uri": "https://example.com/callback",
            },
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


# ===========================================================================
# 3. PKCE S256-Only Enforcement
# ===========================================================================

class TestPKCES256Only:
    """Verify that only S256 PKCE method is accepted."""

    def test_pkce_plain_rejected(self):
        """The _verify_pkce function must reject 'plain' method."""
        from marketplace.oauth2.server import _verify_pkce

        result = _verify_pkce(
            code_challenge="test-verifier",
            code_challenge_method="plain",
            code_verifier="test-verifier",
        )
        assert result is False, "PKCE plain method should be rejected"

    def test_pkce_s256_accepted(self):
        """The _verify_pkce function must accept S256 with correct verifier."""
        import base64
        from marketplace.oauth2.server import _verify_pkce

        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        result = _verify_pkce(
            code_challenge=challenge,
            code_challenge_method="S256",
            code_verifier=verifier,
        )
        assert result is True

    def test_pkce_s256_wrong_verifier_rejected(self):
        """S256 with wrong verifier must be rejected."""
        import base64
        from marketplace.oauth2.server import _verify_pkce

        verifier = "correct-verifier"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

        result = _verify_pkce(
            code_challenge=challenge,
            code_challenge_method="S256",
            code_verifier="wrong-verifier",
        )
        assert result is False

    def test_pkce_unknown_method_rejected(self):
        """Unknown PKCE methods must be rejected."""
        from marketplace.oauth2.server import _verify_pkce

        result = _verify_pkce(
            code_challenge="anything",
            code_challenge_method="unknown",
            code_verifier="anything",
        )
        assert result is False

    async def test_oidc_discovery_only_advertises_s256(self, client):
        """The OIDC discovery endpoint must only list S256."""
        resp = await client.get("/oauth2/.well-known/openid-configuration")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code_challenge_methods_supported"] == ["S256"]
        assert "plain" not in data["code_challenge_methods_supported"]


# ===========================================================================
# 4. HTML Sanitization Defense-in-Depth
# ===========================================================================

class TestHTMLSanitization:
    """Verify that sanitize_html strips tags AND escapes remaining content."""

    def test_script_tag_stripped(self):
        from marketplace.a2ui.security import sanitize_html

        result = sanitize_html("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "alert(1)" in result

    def test_img_onerror_stripped(self):
        from marketplace.a2ui.security import sanitize_html

        result = sanitize_html('<img src=x onerror="alert(1)">')
        assert "<img" not in result
        assert "onerror" not in result

    def test_nested_tags_stripped(self):
        from marketplace.a2ui.security import sanitize_html

        result = sanitize_html("<b><script>xss</script></b>")
        assert "<" not in result or "&lt;" in result
        assert "xss" in result

    def test_plain_text_unchanged(self):
        from marketplace.a2ui.security import sanitize_html

        result = sanitize_html("Hello, world!")
        assert result == "Hello, world!"

    def test_ampersand_escaped(self):
        from marketplace.a2ui.security import sanitize_html

        result = sanitize_html("a & b")
        assert "&amp;" in result

    def test_angle_brackets_outside_tags_escaped(self):
        from marketplace.a2ui.security import sanitize_html

        # Bare angle brackets that don't form valid tags survive regex but get escaped
        result = sanitize_html("1 < 2 and 3 > 1")
        # The regex won't match "< 2 and 3 >" as a tag, so they'll be escaped
        assert "&lt;" in result or "<" not in result


# ===========================================================================
# 5. Redis TLS Configuration
# ===========================================================================

class TestRedisTLSConfig:
    """Verify that Redis TLS connections enforce certificate verification."""

    def test_redis_ssl_cert_reqs_is_required(self):
        """The RedisRateLimiter must set ssl_cert_reqs='required' for TLS URLs."""
        from marketplace.core.redis_rate_limiter import RedisRateLimiter

        limiter = RedisRateLimiter("rediss://test:6380")
        # We can't easily test the internal connection config without connecting,
        # but we can verify the URL is stored
        assert limiter._redis_url.startswith("rediss://")

    async def test_redis_tls_connect_kwargs(self):
        """Verify that the connect_kwargs include ssl_cert_reqs='required'."""
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_redis) as mock_from_url:
            from marketplace.core.redis_rate_limiter import RedisRateLimiter

            limiter = RedisRateLimiter("rediss://test:6380")
            await limiter._get_redis()

            mock_from_url.assert_called_once()
            call_kwargs = mock_from_url.call_args
            # The ssl_cert_reqs should be "required"
            assert call_kwargs[1].get("ssl_cert_reqs") == "required"


# ===========================================================================
# 6. Config Security Warnings
# ===========================================================================

class TestConfigSecurityWarnings:
    """Verify that insecure defaults produce critical-level log messages."""

    def test_insecure_jwt_secret_logged_critical(self):
        """Default JWT secret should trigger a critical log in non-prod."""
        import logging

        with patch.object(settings, "environment", "development"):
            with patch.object(
                settings, "jwt_secret_key", "dev-secret-change-in-production"
            ):
                with patch("marketplace.config._logger") as mock_logger:
                    from marketplace.config import validate_security_posture

                    validate_security_posture(settings)
                    # Check that critical was called for JWT
                    critical_calls = [
                        str(call) for call in mock_logger.critical.call_args_list
                    ]
                    assert any("JWT_SECRET_KEY" in c for c in critical_calls)

    def test_production_insecure_jwt_raises(self):
        """In production, an insecure JWT secret must raise RuntimeError."""
        from marketplace.config import validate_security_posture, Settings

        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            validate_security_posture(
                Settings(
                    environment="production",
                    jwt_secret_key="dev-secret-change-in-production",
                    event_signing_secret="secure-random-signing-secret-64chars-long-enough",
                    memory_encryption_key="secure-random-encryption-key-64chars-long-enough",
                )
            )
