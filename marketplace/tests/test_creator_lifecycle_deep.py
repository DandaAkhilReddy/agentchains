"""Deep lifecycle tests: Creator register -> claim -> earn -> redeem E2E.

20 tests covering email normalization, payout method mapping, redemption
workflows, and full end-to-end flows through the service layer and HTTP API.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from marketplace.config import settings
from marketplace.core.creator_auth import create_creator_token, hash_password
from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.models.redemption import ApiCreditBalance, RedemptionRequest
from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.services import creator_service, redemption_service
from marketplace.services.payout_service import run_monthly_payout
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = "/api/v1"
_CREATORS = f"{_BASE}/creators"
_REDEMPTIONS = f"{_BASE}/redemptions"


def _unique_email() -> str:
    return f"deep-{uuid.uuid4().hex[:8]}@test.com"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_via_api(client, *, email=None, password="testpass123",
                            display_name="Deep Creator", country=None):
    payload = {"email": email or _unique_email(), "password": password,
               "display_name": display_name}
    if country is not None:
        payload["country"] = country
    resp = await client.post(f"{_CREATORS}/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_agent_in_db(creator_id=None):
    """Create agent directly in DB. Returns agent_id."""
    async with TestSession() as db:
        aid = _new_id()
        agent = RegisteredAgent(
            id=aid, name=f"agent-{aid[:8]}", agent_type="both",
            public_key="ssh-rsa AAAA_test", status="active",
            creator_id=creator_id,
        )
        db.add(agent)
        await db.commit()
        return aid


async def _give_creator_balance(creator_id: str, amount: float):
    """Top up a creator's token account directly in DB."""
    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = result.scalar_one()
        acct.balance = Decimal(str(float(acct.balance) + amount))
        acct.total_earned = Decimal(str(float(acct.total_earned) + amount))
        await db.commit()


async def _add_agent_token_account(agent_id: str, earned: float = 0):
    """Create a token account for an agent with given earnings."""
    async with TestSession() as db:
        acct = TokenAccount(
            id=_new_id(), agent_id=agent_id,
            balance=Decimal(str(earned)),
            total_earned=Decimal(str(earned)),
        )
        db.add(acct)
        await db.commit()


# ===================================================================
# 1. Register returns token + creator, creates TokenAccount w/ bonus
# ===================================================================

async def test_register_returns_token_and_creator_with_bonus(db):
    """register_creator returns {creator, token} and creates TokenAccount with signup bonus."""
    result = await creator_service.register_creator(
        db, "newuser@example.com", "password123", "New User",
    )

    assert "creator" in result
    assert "token" in result
    assert result["creator"]["email"] == "newuser@example.com"
    assert result["creator"]["status"] == "active"
    assert len(result["token"]) > 50

    # Verify TokenAccount was created with signup bonus
    acct_result = await db.execute(
        select(TokenAccount).where(
            TokenAccount.creator_id == result["creator"]["id"]
        )
    )
    acct = acct_result.scalar_one()
    assert float(acct.balance) == settings.signup_bonus_usd
    assert float(acct.total_deposited) == settings.signup_bonus_usd


# ===================================================================
# 2. Email is lowercased and trimmed on registration
# ===================================================================

async def test_register_email_normalized(db):
    """Email is lowercased and stripped of whitespace during registration."""
    result = await creator_service.register_creator(
        db, "  Alice@Example.COM  ", "password123", "Alice",
    )
    assert result["creator"]["email"] == "alice@example.com"


# ===================================================================
# 3. Duplicate email raises ValueError
# ===================================================================

async def test_register_duplicate_email_raises(db):
    """Registering the same email twice raises ValueError."""
    await creator_service.register_creator(
        db, "dupe@example.com", "password123", "First",
    )
    with pytest.raises(ValueError, match="already registered"):
        await creator_service.register_creator(
            db, "dupe@example.com", "password999", "Second",
        )


# ===================================================================
# 4. Login success returns creator + token
# ===================================================================

async def test_login_success(db):
    """login_creator with correct credentials returns {creator, token}."""
    await creator_service.register_creator(
        db, "login@test.com", "correctpw1", "LoginUser",
    )
    result = await creator_service.login_creator(db, "login@test.com", "correctpw1")
    assert "token" in result
    assert result["creator"]["email"] == "login@test.com"


# ===================================================================
# 5. Login wrong password raises UnauthorizedError
# ===================================================================

async def test_login_wrong_password_raises(db):
    """login_creator with wrong password raises UnauthorizedError (HTTP 401)."""
    from marketplace.core.exceptions import UnauthorizedError

    await creator_service.register_creator(
        db, "wrongpw@test.com", "rightpass1", "WrongPW",
    )
    with pytest.raises(UnauthorizedError):
        await creator_service.login_creator(db, "wrongpw@test.com", "badpass99")


# ===================================================================
# 6. Login suspended account raises UnauthorizedError
# ===================================================================

async def test_login_suspended_raises(db):
    """login_creator for a suspended account raises UnauthorizedError."""
    from marketplace.core.exceptions import UnauthorizedError

    reg = await creator_service.register_creator(
        db, "susp@test.com", "password123", "Suspended",
    )
    # Suspend the creator
    creator_result = await db.execute(
        select(Creator).where(Creator.id == reg["creator"]["id"])
    )
    creator = creator_result.scalar_one()
    creator.status = "suspended"
    await db.commit()

    with pytest.raises(UnauthorizedError, match="suspended"):
        await creator_service.login_creator(db, "susp@test.com", "password123")


# ===================================================================
# 7. Link agent success
# ===================================================================

async def test_link_agent_success(db):
    """link_agent_to_creator sets creator_id on an unclaimed agent."""
    reg = await creator_service.register_creator(
        db, "linker@test.com", "password123", "Linker",
    )
    creator_id = reg["creator"]["id"]

    # Create an unclaimed agent
    agent = RegisteredAgent(
        id=_new_id(), name="link-agent", agent_type="both",
        public_key="ssh-rsa AAAA_test", status="active",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    result = await creator_service.link_agent_to_creator(db, creator_id, agent.id)
    assert result["creator_id"] == creator_id
    assert result["agent_id"] == agent.id


# ===================================================================
# 8. Link agent already claimed by another raises
# ===================================================================

async def test_link_agent_claimed_by_another_raises(db):
    """Linking an agent already claimed by another creator raises ValueError."""
    reg1 = await creator_service.register_creator(
        db, "owner1@test.com", "password123", "Owner1",
    )
    reg2 = await creator_service.register_creator(
        db, "owner2@test.com", "password123", "Owner2",
    )

    agent = RegisteredAgent(
        id=_new_id(), name="claimed-agent", agent_type="both",
        public_key="ssh-rsa AAAA_test", status="active",
        creator_id=reg1["creator"]["id"],
    )
    db.add(agent)
    await db.commit()

    with pytest.raises(ValueError, match="already claimed"):
        await creator_service.link_agent_to_creator(
            db, reg2["creator"]["id"], agent.id,
        )


# ===================================================================
# 9. Re-linking same creator to own agent is OK
# ===================================================================

async def test_relink_same_creator_ok(db):
    """Re-linking an agent that is already owned by the same creator succeeds."""
    reg = await creator_service.register_creator(
        db, "relink@test.com", "password123", "ReLinkr",
    )
    creator_id = reg["creator"]["id"]

    agent = RegisteredAgent(
        id=_new_id(), name="relink-agent", agent_type="both",
        public_key="ssh-rsa AAAA_test", status="active",
        creator_id=creator_id,
    )
    db.add(agent)
    await db.commit()

    # Should not raise
    result = await creator_service.link_agent_to_creator(db, creator_id, agent.id)
    assert result["creator_id"] == creator_id


# ===================================================================
# 10. get_creator_agents includes per-agent earnings
# ===================================================================

async def test_get_creator_agents_includes_earnings(db):
    """get_creator_agents returns total_earned / total_spent per agent."""
    reg = await creator_service.register_creator(
        db, "earnings@test.com", "password123", "Earner",
    )
    creator_id = reg["creator"]["id"]

    agent = RegisteredAgent(
        id=_new_id(), name="earn-agent", agent_type="seller",
        public_key="ssh-rsa AAAA_test", status="active",
        creator_id=creator_id,
    )
    db.add(agent)
    await db.commit()

    # Create token account for the agent with earnings
    agent_acct = TokenAccount(
        id=_new_id(), agent_id=agent.id,
        balance=Decimal("500"), total_earned=Decimal("750"),
        total_spent=Decimal("250"),
    )
    db.add(agent_acct)
    await db.commit()

    agents = await creator_service.get_creator_agents(db, creator_id)
    assert len(agents) == 1
    assert agents[0]["total_earned"] == 750.0
    assert agents[0]["total_spent"] == 250.0
    assert agents[0]["balance"] == 500.0


# ===================================================================
# 11. Dashboard aggregates agents_count, total_earnings, balance
# ===================================================================

async def test_dashboard_aggregates(db):
    """get_creator_dashboard aggregates agents and balance."""
    reg = await creator_service.register_creator(
        db, "dash@test.com", "password123", "DashCreator",
    )
    creator_id = reg["creator"]["id"]

    # Add two agents claimed by this creator
    for i in range(2):
        agent = RegisteredAgent(
            id=_new_id(), name=f"dash-agent-{i}", agent_type="both",
            public_key="ssh-rsa AAAA_test", status="active",
            creator_id=creator_id,
        )
        db.add(agent)
        await db.commit()
        agent_acct = TokenAccount(
            id=_new_id(), agent_id=agent.id,
            balance=Decimal("100"), total_earned=Decimal("200"),
        )
        db.add(agent_acct)
        await db.commit()

    dash = await creator_service.get_creator_dashboard(db, creator_id)
    assert dash["agents_count"] == 2
    assert dash["total_agent_earnings"] == 400.0  # 200 * 2
    # Creator balance = signup bonus ($0.10 USD)
    assert dash["creator_balance"] == pytest.approx(0.10, abs=0.01)


# ===================================================================
# 12. Wallet returns balance
# ===================================================================

async def test_wallet_fields(db):
    """get_creator_wallet returns balance."""
    reg = await creator_service.register_creator(
        db, "wallet@test.com", "password123", "Wallet",
    )
    wallet = await creator_service.get_creator_wallet(db, reg["creator"]["id"])
    assert wallet["balance"] == pytest.approx(0.10, abs=0.01)


# ===================================================================
# 13. Update: allowed fields only, country uppercased
# ===================================================================

async def test_update_allowed_fields_only(db):
    """update_creator only applies allowed fields; country is uppercased."""
    reg = await creator_service.register_creator(
        db, "upd@test.com", "password123", "Updater",
    )
    creator_id = reg["creator"]["id"]

    result = await creator_service.update_creator(db, creator_id, {
        "display_name": "Updated Name",
        "country": "in",
        "email": "hack@evil.com",  # not allowed
        "status": "suspended",    # not allowed
    })
    assert result["display_name"] == "Updated Name"
    assert result["country"] == "IN"
    assert result["email"] == "upd@test.com"  # unchanged
    assert result["status"] == "active"        # unchanged


# ===================================================================
# 14. Update: payout_details dict is stored as JSON string
# ===================================================================

async def test_update_payout_details_json(db):
    """update_creator serializes payout_details dict to JSON string."""
    reg = await creator_service.register_creator(
        db, "payout@test.com", "password123", "Payer",
    )
    creator_id = reg["creator"]["id"]

    details = {"upi_id": "creator@upi", "bank": "SBI"}
    await creator_service.update_creator(db, creator_id, {
        "payout_details": details,
    })

    # Verify stored as JSON string in DB
    row = await db.execute(select(Creator).where(Creator.id == creator_id))
    creator = row.scalar_one()
    import json
    assert json.loads(creator.payout_details) == details


# ===================================================================
# 15. Redemption: api_credits auto-completes instantly
# ===================================================================

async def test_redemption_api_credits_instant(db):
    """api_credits redemption auto-completes and creates ApiCreditBalance."""
    reg = await creator_service.register_creator(
        db, "redeem@test.com", "password123", "Redeemer",
    )
    creator_id = reg["creator"]["id"]

    # Give enough balance
    acct_r = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    acct = acct_r.scalar_one()
    acct.balance = Decimal("5.00")
    await db.commit()

    result = await redemption_service.create_redemption(
        db, creator_id, "api_credits", 2.00,
    )
    assert result["status"] == "completed"
    assert result["redemption_type"] == "api_credits"
    assert result["amount_usd"] == pytest.approx(2.00, abs=0.01)

    # Check API credit balance was created
    credit_r = await db.execute(
        select(ApiCreditBalance).where(ApiCreditBalance.creator_id == creator_id)
    )
    credit = credit_r.scalar_one()
    assert int(credit.credits_remaining) > 0
    assert int(credit.credits_total_purchased) > 0


# ===================================================================
# 16. Redemption below minimum raises ValueError
# ===================================================================

async def test_redemption_below_minimum_raises(db):
    """Attempting to redeem below the minimum threshold raises ValueError."""
    reg = await creator_service.register_creator(
        db, "lowmin@test.com", "password123", "LowMin",
    )
    creator_id = reg["creator"]["id"]

    with pytest.raises(ValueError, match="Minimum"):
        await redemption_service.create_redemption(
            db, creator_id, "api_credits", 0.05,  # min is $0.10
        )


# ===================================================================
# 17. Redemption with insufficient balance raises ValueError
# ===================================================================

async def test_redemption_insufficient_balance_raises(db):
    """Redeeming more than the balance raises ValueError."""
    reg = await creator_service.register_creator(
        db, "insuf@test.com", "password123", "Insufficient",
    )
    creator_id = reg["creator"]["id"]
    # Balance is $0.10 (signup bonus), try to redeem $5.00
    with pytest.raises(ValueError, match="Insufficient balance"):
        await redemption_service.create_redemption(
            db, creator_id, "upi", 5.00,
        )


# ===================================================================
# 18. Cancel redemption refunds balance
# ===================================================================

async def test_cancel_redemption_refunds_balance(db):
    """Cancelling a pending redemption refunds USD to the creator."""
    reg = await creator_service.register_creator(
        db, "cancel@test.com", "password123", "Canceller",
    )
    creator_id = reg["creator"]["id"]

    # Give enough balance for a gift_card redemption (min $1.00)
    acct_r = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    acct = acct_r.scalar_one()
    acct.balance = Decimal("20.00")
    await db.commit()

    # Create a gift_card redemption (stays pending, not auto-completed)
    result = await redemption_service.create_redemption(
        db, creator_id, "gift_card", 10.00,
    )
    assert result["status"] == "pending"
    redemption_id = result["id"]

    # Verify balance was debited
    await db.refresh(acct)
    assert float(acct.balance) == pytest.approx(10.00, abs=0.01)

    # Cancel it
    cancel_result = await redemption_service.cancel_redemption(
        db, redemption_id, creator_id,
    )
    assert cancel_result["status"] == "rejected"

    # Verify balance was refunded
    await db.refresh(acct)
    assert float(acct.balance) == pytest.approx(20.00, abs=0.01)


# ===================================================================
# 19. Payout service maps creator payout_method to redemption_type
# ===================================================================

async def test_payout_method_mapping(db):
    """run_monthly_payout maps payout_method 'bank' -> 'bank_withdrawal'."""
    reg = await creator_service.register_creator(
        db, "payout_map@test.com", "password123", "PayMap",
    )
    creator_id = reg["creator"]["id"]

    # Set payout_method and give balance above creator_min_withdrawal_usd
    await creator_service.update_creator(db, creator_id, {"payout_method": "bank"})

    acct_r = await db.execute(
        select(TokenAccount).where(TokenAccount.creator_id == creator_id)
    )
    acct = acct_r.scalar_one()
    acct.balance = Decimal("15.00")  # above $10.00 min
    await db.commit()

    result = await run_monthly_payout(db)
    assert result["processed"] == 1

    # Verify the created redemption is type bank_withdrawal
    redemptions = await db.execute(
        select(RedemptionRequest).where(
            RedemptionRequest.creator_id == creator_id
        )
    )
    r = redemptions.scalar_one()
    assert r.redemption_type == "bank_withdrawal"
    assert float(r.amount_usd) == pytest.approx(15.00, abs=0.01)


# ===================================================================
# 20. E2E: register -> claim -> earn -> dashboard -> redeem
# ===================================================================

@pytest.mark.asyncio
async def test_e2e_register_claim_earn_dashboard_redeem(client):
    """Full lifecycle: register, claim agent, add earnings, check dashboard, redeem."""
    # Step 1: Register via API
    data = await _register_via_api(client, display_name="E2E Creator")
    token = data["token"]
    creator_id = data["creator"]["id"]

    # Step 2: Create and claim an agent
    agent_id = await _make_agent_in_db()
    claim_resp = await client.post(
        f"{_CREATORS}/me/agents/{agent_id}/claim", headers=_auth(token),
    )
    assert claim_resp.status_code == 200
    assert claim_resp.json()["agent_id"] == agent_id

    # Step 3: Add earnings to the agent's token account
    await _add_agent_token_account(agent_id, earned=3.00)

    # Step 4: Give creator enough balance to redeem
    await _give_creator_balance(creator_id, 4.90)  # total = 0.10 + 4.90 = 5.00

    # Step 5: Check dashboard via API
    dash_resp = await client.get(
        f"{_CREATORS}/me/dashboard", headers=_auth(token),
    )
    assert dash_resp.status_code == 200
    dash = dash_resp.json()
    assert dash["agents_count"] == 1
    assert dash["total_agent_earnings"] == pytest.approx(3.00, abs=0.01)
    assert dash["creator_balance"] == pytest.approx(5.00, abs=0.01)

    # Step 6: Redeem $2.00 USD as API credits via API
    redeem_resp = await client.post(f"{_REDEMPTIONS}", json={
        "redemption_type": "api_credits",
        "amount_usd": 2.00,
    }, headers=_auth(token))
    assert redeem_resp.status_code == 201
    r = redeem_resp.json()
    assert r["status"] == "completed"
    assert r["amount_usd"] == pytest.approx(2.00, abs=0.01)

    # Step 7: Verify wallet balance decreased
    wallet_resp = await client.get(
        f"{_CREATORS}/me/wallet", headers=_auth(token),
    )
    assert wallet_resp.status_code == 200
    assert wallet_resp.json()["balance"] == pytest.approx(3.00, abs=0.01)
