"""Integration tests for the Creator lifecycle — 20 tests covering
registration, login, profile, agent linking, wallet, redemptions, and E2E flow.

Uses the httpx AsyncClient with ASGI transport from the ``client`` fixture.
"""

import uuid

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = "/api/v1"
_CREATORS = f"{_BASE}/creators"
_REDEMPTIONS = f"{_BASE}/redemptions"


def _unique_email() -> str:
    return f"creator-{uuid.uuid4().hex[:8]}@test.com"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, *, email: str | None = None, password: str = "testpass123",
                    display_name: str = "Test Creator", country: str | None = None) -> dict:
    """Register a creator via the API and return the full JSON response."""
    payload = {
        "email": email or _unique_email(),
        "password": password,
        "display_name": display_name,
    }
    if country is not None:
        payload["country"] = country
    resp = await client.post(f"{_CREATORS}/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_agent(client, token: str) -> dict:
    """Register an agent via the registry endpoint and return its JSON."""
    payload = {
        "name": f"agent-{uuid.uuid4().hex[:8]}",
        "agent_type": "both",
        "public_key": "ssh-rsa AAAA_test_key_placeholder",
    }
    resp = await client.post(f"{_BASE}/agents/register", json=payload)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 1. test_creator_register
# ---------------------------------------------------------------------------

async def test_creator_register(client):
    """POST /api/v1/creators/register returns creator dict + JWT token."""
    data = await _register(client, display_name="Alice")
    assert "creator" in data
    assert "token" in data
    assert data["creator"]["display_name"] == "Alice"
    assert data["creator"]["status"] == "active"
    assert data["creator"]["email"].endswith("@test.com")


# ---------------------------------------------------------------------------
# 2. test_creator_register_duplicate
# ---------------------------------------------------------------------------

async def test_creator_register_duplicate(client):
    """Registering the same email twice returns 409."""
    email = _unique_email()
    await _register(client, email=email)
    resp = await client.post(f"{_CREATORS}/register", json={
        "email": email,
        "password": "testpass123",
        "display_name": "Dup",
    })
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 3. test_creator_login
# ---------------------------------------------------------------------------

async def test_creator_login(client):
    """POST /api/v1/creators/login succeeds with correct credentials."""
    email = _unique_email()
    await _register(client, email=email, password="secret8chars")
    resp = await client.post(f"{_CREATORS}/login", json={
        "email": email,
        "password": "secret8chars",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["creator"]["email"] == email.lower().strip()


# ---------------------------------------------------------------------------
# 4. test_creator_login_wrong_password
# ---------------------------------------------------------------------------

async def test_creator_login_wrong_password(client):
    """POST /api/v1/creators/login with bad password returns 401."""
    email = _unique_email()
    await _register(client, email=email)
    resp = await client.post(f"{_CREATORS}/login", json={
        "email": email,
        "password": "wrong-password-here",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 5. test_creator_profile
# ---------------------------------------------------------------------------

async def test_creator_profile(client):
    """GET /api/v1/creators/me with auth returns the creator's profile."""
    data = await _register(client, display_name="ProfileTest")
    token = data["token"]
    resp = await client.get(f"{_CREATORS}/me", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "ProfileTest"
    assert body["id"] == data["creator"]["id"]


# ---------------------------------------------------------------------------
# 6. test_creator_profile_unauthorized
# ---------------------------------------------------------------------------

async def test_creator_profile_unauthorized(client):
    """GET /api/v1/creators/me without auth returns 401."""
    resp = await client.get(f"{_CREATORS}/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 7. test_creator_update_profile
# ---------------------------------------------------------------------------

async def test_creator_update_profile(client):
    """PUT /api/v1/creators/me updates display_name (and other fields)."""
    data = await _register(client, display_name="Before")
    token = data["token"]
    resp = await client.put(f"{_CREATORS}/me", json={
        "display_name": "After",
    }, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "After"


# ---------------------------------------------------------------------------
# 8. test_creator_link_agent
# ---------------------------------------------------------------------------

async def test_creator_link_agent(client):
    """POST /api/v1/creators/me/agents/{agent_id}/claim links an agent to the creator."""
    creator_data = await _register(client)
    token = creator_data["token"]

    # Register an agent through the registry API
    agent_resp = await _register_agent(client, token)
    agent_id = agent_resp.get("id") or agent_resp.get("agent_id") or agent_resp.get("agent", {}).get("id")
    assert agent_id is not None, f"Could not extract agent_id from: {agent_resp}"

    resp = await client.post(
        f"{_CREATORS}/me/agents/{agent_id}/claim",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert body["creator_id"] == creator_data["creator"]["id"]


# ---------------------------------------------------------------------------
# 9. test_creator_list_agents
# ---------------------------------------------------------------------------

async def test_creator_list_agents(client):
    """GET /api/v1/creators/me/agents returns linked agents."""
    creator_data = await _register(client)
    token = creator_data["token"]

    # Initially empty
    resp = await client.get(f"{_CREATORS}/me/agents", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["agents"] == []

    # Link an agent
    agent_resp = await _register_agent(client, token)
    agent_id = agent_resp.get("id") or agent_resp.get("agent_id") or agent_resp.get("agent", {}).get("id")
    await client.post(
        f"{_CREATORS}/me/agents/{agent_id}/claim",
        headers=_auth(token),
    )

    # Now should have one agent
    resp = await client.get(f"{_CREATORS}/me/agents", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["agents"][0]["agent_id"] == agent_id


# ---------------------------------------------------------------------------
# 10. test_creator_dashboard
# ---------------------------------------------------------------------------

async def test_creator_dashboard(client):
    """GET /api/v1/creators/me/dashboard returns aggregated dashboard data."""
    data = await _register(client)
    token = data["token"]
    resp = await client.get(f"{_CREATORS}/me/dashboard", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "creator_balance" in body
    assert "agents_count" in body
    assert body["agents_count"] == 0
    assert body["creator_balance"] == pytest.approx(0.10, abs=0.01)  # signup bonus


# ---------------------------------------------------------------------------
# 11. test_creator_wallet
# ---------------------------------------------------------------------------

async def test_creator_wallet(client):
    """GET /api/v1/creators/me/wallet returns balance info."""
    data = await _register(client)
    token = data["token"]
    resp = await client.get(f"{_CREATORS}/me/wallet", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "balance" in body
    assert body["balance"] == pytest.approx(0.10, abs=0.01)  # signup bonus


# ---------------------------------------------------------------------------
# 12. test_creator_wallet_signup_bonus
# ---------------------------------------------------------------------------

async def test_creator_wallet_signup_bonus(client):
    """A new creator receives the signup bonus ($0.10 USD) in their wallet."""
    data = await _register(client)
    token = data["token"]
    resp = await client.get(f"{_CREATORS}/me/wallet", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] == pytest.approx(0.10, abs=0.01)
    assert body["total_deposited"] == pytest.approx(0.10, abs=0.01)


# ---------------------------------------------------------------------------
# 13. test_creator_redeem_api_credits
# ---------------------------------------------------------------------------

async def test_creator_redeem_api_credits(client):
    """POST /api/v1/redemptions for api_credits is processed instantly."""
    data = await _register(client)
    token = data["token"]
    resp = await client.post(f"{_REDEMPTIONS}", json={
        "redemption_type": "api_credits",
        "amount_usd": 0.10,
    }, headers=_auth(token))
    assert resp.status_code == 201
    body = resp.json()
    assert body["redemption_type"] == "api_credits"
    assert body["status"] == "completed"  # auto-processed instantly
    assert body["amount_usd"] == pytest.approx(0.10, abs=0.01)

    # After redemption, wallet balance should be 0
    wallet_resp = await client.get(f"{_CREATORS}/me/wallet", headers=_auth(token))
    assert wallet_resp.status_code == 200
    assert wallet_resp.json()["balance"] == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# 14. test_creator_redeem_below_threshold
# ---------------------------------------------------------------------------

async def test_creator_redeem_below_threshold(client):
    """Redeeming below the minimum threshold returns 400."""
    data = await _register(client)
    token = data["token"]
    # api_credits minimum is $0.10, try with $0.05
    resp = await client.post(f"{_REDEMPTIONS}", json={
        "redemption_type": "api_credits",
        "amount_usd": 0.05,
    }, headers=_auth(token))
    assert resp.status_code == 400
    assert "Minimum" in resp.json()["detail"] or "minimum" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 15. test_creator_cancel_redemption
# ---------------------------------------------------------------------------

async def test_creator_cancel_redemption(client):
    """Cancel a completed redemption should fail with 400."""
    data = await _register(client)
    token = data["token"]

    # With only $0.10 signup bonus, the only redemption we can make is
    # api_credits (min $0.10), which auto-completes instantly.
    # We verify that trying to cancel a completed redemption returns 400.

    # Create api_credits redemption (auto-completes)
    redeem_resp = await client.post(f"{_REDEMPTIONS}", json={
        "redemption_type": "api_credits",
        "amount_usd": 0.10,
    }, headers=_auth(token))
    assert redeem_resp.status_code == 201
    redemption_id = redeem_resp.json()["id"]

    # Try to cancel a completed redemption — should fail
    cancel_resp = await client.post(
        f"{_REDEMPTIONS}/{redemption_id}/cancel",
        headers=_auth(token),
    )
    assert cancel_resp.status_code == 400
    assert "Cannot cancel" in cancel_resp.json()["detail"] or "completed" in cancel_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 16. test_creator_list_redemptions
# ---------------------------------------------------------------------------

async def test_creator_list_redemptions(client):
    """GET /api/v1/redemptions returns a paginated list of redemptions."""
    data = await _register(client)
    token = data["token"]

    # No redemptions yet
    resp = await client.get(f"{_REDEMPTIONS}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["redemptions"] == []
    assert body["page"] == 1

    # Create one
    await client.post(f"{_REDEMPTIONS}", json={
        "redemption_type": "api_credits",
        "amount_usd": 0.10,
    }, headers=_auth(token))

    # Now should have one
    resp = await client.get(f"{_REDEMPTIONS}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["redemptions"]) == 1
    assert body["redemptions"][0]["redemption_type"] == "api_credits"


# ---------------------------------------------------------------------------
# 17. test_creator_redemption_methods
# ---------------------------------------------------------------------------

async def test_creator_redemption_methods(client):
    """GET /api/v1/redemptions/methods returns 4 redemption types."""
    resp = await client.get(f"{_REDEMPTIONS}/methods")
    assert resp.status_code == 200
    body = resp.json()
    assert "methods" in body
    assert len(body["methods"]) == 4
    types = {m["type"] for m in body["methods"]}
    assert types == {"api_credits", "gift_card", "upi", "bank_withdrawal"}
    # Verify methods have min_usd field
    for m in body["methods"]:
        assert "min_usd" in m


# ---------------------------------------------------------------------------
# 18. test_creator_full_lifecycle
# ---------------------------------------------------------------------------

async def test_creator_full_lifecycle(client):
    """End-to-end: register -> login -> dashboard -> redeem."""
    email = _unique_email()

    # 1. Register
    reg = await _register(client, email=email, display_name="E2E Creator")
    token = reg["token"]
    creator_id = reg["creator"]["id"]

    # 2. Login with same credentials
    login_resp = await client.post(f"{_CREATORS}/login", json={
        "email": email,
        "password": "testpass123",
    })
    assert login_resp.status_code == 200
    login_token = login_resp.json()["token"]

    # 3. Check dashboard (use login token to prove it works)
    dash_resp = await client.get(
        f"{_CREATORS}/me/dashboard",
        headers=_auth(login_token),
    )
    assert dash_resp.status_code == 200
    dash = dash_resp.json()
    assert dash["creator_balance"] == pytest.approx(0.10, abs=0.01)
    assert dash["agents_count"] == 0

    # 4. Redeem signup bonus as API credits
    redeem_resp = await client.post(f"{_REDEMPTIONS}", json={
        "redemption_type": "api_credits",
        "amount_usd": 0.10,
    }, headers=_auth(login_token))
    assert redeem_resp.status_code == 201
    assert redeem_resp.json()["status"] == "completed"
    assert redeem_resp.json()["creator_id"] == creator_id

    # 5. Verify wallet is now zero
    wallet_resp = await client.get(
        f"{_CREATORS}/me/wallet",
        headers=_auth(login_token),
    )
    assert wallet_resp.status_code == 200
    assert wallet_resp.json()["balance"] == 0.0


# ---------------------------------------------------------------------------
# 19. test_creator_register_email_normalization
# ---------------------------------------------------------------------------

async def test_creator_register_email_normalization(client):
    """Uppercase email is lowered and stripped on registration."""
    raw_email = f"  UPPER-{uuid.uuid4().hex[:6]}@TEST.COM  "
    data = await _register(client, email=raw_email)
    stored_email = data["creator"]["email"]
    assert stored_email == raw_email.lower().strip()
    assert stored_email == stored_email.lower()
    assert not stored_email.startswith(" ")
    assert not stored_email.endswith(" ")


# ---------------------------------------------------------------------------
# 20. test_creator_country_uppercase
# ---------------------------------------------------------------------------

async def test_creator_country_uppercase(client):
    """Country code "in" is stored as "IN"."""
    data = await _register(client, country="in")
    token = data["token"]

    # Check via profile endpoint
    resp = await client.get(f"{_CREATORS}/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["country"] == "IN"
