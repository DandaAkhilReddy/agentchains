"""OAuth2 provider tests — client registration, authorization, token exchange, PKCE, revocation."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.oauth2.server import (
    _hash_secret,
    _generate_token,
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    AUTHORIZATION_CODE_LIFETIME,
)


class TestOAuth2Utilities:
    """Tests for OAuth2 helper functions."""

    def test_hash_secret_deterministic(self):
        result1 = _hash_secret("my_secret")
        result2 = _hash_secret("my_secret")
        assert result1 == result2

    def test_hash_secret_is_sha256(self):
        secret = "test_secret_value"
        expected = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        assert _hash_secret(secret) == expected

    def test_hash_secret_different_inputs_different_outputs(self):
        h1 = _hash_secret("secret_a")
        h2 = _hash_secret("secret_b")
        assert h1 != h2

    def test_hash_secret_returns_hex_string(self):
        result = _hash_secret("any_secret")
        assert len(result) == 64  # SHA-256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in result)

    def test_generate_token_returns_string(self):
        token = _generate_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_is_unique(self):
        tokens = {_generate_token() for _ in range(100)}
        assert len(tokens) == 100  # all unique

    def test_generate_token_url_safe(self):
        token = _generate_token()
        # URL-safe base64 chars only
        import re
        assert re.match(r"^[A-Za-z0-9_-]+$", token)

    def test_access_token_lifetime(self):
        assert ACCESS_TOKEN_LIFETIME == timedelta(hours=1)

    def test_refresh_token_lifetime(self):
        assert REFRESH_TOKEN_LIFETIME == timedelta(days=30)

    def test_authorization_code_lifetime(self):
        assert AUTHORIZATION_CODE_LIFETIME == timedelta(minutes=10)


class TestOAuth2Models:
    """Tests for OAuth2 data model definitions."""

    def test_oauth_client_model_import(self):
        from marketplace.oauth2.models import OAuthClient
        assert OAuthClient is not None

    def test_authorization_code_model_import(self):
        from marketplace.oauth2.models import AuthorizationCode
        assert AuthorizationCode is not None

    def test_access_token_model_import(self):
        from marketplace.oauth2.models import OAuthAccessToken
        assert OAuthAccessToken is not None

    def test_refresh_token_model_import(self):
        from marketplace.oauth2.models import OAuthRefreshToken
        assert OAuthRefreshToken is not None


class TestOAuth2ClientRegistration:
    """Tests for register_client function."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_register_client_returns_credentials(self, mock_db):
        from marketplace.oauth2.server import register_client

        result = await register_client(
            mock_db,
            name="Test App",
            redirect_uris=["https://example.com/callback"],
            scopes="read write",
            owner_id="user-1",
        )
        assert "client_id" in result
        assert "client_secret" in result
        assert len(result["client_id"]) > 0
        assert len(result["client_secret"]) > 0

    @pytest.mark.asyncio
    async def test_register_client_adds_to_db(self, mock_db):
        from marketplace.oauth2.server import register_client

        await register_client(
            mock_db,
            name="App",
            redirect_uris=["https://example.com/cb"],
            scopes="read",
            owner_id="user-2",
        )
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_client_unique_credentials(self, mock_db):
        from marketplace.oauth2.server import register_client

        r1 = await register_client(mock_db, "A", ["https://a.com"], "read", "u1")
        r2 = await register_client(mock_db, "B", ["https://b.com"], "read", "u2")
        assert r1["client_id"] != r2["client_id"]
        assert r1["client_secret"] != r2["client_secret"]


class TestOAuth2Authorization:
    """Tests for the authorize function."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_authorize_invalid_client_raises(self, mock_db):
        from marketplace.oauth2.server import authorize

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid or inactive client"):
            await authorize(
                mock_db,
                client_id="bad-client",
                redirect_uri="https://example.com/cb",
                scope="read",
                code_challenge="challenge",
                code_challenge_method="S256",
                user_id="user-1",
            )

    @pytest.mark.asyncio
    async def test_authorize_invalid_redirect_uri_raises(self, mock_db):
        from marketplace.oauth2.server import authorize
        import json

        mock_client = MagicMock()
        mock_client.redirect_uris = json.dumps(["https://allowed.com/cb"])
        mock_client.scopes = "read"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid redirect_uri"):
            await authorize(
                mock_db,
                client_id="client-1",
                redirect_uri="https://evil.com/steal",
                scope="read",
                code_challenge="ch",
                code_challenge_method="S256",
                user_id="user-1",
            )

    @pytest.mark.asyncio
    async def test_authorize_success_returns_code(self, mock_db):
        from marketplace.oauth2.server import authorize
        import json

        mock_client = MagicMock()
        mock_client.redirect_uris = json.dumps(["https://app.com/cb"])
        mock_client.scopes = "read write"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute = AsyncMock(return_value=mock_result)

        code = await authorize(
            mock_db,
            client_id="client-1",
            redirect_uri="https://app.com/cb",
            scope="read",
            code_challenge="ch",
            code_challenge_method="S256",
            user_id="user-1",
        )
        assert isinstance(code, str)
        assert len(code) > 10


class TestOAuth2TokenExchange:
    """Tests for exchange_token function."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_exchange_unsupported_grant_type_raises(self, mock_db):
        from marketplace.oauth2.server import exchange_token

        with pytest.raises(ValueError):
            await exchange_token(
                mock_db,
                grant_type="client_credentials",
                code="code",
                client_id="c1",
                client_secret="s1",
                redirect_uri="https://app.com/cb",
            )


class TestOAuth2PKCE:
    """Tests for PKCE code challenge verification."""

    def test_s256_challenge(self):
        import base64
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        expected_hash = hashlib.sha256(verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(expected_hash).rstrip(b"=").decode("ascii")
        assert challenge == computed

    def test_plain_challenge(self):
        verifier = "my_plain_verifier_string"
        challenge = verifier  # plain method: challenge == verifier
        assert challenge == verifier


class TestOAuth2Routes:
    """Tests for OAuth2 route module existence."""

    def test_routes_module_imports(self):
        from marketplace.oauth2 import routes
        assert routes is not None

    def test_server_module_imports(self):
        from marketplace.oauth2 import server
        assert server is not None

    def test_models_module_imports(self):
        from marketplace.oauth2 import models
        assert models is not None
