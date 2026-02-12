"""Integration tests for the redemption API routes (/api/v1/redemptions).

25 tests covering creation, validation, listing, cancellation, admin actions,
and edge cases. Uses httpx AsyncClient against the real FastAPI app with an
in-memory SQLite database.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.creator_auth import create_creator_token, hash_password
from marketplace.models.creator import Creator
from marketplace.models.redemption import ApiCreditBalance, RedemptionRequest
from marketplace.models.token_account import TokenAccount
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "/api/v1/redemptions"


async def _seed_creator(balance: float = 1000.0) -> tuple[str, str]:
    """Create a Creator + TokenAccount via direct DB. Returns (creator_id, jwt)."""
    async with TestSession() as db:
        creator_id = _new_id()
        email = f"creator-{creator_id[:8]}@test.com"
        creator = Creator(
            id=creator_id,
            email=email,
            password_hash=hash_password("testpass123"),
            display_name="Test Creator",
            status="active",
        )
        db.add(creator)

        account = TokenAccount(
            id=_new_id(),
            agent_id=None,
            creator_id=creator_id,
            balance=Decimal(str(balance)),
            total_deposited=Decimal(str(balance)),
        )
        db.add(account)
        await db.commit()

        jwt = create_creator_token(creator_id, email)
        return creator_id, jwt


async def _set_balance(creator_id: str, amount: float) -> None:
    """Directly update a creator's token account balance."""
    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = result.scalar_one()
        acct.balance = Decimal(str(amount))
        await db.commit()


async def _get_balance(creator_id: str) -> float:
    """Read a creator's current ARD balance."""
    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.creator_id == creator_id)
        )
        acct = result.scalar_one()
        return float(acct.balance)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. test_create_api_credits_redemption
# ---------------------------------------------------------------------------

async def test_create_api_credits_redemption(client):
    """api_credits (100 ARD) auto-completes with status='completed'."""
    creator_id, jwt = await _seed_creator(balance=1000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 100},
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["redemption_type"] == "api_credits"
    assert data["amount_ard"] == 100.0
    assert data["payout_ref"] == "api_credits_100"


# ---------------------------------------------------------------------------
# 2. test_create_gift_card_redemption
# ---------------------------------------------------------------------------

async def test_create_gift_card_redemption(client):
    """gift_card (1000 ARD) stays pending until admin action."""
    creator_id, jwt = await _seed_creator(balance=2000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "gift_card", "amount_ard": 1000},
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["redemption_type"] == "gift_card"
    assert data["amount_ard"] == 1000.0
    assert data["amount_fiat"] is not None


# ---------------------------------------------------------------------------
# 3. test_create_bank_withdrawal
# ---------------------------------------------------------------------------

async def test_create_bank_withdrawal(client):
    """bank_withdrawal (10000 ARD) requires higher balance, stays pending."""
    creator_id, jwt = await _seed_creator(balance=20000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "bank_withdrawal", "amount_ard": 10000},
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["redemption_type"] == "bank_withdrawal"
    assert data["amount_ard"] == 10000.0


# ---------------------------------------------------------------------------
# 4. test_create_upi_redemption
# ---------------------------------------------------------------------------

async def test_create_upi_redemption(client):
    """UPI (5000 ARD) stays pending."""
    creator_id, jwt = await _seed_creator(balance=10000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "upi", "amount_ard": 5000},
        headers=_auth(jwt),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["redemption_type"] == "upi"
    assert data["amount_ard"] == 5000.0


# ---------------------------------------------------------------------------
# 5. test_create_below_minimum_api_credits
# ---------------------------------------------------------------------------

async def test_create_below_minimum_api_credits(client):
    """50 ARD is below api_credits minimum (100) -> 400."""
    _, jwt = await _seed_creator(balance=1000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 50},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400
    assert "Minimum" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 6. test_create_below_minimum_gift_card
# ---------------------------------------------------------------------------

async def test_create_below_minimum_gift_card(client):
    """500 ARD is below gift_card minimum (1000) -> 400."""
    _, jwt = await _seed_creator(balance=1000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "gift_card", "amount_ard": 500},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400
    assert "Minimum" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 7. test_create_insufficient_balance
# ---------------------------------------------------------------------------

async def test_create_insufficient_balance(client):
    """Requesting 100000 ARD with only 1000 balance -> 400."""
    _, jwt = await _seed_creator(balance=1000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "bank_withdrawal", "amount_ard": 100000},
        headers=_auth(jwt),
    )
    assert resp.status_code == 400
    assert "Insufficient balance" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 8. test_create_invalid_type
# ---------------------------------------------------------------------------

async def test_create_invalid_type(client):
    """'bitcoin' does not match Pydantic pattern -> 422."""
    _, jwt = await _seed_creator(balance=1000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "bitcoin", "amount_ard": 100},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 9. test_create_zero_amount
# ---------------------------------------------------------------------------

async def test_create_zero_amount(client):
    """0 amount violates gt=0 constraint -> 422."""
    _, jwt = await _seed_creator(balance=1000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 0},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 10. test_create_negative_amount
# ---------------------------------------------------------------------------

async def test_create_negative_amount(client):
    """Negative amount violates gt=0 constraint -> 422."""
    _, jwt = await _seed_creator(balance=1000)

    resp = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": -100},
        headers=_auth(jwt),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 11. test_create_unauthenticated
# ---------------------------------------------------------------------------

async def test_create_unauthenticated(client):
    """No auth header -> 401."""
    resp = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 100},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 12. test_list_redemptions_empty
# ---------------------------------------------------------------------------

async def test_list_redemptions_empty(client):
    """New creator with no redemptions -> empty list."""
    _, jwt = await _seed_creator(balance=1000)

    resp = await client.get(BASE, headers=_auth(jwt))
    assert resp.status_code == 200
    data = resp.json()
    assert data["redemptions"] == []
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# 13. test_list_redemptions_with_entries
# ---------------------------------------------------------------------------

async def test_list_redemptions_with_entries(client):
    """Create 3 redemptions, list shows all three."""
    creator_id, jwt = await _seed_creator(balance=5000)

    # Create 3 api_credits redemptions (auto-complete)
    for _ in range(3):
        r = await client.post(
            BASE,
            json={"redemption_type": "api_credits", "amount_ard": 100},
            headers=_auth(jwt),
        )
        assert r.status_code == 201

    resp = await client.get(BASE, headers=_auth(jwt))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["redemptions"]) == 3


# ---------------------------------------------------------------------------
# 14. test_list_redemptions_status_filter
# ---------------------------------------------------------------------------

async def test_list_redemptions_status_filter(client):
    """Filter by status='completed' excludes pending ones."""
    creator_id, jwt = await _seed_creator(balance=5000)

    # 1 api_credits -> completed
    await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 100},
        headers=_auth(jwt),
    )
    # 1 gift_card -> pending
    await client.post(
        BASE,
        json={"redemption_type": "gift_card", "amount_ard": 1000},
        headers=_auth(jwt),
    )

    # Filter for completed only
    resp = await client.get(
        BASE, params={"status": "completed"}, headers=_auth(jwt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert all(r["status"] == "completed" for r in data["redemptions"])


# ---------------------------------------------------------------------------
# 15. test_list_redemptions_pagination
# ---------------------------------------------------------------------------

async def test_list_redemptions_pagination(client):
    """page=1, page_size=2 with 3 entries returns only 2."""
    creator_id, jwt = await _seed_creator(balance=5000)

    for _ in range(3):
        await client.post(
            BASE,
            json={"redemption_type": "api_credits", "amount_ard": 100},
            headers=_auth(jwt),
        )

    resp = await client.get(
        BASE, params={"page": 1, "page_size": 2}, headers=_auth(jwt),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["redemptions"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


# ---------------------------------------------------------------------------
# 16. test_get_single_redemption
# ---------------------------------------------------------------------------

async def test_get_single_redemption(client):
    """GET /{id} returns the correct redemption."""
    creator_id, jwt = await _seed_creator(balance=1000)

    create_resp = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 100},
        headers=_auth(jwt),
    )
    assert create_resp.status_code == 201
    redemption_id = create_resp.json()["id"]

    resp = await client.get(f"{BASE}/{redemption_id}", headers=_auth(jwt))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == redemption_id
    assert data["redemption_type"] == "api_credits"


# ---------------------------------------------------------------------------
# 17. test_get_nonexistent_redemption
# ---------------------------------------------------------------------------

async def test_get_nonexistent_redemption(client):
    """GET /{bad_id} -> 404."""
    _, jwt = await _seed_creator(balance=1000)

    resp = await client.get(
        f"{BASE}/nonexistent-id-12345", headers=_auth(jwt),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 18. test_cancel_pending_redemption
# ---------------------------------------------------------------------------

async def test_cancel_pending_redemption(client):
    """Cancelling a pending redemption restores the creator's balance."""
    creator_id, jwt = await _seed_creator(balance=2000)

    # Create a gift_card (pending)
    create_resp = await client.post(
        BASE,
        json={"redemption_type": "gift_card", "amount_ard": 1000},
        headers=_auth(jwt),
    )
    assert create_resp.status_code == 201
    redemption_id = create_resp.json()["id"]

    # Balance should be reduced
    balance_after_create = await _get_balance(creator_id)
    assert balance_after_create == pytest.approx(1000.0, abs=0.01)

    # Cancel
    cancel_resp = await client.post(
        f"{BASE}/{redemption_id}/cancel", headers=_auth(jwt),
    )
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["status"] == "rejected"
    assert cancel_data["rejection_reason"] == "Cancelled by creator"

    # Balance should be restored
    balance_after_cancel = await _get_balance(creator_id)
    assert balance_after_cancel == pytest.approx(2000.0, abs=0.01)


# ---------------------------------------------------------------------------
# 19. test_cancel_completed_redemption
# ---------------------------------------------------------------------------

async def test_cancel_completed_redemption(client):
    """Cannot cancel a completed (api_credits auto-processed) redemption -> 400."""
    _, jwt = await _seed_creator(balance=1000)

    create_resp = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 100},
        headers=_auth(jwt),
    )
    assert create_resp.status_code == 201
    redemption_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "completed"

    cancel_resp = await client.post(
        f"{BASE}/{redemption_id}/cancel", headers=_auth(jwt),
    )
    assert cancel_resp.status_code == 400
    assert "Cannot cancel" in cancel_resp.json()["detail"]


# ---------------------------------------------------------------------------
# 20. test_cancel_unauthenticated
# ---------------------------------------------------------------------------

async def test_cancel_unauthenticated(client):
    """No auth header on cancel -> 401."""
    resp = await client.post(f"{BASE}/some-id/cancel")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 21. test_admin_approve_gift_card
# ---------------------------------------------------------------------------

async def test_admin_approve_gift_card(client):
    """Admin approve moves gift_card from pending to processing."""
    creator_id, jwt = await _seed_creator(balance=2000)

    # Create gift_card redemption
    create_resp = await client.post(
        BASE,
        json={"redemption_type": "gift_card", "amount_ard": 1000},
        headers=_auth(jwt),
    )
    assert create_resp.status_code == 201
    redemption_id = create_resp.json()["id"]

    # Admin approve (uses same creator JWT as admin for testing purposes)
    # Admin endpoints use Depends(get_current_creator_id) which resolves
    # `authorization` as a query parameter, not a header.
    approve_resp = await client.post(
        f"{BASE}/admin/{redemption_id}/approve",
        params={"authorization": f"Bearer {jwt}"},
        json={"admin_notes": "Approved by admin"},
    )
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["status"] == "processing"


# ---------------------------------------------------------------------------
# 22. test_admin_reject_with_refund
# ---------------------------------------------------------------------------

async def test_admin_reject_with_refund(client):
    """Admin reject refunds ARD and sets the rejection reason."""
    creator_id, jwt = await _seed_creator(balance=2000)

    # Create gift_card redemption
    create_resp = await client.post(
        BASE,
        json={"redemption_type": "gift_card", "amount_ard": 1000},
        headers=_auth(jwt),
    )
    assert create_resp.status_code == 201
    redemption_id = create_resp.json()["id"]

    # Balance should be debited
    balance_after = await _get_balance(creator_id)
    assert balance_after == pytest.approx(1000.0, abs=0.01)

    # Admin reject — admin endpoints use Depends(), so pass via query param
    reject_resp = await client.post(
        f"{BASE}/admin/{redemption_id}/reject",
        params={"authorization": f"Bearer {jwt}"},
        json={"reason": "Suspicious activity"},
    )
    assert reject_resp.status_code == 200
    data = reject_resp.json()
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Suspicious activity"

    # Balance should be restored
    balance_restored = await _get_balance(creator_id)
    assert balance_restored == pytest.approx(2000.0, abs=0.01)


# ---------------------------------------------------------------------------
# 23. test_admin_reject_empty_reason
# ---------------------------------------------------------------------------

async def test_admin_reject_empty_reason(client):
    """Empty reason string fails Pydantic validation (min_length=1) -> 422."""
    _, jwt = await _seed_creator(balance=2000)

    # Create gift_card
    create_resp = await client.post(
        BASE,
        json={"redemption_type": "gift_card", "amount_ard": 1000},
        headers=_auth(jwt),
    )
    redemption_id = create_resp.json()["id"]

    # Reject with empty reason — admin endpoints use Depends(), pass via query param
    reject_resp = await client.post(
        f"{BASE}/admin/{redemption_id}/reject",
        params={"authorization": f"Bearer {jwt}"},
        json={"reason": ""},
    )
    assert reject_resp.status_code == 422


# ---------------------------------------------------------------------------
# 24. test_get_methods
# ---------------------------------------------------------------------------

async def test_get_methods(client):
    """GET /methods returns 4 methods with correct thresholds (no auth needed)."""
    resp = await client.get(f"{BASE}/methods")
    assert resp.status_code == 200
    data = resp.json()

    assert "methods" in data
    assert len(data["methods"]) == 4

    by_type = {m["type"]: m for m in data["methods"]}
    assert "api_credits" in by_type
    assert "gift_card" in by_type
    assert "upi" in by_type
    assert "bank_withdrawal" in by_type

    # Verify minimum thresholds
    assert by_type["api_credits"]["min_ard"] == 100.0
    assert by_type["gift_card"]["min_ard"] == 1000.0
    assert by_type["upi"]["min_ard"] == 5000.0
    assert by_type["bank_withdrawal"]["min_ard"] == 10000.0

    # Verify token metadata
    assert "peg_rate_usd" in data
    assert data["peg_rate_usd"] == pytest.approx(0.001)


# ---------------------------------------------------------------------------
# 25. test_api_credits_adds_credits
# ---------------------------------------------------------------------------

async def test_api_credits_adds_credits(client):
    """After api_credits redemption, ApiCreditBalance is created/updated."""
    creator_id, jwt = await _seed_creator(balance=1000)

    # First redemption: 100 credits
    resp1 = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 100},
        headers=_auth(jwt),
    )
    assert resp1.status_code == 201
    assert resp1.json()["status"] == "completed"

    # Verify ApiCreditBalance was created
    async with TestSession() as db:
        result = await db.execute(
            select(ApiCreditBalance).where(
                ApiCreditBalance.creator_id == creator_id
            )
        )
        credit_bal = result.scalar_one()
        assert int(credit_bal.credits_remaining) == 100
        assert int(credit_bal.credits_total_purchased) == 100

    # Second redemption: 200 more credits (should accumulate)
    resp2 = await client.post(
        BASE,
        json={"redemption_type": "api_credits", "amount_ard": 200},
        headers=_auth(jwt),
    )
    assert resp2.status_code == 201
    assert resp2.json()["status"] == "completed"

    # Verify accumulated credits
    async with TestSession() as db:
        result = await db.execute(
            select(ApiCreditBalance).where(
                ApiCreditBalance.creator_id == creator_id
            )
        )
        credit_bal = result.scalar_one()
        assert int(credit_bal.credits_remaining) == 300
        assert int(credit_bal.credits_total_purchased) == 300
