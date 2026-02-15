from datetime import datetime, timedelta, timezone

from fastapi import Header
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


def create_stream_token(agent_id: str) -> str:
    """Create a short-lived JWT for WebSocket stream subscription."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.stream_token_expire_minutes)
    payload = {
        "sub": agent_id,
        "type": "stream",
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
        if payload.get("type") == "creator":
            raise UnauthorizedError("Creator tokens cannot be used for agent endpoints")
        return payload
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")


def decode_stream_token(token: str) -> dict:
    """Decode and validate a short-lived WebSocket stream token."""
    payload = decode_token(token)
    if payload.get("type") != "stream":
        raise UnauthorizedError("Stream token required")
    return payload


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
