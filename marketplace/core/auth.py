from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header
from jose import JWTError, jwt

from marketplace.config import settings
from marketplace.core.exceptions import UnauthorizedError


def create_access_token(agent_id: str, agent_name: str) -> str:
    """Create a JWT token for an agent."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": agent_id,
        "name": agent_name,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Returns the payload."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("sub") is None:
            raise UnauthorizedError("Token missing subject")
        return payload
    except JWTError as e:
        raise UnauthorizedError(f"Invalid token: {e}")


def get_current_agent_id(authorization: str = Header(None)) -> str:
    """FastAPI dependency that extracts the agent_id from the Authorization header."""
    if not authorization:
        raise UnauthorizedError("Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Authorization header must be: Bearer <token>")

    payload = decode_token(parts[1])
    return payload["sub"]


def optional_agent_id(authorization: str = Header(None)) -> str | None:
    """FastAPI dependency that optionally extracts agent_id (returns None if no auth)."""
    if not authorization:
        return None
    try:
        return get_current_agent_id(authorization)
    except UnauthorizedError:
        return None
