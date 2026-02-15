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


def create_stream_token(
    subject_id: str,
    *,
    token_type: str = "stream_agent",
    allowed_topics: list[str] | None = None,
) -> str:
    """Create a short-lived JWT for WebSocket stream subscription."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.stream_token_expire_minutes)
    if allowed_topics is None:
        if token_type == "stream_admin":
            allowed_topics = ["public.market", "private.admin"]
        elif token_type == "stream_user":
            allowed_topics = ["public.market", "public.market.orders", "private.user"]
        else:
            allowed_topics = ["public.market", "private.agent"]
    if token_type == "stream_admin":
        subject_type = "admin"
    elif token_type == "stream_user":
        subject_type = "user"
    else:
        subject_type = "agent"
    payload = {
        "sub": subject_id,
        "type": token_type,
        "sub_type": subject_type,
        "allowed_topics": allowed_topics,
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
        token_type = payload.get("type")
        if token_type == "creator":
            raise UnauthorizedError("Creator tokens cannot be used for agent endpoints")
        if token_type == "user":
            raise UnauthorizedError("User tokens cannot be used for agent endpoints")
        if token_type in {"stream", "stream_agent", "stream_admin", "stream_user"}:
            raise UnauthorizedError("Stream tokens cannot be used for API endpoints")
        return payload
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")


def decode_stream_token(token: str) -> dict:
    """Decode and validate a short-lived WebSocket stream token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")
    if payload.get("sub") is None:
        raise UnauthorizedError("Token missing subject")
    if payload.get("type") not in {"stream", "stream_agent", "stream_admin", "stream_user"}:
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
