"""Unit tests for the ZKP service — zero-knowledge proof generation and verification.

Tests use in-memory SQLite via conftest fixtures.
All 4 proof types are tested: merkle_root, schema, bloom_filter, metadata.
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services import zkp_service
from marketplace.models.zkproof import ZKProof


# ---------------------------------------------------------------------------
# Merkle Tree Tests
# ---------------------------------------------------------------------------

def test_build_merkle_tree_single_chunk():
    """A single chunk (< 1KB) creates a tree with 1 leaf, depth=0."""
    content = b"Hello, World!"
    result = zkp_service.build_merkle_tree(content)

    assert "root" in result
    assert result["leaf_count"] == 1
    assert result["depth"] == 0
    assert len(result["leaves"]) == 1
    assert isinstance(result["root"], str)
    assert len(result["root"]) == 64  # SHA-256 hex


def test_build_merkle_tree_multiple_chunks():
    """Content > 1KB creates multiple chunks and builds a proper tree."""
    # Create 3KB of content (3 chunks)
    content = b"x" * (zkp_service.CHUNK_SIZE * 3)
    result = zkp_service.build_merkle_tree(content)

    assert result["leaf_count"] == 3
    assert result["depth"] == 2  # log2(3) rounded up needs 2 levels to reach 1 root
    assert len(result["leaves"]) == 3


def test_build_merkle_tree_empty_content():
    """Empty content creates a tree with 1 empty chunk."""
    content = b""
    result = zkp_service.build_merkle_tree(content)

    assert result["leaf_count"] == 1
    assert result["depth"] == 0
    assert len(result["leaves"]) == 1


def test_build_merkle_tree_exactly_2kb():
    """Exactly 2KB creates 2 chunks, depth=1."""
    content = b"x" * (zkp_service.CHUNK_SIZE * 2)
    result = zkp_service.build_merkle_tree(content)

    assert result["leaf_count"] == 2
    assert result["depth"] == 1
    assert len(result["leaves"]) == 2


# ---------------------------------------------------------------------------
# Schema Extraction Tests
# ---------------------------------------------------------------------------

def test_extract_schema_json_object():
    """JSON object extracts field names, types, and counts."""
    content = json.dumps({
        "name": "Alice",
        "age": 30,
        "active": True,
    }).encode()

    schema = zkp_service.extract_schema(content)

    assert schema["type"] == "object"
    assert schema["field_count"] == 3
    assert "name" in schema["fields"]
    assert schema["fields"]["name"]["type"] == "string"
    assert schema["fields"]["age"]["type"] == "number"
    assert schema["fields"]["active"]["type"] == "boolean"


def test_extract_schema_json_array():
    """JSON array extracts item schema and count."""
    content = json.dumps([
        {"id": 1, "value": "first"},
        {"id": 2, "value": "second"},
    ]).encode()

    schema = zkp_service.extract_schema(content)

    assert schema["type"] == "array"
    assert schema["item_count"] == 2
    assert schema["item_schema"]["type"] == "object"
    assert schema["item_schema"]["field_count"] == 2


def test_extract_schema_json_nested():
    """Nested JSON extracts nested structure."""
    content = json.dumps({
        "user": {
            "name": "Bob",
            "tags": ["admin", "verified"]
        }
    }).encode()

    schema = zkp_service.extract_schema(content)

    assert schema["type"] == "object"
    assert schema["field_count"] == 1
    assert schema["fields"]["user"]["type"] == "object"
    assert schema["fields"]["user"]["fields"]["tags"]["type"] == "array"


def test_extract_schema_text_fallback():
    """Non-JSON content returns text-mode schema with word/line counts."""
    content = b"This is plain text.\nWith multiple lines.\nAnd words."

    schema = zkp_service.extract_schema(content)

    assert schema["mode"] == "text"
    assert schema["line_count"] == 3
    assert schema["word_count"] == 9
    assert "char_count" in schema


def test_extract_schema_invalid_json():
    """Invalid JSON falls back to text mode."""
    content = b'{"invalid": json but not really}'

    schema = zkp_service.extract_schema(content)

    assert schema["mode"] == "text"


# ---------------------------------------------------------------------------
# Bloom Filter Tests
# ---------------------------------------------------------------------------

def test_build_bloom_filter_basic():
    """Bloom filter is 256 bytes and contains inserted words."""
    content = b"machine learning python tutorial"
    bloom = zkp_service.build_bloom_filter(content)

    assert isinstance(bloom, bytes)
    assert len(bloom) == zkp_service.BLOOM_SIZE  # 256 bytes

    # Check that words are in the filter
    assert zkp_service.check_bloom(bloom, "machine")
    assert zkp_service.check_bloom(bloom, "learning")
    assert zkp_service.check_bloom(bloom, "python")
    assert zkp_service.check_bloom(bloom, "tutorial")


def test_build_bloom_filter_case_insensitive():
    """Bloom filter is case-insensitive."""
    content = b"Python MACHINE Learning"
    bloom = zkp_service.build_bloom_filter(content)

    assert zkp_service.check_bloom(bloom, "python")
    assert zkp_service.check_bloom(bloom, "PYTHON")
    assert zkp_service.check_bloom(bloom, "Python")
    assert zkp_service.check_bloom(bloom, "machine")
    assert zkp_service.check_bloom(bloom, "MACHINE")


def test_bloom_filter_negative_check():
    """Words not in content return False (no false negatives)."""
    content = b"data science analytics"
    bloom = zkp_service.build_bloom_filter(content)

    # These words should NOT be in the filter
    assert not zkp_service.check_bloom(bloom, "javascript")
    assert not zkp_service.check_bloom(bloom, "blockchain")
    assert not zkp_service.check_bloom(bloom, "quantum")


def test_bloom_filter_special_characters():
    """Special characters are treated as word separators."""
    content = b"hello-world test_case foo.bar"
    bloom = zkp_service.build_bloom_filter(content)

    # Each part separated by special chars is a word
    assert zkp_service.check_bloom(bloom, "hello")
    assert zkp_service.check_bloom(bloom, "world")
    assert zkp_service.check_bloom(bloom, "test")
    assert zkp_service.check_bloom(bloom, "case")


# ---------------------------------------------------------------------------
# Metadata Commitment Tests
# ---------------------------------------------------------------------------

def test_build_metadata_commitment_basic():
    """Metadata commitment returns hash and public inputs."""
    now = datetime.now(timezone.utc)
    result = zkp_service.build_metadata_commitment(
        content_size=1024,
        category="web_search",
        freshness_at=now,
        quality_score=0.85,
    )

    assert "commitment" in result
    assert "public_inputs" in result
    assert isinstance(result["commitment"], str)
    assert len(result["commitment"]) == 64  # SHA-256 hex

    inputs = result["public_inputs"]
    assert inputs["content_size"] == 1024
    assert inputs["category"] == "web_search"
    assert inputs["quality_score"] == 0.85
    assert inputs["freshness_at"] == now.isoformat()


def test_build_metadata_commitment_deterministic():
    """Same inputs produce same commitment hash."""
    now = datetime.now(timezone.utc)

    c1 = zkp_service.build_metadata_commitment(
        content_size=2048,
        category="api_data",
        freshness_at=now,
        quality_score=0.75,
    )

    c2 = zkp_service.build_metadata_commitment(
        content_size=2048,
        category="api_data",
        freshness_at=now,
        quality_score=0.75,
    )

    assert c1["commitment"] == c2["commitment"]


def test_build_metadata_commitment_different_inputs():
    """Different inputs produce different commitments."""
    now = datetime.now(timezone.utc)

    c1 = zkp_service.build_metadata_commitment(1024, "web_search", now, 0.85)
    c2 = zkp_service.build_metadata_commitment(2048, "web_search", now, 0.85)

    assert c1["commitment"] != c2["commitment"]


# ---------------------------------------------------------------------------
# Generate Proofs Tests (integration with DB)
# ---------------------------------------------------------------------------

async def test_generate_proofs_creates_4_proofs(db: AsyncSession, make_listing, make_agent):
    """generate_proofs creates all 4 proof types for a listing."""
    agent, _ = await make_agent("seller")
    listing = await make_listing(agent.id, price_usdc=1.0)

    content = b'{"title": "Test Data", "tags": ["python", "tutorial"]}'
    now = datetime.now(timezone.utc)

    proofs = await zkp_service.generate_proofs(
        db,
        listing.id,
        content,
        category="web_search",
        content_size=len(content),
        freshness_at=now,
        quality_score=0.85,
    )

    assert len(proofs) == 4
    proof_types = {p.proof_type for p in proofs}
    assert proof_types == {"merkle_root", "schema", "bloom_filter", "metadata"}


async def test_generate_proofs_merkle_root_proof(db: AsyncSession, make_listing, make_agent):
    """Merkle root proof contains root, leaf_count, depth."""
    agent, _ = await make_agent("seller2")
    listing = await make_listing(agent.id)

    content = b"x" * 2048  # 2KB
    now = datetime.now(timezone.utc)

    proofs = await zkp_service.generate_proofs(
        db, listing.id, content, "api_data", len(content), now, 0.8
    )

    merkle = next(p for p in proofs if p.proof_type == "merkle_root")
    assert merkle.commitment  # root hash

    proof_data = json.loads(merkle.proof_data)
    assert proof_data["leaf_count"] == 2
    assert proof_data["depth"] == 1


async def test_generate_proofs_schema_proof(db: AsyncSession, make_listing, make_agent):
    """Schema proof contains field names and types."""
    agent, _ = await make_agent("seller3")
    listing = await make_listing(agent.id)

    content = json.dumps({"name": "Alice", "score": 95}).encode()
    now = datetime.now(timezone.utc)

    proofs = await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.9
    )

    schema_proof = next(p for p in proofs if p.proof_type == "schema")
    public_inputs = json.loads(schema_proof.public_inputs)

    assert public_inputs["type"] == "object"
    assert public_inputs["field_count"] == 2
    assert "name" in public_inputs["field_names"]
    assert "score" in public_inputs["field_names"]


async def test_generate_proofs_bloom_filter_proof(db: AsyncSession, make_listing, make_agent):
    """Bloom filter proof contains bloom_hex and metadata."""
    agent, _ = await make_agent("seller4")
    listing = await make_listing(agent.id)

    content = b"blockchain cryptocurrency bitcoin ethereum"
    now = datetime.now(timezone.utc)

    proofs = await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.75
    )

    bloom_proof = next(p for p in proofs if p.proof_type == "bloom_filter")
    proof_data = json.loads(bloom_proof.proof_data)

    assert "bloom_hex" in proof_data
    assert proof_data["size_bytes"] == 256
    assert proof_data["hash_count"] == 3

    # Verify words are in the bloom filter
    bloom_bytes = bytes.fromhex(proof_data["bloom_hex"])
    assert zkp_service.check_bloom(bloom_bytes, "blockchain")
    assert zkp_service.check_bloom(bloom_bytes, "bitcoin")


async def test_generate_proofs_metadata_proof(db: AsyncSession, make_listing, make_agent):
    """Metadata proof contains size, category, freshness, quality."""
    agent, _ = await make_agent("seller5")
    listing = await make_listing(agent.id)

    content = b"test data content"
    now = datetime.now(timezone.utc)

    proofs = await zkp_service.generate_proofs(
        db, listing.id, content, "api_data", 1024, now, 0.88
    )

    meta_proof = next(p for p in proofs if p.proof_type == "metadata")
    public_inputs = json.loads(meta_proof.public_inputs)

    assert public_inputs["content_size"] == 1024
    assert public_inputs["category"] == "api_data"
    assert public_inputs["quality_score"] == 0.88
    assert public_inputs["freshness_at"] == now.isoformat()


# ---------------------------------------------------------------------------
# Verify Listing Tests
# ---------------------------------------------------------------------------

async def test_verify_listing_no_proofs(db: AsyncSession, make_listing, make_agent):
    """verify_listing returns error when no proofs exist."""
    agent, _ = await make_agent("buyer")
    listing = await make_listing(agent.id)

    result = await zkp_service.verify_listing(db, listing.id)

    assert result["listing_id"] == listing.id
    assert result["verified"] is False
    assert "error" in result


async def test_verify_listing_keyword_check_pass(db: AsyncSession, make_listing, make_agent):
    """verify_listing passes when all keywords are in bloom filter."""
    agent, _ = await make_agent("seller6")
    listing = await make_listing(agent.id)

    content = b"machine learning deep neural networks AI python tensorflow"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.9
    )

    result = await zkp_service.verify_listing(
        db, listing.id, keywords=["machine", "learning", "python"]
    )

    assert result["verified"] is True
    assert result["checks"]["keywords"]["passed"] is True
    assert result["checks"]["keywords"]["details"]["machine"] is True
    assert result["checks"]["keywords"]["details"]["python"] is True


async def test_verify_listing_keyword_check_fail(db: AsyncSession, make_listing, make_agent):
    """verify_listing fails when any keyword is not in bloom filter."""
    agent, _ = await make_agent("seller7")
    listing = await make_listing(agent.id)

    content = b"machine learning python"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.9
    )

    result = await zkp_service.verify_listing(
        db, listing.id, keywords=["blockchain", "quantum"]
    )

    assert result["verified"] is False
    assert result["checks"]["keywords"]["passed"] is False


async def test_verify_listing_schema_fields_pass(db: AsyncSession, make_listing, make_agent):
    """verify_listing passes when required fields exist in schema."""
    agent, _ = await make_agent("seller8")
    listing = await make_listing(agent.id)

    content = json.dumps({
        "user_id": 123,
        "username": "alice",
        "email": "alice@example.com"
    }).encode()
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "api_data", len(content), now, 0.85
    )

    result = await zkp_service.verify_listing(
        db, listing.id, schema_has_fields=["user_id", "username"]
    )

    assert result["verified"] is True
    assert result["checks"]["schema_fields"]["passed"] is True
    assert result["checks"]["schema_fields"]["details"]["user_id"] is True


async def test_verify_listing_schema_fields_fail(db: AsyncSession, make_listing, make_agent):
    """verify_listing fails when required fields are missing."""
    agent, _ = await make_agent("seller9")
    listing = await make_listing(agent.id)

    content = json.dumps({"name": "Alice"}).encode()
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "api_data", len(content), now, 0.85
    )

    result = await zkp_service.verify_listing(
        db, listing.id, schema_has_fields=["age", "address"]
    )

    assert result["verified"] is False
    assert result["checks"]["schema_fields"]["passed"] is False


async def test_verify_listing_min_size_pass(db: AsyncSession, make_listing, make_agent):
    """verify_listing passes when content size meets minimum."""
    agent, _ = await make_agent("seller10")
    listing = await make_listing(agent.id)

    content = b"x" * 2048
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", 2048, now, 0.8
    )

    result = await zkp_service.verify_listing(db, listing.id, min_size=1024)

    assert result["verified"] is True
    assert result["checks"]["min_size"]["passed"] is True
    assert result["checks"]["min_size"]["actual"] == 2048


async def test_verify_listing_min_size_fail(db: AsyncSession, make_listing, make_agent):
    """verify_listing fails when content size is below minimum."""
    agent, _ = await make_agent("seller11")
    listing = await make_listing(agent.id)

    content = b"small"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", 5, now, 0.8
    )

    result = await zkp_service.verify_listing(db, listing.id, min_size=1024)

    assert result["verified"] is False
    assert result["checks"]["min_size"]["passed"] is False


async def test_verify_listing_min_quality_pass(db: AsyncSession, make_listing, make_agent):
    """verify_listing passes when quality meets minimum."""
    agent, _ = await make_agent("seller12")
    listing = await make_listing(agent.id)

    content = b"high quality data"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.92
    )

    result = await zkp_service.verify_listing(db, listing.id, min_quality=0.8)

    assert result["verified"] is True
    assert result["checks"]["min_quality"]["passed"] is True
    assert result["checks"]["min_quality"]["actual"] == 0.92


async def test_verify_listing_min_quality_fail(db: AsyncSession, make_listing, make_agent):
    """verify_listing fails when quality is below minimum."""
    agent, _ = await make_agent("seller13")
    listing = await make_listing(agent.id)

    content = b"low quality data"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.5
    )

    result = await zkp_service.verify_listing(db, listing.id, min_quality=0.8)

    assert result["verified"] is False
    assert result["checks"]["min_quality"]["passed"] is False


async def test_verify_listing_multiple_checks_all_pass(db: AsyncSession, make_listing, make_agent):
    """verify_listing passes when all requested checks pass."""
    agent, _ = await make_agent("seller14")
    listing = await make_listing(agent.id)

    content = json.dumps({
        "title": "Python Machine Learning Tutorial",
        "content": "Learn ML with Python, tensorflow, neural networks",
        "rating": 4.8
    }).encode()
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.9
    )

    result = await zkp_service.verify_listing(
        db,
        listing.id,
        keywords=["python", "machine"],
        schema_has_fields=["title", "content"],
        min_size=100,
        min_quality=0.85,
    )

    assert result["verified"] is True
    assert all(check["passed"] for check in result["checks"].values())


async def test_verify_listing_multiple_checks_one_fail(db: AsyncSession, make_listing, make_agent):
    """verify_listing fails when any check fails."""
    agent, _ = await make_agent("seller15")
    listing = await make_listing(agent.id)

    content = json.dumps({"title": "Test"}).encode()
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.6
    )

    result = await zkp_service.verify_listing(
        db,
        listing.id,
        keywords=["test"],
        min_quality=0.8,  # This will fail (actual is 0.6)
    )

    assert result["verified"] is False


# ---------------------------------------------------------------------------
# Bloom Check Single Word Tests
# ---------------------------------------------------------------------------

async def test_bloom_check_word_present(db: AsyncSession, make_listing, make_agent):
    """bloom_check_word returns True when word is in filter."""
    agent, _ = await make_agent("seller16")
    listing = await make_listing(agent.id)

    content = b"blockchain cryptocurrency bitcoin decentralized"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.85
    )

    result = await zkp_service.bloom_check_word(db, listing.id, "bitcoin")

    assert result["listing_id"] == listing.id
    assert result["word"] == "bitcoin"
    assert result["probably_present"] is True
    assert "note" in result


async def test_bloom_check_word_absent(db: AsyncSession, make_listing, make_agent):
    """bloom_check_word returns False when word is not in filter."""
    agent, _ = await make_agent("seller17")
    listing = await make_listing(agent.id)

    content = b"machine learning artificial intelligence"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.85
    )

    result = await zkp_service.bloom_check_word(db, listing.id, "quantum")

    assert result["probably_present"] is False


async def test_bloom_check_word_no_proof(db: AsyncSession, make_listing, make_agent):
    """bloom_check_word returns error when no bloom filter proof exists."""
    agent, _ = await make_agent("seller18")
    listing = await make_listing(agent.id)

    result = await zkp_service.bloom_check_word(db, listing.id, "test")

    assert "error" in result
    assert "No bloom filter proof found" in result["error"]


async def test_bloom_check_word_case_insensitive(db: AsyncSession, make_listing, make_agent):
    """bloom_check_word is case-insensitive."""
    agent, _ = await make_agent("seller19")
    listing = await make_listing(agent.id)

    content = b"Python Machine Learning"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.85
    )

    result1 = await zkp_service.bloom_check_word(db, listing.id, "python")
    result2 = await zkp_service.bloom_check_word(db, listing.id, "PYTHON")
    result3 = await zkp_service.bloom_check_word(db, listing.id, "Python")

    assert result1["probably_present"] is True
    assert result2["probably_present"] is True
    assert result3["probably_present"] is True


# ---------------------------------------------------------------------------
# Get Proofs Tests
# ---------------------------------------------------------------------------

async def test_get_proofs_returns_all(db: AsyncSession, make_listing, make_agent):
    """get_proofs returns all proofs for a listing."""
    agent, _ = await make_agent("seller20")
    listing = await make_listing(agent.id)

    content = b"test content"
    now = datetime.now(timezone.utc)

    await zkp_service.generate_proofs(
        db, listing.id, content, "web_search", len(content), now, 0.85
    )

    proofs = await zkp_service.get_proofs(db, listing.id)

    assert len(proofs) == 4
    proof_types = {p.proof_type for p in proofs}
    assert proof_types == {"merkle_root", "schema", "bloom_filter", "metadata"}


async def test_get_proofs_empty_when_no_proofs(db: AsyncSession, make_listing, make_agent):
    """get_proofs returns empty list when no proofs exist."""
    agent, _ = await make_agent("seller21")
    listing = await make_listing(agent.id)

    proofs = await zkp_service.get_proofs(db, listing.id)

    assert proofs == []
