"""OAuth2 authorization server logic.

Implements the authorization code grant flow with PKCE support,
token exchange, token revocation, and userinfo endpoint.
"""

import hashlib
import secrets
import base64
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.oauth2.models import (
    OAuthClient,
    AuthorizationCode,
    OAuthAccessToken,
    OAuthRefreshToken,
)


# Token lifetimes
ACCESS_TOKEN_LIFETIME = timedelta(hours=1)
REFRESH_TOKEN_LIFETIME = timedelta(days=30)
AUTHORIZATION_CODE_LIFETIME = timedelta(minutes=10)


def _hash_secret(secret: str) -> str:
    """Hash a client secret using SHA-256.

    Design note: SHA-256 (not bcrypt) is intentional here. OAuth2 client
    secrets are high-entropy, machine-generated tokens (48+ bytes from
    secrets.token_urlsafe), not user-chosen passwords. For such secrets,
    SHA-256 is sufficient and avoids the latency of bcrypt on every token
    exchange. Bcrypt's password-stretching benefit is unnecessary when the
    input already has >256 bits of entropy and is not susceptible to
    dictionary attacks.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _generate_token() -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(48)


async def register_client(
    db: AsyncSession,
    name: str,
    redirect_uris: list[str],
    scopes: str,
    owner_id: str,
) -> dict:
    """Register a new OAuth2 client application.

    Args:
        db: Database session.
        name: Human-readable client name.
        redirect_uris: List of allowed redirect URIs.
        scopes: Space-separated list of requested scopes.
        owner_id: ID of the user who owns this client.

    Returns:
        dict with client_id and client_secret (plain text, shown only once).
    """
    import json

    client_id = secrets.token_urlsafe(32)
    client_secret = secrets.token_urlsafe(48)

    client = OAuthClient(
        id=str(uuid.uuid4()),
        client_id=client_id,
        client_secret_hash=_hash_secret(client_secret),
        name=name,
        redirect_uris=json.dumps(redirect_uris),
        scopes=scopes,
        grant_types="authorization_code",
        owner_id=owner_id,
        status="active",
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    return {"client_id": client_id, "client_secret": client_secret}


async def authorize(
    db: AsyncSession,
    client_id: str,
    redirect_uri: str,
    scope: str,
    code_challenge: str,
    code_challenge_method: str,
    user_id: str,
) -> str:
    """Create an authorization code for the given user and client.

    Args:
        db: Database session.
        client_id: The client requesting authorization.
        redirect_uri: Where to redirect after authorization.
        scope: Requested scopes.
        code_challenge: PKCE code challenge.
        code_challenge_method: PKCE method, must be "S256".
        user_id: The authenticated user granting authorization.

    Returns:
        The authorization code string.

    Raises:
        ValueError: If the client is not found, inactive, or redirect_uri is invalid.
    """
    import json

    # Validate client
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.status == "active",
        )
    )
    client = result.scalar_one_or_none()

    if client is None:
        raise ValueError("Invalid or inactive client")

    # Validate redirect URI
    allowed_uris = json.loads(client.redirect_uris) if client.redirect_uris else []
    if allowed_uris and redirect_uri not in allowed_uris:
        raise ValueError("Invalid redirect_uri for this client")

    # Generate authorization code
    code = secrets.token_urlsafe(32)

    auth_code = AuthorizationCode(
        id=str(uuid.uuid4()),
        code=code,
        client_id=client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scope=scope or client.scopes,
        code_challenge=code_challenge or "",
        code_challenge_method=code_challenge_method or "",
        expires_at=datetime.now(timezone.utc) + AUTHORIZATION_CODE_LIFETIME,
        used=False,
    )
    db.add(auth_code)
    await db.commit()

    return code


async def exchange_token(
    db: AsyncSession,
    grant_type: str,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code_verifier: str = "",
) -> dict:
    """Exchange an authorization code for access and refresh tokens.

    Args:
        db: Database session.
        grant_type: Must be "authorization_code".
        code: Authorization code.
        client_id: Client identifier.
        client_secret: Client secret for authentication.
        redirect_uri: Must match the original redirect URI.
        code_verifier: PKCE code verifier (optional).

    Returns:
        dict with access_token, refresh_token, expires_in, token_type, scope.
    """
    if grant_type == "authorization_code":
        return await _exchange_authorization_code(
            db, code, client_id, client_secret, redirect_uri, code_verifier
        )
    elif grant_type == "refresh_token":
        return await _exchange_refresh_token(
            db, code, client_id, client_secret
        )
    else:
        raise ValueError(f"Unsupported grant_type: {grant_type}")


# Keep backward-compatible alias
token_exchange = exchange_token


async def _exchange_authorization_code(
    db: AsyncSession,
    code: str | None,
    client_id: str | None,
    client_secret: str | None,
    redirect_uri: str | None,
    code_verifier: str | None,
) -> dict:
    """Handle the authorization_code grant type."""
    if not code:
        raise ValueError("Authorization code is required")
    if not client_id:
        raise ValueError("client_id is required")

    # Look up the authorization code
    result = await db.execute(
        select(AuthorizationCode).where(AuthorizationCode.code == code)
    )
    auth_code = result.scalar_one_or_none()

    if auth_code is None:
        raise ValueError("Invalid authorization code")
    if auth_code.used:
        raise ValueError("Authorization code has already been used")
    if auth_code.expires_at < datetime.now(timezone.utc):
        raise ValueError("Authorization code has expired")
    if auth_code.client_id != client_id:
        raise ValueError("Client ID mismatch")
    if redirect_uri and auth_code.redirect_uri != redirect_uri:
        raise ValueError("Redirect URI mismatch")

    # Verify PKCE if code_challenge was set
    if auth_code.code_challenge:
        if not code_verifier:
            raise ValueError("PKCE code_verifier is required")
        if not _verify_pkce(
            auth_code.code_challenge,
            auth_code.code_challenge_method or "S256",
            code_verifier,
        ):
            raise ValueError("PKCE verification failed")

    # Verify client secret (if no PKCE, client_secret is mandatory)
    if not auth_code.code_challenge:
        if not client_secret:
            raise ValueError("client_secret is required for non-PKCE flow")
        client_result = await db.execute(
            select(OAuthClient).where(OAuthClient.client_id == client_id)
        )
        client = client_result.scalar_one_or_none()
        if client is None or client.client_secret_hash != _hash_secret(client_secret):
            raise ValueError("Invalid client credentials")

    # Mark code as used
    auth_code.used = True

    # Generate tokens
    access_token_str = _generate_token()
    refresh_token_str = _generate_token()
    now = datetime.now(timezone.utc)

    access_token_id = str(uuid.uuid4())
    access_token = OAuthAccessToken(
        id=access_token_id,
        client_id=client_id,
        user_id=auth_code.user_id,
        token=access_token_str,
        scope=auth_code.scope,
        expires_at=now + ACCESS_TOKEN_LIFETIME,
        revoked=False,
        created_at=now,
    )
    db.add(access_token)

    refresh_token_obj = OAuthRefreshToken(
        id=str(uuid.uuid4()),
        access_token_id=access_token_id,
        token=refresh_token_str,
        client_id=client_id,
        user_id=auth_code.user_id,
        expires_at=now + REFRESH_TOKEN_LIFETIME,
        revoked=False,
        created_at=now,
    )
    db.add(refresh_token_obj)

    await db.commit()

    return {
        "access_token": access_token_str,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_LIFETIME.total_seconds()),
        "refresh_token": refresh_token_str,
        "scope": auth_code.scope,
    }


async def _exchange_refresh_token(
    db: AsyncSession,
    refresh_token: str | None,
    client_id: str | None,
    client_secret: str | None,
) -> dict:
    """Handle the refresh_token grant type."""
    if not refresh_token:
        raise ValueError("refresh_token is required")
    if not client_id:
        raise ValueError("client_id is required")

    # Look up the refresh token
    result = await db.execute(
        select(OAuthRefreshToken).where(
            OAuthRefreshToken.token == refresh_token
        )
    )
    rt = result.scalar_one_or_none()

    if rt is None:
        raise ValueError("Invalid refresh token")
    if rt.revoked:
        raise ValueError("Refresh token has been revoked")
    if rt.expires_at < datetime.now(timezone.utc):
        raise ValueError("Refresh token has expired")

    # Look up the original access token to get user info
    at_result = await db.execute(
        select(OAuthAccessToken).where(OAuthAccessToken.id == rt.access_token_id)
    )
    original_at = at_result.scalar_one_or_none()

    if original_at is None:
        raise ValueError("Associated access token not found")
    if original_at.client_id != client_id:
        raise ValueError("Client ID mismatch")

    # Verify client secret
    if client_secret:
        client_result = await db.execute(
            select(OAuthClient).where(OAuthClient.client_id == client_id)
        )
        client = client_result.scalar_one_or_none()
        if client is None or client.client_secret_hash != _hash_secret(client_secret):
            raise ValueError("Invalid client credentials")

    # Revoke old tokens
    rt.revoked = True
    original_at.revoked = True

    # Generate new tokens
    new_access_token_str = _generate_token()
    new_refresh_token_str = _generate_token()
    now = datetime.now(timezone.utc)

    new_access_token_id = str(uuid.uuid4())
    new_access_token = OAuthAccessToken(
        id=new_access_token_id,
        client_id=client_id,
        user_id=original_at.user_id,
        token=new_access_token_str,
        scope=original_at.scope,
        expires_at=now + ACCESS_TOKEN_LIFETIME,
        revoked=False,
        created_at=now,
    )
    db.add(new_access_token)

    new_refresh_token = OAuthRefreshToken(
        id=str(uuid.uuid4()),
        access_token_id=new_access_token_id,
        token=new_refresh_token_str,
        client_id=client_id,
        user_id=original_at.user_id,
        expires_at=now + REFRESH_TOKEN_LIFETIME,
        revoked=False,
        created_at=now,
    )
    db.add(new_refresh_token)

    await db.commit()

    return {
        "access_token": new_access_token_str,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_LIFETIME.total_seconds()),
        "refresh_token": new_refresh_token_str,
        "scope": original_at.scope,
    }


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Refresh an access token using a refresh token.

    Returns:
        dict with access_token, refresh_token, expires_in.
    """
    return await _exchange_refresh_token(db, refresh_token, client_id, client_secret)


async def revoke_token(
    db: AsyncSession,
    token: str,
    client_id: str = "",
) -> bool:
    """Revoke an access token or refresh token.

    Args:
        db: Database session.
        token: The token string to revoke.
        client_id: Client identifier (optional filter).

    Returns:
        True if the token was found and revoked, False otherwise.
    """
    # Try access token first
    stmt = select(OAuthAccessToken).where(OAuthAccessToken.token == token)
    if client_id:
        stmt = stmt.where(OAuthAccessToken.client_id == client_id)
    result = await db.execute(stmt)
    at = result.scalar_one_or_none()
    if at:
        at.revoked = True
        await db.commit()
        return True

    # Try refresh token
    stmt = select(OAuthRefreshToken).where(OAuthRefreshToken.token == token)
    if client_id:
        stmt = stmt.where(OAuthRefreshToken.client_id == client_id)
    result = await db.execute(stmt)
    rt = result.scalar_one_or_none()
    if rt:
        rt.revoked = True
        await db.commit()
        return True

    return False


async def get_userinfo(db: AsyncSession, access_token: str) -> dict:
    """Get user information from a valid access token.

    Returns:
        dict with sub, name, scope.

    Raises:
        ValueError: If the token is invalid, expired, or revoked.
    """
    token_info = await validate_access_token(db, access_token)
    if not token_info:
        raise ValueError("Invalid or expired access token")

    return {
        "sub": token_info["user_id"],
        "name": token_info["user_id"],  # placeholder: real impl would look up user name
        "scope": token_info["scope"],
    }


async def validate_access_token(db: AsyncSession, token: str) -> dict | None:
    """Validate an access token and return its metadata if valid.

    Returns:
        dict with user_id, client_id, scope, expires_at if valid; None otherwise.
    """
    result = await db.execute(
        select(OAuthAccessToken).where(OAuthAccessToken.token == token)
    )
    at = result.scalar_one_or_none()
    if not at:
        return None
    if at.revoked:
        return None
    if at.expires_at < datetime.now(timezone.utc):
        return None

    return {
        "user_id": at.user_id,
        "client_id": at.client_id,
        "scope": at.scope,
        "expires_at": at.expires_at.isoformat(),
    }


def _verify_pkce(
    code_challenge: str,
    code_challenge_method: str,
    code_verifier: str,
) -> bool:
    """Verify a PKCE code verifier against the stored challenge.

    Args:
        code_challenge: The stored code challenge from the authorization request.
        code_challenge_method: "S256" or "plain".
        code_verifier: The code verifier provided by the client.

    Returns:
        True if the verifier matches the challenge.
    """
    if code_challenge_method != "S256":
        # Only S256 is supported; "plain" is insecure and has been removed.
        return False
    # S256: BASE64URL(SHA256(code_verifier)) == code_challenge
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed_challenge = (
        base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    )
    return computed_challenge == code_challenge


class OAuth2Server:
    """Class wrapper for OAuth2 server functions."""

    async def register_client(self, db, **kwargs):
        return await register_client(db, **kwargs)

    async def authorize(self, db, **kwargs):
        return await authorize(db, **kwargs)

    async def exchange_token(self, db, **kwargs):
        return await token_exchange(db, **kwargs)

    async def validate_token(self, db, token):
        return await validate_access_token(db, token)
