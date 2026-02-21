"""FastAPI routes for OAuth2 authorization server."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.config import settings
from marketplace.database import get_db
from marketplace.oauth2 import server

router = APIRouter(prefix="/oauth2", tags=["oauth2"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ClientCreateRequest(BaseModel):
    name: str
    redirect_uris: list[str]
    scopes: str = "read"
    owner_id: str


class ClientCreateResponse(BaseModel):
    client_id: str
    client_secret: str
    name: str
    redirect_uris: list[str]
    scopes: str
    status: str


class TokenRequest(BaseModel):
    grant_type: str
    code: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    code_verifier: Optional[str] = None
    refresh_token: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str


class RevokeRequest(BaseModel):
    token: str
    client_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/clients", response_model=ClientCreateResponse)
async def register_client(
    request: ClientCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new OAuth2 client application."""
    result = await server.register_client(
        db=db,
        name=request.name,
        redirect_uris=request.redirect_uris,
        scopes=request.scopes,
        owner_id=request.owner_id,
    )

    return ClientCreateResponse(
        client_id=result["client_id"],
        client_secret=result["client_secret"],
        name=request.name,
        redirect_uris=request.redirect_uris,
        scopes=request.scopes,
        status="active",
    )


@router.get("/clients/{client_id}")
async def get_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get OAuth2 client details by client_id."""
    import json
    from sqlalchemy import select
    from marketplace.oauth2.models import OAuthClient

    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return {
        "client_id": client.client_id,
        "name": client.name,
        "redirect_uris": json.loads(client.redirect_uris or "[]"),
        "scopes": client.scopes,
        "grant_types": client.grant_types,
        "owner_id": client.owner_id,
        "status": client.status,
        "created_at": client.created_at.isoformat() if client.created_at else "",
    }


@router.get("/authorize")
async def authorize_endpoint(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(default="code"),
    scope: str = Query(default="read"),
    state: Optional[str] = Query(default=None),
    code_challenge: Optional[str] = Query(default=None),
    code_challenge_method: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Authorization endpoint - issues an authorization code.

    Requires a valid Bearer token to identify the user. The user_id query
    parameter is only accepted in non-production environments for testing.
    """
    from marketplace.core.auth import decode_token

    authenticated_user_id: Optional[str] = None

    # Extract user_id from auth token if provided
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            try:
                payload = decode_token(parts[1])
                authenticated_user_id = payload.get("sub")
            except Exception:
                raise HTTPException(status_code=401, detail="Invalid authorization token")

    is_prod = settings.environment.lower() in {"production", "prod"}

    if authenticated_user_id:
        resolved_user_id = authenticated_user_id
    elif user_id and not is_prod:
        # Allow query-param user_id only in non-production (testing convenience)
        resolved_user_id = user_id
    elif user_id and is_prod:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required in production; user_id query param is not accepted",
        )
    else:
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    try:
        code = await server.authorize(
            db=db,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge or "",
            code_challenge_method=code_challenge_method or "",
            user_id=resolved_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Build redirect URL with code and optional state
    separator = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{separator}code={code}"
    if state:
        location += f"&state={state}"

    return {"redirect_uri": location, "code": code}


@router.post("/token", response_model=TokenResponse)
async def token_endpoint(
    request: TokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Token endpoint - exchanges authorization code or refresh token for tokens."""
    try:
        # exchange_token expects code positionally; for refresh_token grant,
        # pass the refresh_token value as the code parameter.
        code_or_rt = request.code or request.refresh_token or ""
        token_data = await server.exchange_token(
            db=db,
            grant_type=request.grant_type,
            code=code_or_rt,
            client_id=request.client_id or "",
            client_secret=request.client_secret or "",
            redirect_uri=request.redirect_uri or "",
            code_verifier=request.code_verifier or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return TokenResponse(**token_data)


@router.post("/revoke")
async def revoke_endpoint(
    request: RevokeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Token revocation endpoint."""
    success = await server.revoke_token(
        db=db,
        token=request.token,
        client_id=request.client_id or "",
    )
    return {"revoked": success}


@router.get("/userinfo")
async def userinfo_endpoint(
    authorization: str = Query(..., alias="access_token"),
    db: AsyncSession = Depends(get_db),
):
    """Get user information using a valid access token."""
    # Strip "Bearer " prefix if present
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    try:
        userinfo = await server.get_userinfo(db=db, access_token=token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    return userinfo


@router.get("/.well-known/openid-configuration")
async def openid_configuration():
    """OpenID Connect discovery endpoint."""
    return {
        "issuer": "https://agentchains.io",
        "authorization_endpoint": "/oauth2/authorize",
        "token_endpoint": "/oauth2/token",
        "userinfo_endpoint": "/oauth2/userinfo",
        "revocation_endpoint": "/oauth2/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "scopes_supported": ["read", "write", "admin", "agent:read", "agent:write"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "none",
        ],
        "code_challenge_methods_supported": ["S256", "plain"],
        "subject_types_supported": ["public"],
    }
