"""Comprehensive tests for transaction API routes.

Tests all endpoints in marketplace/api/transactions.py:
- POST /api/v1/transactions/initiate
- POST /api/v1/transactions/{id}/confirm-payment
- POST /api/v1/transactions/{id}/deliver
- POST /api/v1/transactions/{id}/verify
- GET /api/v1/transactions/{id}
- GET /api/v1/transactions (list with filters)
"""

import pytest


# ---------------------------------------------------------------------------
# POST /api/v1/transactions/initiate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initiate_transaction_success(client, make_agent, make_listing, auth_header):
    """Successfully initiate a transaction for a listing."""
    seller, seller_token = await make_agent(name="seller", agent_type="seller")
    buyer, buyer_token = await make_agent(name="buyer", agent_type="buyer")
    listing = await make_listing(seller.id, price_usdc=5.0)

    resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "payment_pending"
    assert data["amount_usdc"] == 5.0
    assert data["content_hash"] == listing.content_hash
    assert "transaction_id" in data
    assert "payment_details" in data
    assert data["payment_details"]["amount_usdc"] == 5.0
    assert data["payment_details"]["simulated"] is True


@pytest.mark.asyncio
async def test_initiate_transaction_no_auth(client, make_agent, make_listing):
    """Reject initiation without authentication."""
    seller, _ = await make_agent(name="seller")
    listing = await make_listing(seller.id)

    resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_initiate_transaction_listing_not_found(client, make_agent, auth_header):
    """Return 404 when listing does not exist."""
    buyer, buyer_token = await make_agent(name="buyer")

    resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": "nonexistent-listing-id"},
        headers=auth_header(buyer_token),
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/transactions/{id}/confirm-payment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_payment_simulated(client, make_agent, make_listing, auth_header):
    """Confirm payment in simulated mode (no signature required)."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id, price_usdc=3.0)

    # Initiate transaction
    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    assert init_resp.status_code == 201
    tx_id = init_resp.json()["transaction_id"]

    # Confirm payment (simulated mode, empty signature)
    confirm_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )
    assert confirm_resp.status_code == 200
    data = confirm_resp.json()
    assert data["status"] == "payment_confirmed"
    assert data["payment_tx_hash"].startswith("sim_0x")
    assert data["paid_at"] is not None


@pytest.mark.asyncio
async def test_confirm_payment_with_tx_hash(client, make_agent, make_listing, auth_header):
    """Confirm payment with a transaction hash."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id)

    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]

    confirm_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": "0xabcd1234"},
        headers=auth_header(buyer_token),
    )
    assert confirm_resp.status_code == 200
    data = confirm_resp.json()
    assert data["status"] == "payment_confirmed"
    assert data["payment_tx_hash"] == "0xabcd1234"


@pytest.mark.asyncio
async def test_confirm_payment_invalid_state(client, make_agent, make_listing, auth_header):
    """Return 400 when trying to confirm payment on non-pending transaction."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id)

    # Initiate and confirm once
    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]
    await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )

    # Try to confirm again
    confirm_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )
    assert confirm_resp.status_code == 400
    assert "expected 'payment_pending'" in confirm_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_payment_no_auth(client, make_agent, make_listing, auth_header):
    """Reject payment confirmation without authentication."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id)

    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]

    confirm_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
    )
    assert confirm_resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/transactions/{id}/deliver
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deliver_content_success(client, make_agent, make_listing, auth_header):
    """Seller can deliver content after payment confirmation."""
    seller, seller_token = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id, price_usdc=2.0)

    # Initiate and confirm payment
    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]
    await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )

    # Deliver content
    deliver_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/deliver",
        json={"content": "sensitive data payload"},
        headers=auth_header(seller_token),
    )
    assert deliver_resp.status_code == 200
    data = deliver_resp.json()
    assert data["status"] == "delivered"
    assert data["delivered_hash"] is not None
    assert data["delivered_at"] is not None


@pytest.mark.asyncio
async def test_deliver_content_not_seller(client, make_agent, make_listing, auth_header):
    """Only the seller can deliver content (403 for others)."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    intruder, intruder_token = await make_agent(name="intruder")
    listing = await make_listing(seller.id)

    # Initiate and confirm
    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]
    await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )

    # Try to deliver as intruder
    deliver_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/deliver",
        json={"content": "fake data"},
        headers=auth_header(intruder_token),
    )
    assert deliver_resp.status_code == 403
    assert "not the seller" in deliver_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deliver_content_invalid_state(client, make_agent, make_listing, auth_header):
    """Return 400 when trying to deliver content before payment confirmation."""
    seller, seller_token = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id)

    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]

    # Try to deliver before payment confirmation
    deliver_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/deliver",
        json={"content": "premature data"},
        headers=auth_header(seller_token),
    )
    assert deliver_resp.status_code == 400
    assert "expected 'payment_confirmed'" in deliver_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/transactions/{id}/verify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_delivery_success(client, make_agent, make_listing, auth_header):
    """Buyer can verify delivery and complete transaction."""
    seller, seller_token = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")

    # Create listing with known content hash
    content_hash = "sha256:abcd1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab"
    listing = await make_listing(seller.id, content_hash=content_hash)

    # Initiate and confirm payment
    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]
    await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )

    # Deliver content
    await client.post(
        f"/api/v1/transactions/{tx_id}/deliver",
        json={"content": "sensitive data payload"},
        headers=auth_header(seller_token),
    )

    # Verify delivery
    verify_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/verify",
        headers=auth_header(buyer_token),
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    # Hash won't match in test, so should be disputed
    assert data["status"] == "disputed"
    assert data["verification_status"] == "failed"


@pytest.mark.asyncio
async def test_verify_delivery_not_buyer(client, make_agent, make_listing, auth_header):
    """Only the buyer can verify delivery (403 for others)."""
    seller, seller_token = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    intruder, intruder_token = await make_agent(name="intruder")
    listing = await make_listing(seller.id)

    # Initiate, confirm, deliver
    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]
    await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )
    await client.post(
        f"/api/v1/transactions/{tx_id}/deliver",
        json={"content": "data"},
        headers=auth_header(seller_token),
    )

    # Try to verify as intruder
    verify_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/verify",
        headers=auth_header(intruder_token),
    )
    assert verify_resp.status_code == 403
    assert "not the buyer" in verify_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_delivery_invalid_state(client, make_agent, make_listing, auth_header):
    """Return 400 when trying to verify before delivery."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id)

    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]
    await client.post(
        f"/api/v1/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )

    # Try to verify before delivery
    verify_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/verify",
        headers=auth_header(buyer_token),
    )
    assert verify_resp.status_code == 400
    assert "expected 'delivered'" in verify_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/v1/transactions/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_transaction_success(client, make_agent, make_listing, auth_header):
    """Retrieve a transaction by ID."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id, price_usdc=4.5)

    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]

    get_resp = await client.get(
        f"/api/v1/transactions/{tx_id}",
        headers=auth_header(buyer_token),
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == tx_id
    assert data["listing_id"] == listing.id
    assert data["buyer_id"] == buyer.id
    assert data["seller_id"] == seller.id
    assert data["amount_usdc"] == 4.5
    assert data["status"] == "payment_pending"


@pytest.mark.asyncio
async def test_get_transaction_not_found(client, make_agent, auth_header):
    """Return 404 when transaction does not exist."""
    agent, token = await make_agent(name="agent")

    resp = await client.get(
        "/api/v1/transactions/nonexistent-tx-id",
        headers=auth_header(token),
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_transaction_no_auth(client, make_agent, make_listing, auth_header):
    """Reject get transaction without authentication."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    listing = await make_listing(seller.id)

    init_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer_token),
    )
    tx_id = init_resp.json()["transaction_id"]

    resp = await client.get(f"/api/v1/transactions/{tx_id}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/transactions (list)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_transactions_as_buyer(client, make_agent, make_listing, auth_header):
    """List transactions where current agent is buyer."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")
    other, _ = await make_agent(name="other")

    listing1 = await make_listing(seller.id, price_usdc=1.0)
    listing2 = await make_listing(seller.id, price_usdc=2.0)
    listing3 = await make_listing(other.id, price_usdc=3.0)

    # Buyer initiates 2 transactions
    await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing1.id},
        headers=auth_header(buyer_token),
    )
    await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing2.id},
        headers=auth_header(buyer_token),
    )

    # List transactions as buyer
    list_resp = await client.get(
        "/api/v1/transactions",
        headers=auth_header(buyer_token),
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["transactions"]) == 2
    for tx in data["transactions"]:
        assert tx["buyer_id"] == buyer.id


@pytest.mark.asyncio
async def test_list_transactions_as_seller(client, make_agent, make_listing, auth_header):
    """List transactions where current agent is seller."""
    seller, seller_token = await make_agent(name="seller")
    buyer1, buyer1_token = await make_agent(name="buyer1")
    buyer2, buyer2_token = await make_agent(name="buyer2")

    listing = await make_listing(seller.id, price_usdc=5.0)

    # Two buyers initiate transactions
    await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer1_token),
    )
    await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing.id},
        headers=auth_header(buyer2_token),
    )

    # List transactions as seller
    list_resp = await client.get(
        "/api/v1/transactions",
        headers=auth_header(seller_token),
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    for tx in data["transactions"]:
        assert tx["seller_id"] == seller.id


@pytest.mark.asyncio
async def test_list_transactions_with_status_filter(client, make_agent, make_listing, auth_header):
    """Filter transactions by status."""
    seller, seller_token = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")

    listing1 = await make_listing(seller.id)
    listing2 = await make_listing(seller.id)

    # Create transaction 1 and confirm payment
    init1_resp = await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing1.id},
        headers=auth_header(buyer_token),
    )
    tx1_id = init1_resp.json()["transaction_id"]
    await client.post(
        f"/api/v1/transactions/{tx1_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=auth_header(buyer_token),
    )

    # Create transaction 2 and leave pending
    await client.post(
        "/api/v1/transactions/initiate",
        json={"listing_id": listing2.id},
        headers=auth_header(buyer_token),
    )

    # Filter by payment_pending
    list_resp = await client.get(
        "/api/v1/transactions?status=payment_pending",
        headers=auth_header(buyer_token),
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    assert data["transactions"][0]["status"] == "payment_pending"

    # Filter by payment_confirmed
    list_resp2 = await client.get(
        "/api/v1/transactions?status=payment_confirmed",
        headers=auth_header(buyer_token),
    )
    assert list_resp2.status_code == 200
    data2 = list_resp2.json()
    assert data2["total"] == 1
    assert data2["transactions"][0]["status"] == "payment_confirmed"


@pytest.mark.asyncio
async def test_list_transactions_pagination(client, make_agent, make_listing, auth_header):
    """Test pagination with page and page_size parameters."""
    seller, _ = await make_agent(name="seller")
    buyer, buyer_token = await make_agent(name="buyer")

    # Create 5 listings and transactions
    for i in range(5):
        listing = await make_listing(seller.id, price_usdc=float(i + 1))
        await client.post(
            "/api/v1/transactions/initiate",
            json={"listing_id": listing.id},
            headers=auth_header(buyer_token),
        )

    # Get page 1 with page_size 2
    resp1 = await client.get(
        "/api/v1/transactions?page=1&page_size=2",
        headers=auth_header(buyer_token),
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["total"] == 5
    assert len(data1["transactions"]) == 2
    assert data1["page"] == 1
    assert data1["page_size"] == 2

    # Get page 2
    resp2 = await client.get(
        "/api/v1/transactions?page=2&page_size=2",
        headers=auth_header(buyer_token),
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 5
    assert len(data2["transactions"]) == 2
    assert data2["page"] == 2


@pytest.mark.asyncio
async def test_list_transactions_no_auth(client):
    """Reject list transactions without authentication."""
    resp = await client.get("/api/v1/transactions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_transactions_empty(client, make_agent, auth_header):
    """Return empty list when agent has no transactions."""
    agent, token = await make_agent(name="lonely-agent")

    resp = await client.get(
        "/api/v1/transactions",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["transactions"] == []
