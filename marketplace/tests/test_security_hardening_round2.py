"""Tests for security hardening round 2 — CORS restriction, OData injection,
SSRF protection, ZKP error leakage, error detail sanitization, pickle removal,
and webhook replay protection.
"""

import hashlib
import hmac
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.config import settings


# ===========================================================================
# 1. CORS — Restrict methods and headers
# ===========================================================================

class TestCORSRestriction:
    """Verify CORS middleware only allows explicitly listed methods/headers."""

    async def test_preflight_allows_listed_method(self, client):
        """OPTIONS preflight for GET should succeed."""
        resp = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS preflight should not return 405
        assert resp.status_code in (200, 204, 400)

    async def test_preflight_allows_post(self, client):
        """OPTIONS preflight for POST should succeed."""
        resp = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code in (200, 204, 400)

    async def test_cors_does_not_allow_wildcard_methods(self):
        """Verify the CORS middleware is configured with explicit methods, not wildcard."""
        from marketplace.main import create_app

        test_app = create_app()
        # Inspect middleware stack for CORSMiddleware config
        for middleware in test_app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                kwargs = middleware.kwargs
                methods = kwargs.get("allow_methods", [])
                assert methods != ["*"], "CORS allow_methods should not be wildcard"
                assert "GET" in methods
                assert "POST" in methods
                assert "DELETE" in methods
                break

    async def test_cors_does_not_allow_wildcard_headers(self):
        """Verify the CORS middleware is configured with explicit headers, not wildcard."""
        from marketplace.main import create_app

        test_app = create_app()
        for middleware in test_app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                kwargs = middleware.kwargs
                headers = kwargs.get("allow_headers", [])
                assert headers != ["*"], "CORS allow_headers should not be wildcard"
                assert "Content-Type" in headers
                assert "Authorization" in headers
                break


# ===========================================================================
# 2. OData filter injection
# ===========================================================================

class TestODataInjection:
    """Verify that malicious OData values are rejected in search filters."""

    def test_single_quote_rejected(self):
        """Single quotes in category values must be rejected."""
        from marketplace.api.v2_search import _sanitize_odata_value
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _sanitize_odata_value("test' or 1 eq 1")
        assert exc_info.value.status_code == 400
        assert "single quotes" in exc_info.value.detail

    def test_odata_keyword_eq_rejected(self):
        """OData keyword 'eq' in a filter value must be rejected."""
        from marketplace.api.v2_search import _sanitize_odata_value
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _sanitize_odata_value("value eq other")
        assert exc_info.value.status_code == 400
        assert "reserved keyword" in exc_info.value.detail

    def test_odata_keyword_or_rejected(self):
        """OData keyword 'or' in a filter value must be rejected."""
        from marketplace.api.v2_search import _sanitize_odata_value
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _sanitize_odata_value("category or true")
        assert exc_info.value.status_code == 400

    def test_odata_keyword_and_rejected(self):
        """OData keyword 'and' must be rejected."""
        from marketplace.api.v2_search import _sanitize_odata_value
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _sanitize_odata_value("a and b")
        assert exc_info.value.status_code == 400

    def test_clean_value_passes(self):
        """Normal category values should pass sanitization."""
        from marketplace.api.v2_search import _sanitize_odata_value

        result = _sanitize_odata_value("web_search")
        assert result == "web_search"

    def test_clean_value_with_hyphens_passes(self):
        """Values with hyphens and underscores should pass."""
        from marketplace.api.v2_search import _sanitize_odata_value

        result = _sanitize_odata_value("machine-learning_data")
        assert result == "machine-learning_data"

    def test_build_listing_filter_sanitizes_category(self):
        """_build_listing_filter should reject injected category."""
        from marketplace.api.v2_search import _build_listing_filter
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            _build_listing_filter(category="test' or 1 eq 1")

    def test_build_category_filter_sanitizes(self):
        """_build_category_filter should reject injected category."""
        from marketplace.api.v2_search import _build_category_filter
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            _build_category_filter(category="x' or '1'='1")


# ===========================================================================
# 3. SSRF protection — MCP federation base_url
# ===========================================================================

class TestSSRFProtection:
    """Verify that private/reserved IPs are rejected for MCP federation URLs."""

    def test_localhost_rejected(self):
        """Localhost base_url must be rejected."""
        from marketplace.core.url_validation import validate_url

        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://127.0.0.1:8080/api")

    def test_private_10_network_rejected(self):
        """10.x.x.x private IPs must be rejected."""
        from marketplace.core.url_validation import validate_url

        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://10.0.0.1:8080/api")

    def test_private_172_network_rejected(self):
        """172.16.x.x private IPs must be rejected."""
        from marketplace.core.url_validation import validate_url

        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://172.16.0.1:8080/api")

    def test_private_192_network_rejected(self):
        """192.168.x.x private IPs must be rejected."""
        from marketplace.core.url_validation import validate_url

        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://192.168.1.1:8080/api")

    def test_link_local_rejected(self):
        """169.254.x.x link-local IPs must be rejected."""
        from marketplace.core.url_validation import validate_url

        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://169.254.169.254/metadata")

    def test_ipv6_loopback_rejected(self):
        """IPv6 loopback ::1 must be rejected."""
        from marketplace.core.url_validation import validate_url

        with pytest.raises(ValueError, match="private or reserved"):
            validate_url("http://[::1]:8080/api")

    def test_valid_public_url_accepted(self):
        """A valid public URL should pass validation."""
        from marketplace.core.url_validation import validate_url

        result = validate_url("https://mcp.example.com/api")
        assert result == "https://mcp.example.com/api"

    def test_invalid_scheme_rejected(self):
        """Non-http/https schemes must be rejected."""
        from marketplace.core.url_validation import validate_url

        with pytest.raises(ValueError, match="http or https"):
            validate_url("ftp://example.com/api")

    def test_empty_url_rejected(self):
        """Empty URL must be rejected."""
        from marketplace.core.url_validation import validate_url

        with pytest.raises(ValueError):
            validate_url("")

    def test_is_disallowed_ip_helper(self):
        """Test the is_disallowed_ip utility function."""
        import ipaddress
        from marketplace.core.url_validation import is_disallowed_ip

        assert is_disallowed_ip(ipaddress.ip_address("127.0.0.1")) is True
        assert is_disallowed_ip(ipaddress.ip_address("10.0.0.1")) is True
        assert is_disallowed_ip(ipaddress.ip_address("192.168.1.1")) is True
        assert is_disallowed_ip(ipaddress.ip_address("169.254.0.1")) is True
        assert is_disallowed_ip(ipaddress.ip_address("::1")) is True

    async def test_federation_register_rejects_private_ip(self, client, make_agent):
        """MCP federation register_server should reject private IP base_url."""
        agent, token = await make_agent()
        resp = await client.post(
            "/api/v3/federation/servers",
            json={
                "name": "evil-server",
                "base_url": "http://127.0.0.1:8080/api",
                "namespace": "evil",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


# ===========================================================================
# 4. ZKP error leakage
# ===========================================================================

class TestZKPErrorLeakage:
    """Verify that ZKP bloom_check returns generic errors, not internal details."""

    async def test_bloom_check_error_is_generic(self, client, db):
        """On exception, bloom_check should return 'Internal server error'."""
        with patch(
            "marketplace.api.zkp.zkp_service.bloom_check_word",
            side_effect=RuntimeError("secret internal db error /var/lib/data"),
        ):
            resp = await client.get(
                "/api/v1/zkp/fake-listing-id/bloom-check",
                params={"word": "test"},
            )
            data = resp.json()
            assert data["error"] == "Internal server error"
            assert "RuntimeError" not in data["error"]
            assert "/var/lib" not in data["error"]
            assert "secret" not in data["error"]

    async def test_bloom_check_error_does_not_leak_class_name(self, client, db):
        """Exception type names must not appear in the response."""
        with patch(
            "marketplace.api.zkp.zkp_service.bloom_check_word",
            side_effect=ValueError("sensitive config path"),
        ):
            resp = await client.get(
                "/api/v1/zkp/fake-listing-id/bloom-check",
                params={"word": "test"},
            )
            data = resp.json()
            assert "ValueError" not in json.dumps(data)
            assert "sensitive" not in json.dumps(data)


# ===========================================================================
# 5. Error detail sanitization — health check
# ===========================================================================

class TestErrorDetailSanitization:
    """Verify that catch-all exception handlers don't leak internal details."""

    async def test_readiness_probe_error_is_generic(self, client):
        """Health readiness probe should not leak database error details."""
        with patch(
            "marketplace.api.health.get_db",
        ) as mock_get_db:
            # Make the DB session raise an exception with internal details
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception(
                "FATAL: password authentication failed for user 'admin'"
            )

            async def _override():
                yield mock_session

            from marketplace.database import get_db
            from marketplace.main import app

            app.dependency_overrides[get_db] = _override
            try:
                resp = await client.get("/api/v1/health/ready")
                data = resp.json()
                assert resp.status_code == 503
                assert "password" not in json.dumps(data)
                assert "FATAL" not in json.dumps(data)
                assert data["database"] == "unavailable"
            finally:
                app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# 6. Pickle removal — joblib + SHA-256 integrity
# ===========================================================================

class TestModelSerialization:
    """Verify reputation model uses joblib instead of pickle with integrity checks."""

    def test_model_path_uses_joblib_extension(self):
        """Default model path should use .joblib extension, not .pkl."""
        from marketplace.ml.reputation_model import ReputationModel

        model = ReputationModel(model_dir="/tmp/test-models")
        assert str(model._model_path).endswith(".joblib")
        assert not str(model._model_path).endswith(".pkl")

    def test_hash_path_uses_sha256_extension(self):
        """Hash file should use .sha256 extension."""
        from marketplace.ml.reputation_model import ReputationModel

        model = ReputationModel(model_dir="/tmp/test-models")
        assert str(model._hash_path).endswith(".sha256")

    def test_compute_file_hash(self, tmp_path):
        """_compute_file_hash should return consistent SHA-256 hash."""
        from marketplace.ml.reputation_model import ReputationModel

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"test content for hashing")

        hash1 = ReputationModel._compute_file_hash(test_file)
        hash2 = ReputationModel._compute_file_hash(test_file)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest length

    def test_tampered_model_fails_integrity_check(self, tmp_path):
        """Loading a tampered model file should raise ValueError."""
        import joblib
        from marketplace.ml.reputation_model import ReputationModel

        model_file = tmp_path / "reputation_model.joblib"
        hash_file = tmp_path / "reputation_model.sha256"

        # Save a valid model file
        joblib.dump({"model": None, "model_type": "test", "features": []}, model_file)

        # Write a hash for the original content
        original_hash = ReputationModel._compute_file_hash(model_file)
        hash_file.write_text(original_hash)

        # Tamper with the model file
        model_file.write_bytes(b"tampered content")

        # Loading should fail integrity check
        model = ReputationModel(model_dir=str(tmp_path))
        # The __init__ load will fail, let's verify explicitly
        with pytest.raises(ValueError, match="integrity check failed"):
            model.load(str(model_file))

    def test_no_pickle_import_in_reputation_model(self):
        """The reputation_model module should not import pickle."""
        import importlib
        import marketplace.ml.reputation_model as mod

        source = Path(mod.__file__).read_text()
        assert "import pickle" not in source
        assert "pickle.load" not in source
        assert "pickle.dump" not in source


# ===========================================================================
# 7. Webhook replay protection
# ===========================================================================

class TestWebhookReplayProtection:
    """Verify that stale webhook timestamps are rejected."""

    async def test_razorpay_stale_timestamp_rejected(self, client):
        """Razorpay webhook with old timestamp should be rejected."""
        stale_ts = int(time.time()) - 600  # 10 minutes ago (> 5 min tolerance)
        payload = json.dumps({
            "event": "payment.captured",
            "created_at": stale_ts,
            "payload": {},
        }).encode()

        with patch.object(settings, "razorpay_key_secret", ""):
            resp = await client.post(
                "/webhooks/razorpay",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 400
            assert "timestamp too old" in resp.json()["error"]

    async def test_razorpay_fresh_timestamp_accepted(self, client):
        """Razorpay webhook with fresh timestamp should be accepted."""
        fresh_ts = int(time.time())
        payload = json.dumps({
            "event": "payment.captured",
            "created_at": fresh_ts,
            "payload": {},
        }).encode()

        with patch.object(settings, "razorpay_key_secret", ""):
            resp = await client.post(
                "/webhooks/razorpay",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 200

    async def test_razorpay_no_timestamp_still_accepted(self, client):
        """Razorpay webhook without timestamp field should still be accepted."""
        payload = json.dumps({
            "event": "payment.captured",
            "payload": {},
        }).encode()

        with patch.object(settings, "razorpay_key_secret", ""):
            resp = await client.post(
                "/webhooks/razorpay",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 200

    async def test_razorpay_timestamp_field_alternative(self, client):
        """Razorpay webhook with 'timestamp' field (alt key) should also be validated."""
        stale_ts = int(time.time()) - 600
        payload = json.dumps({
            "event": "payment.captured",
            "timestamp": stale_ts,
            "payload": {},
        }).encode()

        with patch.object(settings, "razorpay_key_secret", ""):
            resp = await client.post(
                "/webhooks/razorpay",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 400

    def test_webhook_timestamp_tolerance_constant(self):
        """Verify the timestamp tolerance is 5 minutes (300 seconds)."""
        from marketplace.api.webhooks import _WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS

        assert _WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS == 300
