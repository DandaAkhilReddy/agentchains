"""Integration tests for reputation calculation and ZKP verification.

20 tests total:
- 10 reputation service tests (calculate, get, leaderboard, formula)
- 10 ZKP service tests (merkle, schema, bloom, metadata, generate, verify)

Uses in-memory SQLite via conftest fixtures.
"""

import hashlib
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services import reputation_service, zkp_service
from marketplace.services.zkp_service import (
    build_merkle_tree,
    extract_schema,
    build_bloom_filter,
    check_bloom,
    build_metadata_commitment,
)
from marketplace.models.reputation import ReputationScore
from marketplace.models.zkproof import ZKProof


# ===========================================================================
# REPUTATION TESTS (1-10)
# ===========================================================================


@pytest.mark.asyncio
async def test_calculate_reputation_new_agent(db: AsyncSession, seed_platform, make_agent):
    """New agent with no transactions gets composite_score = 0.2 * 0.8 = 0.16."""
    agent, _ = await make_agent("new-agent")

    rep = await reputation_service.calculate_reputation(db, agent.id)

    assert isinstance(rep, ReputationScore)
    assert rep.total_transactions == 0
    assert rep.successful_deliveries == 0
    assert rep.failed_deliveries == 0
    assert rep.verified_count == 0
    # Formula: 0.4*0 + 0.3*0 + 0.2*0.8 + 0.1*0 = 0.16
    assert float(rep.composite_score) == pytest.approx(0.16, abs=0.001)


@pytest.mark.asyncio
async def test_calculate_reputation_after_sales(
    db: AsyncSession, seed_platform, make_agent, make_listing, make_transaction
):
    """Completed sales increase delivery_rate and raise the composite score."""
    seller, _ = await make_agent("seller-sales")
    buyer, _ = await make_agent("buyer-sales")
    listing = await make_listing(seller.id, price_usdc=5.0)

    # Create 3 completed sales
    await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")
    await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")
    await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=5.0, status="completed")

    rep = await reputation_service.calculate_reputation(db, seller.id)

    assert rep.successful_deliveries == 3
    assert rep.failed_deliveries == 0
    # delivery_rate = 3/3 = 1.0  =>  0.4 * 1.0 = 0.4 contribution
    assert float(rep.composite_score) > 0.16  # strictly higher than a new agent


@pytest.mark.asyncio
async def test_calculate_reputation_with_failed(
    db: AsyncSession, seed_platform, make_agent, make_listing, make_transaction
):
    """Failed deliveries lower the composite score compared to all-completed."""
    seller, _ = await make_agent("seller-fail")
    buyer, _ = await make_agent("buyer-fail")
    listing = await make_listing(seller.id, price_usdc=2.0)

    await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=2.0, status="completed")
    await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=2.0, status="failed")

    rep = await reputation_service.calculate_reputation(db, seller.id)

    assert rep.successful_deliveries == 1
    assert rep.failed_deliveries == 1
    # delivery_rate = 1/2 = 0.5  (lower than 1.0 if all completed)
    # 0.4*0.5 + 0.3*0 + 0.2*0.8 + 0.1*(2/100) = 0.2 + 0.16 + 0.002 = 0.362
    assert float(rep.composite_score) == pytest.approx(0.362, abs=0.001)


@pytest.mark.asyncio
async def test_calculate_reputation_verified(
    db: AsyncSession, seed_platform, make_agent, make_listing, make_transaction
):
    """Verified transactions boost verification_rate and composite score."""
    seller, _ = await make_agent("seller-ver")
    buyer, _ = await make_agent("buyer-ver")
    listing = await make_listing(seller.id, price_usdc=1.0)

    tx1 = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0, status="completed")
    tx2 = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0, status="completed")

    # Mark both as verified
    tx1.verification_status = "verified"
    tx2.verification_status = "verified"
    await db.commit()

    rep = await reputation_service.calculate_reputation(db, seller.id)

    assert rep.verified_count == 2
    # verification_rate = 2/2 = 1.0 => 0.3 * 1.0 = 0.3 contribution
    assert float(rep.composite_score) > 0.16  # higher than a new agent


@pytest.mark.asyncio
async def test_calculate_reputation_volume_saturation(
    db: AsyncSession, seed_platform, make_agent, make_listing, make_transaction
):
    """100+ transactions saturate volume_score at 1.0."""
    seller, _ = await make_agent("seller-vol")
    buyer, _ = await make_agent("buyer-vol")
    listing = await make_listing(seller.id, price_usdc=0.01)

    # Create 105 completed transactions
    for _ in range(105):
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=0.01, status="completed")

    rep = await reputation_service.calculate_reputation(db, seller.id)

    assert rep.total_transactions == 105
    # volume_score = min(105/100, 1.0) = 1.0
    # delivery_rate = 105/105 = 1.0
    # 0.4*1.0 + 0.3*0 + 0.2*0.8 + 0.1*1.0 = 0.4 + 0.16 + 0.1 = 0.66
    assert float(rep.composite_score) == pytest.approx(0.66, abs=0.001)


@pytest.mark.asyncio
async def test_get_reputation_none(db: AsyncSession, seed_platform, make_agent):
    """get_reputation for unknown agent returns None."""
    result = await reputation_service.get_reputation(db, "nonexistent-agent-id-12345")

    assert result is None


@pytest.mark.asyncio
async def test_get_reputation_after_calc(
    db: AsyncSession, seed_platform, make_agent, make_listing, make_transaction
):
    """get_reputation returns the ReputationScore object after calculation."""
    seller, _ = await make_agent("seller-get")
    buyer, _ = await make_agent("buyer-get")
    listing = await make_listing(seller.id, price_usdc=3.0)

    await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=3.0, status="completed")

    # Calculate first
    await reputation_service.calculate_reputation(db, seller.id)

    # Then retrieve
    rep = await reputation_service.get_reputation(db, seller.id)

    assert rep is not None
    assert isinstance(rep, ReputationScore)
    assert rep.agent_id == seller.id
    assert rep.total_transactions == 1
    assert rep.successful_deliveries == 1
    assert rep.last_calculated_at is not None


@pytest.mark.asyncio
async def test_leaderboard_ordering(
    db: AsyncSession, seed_platform, make_agent, make_listing, make_transaction
):
    """3+ agents sorted by composite_score desc on the leaderboard."""
    agents = []
    buyer, _ = await make_agent("buyer-lb")

    # Agent A: 0 completed sales => low score
    agent_a, _ = await make_agent("agent-a")
    listing_a = await make_listing(agent_a.id, price_usdc=1.0)
    await make_transaction(buyer.id, agent_a.id, listing_a.id, amount_usdc=1.0, status="failed")
    agents.append(agent_a)

    # Agent B: 2 completed sales => medium score
    agent_b, _ = await make_agent("agent-b")
    listing_b = await make_listing(agent_b.id, price_usdc=1.0)
    await make_transaction(buyer.id, agent_b.id, listing_b.id, amount_usdc=1.0, status="completed")
    await make_transaction(buyer.id, agent_b.id, listing_b.id, amount_usdc=1.0, status="completed")
    agents.append(agent_b)

    # Agent C: 5 completed sales, all verified => highest score
    agent_c, _ = await make_agent("agent-c")
    listing_c = await make_listing(agent_c.id, price_usdc=1.0)
    for _ in range(5):
        tx = await make_transaction(buyer.id, agent_c.id, listing_c.id, amount_usdc=1.0, status="completed")
        tx.verification_status = "verified"
        await db.commit()
    agents.append(agent_c)

    # Calculate reputations
    for agent in agents:
        await reputation_service.calculate_reputation(db, agent.id)

    leaderboard = await reputation_service.get_leaderboard(db)

    assert len(leaderboard) == 3
    # Scores should be in descending order
    scores = [float(entry.composite_score) for entry in leaderboard]
    assert scores == sorted(scores, reverse=True)
    # Agent C should be first (highest score)
    assert leaderboard[0].agent_id == agent_c.id


@pytest.mark.asyncio
async def test_leaderboard_limit(
    db: AsyncSession, seed_platform, make_agent, make_listing, make_transaction
):
    """limit parameter restricts the number of returned entries."""
    buyer, _ = await make_agent("buyer-limit")

    for i in range(5):
        agent, _ = await make_agent(f"agent-lim-{i}")
        listing = await make_listing(agent.id, price_usdc=1.0)
        await make_transaction(buyer.id, agent.id, listing.id, amount_usdc=1.0, status="completed")
        await reputation_service.calculate_reputation(db, agent.id)

    leaderboard = await reputation_service.get_leaderboard(db, limit=2)

    assert len(leaderboard) == 2


@pytest.mark.asyncio
async def test_reputation_composite_formula(
    db: AsyncSession, seed_platform, make_agent, make_listing, make_transaction
):
    """Verify: composite = 0.4*delivery + 0.3*verification + 0.2*response + 0.1*volume."""
    seller, _ = await make_agent("seller-formula")
    buyer, _ = await make_agent("buyer-formula")
    listing = await make_listing(seller.id, price_usdc=1.0)

    # Create 10 seller transactions: 8 completed, 2 failed
    for _ in range(8):
        tx = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0, status="completed")
        tx.verification_status = "verified"
        await db.commit()
    for _ in range(2):
        await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.0, status="failed")

    rep = await reputation_service.calculate_reputation(db, seller.id)

    # Manual calculation
    delivery_rate = 8 / 10  # 0.8
    verification_rate = 8 / 10  # 8 verified out of 10 total
    response_time_score = 0.8  # placeholder
    volume_score = min(10 / 100, 1.0)  # 0.1

    expected = round(
        0.4 * delivery_rate
        + 0.3 * verification_rate
        + 0.2 * response_time_score
        + 0.1 * volume_score,
        3,
    )
    # 0.4*0.8 + 0.3*0.8 + 0.2*0.8 + 0.1*0.1 = 0.32 + 0.24 + 0.16 + 0.01 = 0.73
    assert float(rep.composite_score) == pytest.approx(expected, abs=0.001)
    assert expected == pytest.approx(0.73, abs=0.001)


# ===========================================================================
# ZKP TESTS (11-20)
# ===========================================================================


@pytest.mark.asyncio
async def test_build_merkle_tree_single_chunk():
    """Small content < 1024 bytes produces a single leaf tree."""
    content = b"Hello, this is a short piece of content."
    result = build_merkle_tree(content)

    assert result["leaf_count"] == 1
    assert result["depth"] == 0
    assert len(result["leaves"]) == 1
    assert len(result["root"]) == 64  # SHA-256 hex digest


@pytest.mark.asyncio
async def test_build_merkle_tree_multi_chunk():
    """Content > 1024 bytes produces multiple leaves in the Merkle tree."""
    # Create 3KB of content (3 chunks of 1024 bytes)
    content = b"A" * (1024 * 3)
    result = build_merkle_tree(content)

    assert result["leaf_count"] == 3
    assert result["depth"] >= 1
    assert len(result["leaves"]) == 3
    # Root should differ from any single leaf
    assert result["root"] not in result["leaves"]


@pytest.mark.asyncio
async def test_extract_schema_json():
    """JSON content returns object schema with field_names."""
    content = json.dumps({
        "name": "Alice",
        "age": 30,
        "active": True,
        "email": "alice@example.com",
    }).encode("utf-8")

    schema = extract_schema(content)

    assert schema["type"] == "object"
    assert schema["field_count"] == 4
    assert "fields" in schema
    assert "name" in schema["fields"]
    assert schema["fields"]["name"]["type"] == "string"
    assert schema["fields"]["age"]["type"] == "number"
    assert schema["fields"]["active"]["type"] == "boolean"


@pytest.mark.asyncio
async def test_extract_schema_text():
    """Non-JSON content returns text mode with line_count and word_count."""
    content = b"This is line one.\nThis is line two.\nThird line here."

    schema = extract_schema(content)

    assert schema["mode"] == "text"
    assert schema["line_count"] == 3
    assert schema["word_count"] == 11
    assert "char_count" in schema


@pytest.mark.asyncio
async def test_bloom_filter_contains():
    """A word present in content returns True from check_bloom."""
    content = b"machine learning deep neural network python tensorflow"
    bloom = build_bloom_filter(content)

    assert check_bloom(bloom, "machine") is True
    assert check_bloom(bloom, "learning") is True
    assert check_bloom(bloom, "python") is True
    assert check_bloom(bloom, "tensorflow") is True


@pytest.mark.asyncio
async def test_bloom_filter_missing():
    """A word NOT in content returns False from check_bloom (most likely)."""
    content = b"machine learning deep neural network python tensorflow"
    bloom = build_bloom_filter(content)

    # These words were never added; bloom filters guarantee no false negatives
    # so absent words should return False (barring extremely rare false positives)
    assert check_bloom(bloom, "javascript") is False
    assert check_bloom(bloom, "blockchain") is False
    assert check_bloom(bloom, "quantum") is False


@pytest.mark.asyncio
async def test_metadata_commitment():
    """Verify commitment hash matches re-computation from public_inputs."""
    now = datetime.now(timezone.utc)
    result = build_metadata_commitment(
        content_size=2048,
        category="api_data",
        freshness_at=now,
        quality_score=0.92,
    )

    assert "commitment" in result
    assert "public_inputs" in result

    # Re-compute the commitment from public_inputs
    payload = json.dumps({
        "content_size": result["public_inputs"]["content_size"],
        "category": result["public_inputs"]["category"],
        "freshness_at": result["public_inputs"]["freshness_at"],
        "quality_score": result["public_inputs"]["quality_score"],
    }, sort_keys=True)
    recomputed = hashlib.sha256(payload.encode()).hexdigest()

    assert result["commitment"] == recomputed


@pytest.mark.asyncio
async def test_generate_proofs_creates_4(
    db: AsyncSession, seed_platform, make_agent, make_listing
):
    """generate_proofs returns exactly 4 ZKProof objects of the expected types."""
    seller, _ = await make_agent("seller-zkp4")
    listing = await make_listing(seller.id, price_usdc=2.0)

    content = b'{"title": "Python Guide", "tags": ["python", "tutorial"]}'
    now = datetime.now(timezone.utc)

    proofs = await zkp_service.generate_proofs(
        db,
        listing.id,
        content,
        category="web_search",
        content_size=len(content),
        freshness_at=now,
        quality_score=0.88,
    )

    assert len(proofs) == 4
    assert all(isinstance(p, ZKProof) for p in proofs)
    proof_types = {p.proof_type for p in proofs}
    assert proof_types == {"merkle_root", "schema", "bloom_filter", "metadata"}

    # Each proof should have a non-empty commitment
    for p in proofs:
        assert p.commitment
        assert p.listing_id == listing.id


@pytest.mark.asyncio
async def test_verify_listing_keywords(
    db: AsyncSession, seed_platform, make_agent, make_listing
):
    """verify_listing with keywords checks bloom filter and passes for present words."""
    seller, _ = await make_agent("seller-vkw")
    listing = await make_listing(seller.id, price_usdc=1.0)

    content = b"artificial intelligence machine learning deep neural networks"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.85
    )

    # Check keywords that ARE in the content
    result = await zkp_service.verify_listing(
        db, listing.id, keywords=["artificial", "machine", "deep"]
    )

    assert result["verified"] is True
    assert result["checks"]["keywords"]["passed"] is True
    assert result["checks"]["keywords"]["details"]["artificial"] is True
    assert result["checks"]["keywords"]["details"]["machine"] is True
    assert result["checks"]["keywords"]["details"]["deep"] is True

    # Check with a keyword that is NOT in the content
    result_fail = await zkp_service.verify_listing(
        db, listing.id, keywords=["blockchain", "cryptocurrency"]
    )

    assert result_fail["verified"] is False
    assert result_fail["checks"]["keywords"]["passed"] is False


@pytest.mark.asyncio
async def test_verify_listing_min_quality(
    db: AsyncSession, seed_platform, make_agent, make_listing
):
    """verify_listing with min_quality checks metadata proof."""
    seller, _ = await make_agent("seller-vq")
    listing = await make_listing(seller.id, price_usdc=1.0)

    content = b"high quality dataset with curated entries"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.95
    )

    # Quality 0.95 >= 0.8 => passes
    result_pass = await zkp_service.verify_listing(
        db, listing.id, min_quality=0.8
    )
    assert result_pass["verified"] is True
    assert result_pass["checks"]["min_quality"]["passed"] is True
    assert result_pass["checks"]["min_quality"]["actual"] == 0.95
    assert result_pass["checks"]["min_quality"]["required"] == 0.8

    # Quality 0.95 < 0.99 => fails
    result_fail = await zkp_service.verify_listing(
        db, listing.id, min_quality=0.99
    )
    assert result_fail["verified"] is False
    assert result_fail["checks"]["min_quality"]["passed"] is False
    assert result_fail["checks"]["min_quality"]["actual"] == 0.95
    assert result_fail["checks"]["min_quality"]["required"] == 0.99
