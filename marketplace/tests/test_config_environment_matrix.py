"""Tests for config & environment management across the Settings matrix.

Agent UT — 25 tests across 5 describe blocks:
  1. Environment variable overrides (5 tests)
  2. Missing required variables & graceful defaults (5 tests)
  3. Type parsing from string env vars (5 tests)
  4. Feature flags & boolean switches (5 tests)
  5. Configuration reload, validation & environment switching (5 tests)

Uses ``monkeypatch`` for individual env-var overrides and
``unittest.mock.patch.dict(os.environ, ...)`` for bulk overrides.
Follows the patterns established in test_config_impact.py and
test_middleware_config.py.
"""

import os
from unittest.mock import patch

import pytest

from marketplace.config import Settings, settings, validate_security_posture


# ═══════════════════════════════════════════════════════════════════════════════
# Block 1: Environment Variable Overrides (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnvVarOverrides:
    """Verify that each key config value can be overridden via environment
    variables, and that precedence rules hold (env > default)."""

    def test_database_url_override(self, monkeypatch):
        """DATABASE_URL env var should override the default SQLite URL."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@db:5432/prod")
        s = Settings()
        assert s.database_url == "postgresql+asyncpg://user:pass@db:5432/prod"

    def test_jwt_secret_key_override(self, monkeypatch):
        """JWT_SECRET_KEY env var should override the dev default."""
        monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-prod-key-2026")
        s = Settings()
        assert s.jwt_secret_key == "super-secret-prod-key-2026"

    def test_cors_origins_override(self, monkeypatch):
        """CORS_ORIGINS env var should override the '*' default."""
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com,https://admin.example.com")
        s = Settings()
        assert s.cors_origins == "https://app.example.com,https://admin.example.com"

    def test_env_takes_precedence_over_default(self, monkeypatch):
        """Env var should always win over the hard-coded default value."""
        monkeypatch.setenv("MARKETPLACE_PORT", "9090")
        s = Settings()
        assert s.marketplace_port == 9090
        # Confirm the hard-coded default is 8000
        monkeypatch.delenv("MARKETPLACE_PORT", raising=False)
        s2 = Settings()
        assert s2.marketplace_port == 8000

    def test_empty_string_env_var_is_not_unset(self, monkeypatch):
        """An env var set to '' should produce an empty string, not the default.

        For string fields, pydantic-settings treats a set-but-empty env var
        as the empty string value, distinct from the variable being absent.
        """
        monkeypatch.setenv("OPENAI_API_KEY", "")
        s = Settings()
        assert s.openai_api_key == ""
        # Verify by setting a non-empty default scenario:
        monkeypatch.setenv("RAZORPAY_KEY_ID", "")
        s2 = Settings()
        assert s2.razorpay_key_id == ""


# ═══════════════════════════════════════════════════════════════════════════════
# Block 2: Missing Required Variables & Graceful Defaults (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMissingVarsAndDefaults:
    """Validate that the Settings class provides safe defaults when
    environment variables are absent, and that all fields have defaults
    (i.e., no required-without-default fields that would crash on init)."""

    def test_settings_loads_without_any_env_vars(self):
        """Settings() should instantiate successfully with zero env vars set.

        Every field in the Settings class has a default, so construction
        must never raise even in a completely bare environment.
        """
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            # Smoke-check a few critical fields have their defaults.
            assert s.database_url == "sqlite+aiosqlite:///./data/marketplace.db"
            assert s.jwt_secret_key == "dev-secret-change-in-production"
            assert s.payment_mode == "simulated"

    def test_missing_db_url_falls_back_to_sqlite(self, monkeypatch):
        """When DATABASE_URL is not set, default is local SQLite."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        s = Settings()
        assert "sqlite" in s.database_url

    def test_missing_openai_keys_default_to_empty(self, monkeypatch):
        """OpenAI keys should default to empty strings, not raise."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = Settings()
        assert s.openai_api_key == ""

    def test_missing_razorpay_keys_default_to_empty(self, monkeypatch):
        """Razorpay payment keys should default to empty strings, not raise."""
        monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
        monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
        s = Settings()
        assert s.razorpay_key_id == ""
        assert s.razorpay_key_secret == ""

    def test_all_fields_have_defaults(self):
        """Every field in Settings must have a default (no required-only fields).

        This guarantees the app can start in dev mode without a .env file.
        """
        # Build a Settings with an empty environment -- if any field lacks a
        # default, pydantic will raise ValidationError.
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            # Iterate all model fields and confirm they are populated.
            for field_name in Settings.model_fields:
                value = getattr(s, field_name)
                assert value is not None, (
                    f"Field '{field_name}' resolved to None -- expected a default"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Block 3: Type Parsing from String Env Vars (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypeParsing:
    """pydantic-settings must coerce string env vars into the correct
    Python types (int, float, bool).  These tests verify that coercion."""

    def test_string_to_int_marketplace_port(self, monkeypatch):
        """MARKETPLACE_PORT='3000' should parse to int 3000."""
        monkeypatch.setenv("MARKETPLACE_PORT", "3000")
        s = Settings()
        assert s.marketplace_port == 3000
        assert isinstance(s.marketplace_port, int)

    def test_string_to_float_platform_fee_pct(self, monkeypatch):
        """PLATFORM_FEE_PCT='0.05' should parse to float 0.05."""
        monkeypatch.setenv("PLATFORM_FEE_PCT", "0.05")
        s = Settings()
        assert s.platform_fee_pct == pytest.approx(0.05)
        assert isinstance(s.platform_fee_pct, float)

    def test_string_to_bool_mcp_enabled_true(self, monkeypatch):
        """MCP_ENABLED='true' should parse to bool True."""
        monkeypatch.setenv("MCP_ENABLED", "true")
        s = Settings()
        assert s.mcp_enabled is True

    def test_string_to_bool_mcp_enabled_false(self, monkeypatch):
        """MCP_ENABLED='false' should parse to bool False."""
        monkeypatch.setenv("MCP_ENABLED", "false")
        s = Settings()
        assert s.mcp_enabled is False

    def test_invalid_int_value_raises_validation_error(self, monkeypatch):
        """A non-numeric string for an int field should raise ValidationError."""
        monkeypatch.setenv("MARKETPLACE_PORT", "not-a-number")
        with pytest.raises(Exception):
            # pydantic raises ValidationError which is a subclass of ValueError
            Settings()


# ═══════════════════════════════════════════════════════════════════════════════
# Block 4: Feature Flags & Boolean Switches (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeatureFlags:
    """Test boolean feature flags, flag combinations, and behavior of the
    ``extra = "ignore"`` config for unknown fields."""

    def test_mcp_enabled_default_true(self):
        """MCP should be enabled by default."""
        s = Settings()
        assert s.mcp_enabled is True

    def test_mcp_disabled_via_env(self, monkeypatch):
        """Setting MCP_ENABLED=false should disable MCP."""
        monkeypatch.setenv("MCP_ENABLED", "false")
        s = Settings()
        assert s.mcp_enabled is False

    def test_flag_combination_mcp_off_payment_mainnet(self, monkeypatch):
        """Multiple flags can be set independently without interference."""
        monkeypatch.setenv("MCP_ENABLED", "false")
        monkeypatch.setenv("PAYMENT_MODE", "mainnet")
        s = Settings()
        assert s.mcp_enabled is False
        assert s.payment_mode == "mainnet"

    def test_unknown_env_vars_are_ignored(self, monkeypatch):
        """Settings uses extra='ignore', so unknown env vars should not raise.

        This is important for deployment environments that set many env vars
        unrelated to the marketplace.
        """
        monkeypatch.setenv("TOTALLY_UNKNOWN_VAR_XYZ", "some_value")
        monkeypatch.setenv("ANOTHER_RANDOM_SETTING", "42")
        # Should not raise
        s = Settings()
        # The unknown vars should not appear as attributes.
        assert not hasattr(s, "totally_unknown_var_xyz")
        assert not hasattr(s, "another_random_setting")

    def test_bool_flag_accepts_various_truthy_values(self, monkeypatch):
        """pydantic-settings accepts '1', 'true', 'True', 'yes' as truthy."""
        for truthy_val in ("1", "true", "True", "yes"):
            monkeypatch.setenv("MCP_ENABLED", truthy_val)
            s = Settings()
            assert s.mcp_enabled is True, (
                f"MCP_ENABLED='{truthy_val}' should parse as True"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Block 5: Configuration Reload, Validation & Environment Switching (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigReloadAndValidation:
    """Test config immutability (singleton behavior), validation on load,
    invalid config rejection, and environment-specific overrides for
    dev/staging/prod switching."""

    def test_singleton_settings_object_is_reusable(self):
        """The module-level ``settings`` object should be a valid Settings instance."""
        assert isinstance(settings, Settings)
        # Reading an attribute should work without re-instantiation.
        assert settings.marketplace_host == "0.0.0.0"
        assert settings.platform_fee_pct == 0.02

    def test_new_settings_instance_independent_of_singleton(self, monkeypatch):
        """Creating a new Settings() should be independent of the module-level singleton.

        The singleton is created at import time; a fresh Settings() call
        should pick up the current environment, not the cached singleton state.
        """
        monkeypatch.setenv("PLATFORM_FEE_PCT", "0.05")
        fresh = Settings()
        assert fresh.platform_fee_pct == 0.05
        # The module-level singleton should still have the original value
        # (it was created before the monkeypatch).
        assert settings.platform_fee_pct == 0.02

    def test_invalid_float_value_raises_on_load(self, monkeypatch):
        """A non-numeric value for a float field should raise on instantiation."""
        monkeypatch.setenv("PLATFORM_FEE_PCT", "not-a-float")
        with pytest.raises(Exception):
            Settings()

    def test_environment_switch_dev_to_prod_overrides(self, monkeypatch):
        """Simulating a dev-to-prod switch by overriding multiple values at once.

        In production, operators would set DATABASE_URL, JWT_SECRET_KEY,
        PAYMENT_MODE, and other critical fields via environment variables.
        """
        prod_env = {
            "DATABASE_URL": "postgresql+asyncpg://prod:secret@db.internal:5432/marketplace",
            "JWT_SECRET_KEY": "prod-256-bit-secret-key-here",
            "PAYMENT_MODE": "mainnet",
            "MCP_ENABLED": "true",
            "CORS_ORIGINS": "https://marketplace.agentchains.io",
            "REST_RATE_LIMIT_AUTHENTICATED": "200",
            "REST_RATE_LIMIT_ANONYMOUS": "10",
        }
        for key, val in prod_env.items():
            monkeypatch.setenv(key, val)

        s = Settings()
        assert s.database_url == prod_env["DATABASE_URL"]
        assert s.jwt_secret_key == prod_env["JWT_SECRET_KEY"]
        assert s.payment_mode == "mainnet"
        assert s.mcp_enabled is True
        assert s.cors_origins == "https://marketplace.agentchains.io"
        assert s.rest_rate_limit_authenticated == 200
        assert s.rest_rate_limit_anonymous == 10

    def test_bulk_env_override_with_patch_dict(self):
        """Using patch.dict(os.environ) for bulk override should work.

        This validates that Settings() reads from os.environ at construction
        time, which is important for test isolation and deployment tooling.
        """
        staging_env = {
            "DATABASE_URL": "postgresql+asyncpg://staging:pw@db-staging:5432/mp",
            "PAYMENT_MODE": "testnet",
            "X402_NETWORK": "base-sepolia",
            "JWT_EXPIRE_HOURS": "48",
            "CDN_HOT_CACHE_MAX_BYTES": "134217728",  # 128 MB
        }
        with patch.dict(os.environ, staging_env, clear=False):
            s = Settings()
            assert s.database_url == staging_env["DATABASE_URL"]
            assert s.payment_mode == "testnet"
            assert s.x402_network == "base-sepolia"
            assert s.jwt_expire_hours == 48
            assert s.cdn_hot_cache_max_bytes == 134217728  # 128 MB


class TestProductionSecurityGuardrails:
    """Security-first production guardrail validation."""

    def test_prod_rejects_default_event_signing_secret(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "super-strong-jwt-secret-2026",
                "EVENT_SIGNING_SECRET": "dev-event-signing-secret-change-in-production",
                "MEMORY_ENCRYPTION_KEY": "super-strong-memory-key-2026",
                "CORS_ORIGINS": "https://app.example.com",
            },
            clear=False,
        ):
            with pytest.raises(RuntimeError):
                validate_security_posture(Settings())

    def test_prod_rejects_equal_event_and_jwt_secret(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "same-secret-for-both",
                "EVENT_SIGNING_SECRET": "same-secret-for-both",
                "MEMORY_ENCRYPTION_KEY": "super-strong-memory-key-2026",
                "CORS_ORIGINS": "https://app.example.com",
            },
            clear=False,
        ):
            with pytest.raises(RuntimeError):
                validate_security_posture(Settings())

    def test_prod_rejects_wildcard_cors(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "super-strong-jwt-secret-2026",
                "EVENT_SIGNING_SECRET": "super-strong-event-secret-2026",
                "MEMORY_ENCRYPTION_KEY": "super-strong-memory-key-2026",
                "CORS_ORIGINS": "*",
            },
            clear=False,
        ):
            with pytest.raises(RuntimeError):
                validate_security_posture(Settings())
