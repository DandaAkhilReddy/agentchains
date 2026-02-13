"""Deep route tests for the express buy endpoint (25 tests).

Covers: token/fiat/simulated payments, error codes (400/401/402/404/422),
response fields, balance mutations, transaction records, listing stats,
multiple purchases, and edge cases.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from marketplace.config import settings
from marketplace.core.auth import create_access_token
from marketplace.models.listing import DataListing
from marketplace.models.token_account import TokenAccount
from marketplace.models.transaction import Transaction
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CDN_PATCH = "marketplace.services.express_service.cdn_get_content"
SAMPLE_CONTENT = b'{"data": "deep route test payload"}'
EXPRESS_URL = "/api/v1/express"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 1. test_express_buy_token_payment — full cycle, returns content + transaction
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_balance_payment(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Full token payment cycle: debits buyer, credits seller, returns content."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-tok")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-tok")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["transaction_id"]
    assert body["listing_id"] == listing.id
    assert body["content"] is not None
    assert body["payment_method"] == "token"
    assert body["cost_usd"] is not None
    assert body["cost_usd"] > 0


# ---------------------------------------------------------------------------
# 2. test_express_buy_fiat_payment — payment_method=fiat
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_fiat_payment(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Fiat payment bypasses balance transfer; cost_usd is None."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-fiat")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-fiat")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "fiat"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_method"] == "fiat"
    assert body["cost_usd"] is None


# ---------------------------------------------------------------------------
# 3. test_express_buy_simulated_payment — payment_method=simulated
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_simulated_payment(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Simulated payment works, no balance debit."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-sim")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-sim")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "simulated"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_method"] == "simulated"
    assert body["cost_usd"] is None
    assert body["content"] is not None


# ---------------------------------------------------------------------------
# 4. test_express_buy_invalid_payment_method — "crypto" -> 422
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_invalid_payment_method(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Invalid payment_method (not token/fiat/simulated) returns 422."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-inv")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-inv")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "crypto"},
    )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. test_express_buy_inactive_listing — 400
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_inactive_listing(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Attempting to buy an inactive listing returns 400."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-inact")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data", status="inactive")

    buyer, buyer_jwt = await make_agent(name="buyer-inact")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 400
    assert "not active" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. test_express_buy_self_purchase — buyer==seller -> 400
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_self_purchase(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Buying your own listing returns 400."""
    mock_cdn.return_value = SAMPLE_CONTENT

    agent, agent_jwt = await make_agent(name="self-buyer")
    await make_token_account(agent.id, balance=5000.0)
    listing = await make_listing(agent.id, price_usdc=0.005, content="test data")

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {agent_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 400
    assert "own listing" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 7. test_express_buy_nonexistent_listing — bad ID -> 404
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_nonexistent_listing(
    mock_cdn, client, seed_platform, make_agent, make_token_account
):
    """Nonexistent listing_id returns 404."""
    mock_cdn.return_value = SAMPLE_CONTENT

    buyer, buyer_jwt = await make_agent(name="buyer-404")
    await make_token_account(buyer.id, balance=5000.0)

    fake_id = _new_id()
    resp = await client.post(
        f"{EXPRESS_URL}/{fake_id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 8. test_express_buy_insufficient_balance — low balance -> 402
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_insufficient_balance(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Buyer with insufficient token balance gets 402."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-insuf")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=10.0, content="expensive data")

    buyer, buyer_jwt = await make_agent(name="buyer-insuf")
    await make_token_account(buyer.id, balance=1.0)  # way too low for 10 USD

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 402
    assert "insufficient" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 9. test_express_buy_unauthenticated — no token -> 401
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_unauthenticated(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Request without auth token returns 401."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-noauth")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        json={"payment_method": "token"},
    )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 10. test_express_buy_returns_content — response contains actual content string
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_returns_content(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Response body contains the actual content string from storage."""
    mock_cdn.return_value = b'{"result": "important data"}'

    seller, _ = await make_agent(name="seller-content")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-content")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == '{"result": "important data"}'
    assert len(body["content"]) > 0


# ---------------------------------------------------------------------------
# 11. test_express_buy_returns_transaction_id — response has transaction_id
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_returns_transaction_id(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Response body includes a non-empty transaction_id string."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-txid")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-txid")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "transaction_id" in body
    assert isinstance(body["transaction_id"], str)
    assert len(body["transaction_id"]) > 0


# ---------------------------------------------------------------------------
# 12. test_express_buy_delivery_ms_header — X-Delivery-Ms header present
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_delivery_ms_header(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Response includes X-Delivery-Ms header with a numeric value."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-hdr")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-hdr")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    # httpx lowercases headers
    header_val = resp.headers.get("x-delivery-ms") or resp.headers.get("X-Delivery-Ms")
    assert header_val is not None
    assert float(header_val) >= 0


# ---------------------------------------------------------------------------
# 13. test_express_buy_cache_hit_field — cache_hit field in response
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_cache_hit_field(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Response body includes the cache_hit boolean field."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-cache")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-cache")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "cache_hit" in body
    assert isinstance(body["cache_hit"], bool)


# ---------------------------------------------------------------------------
# 14. test_express_buy_buyer_balance_updated — balance decreased by price+fee
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_buyer_balance_updated(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Buyer's balance decreases by the USD cost after purchase."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-bdec")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-bdec")
    initial_balance = 5000.0
    await make_token_account(buyer.id, balance=initial_balance)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    cost_usd = resp.json()["cost_usd"]
    new_balance = await _get_token_balance(buyer.id)
    expected = Decimal(str(initial_balance)) - Decimal(str(cost_usd))
    assert abs(float(new_balance) - float(expected)) < 0.01


# ---------------------------------------------------------------------------
# 15. test_express_buy_seller_balance_updated — seller gets price minus fee
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_seller_balance_updated(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Seller's balance increases after the purchase (minus platform fee)."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-sinc")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data", quality_score=0.5)

    buyer, buyer_jwt = await make_agent(name="buyer-sinc")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    seller_balance = await _get_token_balance(seller.id)
    assert float(seller_balance) > 0


# ---------------------------------------------------------------------------
# 16. test_express_buy_creates_transaction_record — Transaction in DB after purchase
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_creates_transaction_record(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """A completed Transaction record exists in the DB after purchase."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-txdb")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-txdb")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    tx_id = resp.json()["transaction_id"]

    tx = await _get_transaction(tx_id)
    assert tx is not None
    assert tx.status == "completed"
    assert tx.buyer_id == buyer.id
    assert tx.seller_id == seller.id
    assert tx.listing_id == listing.id


# ---------------------------------------------------------------------------
# 17. test_express_buy_listing_access_count — access_count incremented
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_listing_access_count(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Listing access_count is incremented by 1 after a purchase."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-cnt")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-cnt")
    await make_token_account(buyer.id, balance=5000.0)

    count_before = await _get_listing_access_count(listing.id)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    count_after = await _get_listing_access_count(listing.id)
    assert count_after == count_before + 1


# ---------------------------------------------------------------------------
# 18. test_express_buy_default_payment_method — defaults to "token"
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_default_payment_method(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Omitting payment_method from request body defaults to 'token'."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-dflt")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-dflt")
    await make_token_account(buyer.id, balance=5000.0)

    # No payment_method in request body
    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_method"] == "token"
    assert body["cost_usd"] is not None


# ---------------------------------------------------------------------------
# 19. test_express_buy_price_usdc_in_response — correct price in response
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_price_usdc_in_response(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Response price_usdc matches the listing's price."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-price")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-price")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "price_usdc" in body
    assert abs(body["price_usdc"] - 0.005) < 0.0001


# ---------------------------------------------------------------------------
# 20. test_express_buy_cost_usd_in_response — USD cost in response
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_cost_usd_in_response(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Response cost_usd reflects the USD amount charged."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-usd")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-usd")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "cost_usd" in body
    assert body["cost_usd"] is not None
    assert body["cost_usd"] > 0


# ---------------------------------------------------------------------------
# 21. test_express_buy_content_hash_in_response — content_hash matches listing
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_content_hash_in_response(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Response content_hash matches the listing's stored content_hash."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-hash")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-hash")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "content_hash" in body
    assert body["content_hash"] == listing.content_hash


# ---------------------------------------------------------------------------
# 22. test_express_buy_multiple_purchases — same listing, 2 different buyers
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_multiple_purchases(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Two different buyers can purchase the same listing; access_count=2."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-multi")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer1, jwt1 = await make_agent(name="buyer-multi-1")
    await make_token_account(buyer1.id, balance=5000.0)

    buyer2, jwt2 = await make_agent(name="buyer-multi-2")
    await make_token_account(buyer2.id, balance=5000.0)

    resp1 = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {jwt1}"},
        json={"payment_method": "token"},
    )
    resp2 = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {jwt2}"},
        json={"payment_method": "token"},
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["transaction_id"] != resp2.json()["transaction_id"]

    count = await _get_listing_access_count(listing.id)
    assert count == 2


# ---------------------------------------------------------------------------
# 23. test_express_buy_low_price_listing — very cheap listing (0.001)
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_low_price_listing(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Very low price listing (0.001 USD) can be purchased successfully."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-cheap")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.001, content="cheap data")

    buyer, buyer_jwt = await make_agent(name="buyer-cheap")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["price_usdc"] == 0.001
    assert body["cost_usd"] is not None


# ---------------------------------------------------------------------------
# 25. test_express_buy_seller_id_in_response — seller_id matches listing's seller
# ---------------------------------------------------------------------------

@patch(CDN_PATCH, new_callable=AsyncMock)
async def test_express_buy_seller_id_in_response(
    mock_cdn, client, seed_platform, make_agent, make_listing, make_token_account
):
    """Response seller_id matches the listing's seller_id."""
    mock_cdn.return_value = SAMPLE_CONTENT

    seller, _ = await make_agent(name="seller-sid")
    await make_token_account(seller.id, balance=0.0)
    listing = await make_listing(seller.id, price_usdc=0.005, content="test data")

    buyer, buyer_jwt = await make_agent(name="buyer-sid")
    await make_token_account(buyer.id, balance=5000.0)

    resp = await client.post(
        f"{EXPRESS_URL}/{listing.id}",
        headers={"Authorization": f"Bearer {buyer_jwt}"},
        json={"payment_method": "token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "seller_id" in body
    assert body["seller_id"] == seller.id
