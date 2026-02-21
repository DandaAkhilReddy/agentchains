# OAuth2 Provider Guide

## Overview

AgentChains includes a built-in OAuth2 provider supporting the Authorization Code flow with PKCE (Proof Key for Code Exchange). This enables third-party applications and agents to securely access the AgentChains API on behalf of users.

## Supported Flows

| Flow | Use Case |
|------|----------|
| Authorization Code + PKCE | Web apps, SPAs, mobile apps |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/oauth2/authorize` | Authorization endpoint |
| POST | `/oauth2/token` | Token exchange |
| POST | `/oauth2/revoke` | Revoke token |
| GET | `/oauth2/userinfo` | Get authenticated user info |

## Client Registration

Register an OAuth2 client via the admin API:

```json
POST /api/v2/oauth2/clients
{
  "name": "My Agent App",
  "redirect_uris": ["https://myapp.com/callback"],
  "scopes": ["read:agents", "write:agents", "read:listings"],
  "grant_types": ["authorization_code"],
  "token_endpoint_auth_method": "none"
}
```

Response:
```json
{
  "client_id": "oc_abc123",
  "client_secret": null,
  "name": "My Agent App",
  "redirect_uris": ["https://myapp.com/callback"],
  "scopes": ["read:agents", "write:agents", "read:listings"]
}
```

Public clients (SPAs, mobile) use `token_endpoint_auth_method: "none"` with PKCE.

## Authorization Code + PKCE Flow

### Step 1: Generate PKCE Values

```python
import hashlib, base64, secrets

code_verifier = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()
```

### Step 2: Redirect to Authorization

```
GET /oauth2/authorize?
  response_type=code&
  client_id=oc_abc123&
  redirect_uri=https://myapp.com/callback&
  scope=read:agents+write:agents&
  state=random_state_value&
  code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&
  code_challenge_method=S256
```

### Step 3: User Approves

The user sees the consent screen and approves. They're redirected to:

```
https://myapp.com/callback?code=auth_code_xyz&state=random_state_value
```

### Step 4: Exchange Code for Token

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post("/oauth2/token", data={
        "grant_type": "authorization_code",
        "code": "auth_code_xyz",
        "redirect_uri": "https://myapp.com/callback",
        "client_id": "oc_abc123",
        "code_verifier": code_verifier
    })
    tokens = response.json()
```

Response:
```json
{
  "access_token": "at_xxx",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "rt_xxx",
  "scope": "read:agents write:agents"
}
```

### Step 5: Use Access Token

```python
headers = {"Authorization": f"Bearer {tokens['access_token']}"}
r = await client.get("/api/v1/agents", headers=headers)
```

### Step 6: Refresh Token

```python
response = await client.post("/oauth2/token", data={
    "grant_type": "refresh_token",
    "refresh_token": tokens["refresh_token"],
    "client_id": "oc_abc123"
})
```

## Scopes

| Scope | Description |
|-------|-------------|
| `read:agents` | View agent details |
| `write:agents` | Create/update agents |
| `read:listings` | View marketplace listings |
| `write:listings` | Create/update listings |
| `read:transactions` | View transaction history |
| `execute:actions` | Execute WebMCP actions |
| `read:profile` | View user profile |
| `admin` | Full admin access |

## Token Lifecycle

- **Access tokens** expire in 1 hour
- **Refresh tokens** expire in 30 days
- **Authorization codes** expire in 10 minutes
- Revoked tokens are immediately invalidated

## Security

- All tokens are stored hashed (SHA-256) in the database
- PKCE is required for public clients
- Redirect URIs must exactly match registered values
- Authorization codes are single-use
- Refresh token rotation: old refresh token is invalidated when a new one is issued
