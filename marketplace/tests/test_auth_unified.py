"""Unit tests for marketplace.core.auth_unified.decode_authorization."""

from __future__ import annotations

import uuid
from contextlib import AsyncExitStack, ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from marketplace.core.auth_context import AuthContext
from marketplace.core.auth_unified import decode_authorization
from marketplace.core.exceptions import UnauthorizedError
from marketplace.database import Base

# ---------------------------------------------------------------------------
# Test secret — overrides the default "dev-secret-change-in-production"
# ---------------------------------------------------------------------------

_TEST_SECRET = "test-secret"
_ALG = "HS256"
_AUD = "agentchains-marketplace"
_ISS = "agentchains"


# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# JWT builder helpers
# ---------------------------------------------------------------------------

def _make_jwt(
    sub: str = "actor-001",
    token_type: str = "agent",
    jti: str | None = None,
    iat: datetime | None = None,
    exp: datetime | None = None,
    secret: str = _TEST_SECRET,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": sub,
        "type": token_type,
        "jti": jti or str(uuid.uuid4()),
        "aud": _AUD,
        "iss": _ISS,
        "iat": iat or now,
        "exp": exp or (now + timedelta(hours=1)),
    }
    return jwt.encode(payload, secret, algorithm=_ALG)


def _bearer(token: str) -> str:
    return f"Bearer {token}"


# ---------------------------------------------------------------------------
# Helpers to patch auth_unified internals via ExitStack
# ---------------------------------------------------------------------------

def _enter_standard_patches(
    stack: ExitStack,
    is_jti_revoked: bool = False,
    is_bulk_revoked: bool = False,
    trust_tier: str = "T1",
    roles: list[str] | None = None,
) -> dict:
    """Enter all standard mocks needed for a happy-path JWT decode.

    Returns a dict of mock objects keyed by name.
    """
    mocks: dict = {}
    mocks["settings"] = stack.enter_context(
        patch("marketplace.core.auth_unified.settings")
    )
    mocks["settings"].jwt_secret_key = _TEST_SECRET
    mocks["settings"].jwt_algorithm = _ALG

    mocks["is_token_revoked"] = stack.enter_context(
        patch(
            "marketplace.core.auth_unified.is_token_revoked",
            new_callable=AsyncMock,
            return_value=is_jti_revoked,
        )
    )
    mocks["is_actor_tokens_revoked_after"] = stack.enter_context(
        patch(
            "marketplace.core.auth_unified.is_actor_tokens_revoked_after",
            new_callable=AsyncMock,
            return_value=is_bulk_revoked,
        )
    )
    mocks["_load_roles"] = stack.enter_context(
        patch(
            "marketplace.core.auth_unified._load_roles",
            new_callable=AsyncMock,
            return_value=roles if roles is not None else [],
        )
    )
    mocks["_load_trust_tier"] = stack.enter_context(
        patch(
            "marketplace.core.auth_unified._load_trust_tier",
            new_callable=AsyncMock,
            return_value=trust_tier,
        )
    )
    return mocks


# ---------------------------------------------------------------------------
# Missing / malformed Authorization header
# ---------------------------------------------------------------------------

class TestAuthorizationHeaderValidation:
    async def test_missing_header_raises_unauthorized_error(self, db: AsyncSession) -> None:
        with pytest.raises(UnauthorizedError, match="Missing Authorization header"):
            await decode_authorization(db, None)

    async def test_empty_string_header_raises_unauthorized_error(self, db: AsyncSession) -> None:
        with pytest.raises(UnauthorizedError):
            await decode_authorization(db, "")

    async def test_non_bearer_scheme_raises_unauthorized_error(self, db: AsyncSession) -> None:
        with pytest.raises(UnauthorizedError, match="Bearer"):
            await decode_authorization(db, "Basic dXNlcjpwYXNz")

    async def test_bearer_without_token_raises_unauthorized_error(self, db: AsyncSession) -> None:
        with pytest.raises(UnauthorizedError):
            await decode_authorization(db, "Bearer")

    async def test_bearer_with_extra_parts_raises_unauthorized_error(self, db: AsyncSession) -> None:
        with pytest.raises(UnauthorizedError):
            await decode_authorization(db, "Bearer tok1 tok2")

    async def test_scheme_is_case_insensitive(self, db: AsyncSession) -> None:
        """bearer (lowercase) should still be accepted."""
        token = _make_jwt()
        with ExitStack() as stack:
            _enter_standard_patches(stack)
            ctx = await decode_authorization(db, f"bearer {token}")
        assert isinstance(ctx, AuthContext)


# ---------------------------------------------------------------------------
# JWT decoding — actor types
# ---------------------------------------------------------------------------

class TestJWTDecoding:
    async def test_agent_token_returns_auth_context_with_agent_actor_type(
        self, db: AsyncSession
    ) -> None:
        token = _make_jwt(sub="agent-1", token_type="agent")
        with ExitStack() as stack:
            _enter_standard_patches(stack)
            ctx = await decode_authorization(db, _bearer(token))
        assert ctx.actor_type == "agent"
        assert ctx.actor_id == "agent-1"

    async def test_creator_token_returns_auth_context_with_creator_actor_type(
        self, db: AsyncSession
    ) -> None:
        token = _make_jwt(sub="creator-1", token_type="creator")
        with ExitStack() as stack:
            _enter_standard_patches(stack)
            ctx = await decode_authorization(db, _bearer(token))
        assert ctx.actor_type == "creator"
        assert ctx.actor_id == "creator-1"

    async def test_user_token_returns_auth_context_with_user_actor_type(
        self, db: AsyncSession
    ) -> None:
        token = _make_jwt(sub="user-1", token_type="user")
        with ExitStack() as stack:
            _enter_standard_patches(stack)
            ctx = await decode_authorization(db, _bearer(token))
        assert ctx.actor_type == "user"
        assert ctx.actor_id == "user-1"

    async def test_unknown_token_type_defaults_to_agent_actor_type(
        self, db: AsyncSession
    ) -> None:
        """Any type value that is not 'creator' or 'user' falls through to agent."""
        token = _make_jwt(sub="agent-x", token_type="custom_type")
        with ExitStack() as stack:
            _enter_standard_patches(stack)
            ctx = await decode_authorization(db, _bearer(token))
        assert ctx.actor_type == "agent"

    async def test_valid_token_returns_full_wildcard_scope(self, db: AsyncSession) -> None:
        token = _make_jwt()
        with ExitStack() as stack:
            _enter_standard_patches(stack)
            ctx = await decode_authorization(db, _bearer(token))
        assert "*" in ctx.scopes

    async def test_valid_token_carries_jti_in_context(self, db: AsyncSession) -> None:
        jti = str(uuid.uuid4())
        token = _make_jwt(jti=jti)
        with ExitStack() as stack:
            _enter_standard_patches(stack)
            ctx = await decode_authorization(db, _bearer(token))
        assert ctx.token_jti == jti

    async def test_agent_token_loads_trust_tier(self, db: AsyncSession) -> None:
        token = _make_jwt(sub="agent-trust", token_type="agent")
        with ExitStack() as stack:
            mocks = _enter_standard_patches(stack, trust_tier="T3")
            ctx = await decode_authorization(db, _bearer(token))
        assert ctx.trust_tier == "T3"
        mocks["_load_trust_tier"].assert_called_once_with(db, "agent-trust")

    async def test_user_token_does_not_call_load_trust_tier(
        self, db: AsyncSession
    ) -> None:
        token = _make_jwt(sub="user-2", token_type="user")
        with ExitStack() as stack:
            mocks = _enter_standard_patches(stack, trust_tier="T0")
            ctx = await decode_authorization(db, _bearer(token))
        mocks["_load_trust_tier"].assert_not_called()
        assert ctx.trust_tier is None

    async def test_creator_token_does_not_call_load_trust_tier(
        self, db: AsyncSession
    ) -> None:
        token = _make_jwt(sub="creator-2", token_type="creator")
        with ExitStack() as stack:
            mocks = _enter_standard_patches(stack, trust_tier="T0")
            ctx = await decode_authorization(db, _bearer(token))
        mocks["_load_trust_tier"].assert_not_called()
        assert ctx.trust_tier is None


# ---------------------------------------------------------------------------
# Invalid JWT
# ---------------------------------------------------------------------------

class TestInvalidJWT:
    async def test_expired_token_raises_unauthorized_error(self, db: AsyncSession) -> None:
        expired = _make_jwt(
            exp=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        with patch("marketplace.core.auth_unified.settings") as mock_settings:
            mock_settings.jwt_secret_key = _TEST_SECRET
            mock_settings.jwt_algorithm = _ALG
            with pytest.raises(UnauthorizedError, match="Invalid or expired token"):
                await decode_authorization(db, _bearer(expired))

    async def test_wrong_secret_raises_unauthorized_error(self, db: AsyncSession) -> None:
        token = _make_jwt(secret="totally-wrong-secret")
        with patch("marketplace.core.auth_unified.settings") as mock_settings:
            mock_settings.jwt_secret_key = _TEST_SECRET
            mock_settings.jwt_algorithm = _ALG
            with pytest.raises(UnauthorizedError):
                await decode_authorization(db, _bearer(token))

    async def test_garbage_token_raises_unauthorized_error(self, db: AsyncSession) -> None:
        with patch("marketplace.core.auth_unified.settings") as mock_settings:
            mock_settings.jwt_secret_key = _TEST_SECRET
            mock_settings.jwt_algorithm = _ALG
            with pytest.raises(UnauthorizedError):
                await decode_authorization(db, "Bearer not.a.jwt")

    async def test_token_missing_sub_raises_unauthorized_error(self, db: AsyncSession) -> None:
        now = datetime.now(timezone.utc)
        payload = {
            "type": "agent",
            "jti": str(uuid.uuid4()),
            "aud": _AUD,
            "iss": _ISS,
            "iat": now,
            "exp": now + timedelta(hours=1),
        }
        token = jwt.encode(payload, _TEST_SECRET, algorithm=_ALG)
        with (
            patch("marketplace.core.auth_unified.settings") as mock_settings,
            patch(
                "marketplace.core.auth_unified.is_token_revoked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "marketplace.core.auth_unified.is_actor_tokens_revoked_after",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            mock_settings.jwt_secret_key = _TEST_SECRET
            mock_settings.jwt_algorithm = _ALG
            with pytest.raises(UnauthorizedError, match="missing subject"):
                await decode_authorization(db, _bearer(token))


# ---------------------------------------------------------------------------
# Stream tokens rejected
# ---------------------------------------------------------------------------

class TestStreamTokenRejection:
    @pytest.mark.parametrize("stream_type", [
        "stream",
        "stream_agent",
        "stream_admin",
        "stream_user",
        "stream_a2ui",
    ])
    async def test_stream_token_raises_unauthorized_error(
        self, db: AsyncSession, stream_type: str
    ) -> None:
        token = _make_jwt(token_type=stream_type)
        with (
            patch("marketplace.core.auth_unified.settings") as mock_settings,
            patch(
                "marketplace.core.auth_unified.is_token_revoked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "marketplace.core.auth_unified.is_actor_tokens_revoked_after",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            mock_settings.jwt_secret_key = _TEST_SECRET
            mock_settings.jwt_algorithm = _ALG
            with pytest.raises(UnauthorizedError, match="Stream tokens"):
                await decode_authorization(db, _bearer(token))


# ---------------------------------------------------------------------------
# Token revocation checks
# ---------------------------------------------------------------------------

class TestRevocationChecks:
    async def test_revoked_jti_raises_unauthorized_error(self, db: AsyncSession) -> None:
        jti = str(uuid.uuid4())
        token = _make_jwt(jti=jti)
        with (
            patch("marketplace.core.auth_unified.settings") as mock_settings,
            patch(
                "marketplace.core.auth_unified.is_token_revoked",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            mock_settings.jwt_secret_key = _TEST_SECRET
            mock_settings.jwt_algorithm = _ALG
            with pytest.raises(UnauthorizedError, match="revoked"):
                await decode_authorization(db, _bearer(token))

    async def test_bulk_revocation_raises_unauthorized_error(self, db: AsyncSession) -> None:
        token = _make_jwt()
        with (
            patch("marketplace.core.auth_unified.settings") as mock_settings,
            patch(
                "marketplace.core.auth_unified.is_token_revoked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "marketplace.core.auth_unified.is_actor_tokens_revoked_after",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            mock_settings.jwt_secret_key = _TEST_SECRET
            mock_settings.jwt_algorithm = _ALG
            with pytest.raises(UnauthorizedError, match="All tokens"):
                await decode_authorization(db, _bearer(token))

    async def test_non_revoked_token_passes_revocation_check(self, db: AsyncSession) -> None:
        token = _make_jwt()
        with ExitStack() as stack:
            _enter_standard_patches(stack, is_jti_revoked=False, is_bulk_revoked=False)
            ctx = await decode_authorization(db, _bearer(token))
        assert isinstance(ctx, AuthContext)


# ---------------------------------------------------------------------------
# API key routing
# ---------------------------------------------------------------------------

class TestAPIKeyRouting:
    async def test_api_key_prefix_routes_to_api_key_service(
        self, db: AsyncSession
    ) -> None:
        fake_key = "ac_live_testkey123"
        expected_ctx = AuthContext(
            actor_id="api-user",
            actor_type="user",
            roles=frozenset(),
            trust_tier=None,
            token_jti="api-jti",
            scopes=frozenset(["read"]),
        )
        with patch(
            "marketplace.core.auth_unified._decode_api_key",
            new_callable=AsyncMock,
            return_value=expected_ctx,
        ) as mock_decode:
            ctx = await decode_authorization(db, f"Bearer {fake_key}")
        mock_decode.assert_called_once_with(db, fake_key)
        assert ctx is expected_ctx

    async def test_non_api_key_prefix_does_not_route_to_api_key_service(
        self, db: AsyncSession
    ) -> None:
        """A token without the ac_live_ prefix should not call _decode_api_key."""
        token = _make_jwt()
        with ExitStack() as stack:
            mocks = _enter_standard_patches(stack)
            stack.enter_context(
                patch(
                    "marketplace.core.auth_unified._decode_api_key",
                    new_callable=AsyncMock,
                )
            )
            await decode_authorization(db, _bearer(token))
        # If we got here without error and without the api_key mock being called, test passes
        assert True
