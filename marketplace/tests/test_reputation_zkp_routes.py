"""Integration tests for reputation and ZKP API routes.

Tests:
- GET /api/v1/reputation/leaderboard
- GET /api/v1/reputation/{agent_id}
- GET /api/v1/zkp/{listing_id}/proofs
- POST /api/v1/zkp/{listing_id}/verify
- GET /api/v1/zkp/{listing_id}/bloom-check

Uses httpx AsyncClient + ASGITransport to test against the real FastAPI app.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from marketplace.services import zkp_service


# ---------------------------------------------------------------------------
# GET /api/v1/reputation/leaderboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leaderboard_empty(client):
    """Leaderboard returns empty list when no reputation data exists."""
    resp = await client.get("/api/v1/reputation/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_leaderboard_with_agents(client, make_agent, make_listing, make_transaction, db):
    """Leaderboard returns ranked agents with reputation scores."""
    # Create two agents
    agent1, _ = await make_agent("agent-1")
    agent2, _ = await make_agent("agent-2")

    # Create listings
    listing1 = await make_listing(agent1.id, price_usdc=5.0)
    listing2 = await make_listing(agent2.id, price_usdc=10.0)

    # Create completed transactions (agent1 has more volume)
    await make_transaction(agent2.id, agent1.id, listing1.id, amount_usdc=5.0, status="completed")
    await make_transaction(agent2.id, agent1.id, listing1.id, amount_usdc=5.0, status="completed")
    await make_transaction(agent1.id, agent2.id, listing2.id, amount_usdc=10.0, status="completed")

    # Calculate reputations
    from marketplace.services import reputation_service
    await reputation_service.calculate_reputation(db, agent1.id)
    await reputation_service.calculate_reputation(db, agent2.id)

    # Request leaderboard
    resp = await client.get("/api/v1/reputation/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 2

    # Verify structure
    first = data["entries"][0]
    assert first["rank"] == 1
    assert "agent_id" in first
    assert "agent_name" in first
    assert "composite_score" in first
    assert "total_transactions" in first
    assert "total_volume_usdc" in first
    assert first["composite_score"] >= 0


@pytest.mark.asyncio
async def test_leaderboard_limit(client, make_agent, make_listing, make_transaction, db):
    """Leaderboard respects limit parameter."""
    # Create 5 agents with transactions
    agents = []
    for i in range(5):
        agent, _ = await make_agent(f"agent-{i}")
        agents.append(agent)
        listing = await make_listing(agent.id, price_usdc=1.0)
        await make_transaction(agents[0].id, agent.id, listing.id, amount_usdc=1.0, status="completed")

    # Calculate reputations
    from marketplace.services import reputation_service
    for agent in agents:
        await reputation_service.calculate_reputation(db, agent.id)

    # Request with limit=3
    resp = await client.get("/api/v1/reputation/leaderboard?limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) <= 3


@pytest.mark.asyncio
async def test_leaderboard_limit_validation(client):
    """Leaderboard rejects invalid limit values."""
    # Limit too large
    resp = await client.get("/api/v1/reputation/leaderboard?limit=101")
    assert resp.status_code == 422

    # Limit too small
    resp = await client.get("/api/v1/reputation/leaderboard?limit=0")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/reputation/{agent_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_reputation_creates_if_missing(client, make_agent):
    """Get reputation auto-calculates if not found."""
    agent, _ = await make_agent()

    resp = await client.get(f"/api/v1/reputation/{agent.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == agent.id
    assert data["agent_name"] == agent.name
    assert data["total_transactions"] == 0
    assert data["composite_score"] >= 0
    assert "last_calculated_at" in data


@pytest.mark.asyncio
async def test_get_reputation_with_data(client, make_agent, make_listing, make_transaction, db):
    """Get reputation returns calculated metrics."""
    agent, _ = await make_agent()
    buyer, _ = await make_agent("buyer")
    listing = await make_listing(agent.id, price_usdc=10.0)

    # Create completed and failed transactions
    tx1 = await make_transaction(buyer.id, agent.id, listing.id, amount_usdc=10.0, status="completed")
    tx2 = await make_transaction(buyer.id, agent.id, listing.id, amount_usdc=10.0, status="completed")
    tx3 = await make_transaction(buyer.id, agent.id, listing.id, amount_usdc=10.0, status="failed")

    # Manually set verification status
    tx1.verification_status = "verified"
    await db.commit()

    resp = await client.get(f"/api/v1/reputation/{agent.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_transactions"] == 3
    assert data["successful_deliveries"] == 2
    assert data["failed_deliveries"] == 1
    assert data["verified_count"] == 1
    assert data["total_volume_usdc"] == 30.0


@pytest.mark.asyncio
async def test_get_reputation_recalculate_flag(client, make_agent, make_listing, make_transaction, db):
    """Get reputation with recalculate=true forces recalculation."""
    agent, _ = await make_agent()
    buyer, _ = await make_agent("buyer")
    listing = await make_listing(agent.id, price_usdc=5.0)
    await make_transaction(buyer.id, agent.id, listing.id, amount_usdc=5.0, status="completed")

    # First call without recalculate
    resp1 = await client.get(f"/api/v1/reputation/{agent.id}")
    assert resp1.status_code == 200
    timestamp1 = resp1.json()["last_calculated_at"]

    # Add another transaction
    await make_transaction(buyer.id, agent.id, listing.id, amount_usdc=5.0, status="completed")

    # Call with recalculate=true
    resp2 = await client.get(f"/api/v1/reputation/{agent.id}?recalculate=true")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["total_transactions"] == 2
    timestamp2 = data["last_calculated_at"]
    # Timestamp should be newer
    assert timestamp2 >= timestamp1


@pytest.mark.asyncio
async def test_get_reputation_nonexistent_agent(client):
    """Get reputation for non-existent agent returns 404 (agent not found)."""
    resp = await client.get("/api/v1/reputation/nonexistent-id-12345")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/zkp/{listing_id}/proofs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_proofs_no_proofs(client, make_agent, make_listing):
    """Get proofs returns empty list when no proofs exist."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    resp = await client.get(f"/api/v1/zkp/{listing.id}/proofs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["listing_id"] == listing.id
    assert data["count"] == 0
    assert data["proofs"] == []


@pytest.mark.asyncio
async def test_get_proofs_with_proofs(client, make_agent, make_listing, db):
    """Get proofs returns all ZK proofs for a listing."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id, content_size=2048, quality_score=0.9)

    # Generate proofs
    content = b'{"name": "test", "description": "python tutorial", "tags": ["python", "tutorial"]}'
    proofs = await zkp_service.generate_proofs(
        db,
        listing.id,
        content,
        "web_search",
        len(content),
        datetime.now(timezone.utc),
        0.9
    )
    await db.commit()

    resp = await client.get(f"/api/v1/zkp/{listing.id}/proofs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["listing_id"] == listing.id
    assert data["count"] == 4  # merkle_root, schema, bloom_filter, metadata
    assert len(data["proofs"]) == 4

    # Verify proof types
    proof_types = {p["proof_type"] for p in data["proofs"]}
    assert proof_types == {"merkle_root", "schema", "bloom_filter", "metadata"}

    # Verify structure
    for proof in data["proofs"]:
        assert "id" in proof
        assert "proof_type" in proof
        assert "commitment" in proof
        assert "public_inputs" in proof
        assert isinstance(proof["public_inputs"], dict)


# ---------------------------------------------------------------------------
# POST /api/v1/zkp/{listing_id}/verify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_no_proofs(client, make_agent, make_listing):
    """Verify returns error when no proofs exist."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"keywords": ["test"]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert data["verified"] is False


@pytest.mark.asyncio
async def test_verify_keywords_pass(client, make_agent, make_listing, db):
    """Verify passes when keywords are present in bloom filter."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    # Generate proofs with specific content
    content = b"python tutorial for beginners"
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"keywords": ["python", "tutorial"]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["checks"]["keywords"]["passed"] is True
    assert data["checks"]["keywords"]["details"]["python"] is True
    assert data["checks"]["keywords"]["details"]["tutorial"] is True


@pytest.mark.asyncio
async def test_verify_keywords_fail(client, make_agent, make_listing, db):
    """Verify fails when keywords are not present."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b"python tutorial for beginners"
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"keywords": ["javascript", "react"]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is False
    assert data["checks"]["keywords"]["passed"] is False


@pytest.mark.asyncio
async def test_verify_schema_fields_pass(client, make_agent, make_listing, db):
    """Verify passes when schema fields exist."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b'{"title": "test", "description": "content", "tags": ["a", "b"]}'
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"schema_has_fields": ["title", "description"]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["checks"]["schema_fields"]["passed"] is True
    assert data["checks"]["schema_fields"]["details"]["title"] is True
    assert data["checks"]["schema_fields"]["details"]["description"] is True


@pytest.mark.asyncio
async def test_verify_schema_fields_fail(client, make_agent, make_listing, db):
    """Verify fails when schema fields don't exist."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b'{"title": "test", "description": "content"}'
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"schema_has_fields": ["missing_field", "another_missing"]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is False
    assert data["checks"]["schema_fields"]["passed"] is False


@pytest.mark.asyncio
async def test_verify_min_size_pass(client, make_agent, make_listing, db):
    """Verify passes when content size meets minimum."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b"x" * 500
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"min_size": 400}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["checks"]["min_size"]["passed"] is True
    assert data["checks"]["min_size"]["actual"] == 500
    assert data["checks"]["min_size"]["required"] == 400


@pytest.mark.asyncio
async def test_verify_min_size_fail(client, make_agent, make_listing, db):
    """Verify fails when content size below minimum."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b"small"
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"min_size": 1000}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is False
    assert data["checks"]["min_size"]["passed"] is False


@pytest.mark.asyncio
async def test_verify_min_quality_pass(client, make_agent, make_listing, db):
    """Verify passes when quality score meets minimum."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b"high quality content"
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.95
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"min_quality": 0.8}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["checks"]["min_quality"]["passed"] is True
    assert data["checks"]["min_quality"]["actual"] == 0.95
    assert data["checks"]["min_quality"]["required"] == 0.8


@pytest.mark.asyncio
async def test_verify_min_quality_fail(client, make_agent, make_listing, db):
    """Verify fails when quality score below minimum."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b"low quality"
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.5
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"min_quality": 0.8}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is False
    assert data["checks"]["min_quality"]["passed"] is False


@pytest.mark.asyncio
async def test_verify_multiple_checks_all_pass(client, make_agent, make_listing, db):
    """Verify passes when all checks succeed."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b'{"title": "python tutorial", "content": "learn python programming"}'
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.9
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={
            "keywords": ["python", "tutorial"],
            "schema_has_fields": ["title", "content"],
            "min_size": 50,
            "min_quality": 0.8
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["checks"]["keywords"]["passed"] is True
    assert data["checks"]["schema_fields"]["passed"] is True
    assert data["checks"]["min_size"]["passed"] is True
    assert data["checks"]["min_quality"]["passed"] is True


@pytest.mark.asyncio
async def test_verify_multiple_checks_one_fails(client, make_agent, make_listing, db):
    """Verify fails when any check fails."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b'{"title": "python tutorial"}'
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.9
    )
    await db.commit()

    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={
            "keywords": ["python"],
            "min_size": 10000  # Too high
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is False
    assert data["checks"]["keywords"]["passed"] is True
    assert data["checks"]["min_size"]["passed"] is False


@pytest.mark.asyncio
async def test_verify_validation_errors(client, make_agent, make_listing):
    """Verify rejects invalid request payloads."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    # Too many keywords
    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"keywords": ["word"] * 25}
    )
    assert resp.status_code == 422

    # Too many schema fields
    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"schema_has_fields": ["field"] * 60}
    )
    assert resp.status_code == 422

    # Negative size
    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"min_size": -1}
    )
    assert resp.status_code == 422

    # Invalid quality range
    resp = await client.post(
        f"/api/v1/zkp/{listing.id}/verify",
        json={"min_quality": 1.5}
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/zkp/{listing_id}/bloom-check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bloom_check_word_present(client, make_agent, make_listing, db):
    """Bloom check returns true for words in content."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b"python tutorial for beginners learning programming"
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    resp = await client.get(f"/api/v1/zkp/{listing.id}/bloom-check?word=python")
    assert resp.status_code == 200
    data = resp.json()
    assert data["listing_id"] == listing.id
    assert data["word"] == "python"
    assert data["probably_present"] is True
    assert "note" in data


@pytest.mark.asyncio
async def test_bloom_check_word_absent(client, make_agent, make_listing, db):
    """Bloom check returns false for words not in content."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id)

    content = b"python tutorial"
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    resp = await client.get(f"/api/v1/zkp/{listing.id}/bloom-check?word=javascript")
    assert resp.status_code == 200
    data = resp.json()
    assert data["probably_present"] is False


@pytest.mark.asyncio
async def test_bloom_check_case_insensitive(client, make_agent, make_listing, db):
    """Bloom check is case-insensitive."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id)

    content = b"Python Tutorial"
    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content),
        datetime.now(timezone.utc), 0.8
    )
    await db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # Check lowercase
    resp = await client.get(f"/api/v1/zkp/{listing.id}/bloom-check?word=python", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["probably_present"] is True

    # Check uppercase
    resp = await client.get(f"/api/v1/zkp/{listing.id}/bloom-check?word=PYTHON", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["probably_present"] is True


@pytest.mark.asyncio
async def test_bloom_check_no_bloom_filter(client, make_agent, make_listing):
    """Bloom check returns error when no bloom filter exists."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id)

    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(f"/api/v1/zkp/{listing.id}/bloom-check?word=test", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_bloom_check_missing_word_param(client, make_agent, make_listing):
    """Bloom check requires word parameter."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id)

    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(f"/api/v1/zkp/{listing.id}/bloom-check", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bloom_check_word_too_long(client, make_agent, make_listing):
    """Bloom check rejects words longer than 100 characters."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id)

    headers = {"Authorization": f"Bearer {token}"}
    long_word = "a" * 101
    resp = await client.get(f"/api/v1/zkp/{listing.id}/bloom-check?word={long_word}", headers=headers)
    assert resp.status_code == 422
