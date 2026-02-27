"""Pydantic schemas for auth API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenPairResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class RevokeTokenRequest(BaseModel):
    """Revoke the current access token (JTI extracted from Bearer header)."""
    pass


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AuthMeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    actor_id: str
    actor_type: str
    roles: list[str]
    trust_tier: str | None = None
    scopes: list[str]


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_-]*$")
    description: str = Field(default="", max_length=255)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str
    permissions: list[str]
    is_system: bool
    created_at: str


class AssignRoleRequest(BaseModel):
    role_name: str = Field(..., min_length=1, max_length=50)


class ActorRoleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role_name: str
    granted_by: str
    granted_at: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["*"])
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class ApiKeyCreateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    key: str = Field(description="Plaintext API key — shown only once")
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: str | None = None
    created_at: str


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: str | None = None
    expires_at: str | None = None
    revoked: bool
    created_at: str


class AuthEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    actor_id: str | None = None
    actor_type: str | None = None
    event_type: str
    ip_address: str | None = None
    details: dict = Field(default_factory=dict)
    created_at: str


class AuthEventSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_events: int
    login_successes: int
    login_failures: int
    token_refreshes: int
    token_revocations: int
    brute_force_detections: int
    period_hours: int = 24
