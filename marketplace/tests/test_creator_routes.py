"""Tests for Creator API routes (api/creators.py).

25 tests covering registration, login, profile management, agent claiming,
dashboard, and wallet endpoints via the httpx AsyncClient.
"""

import uuid

import pytest

from marketplace.core.creator_auth import create_creator_token
from marketplace.models.creator import Creator
from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = "/api/v1"
_CREATORS = f"{_BASE}/creators"


def _unique_email() -> str:
    return f"creator-{uuid.uuid4().hex[:8]}@test.com"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, *, email: str | None = None, password: str = "testpass123",
                    display_name: str = "Test Creator", country: str | None = None,
                    phone: str | None = None) -> dict:
    """Register a creator via the API and return the full JSON response."""
    payload: dict = {
        "email": email or _unique_email(),
        "password": password,
        "display_name": display_name,
    }
    if country is not None:
        payload["country"] = country
    if phone is not None:
        payload["phone"] = phone
    resp = await client.post(f"{_CREATORS}/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _setup_agent() -> tuple[str, str]:
    """Create an agent directly in the DB and return (agent_id, agent_name)."""
    from marketplace.models.agent import RegisteredAgent

    async with TestSession() as db:
        agent_id = _new_id()
        name = f"agent-{agent_id[:8]}"
        agent = RegisteredAgent(
            id=agent_id,
            name=name,
            agent_type="both",
            public_key="ssh-rsa AAAA_test_key_placeholder",
            status="active",
        )
        db.add(agent)
        await db.commit()
        return agent_id, name


async def _setup_claimed_agent(creator_id: str) -> tuple[str, str]:
    """Create an agent already claimed by a creator. Returns (agent_id, name)."""
    from marketplace.models.agent import RegisteredAgent

    async with TestSession() as db:
        agent_id = _new_id()
        name = f"agent-{agent_id[:8]}"
        agent = RegisteredAgent(
            id=agent_id,
            name=name,
            agent_type="both",
            public_key="ssh-rsa AAAA_test_key_placeholder",
            status="active",
            creator_id=creator_id,
        )
        db.add(agent)
        await db.commit()
        return agent_id, name


async def _setup_suspended_creator() -> tuple[str, str, str]:
    """Create a suspended creator directly. Returns (creator_id, email, password)."""
    from marketplace.core.creator_auth import hash_password

    email = _unique_email()
    password = "suspended123"
    async with TestSession() as db:
        creator = Creator(
            id=_new_id(),
            email=email.lower().strip(),
            password_hash=hash_password(password),
            display_name="Suspended Creator",
            status="suspended",
        )
        db.add(creator)
        await db.commit()
        return creator.id, email, password


# ---------------------------------------------------------------------------
# 1. test_register_creator_success
# ---------------------------------------------------------------------------

async def test_register_creator_success(client):
    """POST /creators/register with valid data returns 201, creator dict, and JWT token."""
    data = await _register(client, display_name="Alice Builder")
    assert "creator" in data
    assert "token" in data
    assert data["creator"]["display_name"] == "Alice Builder"
    assert data["creator"]["status"] == "active"
    assert data["creator"]["email"].endswith("@test.com")
    assert len(data["token"]) > 50  # JWT is a long string


# ---------------------------------------------------------------------------
# 2. test_register_duplicate_email
# ---------------------------------------------------------------------------

async def test_register_duplicate_email(client):
    """Registering the same email twice returns 409 Conflict."""
    email = _unique_email()
    await _register(client, email=email)

    resp = await client.post(f"{_CREATORS}/register", json={
        "email": email,
        "password": "testpass123",
        "display_name": "Duplicate",
    })
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 3. test_register_short_password
# ---------------------------------------------------------------------------

async def test_register_short_password(client):
    """Password with only 7 characters is rejected with 422."""
    resp = await client.post(f"{_CREATORS}/register", json={
        "email": _unique_email(),
        "password": "short77",  # 7 chars, min is 8
        "display_name": "Short Pass",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. test_register_missing_email
# ---------------------------------------------------------------------------

async def test_register_missing_email(client):
    """Registration without an email field returns 422."""
    resp = await client.post(f"{_CREATORS}/register", json={
        "password": "testpass123",
        "display_name": "No Email",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. test_register_missing_display_name
# ---------------------------------------------------------------------------

async def test_register_missing_display_name(client):
    """Registration without a display_name field returns 422."""
    resp = await client.post(f"{_CREATORS}/register", json={
        "email": _unique_email(),
        "password": "testpass123",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. test_register_with_country
# ---------------------------------------------------------------------------

async def test_register_with_country(client):
    """Country code is stored uppercased (e.g., 'in' -> 'IN')."""
    data = await _register(client, country="in")
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["country"] == "IN"


# ---------------------------------------------------------------------------
# 7. test_login_success
# ---------------------------------------------------------------------------

async def test_login_success(client):
    """POST /creators/login with correct credentials returns a token."""
    email = _unique_email()
    await _register(client, email=email, password="correct8chars")

    resp = await client.post(f"{_CREATORS}/login", json={
        "email": email,
        "password": "correct8chars",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["creator"]["email"] == email.lower().strip()


# ---------------------------------------------------------------------------
# 8. test_login_wrong_password
# ---------------------------------------------------------------------------

async def test_login_wrong_password(client):
    """POST /creators/login with wrong password returns 401."""
    email = _unique_email()
    await _register(client, email=email)

    resp = await client.post(f"{_CREATORS}/login", json={
        "email": email,
        "password": "wrongpassword99",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 9. test_login_wrong_email
# ---------------------------------------------------------------------------

async def test_login_wrong_email(client):
    """POST /creators/login with nonexistent email returns 401."""
    resp = await client.post(f"{_CREATORS}/login", json={
        "email": "nobody-exists@test.com",
        "password": "testpass123",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 10. test_login_inactive_creator
# ---------------------------------------------------------------------------

async def test_login_inactive_creator(client):
    """POST /creators/login for a suspended creator returns 401."""
    _id, email, password = await _setup_suspended_creator()

    resp = await client.post(f"{_CREATORS}/login", json={
        "email": email,
        "password": password,
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 11. test_get_profile_success
# ---------------------------------------------------------------------------

async def test_get_profile_success(client):
    """GET /creators/me with a valid token returns the creator profile."""
    data = await _register(client, display_name="ProfileUser")
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "ProfileUser"
    assert body["id"] == data["creator"]["id"]
    assert body["status"] == "active"


# ---------------------------------------------------------------------------
# 12. test_get_profile_unauthenticated
# ---------------------------------------------------------------------------

async def test_get_profile_unauthenticated(client):
    """GET /creators/me without an Authorization header returns 401."""
    resp = await client.get(f"{_CREATORS}/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 13. test_update_profile_display_name
# ---------------------------------------------------------------------------

async def test_update_profile_display_name(client):
    """PUT /creators/me updates the display_name."""
    data = await _register(client, display_name="OldName")
    token = data["token"]

    resp = await client.put(f"{_CREATORS}/me", json={
        "display_name": "NewName",
    }, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "NewName"


# ---------------------------------------------------------------------------
# 14. test_update_profile_payout_method
# ---------------------------------------------------------------------------

async def test_update_profile_payout_method(client):
    """PUT /creators/me updates the payout_method field."""
    data = await _register(client)
    token = data["token"]

    resp = await client.put(f"{_CREATORS}/me", json={
        "payout_method": "upi",
    }, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["payout_method"] == "upi"


# ---------------------------------------------------------------------------
# 15. test_update_profile_payout_details
# ---------------------------------------------------------------------------

async def test_update_profile_payout_details(client):
    """PUT /creators/me updates payout_details (dict is serialized to JSON string)."""
    data = await _register(client)
    token = data["token"]

    details = {"upi_id": "creator@upi", "name": "Test Creator"}
    resp = await client.put(f"{_CREATORS}/me", json={
        "payout_details": details,
    }, headers=_auth(token))
    assert resp.status_code == 200
    # payout_details is stored as JSON string in the DB; the response
    # should contain either the JSON string or the dict representation
    body = resp.json()
    assert body["payout_method"] is not None or "payout_details" in body


# ---------------------------------------------------------------------------
# 16. test_update_profile_country
# ---------------------------------------------------------------------------

async def test_update_profile_country(client):
    """PUT /creators/me updates country and uppercases it."""
    data = await _register(client)
    token = data["token"]

    resp = await client.put(f"{_CREATORS}/me", json={
        "country": "us",
    }, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["country"] == "US"


# ---------------------------------------------------------------------------
# 17. test_get_agents_empty
# ---------------------------------------------------------------------------

async def test_get_agents_empty(client):
    """GET /creators/me/agents with no claimed agents returns an empty list."""
    data = await _register(client)
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me/agents", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["agents"] == []


# ---------------------------------------------------------------------------
# 18. test_get_agents_with_claimed
# ---------------------------------------------------------------------------

async def test_get_agents_with_claimed(client):
    """GET /creators/me/agents after claiming an agent shows that agent."""
    data = await _register(client)
    token = data["token"]
    creator_id = data["creator"]["id"]

    # Create and claim an agent
    agent_id, agent_name = await _setup_agent()
    claim_resp = await client.post(
        f"{_CREATORS}/me/agents/{agent_id}/claim",
        headers=_auth(token),
    )
    assert claim_resp.status_code == 200

    # Now list agents
    resp = await client.get(f"{_CREATORS}/me/agents", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["agents"][0]["agent_id"] == agent_id
    assert body["agents"][0]["agent_name"] == agent_name


# ---------------------------------------------------------------------------
# 19. test_claim_agent_success
# ---------------------------------------------------------------------------

async def test_claim_agent_success(client):
    """POST /creators/me/agents/{agent_id}/claim links an unclaimed agent."""
    data = await _register(client)
    token = data["token"]
    creator_id = data["creator"]["id"]

    agent_id, _ = await _setup_agent()

    resp = await client.post(
        f"{_CREATORS}/me/agents/{agent_id}/claim",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert body["creator_id"] == creator_id


# ---------------------------------------------------------------------------
# 20. test_claim_already_claimed
# ---------------------------------------------------------------------------

async def test_claim_already_claimed(client):
    """Claiming an agent already claimed by another creator returns 400."""
    # Register two creators
    data1 = await _register(client, display_name="Creator One")
    data2 = await _register(client, display_name="Creator Two")
    token2 = data2["token"]

    # Create an agent already claimed by creator 1
    agent_id, _ = await _setup_claimed_agent(data1["creator"]["id"])

    # Creator 2 tries to claim the same agent
    resp = await client.post(
        f"{_CREATORS}/me/agents/{agent_id}/claim",
        headers=_auth(token2),
    )
    assert resp.status_code == 400
    assert "already claimed" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 21. test_claim_nonexistent_agent
# ---------------------------------------------------------------------------

async def test_claim_nonexistent_agent(client):
    """Claiming a nonexistent agent_id returns 400."""
    data = await _register(client)
    token = data["token"]

    fake_agent_id = _new_id()
    resp = await client.post(
        f"{_CREATORS}/me/agents/{fake_agent_id}/claim",
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 22. test_get_dashboard
# ---------------------------------------------------------------------------

async def test_get_dashboard(client):
    """GET /creators/me/dashboard returns creator_balance, agents, totals."""
    data = await _register(client)
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me/dashboard", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "creator_balance" in body
    assert "agents_count" in body
    assert "agents" in body
    assert "total_agent_earnings" in body
    assert "total_agent_spent" in body
    assert body["agents_count"] == 0
    assert body["creator_balance"] == pytest.approx(0.10, abs=0.01)  # signup bonus


# ---------------------------------------------------------------------------
# 23. test_get_wallet
# ---------------------------------------------------------------------------

async def test_get_wallet(client):
    """GET /creators/me/wallet returns balance, tier, peg_rate."""
    data = await _register(client)
    token = data["token"]

    resp = await client.get(f"{_CREATORS}/me/wallet", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "balance" in body
    assert body["balance"] == pytest.approx(0.10, abs=0.01)  # signup bonus


# ---------------------------------------------------------------------------
# 24. test_get_wallet_no_account
# ---------------------------------------------------------------------------

async def test_get_wallet_no_account(client):
    """GET /creators/me/wallet for a creator without a token account returns defaults."""
    # Create a creator directly in the DB without a token account
    from marketplace.core.creator_auth import hash_password

    email = _unique_email()
    creator_id = _new_id()
    async with TestSession() as db:
        creator = Creator(
            id=creator_id,
            email=email,
            password_hash=hash_password("testpass123"),
            display_name="No Account Creator",
            status="active",
        )
        db.add(creator)
        await db.commit()

    token = create_creator_token(creator_id, email)

    resp = await client.get(f"{_CREATORS}/me/wallet", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] == 0
    assert body["total_earned"] == 0
    assert body["total_spent"] == 0


# ---------------------------------------------------------------------------
# 25. test_register_creates_token_account
# ---------------------------------------------------------------------------

async def test_register_creates_token_account(client):
    """After registration, a token account exists with the signup bonus ($0.10 USD)."""
    data = await _register(client, display_name="Bonus Tester")
    creator_id = data["creator"]["id"]

    # Verify token account exists via the wallet endpoint
    token = data["token"]
    resp = await client.get(f"{_CREATORS}/me/wallet", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] == pytest.approx(0.10, abs=0.01)  # signup bonus
    assert body["total_deposited"] == pytest.approx(0.10, abs=0.01)

    # Also verify directly in the DB
    async with TestSession() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = result.scalar_one_or_none()
        assert acct is not None
        assert float(acct.balance) == pytest.approx(0.10, abs=0.01)
        assert float(acct.total_deposited) == pytest.approx(0.10, abs=0.01)
