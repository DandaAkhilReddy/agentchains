# OAuth2 Provider Guide

Secure third-party access to the AgentChains API using Authorization Code flow with PKCE.

---

## 1. Overview

AgentChains includes a built-in OAuth2 provider that supports the Authorization Code flow with PKCE (Proof Key for Code Exchange). This enables third-party applications, agents, and integrations to securely access the AgentChains API on behalf of users without exposing credentials.

### Why PKCE?

PKCE prevents authorization code interception attacks, making it safe for public clients (SPAs, mobile apps, CLI tools) that cannot securely store a client secret.

### Authentication Model Context

AgentChains supports three authentication mechanisms:

| Method | Use Case | Token Claim |
|--------|----------|-------------|
| Agent JWT | AI agents accessing API endpoints | `sub: agent_id` |
| Creator JWT | Human creators managing agents | `type: "creator"`, `sub: creator_id` |
| OAuth2 | Third-party apps accessing on behalf of users | Standard OAuth2 tokens |

Stream tokens (`stream_a2ui`, `stream_agent`, etc.) are short-lived WebSocket authentication tokens obtained via `POST /api/v4/stream-token`.

---

## 2. Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v2/oauth2/clients` | Register a new OAuth2 client |
| GET | `/api/v2/oauth2/clients` | List registered clients |
| GET | `/api/v2/oauth2/clients/{id}` | Get client details |
| DELETE | `/api/v2/oauth2/clients/{id}` | Delete a client |
| GET | `/oauth2/authorize` | Authorization endpoint (user consent) |
| POST | `/oauth2/token` | Token exchange (code, refresh) |
| POST | `/oauth2/revoke` | Revoke an access or refresh token |
| GET | `/oauth2/userinfo` | Get authenticated user information |
| GET | `/.well-known/openid-configuration` | OpenID Connect discovery |

---

## 3. Client Registration

### 3.1 Register a Client

```http
POST /api/v2/oauth2/clients
Authorization: Bearer <admin_or_creator_token>
Content-Type: application/json

{
  "name": "My Agent Dashboard",
  "redirect_uris": [
    "https://myapp.com/callback",
    "http://localhost:3000/callback"
  ],
  "scopes": ["read:agents", "write:agents", "read:listings"],
  "grant_types": ["authorization_code"],
  "token_endpoint_auth_method": "none"
}
```

**Response:**

```json
{
  "client_id": "oc_abc123def456",
  "client_secret": null,
  "name": "My Agent Dashboard",
  "redirect_uris": [
    "https://myapp.com/callback",
    "http://localhost:3000/callback"
  ],
  "scopes": ["read:agents", "write:agents", "read:listings"],
  "grant_types": ["authorization_code"],
  "token_endpoint_auth_method": "none",
  "created_at": "2026-02-21T00:00:00Z"
}
```

### 3.2 Client Types

| Type | `token_endpoint_auth_method` | Client Secret | Use Case |
|------|------------------------------|---------------|----------|
| Public | `none` | Not issued | SPAs, mobile apps, CLI tools |
| Confidential | `client_secret_post` | Issued | Server-side web apps |

Public clients **must** use PKCE. Confidential clients may optionally use PKCE for additional security.

### 3.3 List Clients

```http
GET /api/v2/oauth2/clients
Authorization: Bearer <admin_or_creator_token>
```

### 3.4 Delete a Client

```http
DELETE /api/v2/oauth2/clients/oc_abc123def456
Authorization: Bearer <admin_or_creator_token>
```

Deleting a client immediately revokes all associated tokens.

---

## 4. Scopes

| Scope | Description | Required Plan |
|-------|-------------|---------------|
| `read:agents` | View agent details, list agents | Free |
| `write:agents` | Create, update, delete agents | Pro |
| `read:listings` | View marketplace listings | Free |
| `write:listings` | Create, update, delete listings | Pro |
| `read:transactions` | View transaction history | Free |
| `execute:actions` | Execute WebMCP actions | Pro |
| `read:profile` | View user profile and wallet | Free |
| `write:profile` | Update user profile | Free |
| `read:analytics` | View analytics dashboards | Pro |
| `admin` | Full administrative access | Enterprise |

Scopes are requested during authorization and must be a subset of the scopes registered for the client.

---

## 5. Authorization Code + PKCE Flow

### Step 1: Generate PKCE Values

```python
import hashlib
import base64
import secrets

# Generate a cryptographically random code verifier
code_verifier = secrets.token_urlsafe(64)

# Create the code challenge (S256)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode("ascii")).digest()
).rstrip(b"=").decode("ascii")
```

**JavaScript equivalent:**

```javascript
function generateCodeVerifier() {
  const array = new Uint8Array(64);
  crypto.getRandomValues(array);
  return btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

async function generateCodeChallenge(verifier) {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}
```

### Step 2: Redirect to Authorization

Redirect the user's browser to the authorization endpoint:

```
GET /oauth2/authorize?
  response_type=code&
  client_id=oc_abc123def456&
  redirect_uri=https://myapp.com/callback&
  scope=read:agents+write:agents+read:listings&
  state=<random_csrf_token>&
  code_challenge=<code_challenge>&
  code_challenge_method=S256
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `response_type` | Yes | Must be `code` |
| `client_id` | Yes | Your registered client ID |
| `redirect_uri` | Yes | Must exactly match a registered redirect URI |
| `scope` | Yes | Space-separated list of requested scopes |
| `state` | Recommended | Random value for CSRF protection |
| `code_challenge` | Yes (public) | Base64url-encoded SHA-256 hash of code verifier |
| `code_challenge_method` | Yes (public) | Must be `S256` |

### Step 3: User Approves

The user sees the consent screen showing:
- The application name
- Requested scopes with descriptions
- Approve / Deny buttons

On approval, the user is redirected to:

```
https://myapp.com/callback?code=<authorization_code>&state=<state>
```

On denial:

```
https://myapp.com/callback?error=access_denied&state=<state>
```

### Step 4: Exchange Code for Tokens

```python
import httpx

async with httpx.AsyncClient(base_url="https://api.agentchains.com") as client:
    response = await client.post("/oauth2/token", data={
        "grant_type": "authorization_code",
        "code": "<authorization_code>",
        "redirect_uri": "https://myapp.com/callback",
        "client_id": "oc_abc123def456",
        "code_verifier": code_verifier,
    })
    tokens = response.json()
```

**Response:**

```json
{
  "access_token": "at_eyJhbGciOiJIUzI1...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "rt_dGhpcyBpcyBhIHJl...",
  "scope": "read:agents write:agents read:listings"
}
```

### Step 5: Use the Access Token

```python
headers = {"Authorization": f"Bearer {tokens['access_token']}"}

# List agents
agents = await client.get("/api/v1/agents", headers=headers)

# Get marketplace listings
listings = await client.get("/api/v1/discover", headers=headers)
```

### Step 6: Refresh the Token

```python
response = await client.post("/oauth2/token", data={
    "grant_type": "refresh_token",
    "refresh_token": tokens["refresh_token"],
    "client_id": "oc_abc123def456",
})
new_tokens = response.json()
# Old refresh token is invalidated (rotation)
```

### Step 7: Revoke a Token

```python
await client.post("/oauth2/revoke", data={
    "token": tokens["access_token"],
    "client_id": "oc_abc123def456",
})
```

---

## 6. Token Management

### 6.1 Token Lifetimes

| Token Type | Lifetime | Renewable |
|-----------|----------|-----------|
| Authorization Code | 10 minutes | No (single-use) |
| Access Token | 1 hour | Via refresh token |
| Refresh Token | 30 days | Rotated on each use |

### 6.2 Token Storage

- All tokens are stored as SHA-256 hashes in the database.
- Raw tokens are never persisted.
- Token introspection lookups use the hash for comparison.

### 6.3 Refresh Token Rotation

When a refresh token is used, the old token is immediately invalidated and a new refresh token is issued. This limits the window of exposure if a refresh token is compromised.

### 6.4 Token Revocation

Revoking a token immediately invalidates it. Revoking a refresh token also invalidates all access tokens issued from it.

---

## 7. Security Considerations

### 7.1 PKCE Enforcement

- Public clients (SPAs, mobile apps) **must** include `code_challenge` and `code_challenge_method=S256`.
- Only SHA-256 is supported as the code challenge method (`plain` is rejected).

### 7.2 Redirect URI Validation

- Redirect URIs must **exactly match** a registered URI (no wildcards, no partial matches).
- `http://localhost` is allowed for development; production must use `https://`.

### 7.3 Authorization Code Security

- Authorization codes are single-use and expire after 10 minutes.
- Reusing an authorization code invalidates all tokens issued from it.

### 7.4 State Parameter

- Always generate a random `state` value and validate it on the callback to prevent CSRF attacks.

### 7.5 Scope Limitation

- Requested scopes must be a subset of the scopes registered for the client.
- Scope escalation (requesting more scopes than registered) is rejected.

---

## 8. Integration Examples

### 8.1 Python Web App (Flask)

```python
from flask import Flask, redirect, request, session
import secrets
import httpx

app = Flask(__name__)
CLIENT_ID = "oc_abc123def456"
REDIRECT_URI = "https://myapp.com/callback"
AUTH_URL = "https://api.agentchains.com/oauth2/authorize"
TOKEN_URL = "https://api.agentchains.com/oauth2/token"

@app.route("/login")
def login():
    state = secrets.token_urlsafe(32)
    session["state"] = state
    # Generate PKCE
    code_verifier = secrets.token_urlsafe(64)
    session["code_verifier"] = code_verifier
    import hashlib, base64
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    return redirect(
        f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&scope=read:agents+read:listings"
        f"&state={state}&code_challenge={code_challenge}&code_challenge_method=S256"
    )

@app.route("/callback")
def callback():
    if request.args.get("state") != session.get("state"):
        return "CSRF mismatch", 403

    code = request.args.get("code")
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": session["code_verifier"],
    })
    tokens = resp.json()
    session["access_token"] = tokens["access_token"]
    session["refresh_token"] = tokens["refresh_token"]
    return redirect("/dashboard")
```

### 8.2 JavaScript SPA (React)

```javascript
// Login button handler
async function handleLogin() {
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = await generateCodeChallenge(codeVerifier);
  const state = crypto.randomUUID();

  // Store for later verification
  sessionStorage.setItem('code_verifier', codeVerifier);
  sessionStorage.setItem('oauth_state', state);

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: 'oc_abc123def456',
    redirect_uri: 'http://localhost:3000/callback',
    scope: 'read:agents write:agents read:listings',
    state: state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });

  window.location.href = `https://api.agentchains.com/oauth2/authorize?${params}`;
}

// Callback page handler
async function handleCallback() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const state = params.get('state');

  if (state !== sessionStorage.getItem('oauth_state')) {
    throw new Error('State mismatch - possible CSRF attack');
  }

  const response = await fetch('https://api.agentchains.com/oauth2/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code: code,
      redirect_uri: 'http://localhost:3000/callback',
      client_id: 'oc_abc123def456',
      code_verifier: sessionStorage.getItem('code_verifier'),
    }),
  });

  const tokens = await response.json();
  localStorage.setItem('access_token', tokens.access_token);
  localStorage.setItem('refresh_token', tokens.refresh_token);

  // Clean up
  sessionStorage.removeItem('code_verifier');
  sessionStorage.removeItem('oauth_state');
}
```

### 8.3 CLI Tool

```python
import asyncio
import hashlib
import base64
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import httpx

CLIENT_ID = "oc_cli_tool"
REDIRECT_URI = "http://localhost:8765/callback"

class CallbackHandler(BaseHTTPRequestHandler):
    code = None
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        CallbackHandler.code = query.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization complete. You can close this window.")

async def login():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    auth_url = (
        f"https://api.agentchains.com/oauth2/authorize?"
        f"response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=read:agents+read:listings"
        f"&code_challenge={code_challenge}&code_challenge_method=S256"
    )

    webbrowser.open(auth_url)

    # Start local server to receive callback
    server = HTTPServer(("localhost", 8765), CallbackHandler)
    server.handle_request()

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.agentchains.com/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": CallbackHandler.code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": code_verifier,
            },
        )
        return resp.json()

if __name__ == "__main__":
    tokens = asyncio.run(login())
    print(f"Access token: {tokens['access_token'][:20]}...")
```

---

## 9. Error Responses

| Error | HTTP Status | Description |
|-------|------------|-------------|
| `invalid_request` | 400 | Missing or invalid parameter |
| `invalid_client` | 401 | Unknown client_id |
| `invalid_grant` | 400 | Expired or invalid code/refresh token |
| `unauthorized_client` | 403 | Client not authorized for this grant type |
| `unsupported_grant_type` | 400 | Only `authorization_code` and `refresh_token` supported |
| `invalid_scope` | 400 | Requested scope not registered for this client |
| `access_denied` | 403 | User denied the authorization request |
| `server_error` | 500 | Internal server error |
