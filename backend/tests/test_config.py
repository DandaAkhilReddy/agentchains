"""Tests for application configuration, app startup, and routing."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Mock SDK modules before any app imports
for _mod in [
    "firebase_admin", "firebase_admin.auth",
    "openai",
    "pdfplumber",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


# ---------------------------------------------------------------------------
# 1. Config loads with all required fields
# ---------------------------------------------------------------------------

class TestConfigFields:
    """Verify that Settings declares every expected field."""

    def test_settings_has_all_required_fields(self):
        from app.config import Settings

        expected_fields = [
            "database_url",
            "openai_api_key",
            "openai_model",
            "openai_embedding_model",
            "upload_dir",
            "firebase_project_id",
            "firebase_service_account_base64",
            "environment",
            "log_level",
            "cors_origins",
        ]
        model_fields = Settings.model_fields
        for field_name in expected_fields:
            assert field_name in model_fields, (
                f"Settings is missing expected field: {field_name}"
            )

    def test_settings_can_be_instantiated_without_env(self):
        """Settings should load with defaults even when no env vars are set."""
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            s = Settings(_env_file=None)
        # Should not raise — all fields have defaults
        assert isinstance(s, Settings)


# ---------------------------------------------------------------------------
# 2. Default values are correct
# ---------------------------------------------------------------------------

class TestConfigDefaults:
    """Verify default values when no environment variables are set."""

    def _make_settings(self, **overrides):
        from app.config import Settings
        with patch.dict("os.environ", {}, clear=True):
            return Settings(_env_file=None, **overrides)

    def test_environment_defaults_to_development(self):
        s = self._make_settings()
        assert s.environment == "development"

    def test_log_level_defaults_to_info(self):
        s = self._make_settings()
        assert s.log_level == "INFO"

    def test_openai_model_default(self):
        s = self._make_settings()
        assert s.openai_model == "gpt-4o-mini"

    def test_openai_embedding_model_default(self):
        s = self._make_settings()
        assert s.openai_embedding_model == "text-embedding-3-small"

    def test_upload_dir_default(self):
        s = self._make_settings()
        assert s.upload_dir == "./uploads"

    def test_cors_origins_default(self):
        s = self._make_settings()
        assert s.cors_origins == "http://localhost:5173"


# ---------------------------------------------------------------------------
# 3. CORS origins parsing from comma-separated string
# ---------------------------------------------------------------------------

class TestCorsOriginsParsing:
    """The app splits cors_origins on commas to build the allow_origins list."""

    def test_single_origin_from_settings(self):
        from app.config import Settings
        with patch.dict("os.environ", {"CORS_ORIGINS": "https://example.com"}, clear=True):
            s = Settings(_env_file=None)
        parsed = [o.strip() for o in s.cors_origins.split(",")]
        assert parsed == ["https://example.com"]

    def test_multiple_origins_from_settings(self):
        from app.config import Settings
        with patch.dict("os.environ", {"CORS_ORIGINS": "https://a.com,https://b.com,https://c.com"}, clear=True):
            s = Settings(_env_file=None)
        parsed = [o.strip() for o in s.cors_origins.split(",")]
        assert parsed == ["https://a.com", "https://b.com", "https://c.com"]

    def test_origins_with_whitespace_from_settings(self):
        from app.config import Settings
        with patch.dict("os.environ", {"CORS_ORIGINS": " https://a.com , https://b.com "}, clear=True):
            s = Settings(_env_file=None)
        parsed = [o.strip() for o in s.cors_origins.split(",")]
        assert parsed == ["https://a.com", "https://b.com"]

    def test_cors_origins_from_env(self):
        from app.config import Settings

        env = {"CORS_ORIGINS": "http://localhost:3000,http://localhost:5173"}
        with patch.dict("os.environ", env, clear=True):
            s = Settings(_env_file=None)
        parsed = [o.strip() for o in s.cors_origins.split(",")]
        assert parsed == ["http://localhost:3000", "http://localhost:5173"]


# ---------------------------------------------------------------------------
# 4. Database URL format validation
# ---------------------------------------------------------------------------

class TestDatabaseUrlFormat:
    """Verify database_url is accepted from env and defaults to empty string."""

    def test_database_url_defaults_to_empty(self):
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            s = Settings(_env_file=None)
        assert s.database_url == ""

    def test_database_url_from_env(self):
        from app.config import Settings

        db_url = "postgresql+asyncpg://user:pass@host:5432/dbname?ssl=require"
        with patch.dict("os.environ", {"DATABASE_URL": db_url}, clear=True):
            s = Settings(_env_file=None)
        assert s.database_url == db_url

    def test_database_url_contains_asyncpg_driver(self):
        """Typical production URL loaded via Settings should use the asyncpg driver."""
        from app.config import Settings
        db_url = "postgresql+asyncpg://u:p@host:5432/db?ssl=require"
        with patch.dict("os.environ", {"DATABASE_URL": db_url}, clear=True):
            s = Settings(_env_file=None)
        assert "+asyncpg" in s.database_url

    def test_database_url_uses_ssl_require(self):
        """asyncpg requires ?ssl=require, NOT ?sslmode=require."""
        from app.config import Settings
        db_url = "postgresql+asyncpg://u:p@host:5432/db?ssl=require"
        with patch.dict("os.environ", {"DATABASE_URL": db_url}, clear=True):
            s = Settings(_env_file=None)
        assert "ssl=require" in s.database_url
        assert "sslmode=" not in s.database_url


# ---------------------------------------------------------------------------
# 5. OpenAI fields default to empty
# ---------------------------------------------------------------------------

class TestOptionalOpenAIDefaults:
    """OpenAI credentials should default to empty strings."""

    def test_openai_fields_default_to_empty(self):
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            s = Settings(_env_file=None)

        assert s.openai_api_key == ""

    def test_firebase_fields_default_to_empty(self):
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            s = Settings(_env_file=None)

        assert s.firebase_project_id == ""
        assert s.firebase_service_account_base64 == ""

    def test_openai_fields_set_from_env(self):
        from app.config import Settings

        env = {
            "OPENAI_API_KEY": "sk-test-key-123",
        }
        with patch.dict("os.environ", env, clear=True):
            s = Settings(_env_file=None)

        assert s.openai_api_key == "sk-test-key-123"


# ---------------------------------------------------------------------------
# 6. Admin emails list is correct
# ---------------------------------------------------------------------------

class TestAdminEmails:
    """Verify the ADMIN_EMAILS set in deps contains the expected addresses."""

    def test_admin_emails_contains_expected(self):
        from app.api.deps import ADMIN_EMAILS

        assert "areddy@hhamedicine.com" in ADMIN_EMAILS
        assert "admin@test.com" in ADMIN_EMAILS

    def test_admin_emails_is_a_set(self):
        from app.api.deps import ADMIN_EMAILS

        assert isinstance(ADMIN_EMAILS, set)

    def test_admin_emails_count(self):
        from app.api.deps import ADMIN_EMAILS

        assert len(ADMIN_EMAILS) == 2

    def test_non_admin_not_in_list(self):
        from app.api.deps import ADMIN_EMAILS

        assert "random@example.com" not in ADMIN_EMAILS


# ---------------------------------------------------------------------------
# 7. App health endpoint returns 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestHealthEndpoint:
    """Verify /api/health returns the expected response."""

    async def test_health_returns_200(self, async_client: AsyncClient):
        resp = await async_client.get("/api/health")
        assert resp.status_code == 200

    async def test_health_body_contains_status(self, async_client: AsyncClient):
        resp = await async_client.get("/api/health")
        body = resp.json()
        assert body["status"] == "healthy"

    async def test_health_body_contains_version(self, async_client: AsyncClient):
        resp = await async_client.get("/api/health")
        body = resp.json()
        assert body["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# 8. App registers all expected routers
# ---------------------------------------------------------------------------

class TestRouterRegistration:
    """The FastAPI app must include routers for every domain module."""

    EXPECTED_PREFIXES = [
        "/api/auth",
        "/api/loans",
        "/api/optimizer",
        "/api/scanner",
        "/api/emi",
        "/api/ai",
        "/api/user",
        "/api/admin",
        "/api/reviews",
    ]

    def _get_registered_paths(self):
        from app.main import app
        return [route.path for route in app.routes]

    def test_all_router_prefixes_are_registered(self):
        registered_paths = self._get_registered_paths()
        for prefix in self.EXPECTED_PREFIXES:
            matches = [p for p in registered_paths if p.startswith(prefix)]
            assert matches, (
                f"No routes registered under prefix '{prefix}'. "
                f"Registered paths: {registered_paths}"
            )

    def test_health_endpoint_is_registered(self):
        registered_paths = self._get_registered_paths()
        assert "/api/health" in registered_paths

    def test_expected_router_count(self):
        """There should be at least 9 routers (auth, loans, optimizer,
        scanner, emi, ai_insights, user, admin, reviews)."""
        from app.main import app

        # Count unique prefixes from included routers
        prefixes_found = set()
        for route in app.routes:
            path = getattr(route, "path", "")
            for prefix in self.EXPECTED_PREFIXES:
                if path.startswith(prefix):
                    prefixes_found.add(prefix)
        assert len(prefixes_found) >= 9


# ---------------------------------------------------------------------------
# 9. OpenAPI schema is generated successfully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOpenAPISchema:
    """FastAPI must generate a valid OpenAPI schema."""

    async def test_openapi_json_returns_200(self, async_client: AsyncClient):
        resp = await async_client.get("/openapi.json")
        assert resp.status_code == 200

    async def test_openapi_has_info(self, async_client: AsyncClient):
        resp = await async_client.get("/openapi.json")
        schema = resp.json()
        assert "info" in schema
        assert schema["info"]["title"] == "Indian Loan Analyzer API"
        assert schema["info"]["version"] == "0.1.0"

    async def test_openapi_has_paths(self, async_client: AsyncClient):
        resp = await async_client.get("/openapi.json")
        schema = resp.json()
        assert "paths" in schema
        assert len(schema["paths"]) > 0

    async def test_openapi_includes_health(self, async_client: AsyncClient):
        resp = await async_client.get("/openapi.json")
        schema = resp.json()
        assert "/api/health" in schema["paths"]

    async def test_openapi_schema_object_available(self):
        """app.openapi() should return the schema dict directly."""
        from app.main import app

        schema = app.openapi()
        assert isinstance(schema, dict)
        assert schema["info"]["title"] == "Indian Loan Analyzer API"
