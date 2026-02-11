"""Comprehensive edge case tests across multiple marketplace services.

Tests edge cases and boundary conditions including:
- Listing: empty content, huge content hash, zero price, negative quality
- Transaction: double confirm, deliver before payment, verify before delivery
- ZKP: empty content merkle, non-JSON schema fallback
- Catalog: case-insensitive matching
- Token: insufficient balance, account not found
"""

import json
import pytest
from decimal import Decimal

from marketplace.core.exceptions import (
    InvalidTransactionStateError,
    ListingNotFoundError,
    TransactionNotFoundError,
)
from marketplace.services.catalog_service import (
    register_catalog_entry,
    search_catalog,
)
from marketplace.services.listing_service import (
    create_listing,
    get_listing,
)
from marketplace.services.token_service import (
    create_account,
    get_balance,
    transfer,
    deposit,
)
from marketplace.services.transaction_service import (
    initiate_transaction,
    confirm_payment,
    deliver_content,
    verify_delivery,
)
from marketplace.services.zkp_service import (
    generate_proofs,
    get_proofs,
    verify_listing,
    extract_schema,
    build_merkle_tree,
)
from marketplace.schemas.listing import ListingCreateRequest


# ── Listing Edge Cases ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_listing_minimal_content(db, make_agent, seed_platform):
    """Test creating a listing with minimal (single character) content."""
    seller, _ = await make_agent(name="seller")

    req = ListingCreateRequest(
        title="Minimal Data",
        description="This has minimal content",
        category="web_search",
        content="x",  # Minimal content (1 character)
        price_usdc=1.0,
        quality_score=0.5,
        metadata={},
        tags=["test"],
    )

    listing = await create_listing(db, seller.id, req)

    assert listing.id is not None
    assert listing.content_size == 1
    assert listing.content_hash is not None
    assert float(listing.price_usdc) == 1.0


@pytest.mark.asyncio
async def test_listing_huge_content_hash(db, make_agent):
    """Test that content hash is properly truncated/stored."""
    seller, _ = await make_agent()

    # Create listing with normal content
    req = ListingCreateRequest(
        title="Normal listing",
        description="Test",
        category="web_search",
        content="x" * 10000,  # Large content
        price_usdc=2.0,
        quality_score=0.8,
        metadata={},
        tags=[],
    )

    listing = await create_listing(db, seller.id, req)

    # Content hash should be a proper sha256 format
    assert listing.content_hash is not None
    assert listing.content_hash.startswith("sha256:")
    assert len(listing.content_hash) > 7  # "sha256:" + hash
    assert listing.content_size == 10000


@pytest.mark.asyncio
async def test_listing_minimum_price(db, make_agent):
    """Test creating a listing with minimum valid price."""
    seller, _ = await make_agent()

    req = ListingCreateRequest(
        title="Cheap Data",
        description="Very low cost",
        category="web_search",
        content="cheap content here",
        price_usdc=0.001,  # Minimum price
        quality_score=0.5,
        metadata={},
        tags=["cheap"],
    )

    listing = await create_listing(db, seller.id, req)

    assert listing.id is not None
    assert float(listing.price_usdc) == 0.001
    assert listing.status == "active"


@pytest.mark.asyncio
async def test_listing_boundary_quality(db, make_agent):
    """Test creating a listing with boundary quality scores (0.0 and 1.0)."""
    seller, _ = await make_agent()

    # Test with quality = 0.0
    req1 = ListingCreateRequest(
        title="Zero Quality",
        description="Minimum quality",
        category="web_search",
        content="some content",
        price_usdc=1.0,
        quality_score=0.0,
        metadata={},
        tags=[],
    )

    listing1 = await create_listing(db, seller.id, req1)
    assert listing1.id is not None
    assert float(listing1.quality_score) == 0.0

    # Test with quality = 1.0
    req2 = ListingCreateRequest(
        title="Perfect Quality",
        description="Maximum quality",
        category="web_search",
        content="perfect content",
        price_usdc=1.0,
        quality_score=1.0,
        metadata={},
        tags=[],
    )

    listing2 = await create_listing(db, seller.id, req2)
    assert listing2.id is not None
    assert float(listing2.quality_score) == 1.0


@pytest.mark.asyncio
async def test_listing_not_found_error(db):
    """Test that fetching a non-existent listing raises proper error."""
    with pytest.raises(ListingNotFoundError):
        await get_listing(db, "nonexistent-id")


# ── Transaction Edge Cases ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transaction_double_confirm_payment(db, make_agent, make_listing, seed_platform):
    """Test that confirming payment twice raises an error."""
    buyer, _ = await make_agent(name="buyer")
    seller, _ = await make_agent(name="seller")
    await create_account(db, buyer.id)
    await create_account(db, seller.id)

    listing = await make_listing(seller.id, price_usdc=1.0)

    # Initiate transaction
    result = await initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    # Confirm payment first time
    tx = await confirm_payment(db, tx_id)
    assert tx.status == "payment_confirmed"

    # Try to confirm again
    with pytest.raises(InvalidTransactionStateError):
        await confirm_payment(db, tx_id)


@pytest.mark.asyncio
async def test_transaction_deliver_before_payment(db, make_agent, make_listing, seed_platform):
    """Test that delivery before payment raises an error."""
    buyer, _ = await make_agent(name="buyer")
    seller, _ = await make_agent(name="seller")
    await create_account(db, buyer.id)
    await create_account(db, seller.id)

    listing = await make_listing(seller.id, price_usdc=1.0)

    # Initiate transaction
    result = await initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]

    # Try to deliver without payment confirmation
    with pytest.raises(InvalidTransactionStateError):
        await deliver_content(db, tx_id, "delivered content", seller.id)


@pytest.mark.asyncio
async def test_transaction_verify_before_delivery(db, make_agent, make_listing, seed_platform):
    """Test that verification before delivery raises an error."""
    buyer, _ = await make_agent(name="buyer")
    seller, _ = await make_agent(name="seller")
    await create_account(db, buyer.id)
    await create_account(db, seller.id)

    listing = await make_listing(seller.id, price_usdc=1.0)

    # Initiate and confirm payment
    result = await initiate_transaction(db, listing.id, buyer.id)
    tx_id = result["transaction_id"]
    await confirm_payment(db, tx_id)

    # Try to verify without delivery
    with pytest.raises(InvalidTransactionStateError):
        await verify_delivery(db, tx_id, buyer.id)


@pytest.mark.asyncio
async def test_transaction_not_found(db):
    """Test that fetching non-existent transaction raises proper error."""
    from marketplace.services.transaction_service import get_transaction

    with pytest.raises(TransactionNotFoundError):
        await get_transaction(db, "nonexistent-tx-id")


# ── ZKP Edge Cases ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zkp_empty_content_merkle(db, make_agent, make_listing):
    """Test ZKP generation with empty content."""
    seller, _ = await make_agent()
    listing = await make_listing(seller.id, content_hash="sha256:empty")

    empty_content = b""

    # Generate proofs for empty content
    proofs = await generate_proofs(
        db=db,
        listing_id=listing.id,
        content=empty_content,
        category="web_search",
        content_size=0,
        freshness_at=listing.freshness_at,
        quality_score=0.5,
    )

    assert len(proofs) == 4  # All 4 proof types generated

    # Check merkle proof exists and handles empty content
    merkle_proof = next(p for p in proofs if p.proof_type == "merkle_root")
    assert merkle_proof is not None
    assert merkle_proof.commitment is not None

    # Verify the merkle tree structure
    merkle = build_merkle_tree(empty_content)
    assert merkle["leaf_count"] == 1  # Empty content still gets 1 chunk
    assert merkle["depth"] == 0


@pytest.mark.asyncio
async def test_zkp_non_json_schema_fallback(db):
    """Test that non-JSON content falls back to text mode schema."""
    # Plain text content (not JSON)
    text_content = b"This is plain text with some words\nAnd multiple lines"

    schema = extract_schema(text_content)

    assert schema["mode"] == "text"
    assert schema["line_count"] == 2
    assert schema["word_count"] > 0
    assert schema["char_count"] == len(text_content)


@pytest.mark.asyncio
async def test_zkp_verify_listing_no_proofs(db, make_agent, make_listing):
    """Test verification when no proofs exist for a listing."""
    seller, _ = await make_agent()
    listing = await make_listing(seller.id)

    # Try to verify a listing without proofs
    result = await verify_listing(
        db=db,
        listing_id=listing.id,
        keywords=["python"],
        min_quality=0.5,
    )

    assert result["verified"] is False
    assert "error" in result
    assert result["error"] == "No proofs found"


@pytest.mark.asyncio
async def test_zkp_proofs_retrieval(db, make_agent, make_listing):
    """Test retrieving proofs for a listing that has them."""
    seller, _ = await make_agent()
    listing = await make_listing(seller.id)

    content = b'{"data": "test content for proofs"}'

    # Generate proofs
    await generate_proofs(
        db=db,
        listing_id=listing.id,
        content=content,
        category="web_search",
        content_size=len(content),
        freshness_at=listing.freshness_at,
        quality_score=0.85,
    )

    # Retrieve proofs
    proofs = await get_proofs(db, listing.id)

    assert len(proofs) == 4
    proof_types = {p.proof_type for p in proofs}
    assert proof_types == {"merkle_root", "schema", "bloom_filter", "metadata"}


# ── Catalog Edge Cases ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_catalog_case_insensitive_search(db, make_agent):
    """Test that catalog search is case-insensitive."""
    agent, _ = await make_agent(name="seller")

    # Register entry with mixed case
    await register_catalog_entry(
        db=db,
        agent_id=agent.id,
        namespace="WEB_SEARCH",
        topic="Python TUTORIALS",
        description="Learn PYTHON basics",
        price_range_min=0.001,
        price_range_max=0.01,
    )

    # Search with lowercase
    entries, total = await search_catalog(db, q="python")

    assert total == 1
    assert len(entries) == 1
    assert entries[0].topic == "Python TUTORIALS"

    # Search with uppercase
    entries2, total2 = await search_catalog(db, q="PYTHON")

    assert total2 == 1
    assert len(entries2) == 1


@pytest.mark.asyncio
async def test_catalog_search_no_results(db):
    """Test catalog search with no matching results."""
    entries, total = await search_catalog(db, q="nonexistent-query-xyz")

    assert total == 0
    assert len(entries) == 0


# ── Token Service Edge Cases ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_token_insufficient_balance(db, make_agent, seed_platform):
    """Test transfer with insufficient balance."""
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver")

    await create_account(db, sender.id)
    await create_account(db, receiver.id)

    # Try to transfer with zero balance
    with pytest.raises(ValueError, match="Insufficient balance"):
        await transfer(
            db=db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=100.0,
            tx_type="purchase",
        )


@pytest.mark.asyncio
async def test_token_account_not_found(db):
    """Test getting balance for non-existent account."""
    with pytest.raises(ValueError, match="No token account"):
        await get_balance(db, "nonexistent-agent-id")


@pytest.mark.asyncio
async def test_token_zero_amount_transfer(db, make_agent, seed_platform):
    """Test transfer with zero amount (should fail)."""
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver")

    await create_account(db, sender.id)
    await create_account(db, receiver.id)

    with pytest.raises(ValueError, match="must be positive"):
        await transfer(
            db=db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=0.0,
            tx_type="transfer",
        )


@pytest.mark.asyncio
async def test_token_negative_amount_transfer(db, make_agent, seed_platform):
    """Test transfer with negative amount (should fail)."""
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver")

    await create_account(db, sender.id)
    await create_account(db, receiver.id)

    with pytest.raises(ValueError, match="must be positive"):
        await transfer(
            db=db,
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            amount=-10.0,
            tx_type="transfer",
        )


@pytest.mark.asyncio
async def test_token_deposit_zero_amount(db, make_agent, seed_platform):
    """Test deposit with zero amount (should fail)."""
    agent, _ = await make_agent()
    await create_account(db, agent.id)

    with pytest.raises(ValueError, match="must be positive"):
        await deposit(db, agent.id, amount_axn=0.0)


@pytest.mark.asyncio
async def test_token_successful_transfer_with_fees(db, make_agent, seed_platform):
    """Test a successful transfer deducts fees and updates balances correctly."""
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver")

    await create_account(db, sender.id)
    await create_account(db, receiver.id)

    # Give sender some tokens
    await deposit(db, sender.id, amount_axn=1000.0)

    # Transfer tokens
    ledger = await transfer(
        db=db,
        from_agent_id=sender.id,
        to_agent_id=receiver.id,
        amount=100.0,
        tx_type="purchase",
    )

    assert ledger.id is not None
    assert float(ledger.amount) == 100.0
    assert float(ledger.fee_amount) > 0  # Platform fee applied
    assert float(ledger.burn_amount) >= 0  # Burn amount may be applied

    # Check balances
    sender_balance = await get_balance(db, sender.id)
    receiver_balance = await get_balance(db, receiver.id)

    assert sender_balance["balance"] == 900.0
    assert receiver_balance["balance"] > 0  # Should have received net amount


@pytest.mark.asyncio
async def test_token_idempotent_transfer(db, make_agent, seed_platform):
    """Test that duplicate transfer with same idempotency key returns existing ledger."""
    sender, _ = await make_agent(name="sender")
    receiver, _ = await make_agent(name="receiver")

    await create_account(db, sender.id)
    await create_account(db, receiver.id)

    await deposit(db, sender.id, amount_axn=1000.0)

    # First transfer
    ledger1 = await transfer(
        db=db,
        from_agent_id=sender.id,
        to_agent_id=receiver.id,
        amount=50.0,
        tx_type="purchase",
        idempotency_key="test-idempotency-123",
    )

    # Second transfer with same idempotency key
    ledger2 = await transfer(
        db=db,
        from_agent_id=sender.id,
        to_agent_id=receiver.id,
        amount=50.0,
        tx_type="purchase",
        idempotency_key="test-idempotency-123",
    )

    # Should return the same ledger entry
    assert ledger1.id == ledger2.id
    assert ledger1.entry_hash == ledger2.entry_hash

    # Balance should reflect only one transfer
    sender_balance = await get_balance(db, sender.id)
    assert sender_balance["balance"] == 950.0
