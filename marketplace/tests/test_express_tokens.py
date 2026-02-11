"""Integration tests for express buy with AXN token payment.

broadcast_event is imported lazily inside try/except blocks so no mocking needed.
Only cdn_get_content needs mocking (module-level import in express_service).
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.models.token_account import TokenAccount, TokenSupply
from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.core.auth import create_access_token
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_express_scenario(buyer_balance: float = 10000) -> tuple[str, str, str, str]:
    """Create seller + listing + buyer + platform. Return (buyer_id, buyer_jwt, listing_id, seller_id)."""
    async with TestSession() as db:
        # Platform
        platform = TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0"), tier="platform")
        db.add(platform)
        db.add(TokenSupply(id=1))

        # Seller
        seller_id = _new_id()
        seller = RegisteredAgent(
            id=seller_id, name=f"seller-{seller_id[:8]}",
            agent_type="seller", public_key="ssh-rsa AAAA", status="active",
        )
        db.add(seller)
        seller_acct = TokenAccount(id=_new_id(), agent_id=seller_id, balance=Decimal("0"))
        db.add(seller_acct)

        # Listing
        listing_id = _new_id()
        content_hash = f"sha256:{'a' * 64}"
        listing = DataListing(
            id=listing_id, seller_id=seller_id,
            title="Express Test Listing", category="web_search",
            content_hash=content_hash, content_size=512,
            price_usdc=Decimal("0.5"), price_axn=Decimal("500"),
            quality_score=Decimal("0.5"), status="active",
        )
        db.add(listing)

        # Buyer
        buyer_id = _new_id()
        buyer = RegisteredAgent(
            id=buyer_id, name=f"buyer-{buyer_id[:8]}",
            agent_type="buyer", public_key="ssh-rsa AAAA", status="active",
        )
        db.add(buyer)
        buyer_acct = TokenAccount(
            id=_new_id(), agent_id=buyer_id, balance=Decimal(str(buyer_balance)),
        )
        db.add(buyer_acct)

        await db.commit()

        jwt = create_access_token(buyer_id, buyer.name)
        return buyer_id, jwt, listing_id, seller_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("marketplace.services.express_service.cdn_get_content", new_callable=AsyncMock)
async def test_express_token_debits_buyer(mock_cdn, client):
    """Buyer balance decreases by listing price after express buy."""
    mock_cdn.return_value = b'{"result": "test data"}'

    buyer_id, jwt, listing_id, _ = await _setup_express_scenario(10000)

    resp = await client.get(
        f"/api/v1/express/{listing_id}?payment_method=token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data.get("buyer_balance") is not None
    assert data["buyer_balance"] < 10000


@patch("marketplace.services.express_service.cdn_get_content", new_callable=AsyncMock)
async def test_express_response_has_amount_axn(mock_cdn, client):
    mock_cdn.return_value = b'{"result": "data"}'
    _, jwt, listing_id, _ = await _setup_express_scenario(10000)

    resp = await client.get(
        f"/api/v1/express/{listing_id}?payment_method=token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    assert "amount_axn" in resp.json()
    assert resp.json()["amount_axn"] is not None


@patch("marketplace.services.express_service.cdn_get_content", new_callable=AsyncMock)
async def test_express_response_has_payment_method(mock_cdn, client):
    mock_cdn.return_value = b'{"result": "data"}'
    _, jwt, listing_id, _ = await _setup_express_scenario(10000)

    resp = await client.get(
        f"/api/v1/express/{listing_id}?payment_method=token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_method"] == "token"


@patch("marketplace.services.express_service.cdn_get_content", new_callable=AsyncMock)
async def test_express_fiat_skips_token_debit(mock_cdn, client):
    """payment_method=fiat → no token debit, amount_axn is None."""
    mock_cdn.return_value = b'{"result": "data"}'
    _, jwt, listing_id, _ = await _setup_express_scenario(0)

    resp = await client.get(
        f"/api/v1/express/{listing_id}?payment_method=fiat",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    assert resp.json()["amount_axn"] is None
    assert resp.json()["payment_method"] == "fiat"


@patch("marketplace.services.express_service.cdn_get_content", new_callable=AsyncMock)
async def test_express_insufficient_balance_402(mock_cdn, client):
    """402 Payment Required when buyer can't afford."""
    mock_cdn.return_value = b'{"result": "data"}'
    _, jwt, listing_id, _ = await _setup_express_scenario(buyer_balance=0.001)

    resp = await client.get(
        f"/api/v1/express/{listing_id}?payment_method=token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 402


@patch("marketplace.services.express_service.cdn_get_content", new_callable=AsyncMock)
async def test_express_self_purchase_400(mock_cdn, client):
    """Buyer=seller → 400."""
    mock_cdn.return_value = b'{"result": "data"}'

    # Create scenario where buyer IS the seller
    async with TestSession() as db:
        platform = TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0"), tier="platform")
        db.add(platform)
        db.add(TokenSupply(id=1))

        agent_id = _new_id()
        agent = RegisteredAgent(
            id=agent_id, name=f"self-{agent_id[:8]}",
            agent_type="both", public_key="ssh-rsa AAAA", status="active",
        )
        db.add(agent)
        db.add(TokenAccount(id=_new_id(), agent_id=agent_id, balance=Decimal("1000")))

        listing_id = _new_id()
        db.add(DataListing(
            id=listing_id, seller_id=agent_id,
            title="Self Listing", category="web_search",
            content_hash=f"sha256:{'b' * 64}", content_size=100,
            price_usdc=Decimal("0.1"), status="active",
        ))
        await db.commit()

        jwt = create_access_token(agent_id, agent.name)

    resp = await client.get(
        f"/api/v1/express/{listing_id}?payment_method=fiat",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 400


@patch("marketplace.services.express_service.cdn_get_content", new_callable=AsyncMock)
async def test_express_creates_completed_tx(mock_cdn, client):
    """Transaction record has status='completed' in DB."""
    from sqlalchemy import select
    from marketplace.models.transaction import Transaction

    mock_cdn.return_value = b'{"result": "data"}'
    _, jwt, listing_id, _ = await _setup_express_scenario(10000)

    resp = await client.get(
        f"/api/v1/express/{listing_id}?payment_method=token",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert resp.status_code == 200
    tx_id = resp.json()["transaction_id"]

    async with TestSession() as db:
        result = await db.execute(select(Transaction).where(Transaction.id == tx_id))
        tx = result.scalar_one()
        assert tx.status == "completed"
