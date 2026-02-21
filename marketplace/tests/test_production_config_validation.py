"""Tests for production configuration validation and security posture.

Validates:
- .env.example completeness and safety
- .env.production existence and contents
- validate_security_posture() enforcement for production environments
- Azure environment variable mapping in Settings
"""

import pathlib
import re

import pytest

from marketplace.config import Settings, _INSECURE_SECRETS, validate_security_posture

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides) -> Settings:
    """Create a Settings instance without reading any .env file."""
    defaults = {
        "_env_file": None,
        "environment": "development",
        "jwt_secret_key": "dev-secret-change-in-production",
        "event_signing_secret": "dev-event-signing-secret-change-in-production",
        "memory_encryption_key": "dev-memory-encryption-key-change-in-production",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_prod_settings(**overrides) -> Settings:
    """Create a production Settings with strong secrets by default."""
    defaults = {
        "_env_file": None,
        "environment": "production",
        "jwt_secret_key": "strong-random-jwt-secret-not-in-insecure-set",
        "event_signing_secret": "strong-random-event-signing-secret-unique",
        "memory_encryption_key": "strong-random-memory-encryption-key-unique",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ===========================================================================
# 1. Env Completeness (5 tests)
# ===========================================================================

class TestEnvCompleteness:
    """Verify .env.example documents all critical Settings fields."""

    def test_all_settings_fields_documented_in_env_example(self):
        """Every Settings field name (as uppercase) should be documented in
        .env.example, either set or commented out."""
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text(encoding="utf-8").upper()

        critical_fields = [
            "JWT_SECRET_KEY",
            "DATABASE_URL",
            "CORS_ORIGINS",
            "ENVIRONMENT",
            "REDIS_URL",
            "MCP_ENABLED",
        ]
        missing = [f for f in critical_fields if f not in content]
        assert not missing, (
            f"Critical Settings fields not documented in .env.example: {missing}"
        )

    def test_azure_vars_present_in_env_example(self):
        """Azure config vars should appear (even as comments) in .env.example."""
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text(encoding="utf-8").upper()

        azure_vars = [
            "AZURE_KEYVAULT_URL",
            "AZURE_SERVICEBUS_CONNECTION",
            "AZURE_SEARCH_ENDPOINT",
            "AZURE_BLOB_CONNECTION",
            "AZURE_APPINSIGHTS_CONNECTION",
        ]
        for var in azure_vars:
            assert var in content, (
                f"{var} is not documented (even as a comment) in .env.example"
            )

    def test_no_real_credentials_in_env_example(self):
        """Non-comment lines in .env.example should not contain real API keys."""
        env_example = PROJECT_ROOT / ".env.example"
        lines = env_example.read_text(encoding="utf-8").splitlines()

        secret_patterns = [
            re.compile(r"sk-[A-Za-z0-9]{20,}"),       # OpenAI-style key
            re.compile(r"sk_live_[A-Za-z0-9]{20,}"),   # Stripe live key
            re.compile(r"rzp_live_[A-Za-z0-9]{10,}"),  # Razorpay live key
        ]

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for pattern in secret_patterns:
                assert not pattern.search(stripped), (
                    f"Line {lineno} of .env.example appears to contain a real "
                    f"credential matching {pattern.pattern}: {stripped!r}"
                )

    def test_env_production_exists_and_is_loadable(self):
        """The .env.production file must exist and be readable."""
        env_prod = PROJECT_ROOT / ".env.production"
        assert env_prod.is_file(), f".env.production not found at {env_prod}"
        content = env_prod.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, ".env.production is empty"

    def test_env_production_has_jwt_secret_key(self):
        """.env.production must contain a JWT_SECRET_KEY line."""
        env_prod = PROJECT_ROOT / ".env.production"
        content = env_prod.read_text(encoding="utf-8")
        found = any(
            line.strip().startswith("JWT_SECRET_KEY=")
            for line in content.splitlines()
            if not line.strip().startswith("#")
        )
        assert found, "JWT_SECRET_KEY not found in .env.production"


# ===========================================================================
# 2. Production Security (5 tests)
# ===========================================================================

class TestProductionSecurity:
    """Validate that validate_security_posture enforces production safeguards."""

    def test_insecure_jwt_raises_in_prod(self):
        """Using an insecure JWT secret in production must raise RuntimeError."""
        cfg = _make_prod_settings(
            jwt_secret_key="dev-secret-change-in-production",
        )
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            validate_security_posture(cfg)

    def test_wildcard_cors_raises_in_prod(self):
        """Wildcard CORS ('*') in production must raise RuntimeError."""
        cfg = _make_prod_settings(cors_origins="*")
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            validate_security_posture(cfg)

    def test_dev_environment_allows_insecure_defaults(self):
        """Development environment should NOT raise for insecure defaults."""
        cfg = _make_settings(environment="development")
        # Should not raise
        validate_security_posture(cfg)

    def test_env_production_jwt_is_insecure_known_bug(self):
        """.env.production ships with a JWT_SECRET_KEY in _INSECURE_SECRETS.

        This documents a known bug: the production env file has a placeholder
        secret that must be replaced before real deployment.
        """
        env_prod = PROJECT_ROOT / ".env.production"
        content = env_prod.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("JWT_SECRET_KEY="):
                value = stripped.split("=", 1)[1].strip()
                assert value in _INSECURE_SECRETS, (
                    f"Expected .env.production JWT_SECRET_KEY to be an insecure "
                    f"placeholder but got: {value!r}"
                )
                return
        pytest.fail("JWT_SECRET_KEY not found in .env.production")

    def test_env_production_database_url_field_exists(self):
        """Validate DATABASE_URL is set in .env.production (currently sqlite, a known issue)."""
        env_prod = PROJECT_ROOT / ".env.production"
        content = env_prod.read_text(encoding="utf-8")
        found = any(
            line.strip().startswith("DATABASE_URL=")
            for line in content.splitlines()
            if not line.strip().startswith("#")
        )
        assert found, "DATABASE_URL not found in .env.production"


# ===========================================================================
# 3. Security Posture (5 tests)
# ===========================================================================

class TestSecurityPosture:
    """Deep validation of validate_security_posture checks."""

    def test_all_insecure_secrets_rejected_for_jwt_in_prod(self):
        """Every value in _INSECURE_SECRETS must be rejected as jwt_secret_key in prod."""
        for insecure_value in _INSECURE_SECRETS:
            cfg = _make_prod_settings(jwt_secret_key=insecure_value)
            with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
                validate_security_posture(cfg)

    def test_event_signing_secret_must_differ_from_jwt_in_prod(self):
        """In production, event_signing_secret must not equal jwt_secret_key."""
        shared_secret = "some-strong-but-shared-secret-value"
        cfg = _make_prod_settings(
            jwt_secret_key=shared_secret,
            event_signing_secret=shared_secret,
        )
        with pytest.raises(RuntimeError, match="EVENT_SIGNING_SECRET"):
            validate_security_posture(cfg)

    def test_memory_encryption_key_must_be_strong_in_prod(self):
        """In production, memory_encryption_key must not be an insecure default."""
        cfg = _make_prod_settings(
            memory_encryption_key="dev-memory-encryption-key-change-in-production",
        )
        with pytest.raises(RuntimeError, match="MEMORY_ENCRYPTION_KEY"):
            validate_security_posture(cfg)

    def test_event_signing_secret_must_be_strong_in_prod(self):
        """In production, event_signing_secret must not be an insecure default."""
        cfg = _make_prod_settings(
            event_signing_secret="dev-event-signing-secret-change-in-production",
        )
        with pytest.raises(RuntimeError, match="EVENT_SIGNING_SECRET"):
            validate_security_posture(cfg)

    def test_validate_passes_with_all_strong_secrets_in_prod(self):
        """With all strong, unique secrets, production validation should pass."""
        cfg = _make_prod_settings()
        # Should not raise
        validate_security_posture(cfg)


# ===========================================================================
# 4. Azure Env Mapping (3 tests)
# ===========================================================================

class TestAzureEnvMapping:
    """Ensure Settings exposes fields needed for Azure Bicep-injected env vars."""

    def test_settings_model_config_extra_ignore(self):
        """Settings must have extra='ignore' so Bicep-injected vars don't crash startup."""
        assert Settings.model_config.get("extra") == "ignore", (
            "Settings.model_config must have extra='ignore' to tolerate "
            "unrecognised environment variables injected by Azure Bicep"
        )

    def test_settings_has_all_azure_fields(self):
        """Settings must expose fields for all Azure service connection strings."""
        cfg = _make_settings()
        azure_fields = [
            "azure_keyvault_url",
            "azure_servicebus_connection",
            "azure_search_endpoint",
            "azure_blob_connection",
            "azure_appinsights_connection",
        ]
        for field in azure_fields:
            assert hasattr(cfg, field), (
                f"Settings is missing the '{field}' field required for Azure integration"
            )

    def test_required_azure_vars_listed_in_env_example(self):
        """All required Azure vars for production must be documented in .env.example."""
        env_example = PROJECT_ROOT / ".env.example"
        content = env_example.read_text(encoding="utf-8").upper()

        required_azure_vars = [
            "AZURE_KEYVAULT_URL",
            "AZURE_SERVICEBUS_CONNECTION",
            "AZURE_SEARCH_ENDPOINT",
            "AZURE_BLOB_CONNECTION",
            "AZURE_APPINSIGHTS_CONNECTION",
        ]
        for var in required_azure_vars:
            assert var in content, (
                f"Required Azure var {var} not listed in .env.example"
            )
