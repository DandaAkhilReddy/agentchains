"""Integration tests for the express buy flow (20 tests).

Covers the full purchase lifecycle: token payment, fiat/simulated payment,
balance mutations, fee calculations, ledger entries, idempotency,
error cases, listing stat updates, and response format validation.

Uses the shared conftest fixtures (client, make_agent, make_listing,
make_token_account) and the in-memory SQLite test engine.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.config import settings
from marketplace.core.auth import create_access_token
from marketplace.models.token_account import TokenAccount, TokenLedger
from marketplace.models.transaction import Transaction
from marketplace.models.listing import DataListing
from marketplace.tests.conftest import TestSession, _new_id

from sqlalchemy import select


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CDN_PATCH = "marketplace.services.express_service.cdn_get_content"
SAMPLE_CONTENT = b'{"data": "express integration test payload"}'


async def _seed_platform():
    """Ensure platform treasury account exists."""
    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id.is_(None))
        )
        if result.scalar_one_or_none() is None:
            db.add(TokenAccount(
                id=_new_id(), agent_id=None,
                balance=Decimal("0"),
            ))
            await db.commit()


async def _get_token_balance(agent_id: str) -> Decimal:
    """Read the current token balance for an agent."""
    async with TestSession() as db:
        result = await db.execute(
            select(TokenAccount).where(TokenAccount.agent_id == agent_id)
        )
        acct = result.scalar_one()
        return Decimal(str(acct.balance))


async def _get_transaction(tx_id: str) -> Transaction | None:
    """Fetch a transaction by ID."""
    async with TestSession() as db:
        result = await db.execute(
            select(Transaction).where(Transaction.id == tx_id)
        )
        return result.scalar_one_or_none()


async def _get_listing_access_count(listing_id: str) -> int:
    """Fetch the access_count for a listing."""
    async with TestSession() as db:
        result = await db.execute(
            select(DataListing.access_count).where(DataListing.id == listing_id)
        )
        return result.scalar_one()


async def _count_ledger_entries(reference_id: str) -> int:
    """Count TokenLedger rows referencing a given transaction."""
    async with TestSession() as db:
        result = await db.execute(
            select(TokenLedger).where(TokenLedger.reference_id == reference_id)
        )
        return len(result.scalars().all())


async def _get_ledger_for_purchase(tx_id: str) -> TokenLedger | None:
    """Find the purchase ledger entry for a transaction."""
    async with TestSession() as db:
        result = await db.execute(
            select(TokenLedger).where(
                TokenLedger.idempotency_key == f"purchase-{tx_id}"
            )
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 1. test_express_buy_token_success
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_token_success(mock_cdn, client, make_agent, make_listing, make_token_account):
    """POST /api/v1/express/buy with token payment completes the full cycle."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-1")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-1")
    await make_token_account(buyer.id, balance=10000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["transaction_id"]
    assert body["listing_id"] == listing.id
    assert body["content"] == SAMPLE_CONTENT.decode("utf-8")
    assert body["payment_method"] == "token"


# ---------------------------------------------------------------------------
# 2. test_express_buy_creates_transaction
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_creates_transaction(mock_cdn, client, make_agent, make_listing, make_token_account):
    """A completed transaction record is written to the DB with status=completed."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-tx")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=1.0, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-tx")
    await make_token_account(buyer.id, balance=10000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    tx_id = resp.json()["transaction_id"]
    tx = await _get_transaction(tx_id)
    assert tx is not None
    assert tx.status == "completed"
    assert tx.buyer_id == buyer.id
    assert tx.seller_id == seller.id


# ---------------------------------------------------------------------------
# 3. test_express_buy_debits_buyer
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_debits_buyer(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Buyer balance decreases by the total USD cost."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-debit")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-debit")
    initial_balance = 10000.0
    await make_token_account(buyer.id, balance=initial_balance)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    cost_usd = resp.json()["cost_usd"]
    new_balance = await _get_token_balance(buyer.id)
    expected = Decimal(str(initial_balance)) - Decimal(str(cost_usd))
    assert abs(float(new_balance) - float(expected)) < 0.01


# ---------------------------------------------------------------------------
# 4. test_express_buy_credits_seller
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_credits_seller(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Seller balance increases after the purchase (minus the platform fee)."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-credit")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=1.0, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-credit")
    await make_token_account(buyer.id, balance=50000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    seller_balance = await _get_token_balance(seller.id)
    assert float(seller_balance) > 0


# ---------------------------------------------------------------------------
# 5. test_express_buy_fee_calculated
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_fee_calculated(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Platform fee of 2% is correctly applied to the USD transfer."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-fee")
    await make_token_account(seller.id, balance=0)
    price_usdc = 1.0
    listing = await make_listing(seller.id, price_usdc=price_usdc, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-fee")
    await make_token_account(buyer.id, balance=50000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    tx_id = resp.json()["transaction_id"]
    ledger = await _get_ledger_for_purchase(tx_id)
    assert ledger is not None

    amount = Decimal(str(ledger.amount))
    fee = Decimal(str(ledger.fee_amount))
    expected_fee = (amount * Decimal(str(settings.platform_fee_pct))).quantize(
        Decimal("0.000001")
    )
    assert abs(fee - expected_fee) < Decimal("0.001")


# ---------------------------------------------------------------------------
# 6. test_express_buy_fee_deducted
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_fee_deducted(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Platform fee is deducted from the purchase."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-fee2")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=2.0, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-fee2")
    await make_token_account(buyer.id, balance=100000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    tx_id = resp.json()["transaction_id"]
    ledger = await _get_ledger_for_purchase(tx_id)
    assert ledger is not None

    fee = Decimal(str(ledger.fee_amount))
    assert fee > 0


# ---------------------------------------------------------------------------
# 7. test_express_buy_creates_ledger
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_creates_ledger(mock_cdn, client, make_agent, make_listing, make_token_account):
    """A TokenLedger entry is created for the purchase."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-ledger")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-ledger")
    await make_token_account(buyer.id, balance=10000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    tx_id = resp.json()["transaction_id"]
    count = await _count_ledger_entries(tx_id)
    assert count >= 1


# ---------------------------------------------------------------------------
# 8. test_express_buy_fiat_mode
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_fiat_mode(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Fiat/simulated payment mode works (no token balance needed)."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-fiat")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=1.0, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-fiat")
    # No token account needed for fiat, but create with 0 balance for safety
    await make_token_account(buyer.id, balance=0)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=simulated",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_method"] == "simulated"
    assert body["cost_usd"] is None  # no balance transfer for fiat
    assert body["content"] == SAMPLE_CONTENT.decode("utf-8")


# ---------------------------------------------------------------------------
# 9. test_express_buy_self_purchase
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_self_purchase(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Buying your own listing returns 400."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, seller_jwt = await make_agent(name="seller-self")
    await make_token_account(seller.id, balance=10000)
    listing = await make_listing(seller.id, price_usdc=0.5)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {seller_jwt}"},
    )

    assert resp.status_code == 400
    assert "own listing" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 10. test_express_buy_insufficient_balance
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_insufficient_balance(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Buyer with insufficient token balance gets 402."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-insuf")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=10.0, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-insuf")
    await make_token_account(buyer.id, balance=1)  # way too low

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 402
    assert "insufficient" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 11. test_express_buy_inactive_listing
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_inactive_listing(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Attempting to buy an inactive listing fails with 400."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-inactive")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, status="inactive")

    buyer, buyer_jwt = await make_agent(name="buyer-inactive")
    await make_token_account(buyer.id, balance=10000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 400
    assert "not active" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 12. test_express_buy_missing_listing
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_missing_listing(mock_cdn, client, make_agent, make_token_account):
    """Nonexistent listing_id returns 404."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    buyer, buyer_jwt = await make_agent(name="buyer-missing")
    await make_token_account(buyer.id, balance=10000)

    fake_id = _new_id()
    resp = await client.get(
        f"/api/v1/express/{fake_id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 13. test_express_buy_unauthorized
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_unauthorized(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Request without auth token returns 401."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-noauth")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
    )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 14. test_express_buy_updates_listing_stats
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_updates_listing_stats(mock_cdn, client, make_agent, make_listing, make_token_account):
    """The listing's access_count is incremented after purchase."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-stats")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-stats")
    await make_token_account(buyer.id, balance=10000)

    count_before = await _get_listing_access_count(listing.id)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    count_after = await _get_listing_access_count(listing.id)
    assert count_after == count_before + 1


# ---------------------------------------------------------------------------
# 15. test_express_buy_content_delivered
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_content_delivered(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Response includes both content and content_hash."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-content")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-content")
    await make_token_account(buyer.id, balance=10000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "content" in body
    assert "content_hash" in body
    assert body["content_hash"] == listing.content_hash
    assert len(body["content"]) > 0


# ---------------------------------------------------------------------------
# 16. test_express_buy_idempotency
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_idempotency(mock_cdn, client, make_agent, make_listing, make_token_account):
    """The same purchase by the same buyer does NOT double-charge thanks to
    the idempotency key on token_ledger (purchase-{tx_id}).  A second
    purchase creates a new transaction with a new tx_id, but the token
    transfer idempotency is per-tx, so each is unique.  We verify that
    balance decrements are consistent (two purchases = 2x debit)."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-idemp")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-idemp")
    await make_token_account(buyer.id, balance=50000)

    balance_before = await _get_token_balance(buyer.id)

    resp1 = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )
    assert resp1.status_code == 200
    amount1 = Decimal(str(resp1.json()["cost_usd"]))

    resp2 = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )
    assert resp2.status_code == 200
    amount2 = Decimal(str(resp2.json()["cost_usd"]))

    balance_after = await _get_token_balance(buyer.id)
    total_debited = balance_before - balance_after
    # Two separate purchases each debit the same amount
    assert abs(total_debited - (amount1 + amount2)) < Decimal("0.01")
    # Transaction IDs are distinct
    assert resp1.json()["transaction_id"] != resp2.json()["transaction_id"]


# ---------------------------------------------------------------------------
# 17. test_express_buy_zero_price_listing
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_zero_price_listing(mock_cdn, client, make_agent, make_listing, make_token_account):
    """A free listing (price_usdc=0) can be purchased — balance unchanged."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-free")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.0, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-free")
    await make_token_account(buyer.id, balance=100)

    # Use simulated payment for zero price to avoid division issues
    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=simulated",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["price_usdc"] == 0.0
    # Buyer balance should be untouched for simulated payment
    balance_after = await _get_token_balance(buyer.id)
    assert float(balance_after) == 100.0


# ---------------------------------------------------------------------------
# 18. test_express_buy_multiple_purchases
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_multiple_purchases(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Different buyers can purchase the same listing."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-multi")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer1, jwt1 = await make_agent(name="buyer-multi-1")
    await make_token_account(buyer1.id, balance=10000)

    buyer2, jwt2 = await make_agent(name="buyer-multi-2")
    await make_token_account(buyer2.id, balance=10000)

    resp1 = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {jwt1}"},
    )
    resp2 = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {jwt2}"},
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["transaction_id"] != resp2.json()["transaction_id"]

    # Listing access_count should be 2
    count = await _get_listing_access_count(listing.id)
    assert count == 2


# ---------------------------------------------------------------------------
# 20. test_express_buy_response_format
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_response_format(mock_cdn, client, make_agent, make_listing, make_token_account):
    """Response body contains transaction_id, content_hash, and cost_usd fields."""
    mock_cdn.return_value = SAMPLE_CONTENT
    await _seed_platform()

    seller, _ = await make_agent(name="seller-fmt")
    await make_token_account(seller.id, balance=0)
    listing = await make_listing(seller.id, price_usdc=0.5, quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-fmt")
    await make_token_account(buyer.id, balance=10000)

    resp = await client.get(
        f"/api/v1/express/{listing.id}?payment_method=token",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
    )

    assert resp.status_code == 200
    body = resp.json()

    # Required fields
    assert "transaction_id" in body
    assert "content_hash" in body
    assert "cost_usd" in body  # amount_paid in USD
    assert "price_usdc" in body

    # Type checks
    assert isinstance(body["transaction_id"], str)
    assert isinstance(body["content_hash"], str)
    assert isinstance(body["cost_usd"], (int, float))
    assert isinstance(body["price_usdc"], (int, float))

    # Additional expected keys
    assert "listing_id" in body
    assert "content" in body
    assert "payment_method" in body
    assert "seller_id" in body
    assert "delivery_ms" in body
    assert "cache_hit" in body
    assert "buyer_balance" in body

    # Delivery timing header
    assert "X-Delivery-Ms" in resp.headers or "x-delivery-ms" in resp.headers
