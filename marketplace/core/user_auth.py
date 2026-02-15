"""End-user authentication for buyer-facing APIs."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Header
from jose import JWTError, jwt

from marketplace.config import settings
from marketplace.core.creator_auth import hash_password, verify_password
from marketplace.core.exceptions import UnauthorizedError


def create_user_token(user_id: str, email: str) -> str:
    """Create a JWT for end users (type=user)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "user",
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    """Extract user_id from Authorization: Bearer <token>."""
    if not authorization:
        raise UnauthorizedError("Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Authorization header must be: Bearer <token>")
    try:
        payload = jwt.decode(parts[1], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "user":
            raise UnauthorizedError("Not a user token")
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Token missing subject")
        return user_id
    except JWTError as exc:
        raise UnauthorizedError(f"Invalid token: {exc}") from exc


def optional_user_id(authorization: str | None = Header(default=None)) -> str | None:
    """Best-effort user auth helper for optional endpoints."""
    if not authorization:
        return None
    try:
        return get_current_user_id(authorization)
    except UnauthorizedError:
        return None


__all__ = [
    "create_user_token",
    "get_current_user_id",
    "hash_password",
    "verify_password",
    "optional_user_id",
]
