"""Comprehensive tests for marketplace/oauth2/server.py and marketplace/schemas/common.py.

Covers:
- OAuth2 server service layer via real DB (db fixture)
- OAuth2 API routes via HTTP (client fixture)
- Common schema Pydantic validation
- OAuth2Server class wrapper
- Full end-to-end authorization code flow with and without PKCE
- Refresh token rotation
- Token revocation (access and refresh)
- Userinfo endpoint
- Error paths for every public function
"""

import base64
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import create_access_token

from marketplace.oauth2.models import (
    AuthorizationCode,
    OAuthAccessToken,
    OAuthClient,
    OAuthRefreshToken,
)
from marketplace.oauth2.server import (
    ACCESS_TOKEN_LIFETIME,
    AUTHORIZATION_CODE_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    OAuth2Server,
    _hash_secret,
    _verify_pkce,
    authorize,
    exchange_token,
    get_userinfo,
    refresh_access_token,
    register_client,
    revoke_token,
    token_exchange,
    validate_access_token,
)
from marketplace.schemas.common import (
    CacheStats,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
)
from marketplace.tests.conftest import _new_id


# ===========================================================================
# Helpers
# ===========================================================================


def _make_pkce_pair(verifier: str | None = None):
    """Return (verifier, challenge) for S256 PKCE."""
    verifier = verifier or secrets.token_urlsafe(43)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


async def _seed_client(db: AsyncSession, redirect_uris=None, scopes="read write"):
    """Insert a real OAuthClient row and return (client row, plain_secret)."""
    plain_secret = secrets.token_urlsafe(48)
    client = OAuthClient(
        id=_new_id(),
        client_id=secrets.token_urlsafe(32),
        client_secret_hash=_hash_secret(plain_secret),
        name="Test Client",
        redirect_uris=json.dumps(redirect_uris or ["https://app.example.com/cb"]),
        scopes=scopes,
        grant_types="authorization_code",
        owner_id=_new_id(),
        status="active",
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client, plain_secret


async def _seed_access_token(
    db: AsyncSession,
    client_id: str,
    user_id: str,
    scope: str = "read",
    expired: bool = False,
    revoked: bool = False,
):
    """Insert a real OAuthAccessToken row and return it."""
    now = datetime.now(timezone.utc)
    expires_at = now - timedelta(hours=2) if expired else now + ACCESS_TOKEN_LIFETIME
    at = OAuthAccessToken(
        id=_new_id(),
        client_id=client_id,
        user_id=user_id,
        token=secrets.token_urlsafe(48),
        scope=scope,
        expires_at=expires_at,
        revoked=revoked,
        created_at=now,
    )
    db.add(at)
    await db.commit()
    await db.refresh(at)
    return at


async def _seed_refresh_token(
    db: AsyncSession,
    access_token_id: str,
    client_id: str,
    user_id: str,
    expired: bool = False,
    revoked: bool = False,
):
    """Insert a real OAuthRefreshToken row and return it."""
    now = datetime.now(timezone.utc)
    expires_at = now - timedelta(days=1) if expired else now + REFRESH_TOKEN_LIFETIME
    rt = OAuthRefreshToken(
        id=_new_id(),
        token=secrets.token_urlsafe(48),
        access_token_id=access_token_id,
        client_id=client_id,
        user_id=user_id,
        expires_at=expires_at,
        revoked=revoked,
        created_at=now,
    )
    db.add(rt)
    await db.commit()
    await db.refresh(rt)
    return rt


# ===========================================================================
# Section 1: common.py — Pydantic schema validation
# ===========================================================================


class TestPaginatedResponse:
    """PaginatedResponse must carry total, page, and page_size."""

    def test_constructs_with_all_fields(self):
        resp = PaginatedResponse(total=100, page=2, page_size=25)
        assert resp.total == 100
        assert resp.page == 2
        assert resp.page_size == 25

    def test_zero_values_accepted(self):
        resp = PaginatedResponse(total=0, page=1, page_size=10)
        assert resp.total == 0

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            PaginatedResponse(total=10, page=1)  # page_size missing

    def test_json_roundtrip(self):
        resp = PaginatedResponse(total=5, page=1, page_size=5)
        dumped = resp.model_dump()
        assert dumped == {"total": 5, "page": 1, "page_size": 5}


class TestErrorResponse:
    """ErrorResponse wraps a detail string."""

    def test_constructs_with_detail(self):
        err = ErrorResponse(detail="Something went wrong")
        assert err.detail == "Something went wrong"

    def test_missing_detail_raises(self):
        with pytest.raises(ValidationError):
            ErrorResponse()

    def test_empty_detail_accepted(self):
        err = ErrorResponse(detail="")
        assert err.detail == ""


class TestCacheStats:
    """CacheStats holds three dict fields."""

    def test_constructs_with_all_dicts(self):
        stats = CacheStats(listings={"hits": 10}, content={"hits": 5}, agents={"hits": 2})
        assert stats.listings["hits"] == 10
        assert stats.content["hits"] == 5
        assert stats.agents["hits"] == 2

    def test_empty_dicts_accepted(self):
        stats = CacheStats(listings={}, content={}, agents={})
        assert stats.listings == {}

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            CacheStats(listings={}, content={})  # agents missing


class TestHealthResponse:
    """HealthResponse has required fields and one optional field."""

    def test_constructs_without_cache_stats(self):
        resp = HealthResponse(
            status="ok",
            version="2.0.0",
            agents_count=42,
            listings_count=100,
            transactions_count=7,
        )
        assert resp.status == "ok"
        assert resp.cache_stats is None

    def test_constructs_with_cache_stats(self):
        cs = CacheStats(listings={"hits": 1}, content={"hits": 2}, agents={"hits": 3})
        resp = HealthResponse(
            status="ok",
            version="1.0.0",
            agents_count=1,
            listings_count=2,
            transactions_count=3,
            cache_stats=cs,
        )
        assert resp.cache_stats is not None
        assert resp.cache_stats.listings["hits"] == 1

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            HealthResponse(status="ok", version="1.0.0")  # counts missing

    def test_zero_counts_accepted(self):
        resp = HealthResponse(
            status="degraded",
            version="0.1.0",
            agents_count=0,
            listings_count=0,
            transactions_count=0,
        )
        assert resp.agents_count == 0
        assert resp.listings_count == 0
        assert resp.transactions_count == 0


# ===========================================================================
# Section 2: server.py — unit tests (mock DB)
# ===========================================================================


class TestHashSecret:
    """_hash_secret is a deterministic SHA-256 hex digest."""

    def test_deterministic(self):
        assert _hash_secret("abc") == _hash_secret("abc")

    def test_length_is_64(self):
        assert len(_hash_secret("anything")) == 64

    def test_only_hex_chars(self):
        h = _hash_secret("test")
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_inputs_differ(self):
        assert _hash_secret("a") != _hash_secret("b")

    def test_matches_sha256(self):
        secret = "my_oauth_secret"
        expected = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        assert _hash_secret(secret) == expected


class TestVerifyPkce:
    """_verify_pkce implements S256 only; plain is rejected."""

    def test_s256_correct_verifier(self):
        verifier, challenge = _make_pkce_pair()
        assert _verify_pkce(challenge, "S256", verifier) is True

    def test_s256_wrong_verifier(self):
        verifier, challenge = _make_pkce_pair()
        assert _verify_pkce(challenge, "S256", verifier + "x") is False

    def test_plain_method_rejected(self):
        """plain is insecure; the server rejects it unconditionally."""
        assert _verify_pkce("my_verifier", "plain", "my_verifier") is False

    def test_unknown_method_rejected(self):
        assert _verify_pkce("ch", "RS256", "v") is False

    def test_s256_empty_verifier_matches_empty_challenge(self):
        verifier = ""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert _verify_pkce(challenge, "S256", "") is True

    def test_s256_challenge_mismatch(self):
        _, challenge = _make_pkce_pair("verifier_A")
        assert _verify_pkce(challenge, "S256", "verifier_B") is False


class TestRegisterClientMock:
    """register_client with a mocked DB."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    async def test_returns_client_id_and_secret(self, mock_db):
        result = await register_client(
            mock_db,
            name="My App",
            redirect_uris=["https://example.com/cb"],
            scopes="read write",
            owner_id="owner-1",
        )
        assert "client_id" in result
        assert "client_secret" in result
        assert len(result["client_id"]) > 20
        assert len(result["client_secret"]) > 30

    async def test_adds_and_commits(self, mock_db):
        await register_client(
            mock_db,
            name="App",
            redirect_uris=["https://app.io/cb"],
            scopes="read",
            owner_id="owner-2",
        )
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    async def test_credentials_are_unique(self, mock_db):
        r1 = await register_client(mock_db, "A", ["https://a.com"], "read", "u1")
        r2 = await register_client(mock_db, "B", ["https://b.com"], "read", "u2")
        assert r1["client_id"] != r2["client_id"]
        assert r1["client_secret"] != r2["client_secret"]

    async def test_secret_not_stored_in_plain(self, mock_db):
        """The plain secret returned must not equal what is stored (it's hashed)."""
        captured = {}

        def capture_add(obj):
            if isinstance(obj, OAuthClient):
                captured["hash"] = obj.client_secret_hash

        mock_db.add.side_effect = capture_add
        result = await register_client(
            mock_db, "Z", ["https://z.io"], "read", "owner-z"
        )
        # The stored hash must differ from the raw secret
        assert captured.get("hash") != result["client_secret"]
        # But hashing the secret must match the stored hash
        assert captured["hash"] == _hash_secret(result["client_secret"])


class TestAuthorizeMock:
    """authorize() with a mocked DB."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    def _make_mock_client(self, redirect_uris=None, scopes="read"):
        client = MagicMock()
        client.redirect_uris = json.dumps(redirect_uris or ["https://app.com/cb"])
        client.scopes = scopes
        return client

    async def test_invalid_client_raises(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid or inactive client"):
            await authorize(
                mock_db,
                client_id="bad",
                redirect_uri="https://app.com/cb",
                scope="read",
                code_challenge="ch",
                code_challenge_method="S256",
                user_id="user-1",
            )

    async def test_invalid_redirect_uri_raises(self, mock_db):
        mock_client = self._make_mock_client(["https://allowed.com/cb"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid redirect_uri"):
            await authorize(
                mock_db,
                client_id="c1",
                redirect_uri="https://evil.com/steal",
                scope="read",
                code_challenge="ch",
                code_challenge_method="S256",
                user_id="user-1",
            )

    async def test_success_returns_code_string(self, mock_db):
        mock_client = self._make_mock_client()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute = AsyncMock(return_value=mock_result)

        code = await authorize(
            mock_db,
            client_id="c1",
            redirect_uri="https://app.com/cb",
            scope="read",
            code_challenge="ch",
            code_challenge_method="S256",
            user_id="user-1",
        )
        assert isinstance(code, str)
        assert len(code) > 20

    async def test_scope_falls_back_to_client_scopes(self, mock_db):
        """When scope is empty, the client's scopes should be used."""
        mock_client = self._make_mock_client(scopes="admin write")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute = AsyncMock(return_value=mock_result)

        captured = {}

        def capture_add(obj):
            if isinstance(obj, AuthorizationCode):
                captured["scope"] = obj.scope

        mock_db.add.side_effect = capture_add

        await authorize(
            mock_db,
            client_id="c1",
            redirect_uri="https://app.com/cb",
            scope="",  # empty → fall back
            code_challenge="",
            code_challenge_method="",
            user_id="user-1",
        )
        assert captured.get("scope") == "admin write"


class TestExchangeTokenMock:
    """exchange_token() with a mocked DB — authorization_code grant."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    async def test_unsupported_grant_type_raises(self, mock_db):
        with pytest.raises(ValueError, match="Unsupported grant_type"):
            await exchange_token(
                mock_db,
                grant_type="client_credentials",
                code="code",
                client_id="c1",
                client_secret="s1",
                redirect_uri="https://app.com/cb",
            )

    async def test_missing_code_raises(self, mock_db):
        with pytest.raises(ValueError, match="required"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="",
                client_id="c1",
                client_secret="s1",
                redirect_uri="https://app.com/cb",
            )

    async def test_missing_client_id_raises(self, mock_db):
        with pytest.raises(ValueError, match="required"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="code123",
                client_id="",
                client_secret="s1",
                redirect_uri="https://app.com/cb",
            )

    async def test_invalid_code_raises(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid authorization code"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="garbage",
                client_id="c1",
                client_secret="s1",
                redirect_uri="https://app.com/cb",
            )

    async def test_used_code_raises(self, mock_db):
        mock_code = MagicMock()
        mock_code.used = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_code
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="already been used"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="used_code",
                client_id="c1",
                client_secret="s1",
                redirect_uri="https://app.com/cb",
            )

    async def test_expired_code_raises(self, mock_db):
        mock_code = MagicMock()
        mock_code.used = False
        mock_code.expires_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_code
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="expired"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="expired_code",
                client_id="c1",
                client_secret="s1",
                redirect_uri="https://app.com/cb",
            )

    async def test_client_id_mismatch_raises(self, mock_db):
        mock_code = MagicMock()
        mock_code.used = False
        mock_code.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_code.client_id = "correct_client"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_code
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="mismatch"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="code",
                client_id="wrong_client",
                client_secret="s1",
                redirect_uri="https://app.com/cb",
            )

    async def test_redirect_uri_mismatch_raises(self, mock_db):
        mock_code = MagicMock()
        mock_code.used = False
        mock_code.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_code.client_id = "c1"
        mock_code.redirect_uri = "https://app.com/cb"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_code
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="mismatch"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="code",
                client_id="c1",
                client_secret="s1",
                redirect_uri="https://evil.com/steal",
            )

    async def test_pkce_missing_verifier_raises(self, mock_db):
        """When code_challenge was set, a missing verifier must fail."""
        mock_code = MagicMock()
        mock_code.used = False
        mock_code.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_code.client_id = "c1"
        mock_code.redirect_uri = "https://app.com/cb"
        mock_code.code_challenge = "some_challenge_value"
        mock_code.code_challenge_method = "S256"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_code
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="code_verifier"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="code",
                client_id="c1",
                client_secret="",
                redirect_uri="https://app.com/cb",
                code_verifier="",
            )

    async def test_pkce_wrong_verifier_raises(self, mock_db):
        verifier, challenge = _make_pkce_pair()
        mock_code = MagicMock()
        mock_code.used = False
        mock_code.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_code.client_id = "c1"
        mock_code.redirect_uri = "https://app.com/cb"
        mock_code.code_challenge = challenge
        mock_code.code_challenge_method = "S256"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_code
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="PKCE verification failed"):
            await exchange_token(
                mock_db,
                grant_type="authorization_code",
                code="code",
                client_id="c1",
                client_secret="",
                redirect_uri="https://app.com/cb",
                code_verifier="wrong_verifier",
            )


class TestRefreshTokenMock:
    """exchange_token() with a mocked DB — refresh_token grant."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    async def test_missing_refresh_token_raises(self, mock_db):
        with pytest.raises(ValueError, match="required"):
            await exchange_token(
                mock_db,
                grant_type="refresh_token",
                code="",
                client_id="c1",
                client_secret="s1",
                redirect_uri="",
            )

    async def test_missing_client_id_raises(self, mock_db):
        with pytest.raises(ValueError, match="required"):
            await exchange_token(
                mock_db,
                grant_type="refresh_token",
                code="some_rt",
                client_id="",
                client_secret="s1",
                redirect_uri="",
            )

    async def test_invalid_refresh_token_raises(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid refresh token"):
            await exchange_token(
                mock_db,
                grant_type="refresh_token",
                code="bad_rt",
                client_id="c1",
                client_secret="s1",
                redirect_uri="",
            )

    async def test_revoked_refresh_token_raises(self, mock_db):
        mock_rt = MagicMock()
        mock_rt.revoked = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rt
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="revoked"):
            await exchange_token(
                mock_db,
                grant_type="refresh_token",
                code="revoked_rt",
                client_id="c1",
                client_secret="s1",
                redirect_uri="",
            )

    async def test_expired_refresh_token_raises(self, mock_db):
        mock_rt = MagicMock()
        mock_rt.revoked = False
        mock_rt.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rt
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="expired"):
            await exchange_token(
                mock_db,
                grant_type="refresh_token",
                code="exp_rt",
                client_id="c1",
                client_secret="s1",
                redirect_uri="",
            )


class TestValidateAccessTokenMock:
    """validate_access_token() and get_userinfo() with a mocked DB."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def test_nonexistent_token_returns_none(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        assert await validate_access_token(mock_db, "bad_tok") is None

    async def test_revoked_token_returns_none(self, mock_db):
        mock_at = MagicMock()
        mock_at.revoked = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_at
        mock_db.execute = AsyncMock(return_value=mock_result)
        assert await validate_access_token(mock_db, "rev_tok") is None

    async def test_expired_token_returns_none(self, mock_db):
        mock_at = MagicMock()
        mock_at.revoked = False
        mock_at.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_at
        mock_db.execute = AsyncMock(return_value=mock_result)
        assert await validate_access_token(mock_db, "exp_tok") is None

    async def test_valid_token_returns_metadata(self, mock_db):
        mock_at = MagicMock()
        mock_at.revoked = False
        mock_at.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_at.user_id = "user-42"
        mock_at.client_id = "client-7"
        mock_at.scope = "read write"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_at
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await validate_access_token(mock_db, "valid_tok")
        assert result is not None
        assert result["user_id"] == "user-42"
        assert result["client_id"] == "client-7"
        assert result["scope"] == "read write"
        assert "expires_at" in result

    async def test_get_userinfo_invalid_token_raises(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid or expired"):
            await get_userinfo(mock_db, "bad_tok")

    async def test_get_userinfo_returns_sub_and_scope(self, mock_db):
        mock_at = MagicMock()
        mock_at.revoked = False
        mock_at.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_at.user_id = "user-99"
        mock_at.client_id = "client-1"
        mock_at.scope = "agent:read"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_at
        mock_db.execute = AsyncMock(return_value=mock_result)

        info = await get_userinfo(mock_db, "valid_tok")
        assert info["sub"] == "user-99"
        assert info["scope"] == "agent:read"


class TestRevokeTokenMock:
    """revoke_token() with a mocked DB."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def test_revoke_access_token_returns_true(self, mock_db):
        mock_at = MagicMock()
        mock_at.revoked = False
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_at
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await revoke_token(mock_db, "access_tok")
        assert result is True
        assert mock_at.revoked is True

    async def test_revoke_nonexistent_returns_false(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await revoke_token(mock_db, "no_such_token")
        assert result is False

    async def test_revoke_commits_after_access_token(self, mock_db):
        mock_at = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_at
        mock_db.execute = AsyncMock(return_value=mock_result)

        await revoke_token(mock_db, "tok")
        mock_db.commit.assert_called_once()


# ===========================================================================
# Section 3: server.py — integration tests with real DB (db fixture)
# ===========================================================================


class TestRegisterClientDB:
    """register_client() writes a real persisted row."""

    async def test_client_row_exists_after_registration(self, db: AsyncSession):
        from sqlalchemy import select

        result = await register_client(
            db,
            name="Integration App",
            redirect_uris=["https://integration.test/cb"],
            scopes="read",
            owner_id=_new_id(),
        )
        client_id = result["client_id"]

        from sqlalchemy import select
        row = (await db.execute(
            select(OAuthClient).where(OAuthClient.client_id == client_id)
        )).scalar_one_or_none()
        assert row is not None
        assert row.name == "Integration App"
        assert row.status == "active"

    async def test_secret_is_hashed_in_db(self, db: AsyncSession):
        from sqlalchemy import select

        result = await register_client(
            db,
            name="HashCheck",
            redirect_uris=["https://example.com/cb"],
            scopes="read",
            owner_id=_new_id(),
        )
        plain_secret = result["client_secret"]
        client_id = result["client_id"]

        row = (await db.execute(
            select(OAuthClient).where(OAuthClient.client_id == client_id)
        )).scalar_one_or_none()
        assert row is not None
        assert row.client_secret_hash == _hash_secret(plain_secret)
        assert row.client_secret_hash != plain_secret


class TestAuthorizeDB:
    """authorize() creates real AuthorizationCode rows."""

    async def test_authorization_code_persisted(self, db: AsyncSession):
        from sqlalchemy import select

        client, _ = await _seed_client(db)

        code = await authorize(
            db,
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="read",
            code_challenge="",
            code_challenge_method="",
            user_id=_new_id(),
        )

        row = (await db.execute(
            select(AuthorizationCode).where(AuthorizationCode.code == code)
        )).scalar_one_or_none()
        assert row is not None
        assert row.used is False
        assert row.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)

    async def test_authorize_inactive_client_raises(self, db: AsyncSession):
        """A client with status != 'active' must be rejected."""
        plain_secret = secrets.token_urlsafe(48)
        inactive = OAuthClient(
            id=_new_id(),
            client_id=secrets.token_urlsafe(32),
            client_secret_hash=_hash_secret(plain_secret),
            name="Inactive",
            redirect_uris=json.dumps(["https://app.example.com/cb"]),
            scopes="read",
            grant_types="authorization_code",
            owner_id=_new_id(),
            status="revoked",
        )
        db.add(inactive)
        await db.commit()

        with pytest.raises(ValueError, match="Invalid or inactive client"):
            await authorize(
                db,
                client_id=inactive.client_id,
                redirect_uri="https://app.example.com/cb",
                scope="read",
                code_challenge="",
                code_challenge_method="",
                user_id=_new_id(),
            )


class TestExchangeTokenDB:
    """Full exchange flow with real DB rows."""

    async def test_exchange_without_pkce_returns_tokens(self, db: AsyncSession):
        client, plain_secret = await _seed_client(db)
        user_id = _new_id()

        # Get authorization code
        code = await authorize(
            db,
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="read",
            code_challenge="",
            code_challenge_method="",
            user_id=user_id,
        )

        # Exchange for tokens
        token_data = await exchange_token(
            db,
            grant_type="authorization_code",
            code=code,
            client_id=client.client_id,
            client_secret=plain_secret,
            redirect_uri="https://app.example.com/cb",
        )

        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert token_data["token_type"] == "Bearer"
        assert token_data["expires_in"] == int(ACCESS_TOKEN_LIFETIME.total_seconds())
        assert token_data["scope"] == "read"

    async def test_exchange_with_pkce_returns_tokens(self, db: AsyncSession):
        client, _ = await _seed_client(db)
        verifier, challenge = _make_pkce_pair()
        user_id = _new_id()

        code = await authorize(
            db,
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="read write",
            code_challenge=challenge,
            code_challenge_method="S256",
            user_id=user_id,
        )

        token_data = await exchange_token(
            db,
            grant_type="authorization_code",
            code=code,
            client_id=client.client_id,
            client_secret="",
            redirect_uri="https://app.example.com/cb",
            code_verifier=verifier,
        )

        assert "access_token" in token_data
        assert token_data["scope"] == "read write"

    async def test_code_marked_used_after_exchange(self, db: AsyncSession):
        from sqlalchemy import select

        client, plain_secret = await _seed_client(db)

        code = await authorize(
            db,
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="read",
            code_challenge="",
            code_challenge_method="",
            user_id=_new_id(),
        )

        await exchange_token(
            db,
            grant_type="authorization_code",
            code=code,
            client_id=client.client_id,
            client_secret=plain_secret,
            redirect_uri="https://app.example.com/cb",
        )

        row = (await db.execute(
            select(AuthorizationCode).where(AuthorizationCode.code == code)
        )).scalar_one_or_none()
        assert row.used is True

    async def test_reusing_code_raises(self, db: AsyncSession):
        client, plain_secret = await _seed_client(db)

        code = await authorize(
            db,
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="read",
            code_challenge="",
            code_challenge_method="",
            user_id=_new_id(),
        )

        await exchange_token(
            db,
            grant_type="authorization_code",
            code=code,
            client_id=client.client_id,
            client_secret=plain_secret,
            redirect_uri="https://app.example.com/cb",
        )

        with pytest.raises(ValueError, match="already been used"):
            await exchange_token(
                db,
                grant_type="authorization_code",
                code=code,
                client_id=client.client_id,
                client_secret=plain_secret,
                redirect_uri="https://app.example.com/cb",
            )

    async def test_wrong_client_secret_raises(self, db: AsyncSession):
        client, _ = await _seed_client(db)

        code = await authorize(
            db,
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="read",
            code_challenge="",
            code_challenge_method="",
            user_id=_new_id(),
        )

        with pytest.raises(ValueError, match="Invalid client credentials"):
            await exchange_token(
                db,
                grant_type="authorization_code",
                code=code,
                client_id=client.client_id,
                client_secret="wrong_secret",
                redirect_uri="https://app.example.com/cb",
            )


class TestRefreshTokenDB:
    """Refresh token rotation with real DB rows."""

    async def _full_auth_flow(self, db: AsyncSession):
        """Perform the full auth flow and return (client, plain_secret, token_data)."""
        client, plain_secret = await _seed_client(db)
        code = await authorize(
            db,
            client_id=client.client_id,
            redirect_uri="https://app.example.com/cb",
            scope="read",
            code_challenge="",
            code_challenge_method="",
            user_id=_new_id(),
        )
        token_data = await exchange_token(
            db,
            grant_type="authorization_code",
            code=code,
            client_id=client.client_id,
            client_secret=plain_secret,
            redirect_uri="https://app.example.com/cb",
        )
        return client, plain_secret, token_data

    async def test_refresh_returns_new_tokens(self, db: AsyncSession):
        client, plain_secret, token_data = await self._full_auth_flow(db)

        new_data = await refresh_access_token(
            db,
            refresh_token=token_data["refresh_token"],
            client_id=client.client_id,
            client_secret=plain_secret,
        )

        assert "access_token" in new_data
        assert "refresh_token" in new_data
        # New tokens must differ from the original
        assert new_data["access_token"] != token_data["access_token"]
        assert new_data["refresh_token"] != token_data["refresh_token"]

    async def test_refresh_revokes_old_tokens(self, db: AsyncSession):
        from sqlalchemy import select

        client, plain_secret, token_data = await self._full_auth_flow(db)
        old_at_str = token_data["access_token"]
        old_rt_str = token_data["refresh_token"]

        await refresh_access_token(
            db,
            refresh_token=old_rt_str,
            client_id=client.client_id,
            client_secret=plain_secret,
        )

        old_at = (await db.execute(
            select(OAuthAccessToken).where(OAuthAccessToken.token == old_at_str)
        )).scalar_one_or_none()
        old_rt = (await db.execute(
            select(OAuthRefreshToken).where(OAuthRefreshToken.token == old_rt_str)
        )).scalar_one_or_none()

        assert old_at.revoked is True
        assert old_rt.revoked is True

    async def test_double_refresh_raises(self, db: AsyncSession):
        """Using an already-rotated (revoked) refresh token must raise."""
        client, plain_secret, token_data = await self._full_auth_flow(db)
        old_rt = token_data["refresh_token"]

        await refresh_access_token(
            db,
            refresh_token=old_rt,
            client_id=client.client_id,
            client_secret=plain_secret,
        )

        with pytest.raises(ValueError, match="revoked"):
            await refresh_access_token(
                db,
                refresh_token=old_rt,
                client_id=client.client_id,
                client_secret=plain_secret,
            )


class TestRevokeTokenDB:
    """revoke_token() with real DB rows."""

    async def test_revoke_access_token(self, db: AsyncSession):
        from sqlalchemy import select

        client, _ = await _seed_client(db)
        at = await _seed_access_token(db, client.client_id, _new_id())

        result = await revoke_token(db, at.token)
        assert result is True

        row = (await db.execute(
            select(OAuthAccessToken).where(OAuthAccessToken.id == at.id)
        )).scalar_one_or_none()
        assert row.revoked is True

    async def test_revoke_refresh_token(self, db: AsyncSession):
        from sqlalchemy import select

        client, _ = await _seed_client(db)
        user_id = _new_id()
        at = await _seed_access_token(db, client.client_id, user_id)
        rt = await _seed_refresh_token(db, at.id, client.client_id, user_id)

        result = await revoke_token(db, rt.token)
        assert result is True

        row = (await db.execute(
            select(OAuthRefreshToken).where(OAuthRefreshToken.id == rt.id)
        )).scalar_one_or_none()
        assert row.revoked is True

    async def test_revoke_nonexistent_token_returns_false(self, db: AsyncSession):
        result = await revoke_token(db, "totally_made_up_token_xyz")
        assert result is False

    async def test_revoke_with_client_id_filter(self, db: AsyncSession):
        from sqlalchemy import select

        client, _ = await _seed_client(db)
        at = await _seed_access_token(db, client.client_id, _new_id())

        result = await revoke_token(db, at.token, client_id=client.client_id)
        assert result is True

        row = (await db.execute(
            select(OAuthAccessToken).where(OAuthAccessToken.id == at.id)
        )).scalar_one_or_none()
        assert row.revoked is True

    async def test_revoke_with_wrong_client_id_returns_false(self, db: AsyncSession):
        """Passing a mismatched client_id should cause no match, returning False."""
        client, _ = await _seed_client(db)
        at = await _seed_access_token(db, client.client_id, _new_id())

        result = await revoke_token(db, at.token, client_id="completely_wrong_client_id")
        assert result is False


class TestValidateAccessTokenDB:
    """validate_access_token() and get_userinfo() with real DB rows."""

    async def test_valid_token_passes(self, db: AsyncSession):
        client, _ = await _seed_client(db)
        user_id = _new_id()
        at = await _seed_access_token(db, client.client_id, user_id, scope="read write")

        info = await validate_access_token(db, at.token)
        assert info is not None
        assert info["user_id"] == user_id
        assert info["client_id"] == client.client_id
        assert info["scope"] == "read write"

    async def test_expired_token_returns_none(self, db: AsyncSession):
        client, _ = await _seed_client(db)
        at = await _seed_access_token(db, client.client_id, _new_id(), expired=True)

        assert await validate_access_token(db, at.token) is None

    async def test_revoked_token_returns_none(self, db: AsyncSession):
        client, _ = await _seed_client(db)
        at = await _seed_access_token(db, client.client_id, _new_id(), revoked=True)

        assert await validate_access_token(db, at.token) is None

    async def test_unknown_token_returns_none(self, db: AsyncSession):
        assert await validate_access_token(db, "unknown_token_xyz") is None

    async def test_get_userinfo_valid_token(self, db: AsyncSession):
        client, _ = await _seed_client(db)
        user_id = _new_id()
        at = await _seed_access_token(db, client.client_id, user_id, scope="agent:read")

        info = await get_userinfo(db, at.token)
        assert info["sub"] == user_id
        assert info["scope"] == "agent:read"

    async def test_get_userinfo_invalid_token_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Invalid or expired"):
            await get_userinfo(db, "no_such_token_abc")


# ===========================================================================
# Section 4: OAuth2Server class wrapper
# ===========================================================================


class TestOAuth2ServerClass:
    """OAuth2Server is a thin class wrapper; verify delegation works."""

    @pytest.fixture
    def oauth2(self):
        return OAuth2Server()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    async def test_register_client_delegates(self, oauth2, mock_db):
        result = await oauth2.register_client(
            mock_db,
            name="Wrapped App",
            redirect_uris=["https://example.com/cb"],
            scopes="read",
            owner_id="owner-1",
        )
        assert "client_id" in result
        assert "client_secret" in result

    async def test_authorize_invalid_client_delegates(self, oauth2, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Invalid or inactive client"):
            await oauth2.authorize(
                mock_db,
                client_id="bad",
                redirect_uri="https://app.com/cb",
                scope="read",
                code_challenge="",
                code_challenge_method="",
                user_id="user-1",
            )

    async def test_validate_token_delegates(self, oauth2, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await oauth2.validate_token(mock_db, "bad_token")
        assert result is None

    async def test_exchange_token_delegates(self, oauth2, mock_db):
        with pytest.raises(ValueError, match="Unsupported grant_type"):
            await oauth2.exchange_token(
                mock_db,
                grant_type="implicit",
                code="c",
                client_id="c1",
                client_secret="s",
                redirect_uri="",
            )


class TestTokenExchangeAlias:
    """token_exchange is a backward-compatible alias for exchange_token."""

    async def test_alias_is_exchange_token(self):
        """token_exchange must resolve to exchange_token."""
        assert token_exchange is exchange_token


# ===========================================================================
# Section 5: API route tests (client fixture)
# ===========================================================================


def _auth_headers() -> dict:
    """Create a valid Bearer auth header for OAuth2 API requests."""
    token = create_access_token(str(uuid.uuid4()), "test-oauth-agent")
    return {"Authorization": f"Bearer {token}"}


class TestOAuth2APIClientRegistration:
    """POST /oauth2/clients — HTTP-level tests."""

    async def test_register_client_returns_200(self, client):
        resp = await client.post(
            "/oauth2/clients",
            json={
                "name": "Test App",
                "redirect_uris": ["https://app.com/cb"],
                "scopes": "read",
                "owner_id": _new_id(),
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "client_id" in data
        assert "client_secret" in data
        assert data["status"] == "active"

    async def test_register_client_missing_name_returns_422(self, client):
        resp = await client.post(
            "/oauth2/clients",
            json={
                "redirect_uris": ["https://app.com/cb"],
                "owner_id": _new_id(),
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    async def test_register_client_response_echoes_name(self, client):
        resp = await client.post(
            "/oauth2/clients",
            json={
                "name": "EchoApp",
                "redirect_uris": ["https://echo.com/cb"],
                "scopes": "write",
                "owner_id": _new_id(),
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "EchoApp"
        assert resp.json()["scopes"] == "write"


class TestOAuth2APIGetClient:
    """GET /oauth2/clients/{client_id} — HTTP-level tests."""

    async def test_get_existing_client(self, client):
        # Register first — use the same token for both register and get
        # so the owner_id matches the authenticated user
        headers = _auth_headers()
        reg_resp = await client.post(
            "/oauth2/clients",
            json={
                "name": "Lookup App",
                "redirect_uris": ["https://lookup.com/cb"],
                "scopes": "read",
                "owner_id": _new_id(),
            },
            headers=headers,
        )
        client_id = reg_resp.json()["client_id"]

        resp = await client.get(f"/oauth2/clients/{client_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["client_id"] == client_id
        assert data["name"] == "Lookup App"

    async def test_get_nonexistent_client_returns_404(self, client):
        resp = await client.get(
            "/oauth2/clients/no_such_client_xyz",
            headers=_auth_headers(),
        )
        assert resp.status_code == 404


class TestOAuth2APIAuthorize:
    """GET /oauth2/authorize — HTTP-level tests."""

    async def _register(self, client, redirect_uri="https://app.example.com/cb"):
        reg_resp = await client.post(
            "/oauth2/clients",
            json={
                "name": "Auth Test App",
                "redirect_uris": [redirect_uri],
                "scopes": "read",
                "owner_id": _new_id(),
            },
            headers=_auth_headers(),
        )
        return reg_resp.json()

    async def test_authorize_with_user_id_query_param(self, client):
        reg = await self._register(client)
        resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://app.example.com/cb",
                "user_id": _new_id(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "code" in data
        assert "https://app.example.com/cb" in data["redirect_uri"]

    async def test_authorize_without_user_id_returns_401(self, client):
        reg = await self._register(client)
        resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://app.example.com/cb",
            },
        )
        assert resp.status_code == 401

    async def test_authorize_invalid_client_returns_400(self, client):
        resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": "definitely_not_registered",
                "redirect_uri": "https://app.example.com/cb",
                "user_id": _new_id(),
            },
        )
        assert resp.status_code == 400

    async def test_authorize_returns_state_in_redirect(self, client):
        reg = await self._register(client)
        resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://app.example.com/cb",
                "user_id": _new_id(),
                "state": "csrf_token_abc",
            },
        )
        assert resp.status_code == 200
        assert "csrf_token_abc" in resp.json()["redirect_uri"]


class TestOAuth2APIToken:
    """POST /oauth2/token — HTTP-level tests."""

    async def _setup_and_get_code(self, client):
        """Register a client and get a valid authorization code."""
        reg_resp = await client.post(
            "/oauth2/clients",
            json={
                "name": "Token Test App",
                "redirect_uris": ["https://token.test/cb"],
                "scopes": "read",
                "owner_id": _new_id(),
            },
            headers=_auth_headers(),
        )
        reg = reg_resp.json()

        auth_resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://token.test/cb",
                "user_id": _new_id(),
            },
        )
        code = auth_resp.json()["code"]
        return reg, code

    async def test_exchange_code_for_tokens(self, client):
        reg, code = await self._setup_and_get_code(client)

        resp = await client.post(
            "/oauth2/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "redirect_uri": "https://token.test/cb",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    async def test_token_with_bad_code_returns_400(self, client):
        reg_resp = await client.post(
            "/oauth2/clients",
            json={
                "name": "Bad Code App",
                "redirect_uris": ["https://bad.code/cb"],
                "scopes": "read",
                "owner_id": _new_id(),
            },
            headers=_auth_headers(),
        )
        reg = reg_resp.json()

        resp = await client.post(
            "/oauth2/token",
            json={
                "grant_type": "authorization_code",
                "code": "totally_invalid_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "redirect_uri": "https://bad.code/cb",
            },
        )
        assert resp.status_code == 400

    async def test_unsupported_grant_type_returns_400(self, client):
        resp = await client.post(
            "/oauth2/token",
            json={
                "grant_type": "implicit",
                "code": "code",
                "client_id": "c1",
                "client_secret": "s1",
            },
        )
        assert resp.status_code == 400

    async def test_refresh_token_grant(self, client):
        reg, code = await self._setup_and_get_code(client)

        token_resp = await client.post(
            "/oauth2/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "redirect_uri": "https://token.test/cb",
            },
        )
        refresh_token = token_resp.json()["refresh_token"]

        resp = await client.post(
            "/oauth2/token",
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
            },
        )
        assert resp.status_code == 200
        new_data = resp.json()
        assert "access_token" in new_data
        assert new_data["access_token"] != token_resp.json()["access_token"]


class TestOAuth2APIRevoke:
    """POST /oauth2/revoke — HTTP-level tests."""

    async def test_revoke_valid_token(self, client):
        # Register and get a token
        reg_resp = await client.post(
            "/oauth2/clients",
            json={
                "name": "Revoke App",
                "redirect_uris": ["https://revoke.test/cb"],
                "scopes": "read",
                "owner_id": _new_id(),
            },
            headers=_auth_headers(),
        )
        reg = reg_resp.json()

        auth_resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://revoke.test/cb",
                "user_id": _new_id(),
            },
        )
        code = auth_resp.json()["code"]

        token_resp = await client.post(
            "/oauth2/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "redirect_uri": "https://revoke.test/cb",
            },
        )
        access_token = token_resp.json()["access_token"]

        revoke_resp = await client.post(
            "/oauth2/revoke",
            json={"token": access_token},
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["revoked"] is True

    async def test_revoke_nonexistent_token(self, client):
        resp = await client.post(
            "/oauth2/revoke",
            json={"token": "does_not_exist_xyz"},
        )
        assert resp.status_code == 200
        assert resp.json()["revoked"] is False


class TestOAuth2APIUserinfo:
    """GET /oauth2/userinfo — HTTP-level tests."""

    async def _get_access_token(self, client):
        reg_resp = await client.post(
            "/oauth2/clients",
            json={
                "name": "Userinfo App",
                "redirect_uris": ["https://userinfo.test/cb"],
                "scopes": "read",
                "owner_id": _new_id(),
            },
            headers=_auth_headers(),
        )
        reg = reg_resp.json()

        auth_resp = await client.get(
            "/oauth2/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://userinfo.test/cb",
                "user_id": _new_id(),
            },
        )
        code = auth_resp.json()["code"]

        token_resp = await client.post(
            "/oauth2/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "redirect_uri": "https://userinfo.test/cb",
            },
        )
        return token_resp.json()["access_token"]

    async def test_userinfo_valid_token(self, client):
        access_token = await self._get_access_token(client)
        resp = await client.get(
            "/oauth2/userinfo",
            params={"access_token": access_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sub" in data
        assert "scope" in data

    async def test_userinfo_invalid_token_returns_401(self, client):
        resp = await client.get(
            "/oauth2/userinfo",
            params={"access_token": "invalid_token_xyz"},
        )
        assert resp.status_code == 401


class TestOAuth2APIOpenIDConfig:
    """GET /oauth2/.well-known/openid-configuration — HTTP-level tests."""

    async def test_openid_config_returns_200(self, client):
        resp = await client.get("/oauth2/.well-known/openid-configuration")
        assert resp.status_code == 200

    async def test_openid_config_issuer(self, client):
        resp = await client.get("/oauth2/.well-known/openid-configuration")
        assert resp.json()["issuer"] == "https://agentchains.io"

    async def test_openid_config_has_expected_endpoints(self, client):
        resp = await client.get("/oauth2/.well-known/openid-configuration")
        data = resp.json()
        for key in ("authorization_endpoint", "token_endpoint", "userinfo_endpoint", "revocation_endpoint"):
            assert key in data, f"Missing key: {key}"

    async def test_openid_config_grant_types(self, client):
        resp = await client.get("/oauth2/.well-known/openid-configuration")
        grants = resp.json()["grant_types_supported"]
        assert "authorization_code" in grants
        assert "refresh_token" in grants

    async def test_openid_config_pkce_s256_only(self, client):
        resp = await client.get("/oauth2/.well-known/openid-configuration")
        assert resp.json()["code_challenge_methods_supported"] == ["S256"]

    async def test_openid_config_scopes_include_read_write(self, client):
        resp = await client.get("/oauth2/.well-known/openid-configuration")
        scopes = resp.json()["scopes_supported"]
        assert "read" in scopes
        assert "write" in scopes

    async def test_openid_config_response_types_is_code(self, client):
        resp = await client.get("/oauth2/.well-known/openid-configuration")
        assert resp.json()["response_types_supported"] == ["code"]
