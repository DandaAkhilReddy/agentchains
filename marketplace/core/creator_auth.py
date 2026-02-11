"""Creator authentication — email/password auth for human creator accounts."""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from marketplace.config import settings
from marketplace.core.exceptions import UnauthorizedError


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_creator_token(creator_id: str, email: str) -> str:
    """Create a JWT for a creator. Uses 'type: creator' to distinguish from agent tokens."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": creator_id,
        "email": email,
        "type": "creator",
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_creator_id(authorization: str | None = None) -> str:
    """Extract creator_id from a Bearer token. Raises UnauthorizedError if invalid."""
    if not authorization:
        raise UnauthorizedError("Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Authorization header must be: Bearer <token>")
    try:
        payload = jwt.decode(parts[1], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "creator":
            raise UnauthorizedError("Not a creator token")
        creator_id = payload.get("sub")
        if not creator_id:
            raise UnauthorizedError("Token missing subject")
        return creator_id
    except JWTError as e:
        raise UnauthorizedError(f"Invalid token: {e}")
