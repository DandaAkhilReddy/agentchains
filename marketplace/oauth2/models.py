"""SQLAlchemy models for OAuth2 authorization server."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text

from marketplace.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class OAuthClient(Base):
    """Registered OAuth2 client application."""

    __tablename__ = "oauth_clients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(100), unique=True, nullable=False)
    client_secret_hash = Column(String(200), nullable=False)
    name = Column(String(200), nullable=False)
    redirect_uris = Column(Text, default="[]")  # JSON array of allowed redirect URIs
    scopes = Column(Text, default="read")  # Space-separated scopes
    grant_types = Column(Text, default="authorization_code")
    owner_id = Column(String(36), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("idx_oauth_client_id", "client_id"),
        Index("idx_oauth_client_owner", "owner_id"),
    )


class AuthorizationCode(Base):
    """Short-lived authorization code for the authorization code grant."""

    __tablename__ = "oauth_authorization_codes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(200), unique=True, nullable=False)
    client_id = Column(String(100), nullable=False)
    user_id = Column(String(36), nullable=False)
    redirect_uri = Column(String(500), nullable=False)
    scope = Column(String(500), default="read")
    code_challenge = Column(String(200), default="")
    code_challenge_method = Column(String(10), default="")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_authcode_code", "code"),
        Index("idx_authcode_client", "client_id"),
    )


class OAuthAccessToken(Base):
    """OAuth2 access token issued to a client on behalf of a user."""

    __tablename__ = "oauth_access_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String(500), unique=True, nullable=False)
    client_id = Column(String(100), nullable=False)
    user_id = Column(String(36), nullable=False)
    scope = Column(String(500), default="read")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_access_token", "token"),
        Index("idx_access_token_client", "client_id"),
        Index("idx_access_token_user", "user_id"),
    )


class OAuthRefreshToken(Base):
    """OAuth2 refresh token linked to an access token."""

    __tablename__ = "oauth_refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String(500), unique=True, nullable=False)
    access_token_id = Column(String(36), ForeignKey("oauth_access_tokens.id"), nullable=False)
    client_id = Column(String(100), nullable=False)
    user_id = Column(String(36), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_refresh_token", "token"),
        Index("idx_refresh_token_access", "access_token_id"),
    )
