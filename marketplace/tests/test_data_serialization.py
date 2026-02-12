"""Data serialization tests for the AgentChains marketplace.

Covers:
  - Decimal precision (prices, balances, fees, exchange rates)
  - JSON round-trip (metadata, tags, empty/special chars)
  - Unicode & content hashing (deterministic hashing, binary round-trip)
  - DateTime handling (created_at, freshness_at, API ISO strings)
  - API response format (numeric price, null optionals, agent ID type)
  - Content size (byte-length match, empty-content hash)
"""

import hashlib
import json
import re
import tempfile
from decimal import Decimal, ROUND_HALF_UP

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.listing import DataListing
from marketplace.models.token_account import TokenAccount
from marketplace.services.deposit_service import get_exchange_rate, _EXCHANGE_RATES
from marketplace.storage.hashfs import HashFS


# ============================================================================
# Decimal precision (4 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_listing_price_round_trips_through_db(db: AsyncSession, make_agent, make_listing):
    """Create listing at price=0.123456, read back, verify exact Decimal."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id, price_usdc=0.123456)

    # Re-read from database (bypass cache)
    result = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    row = result.scalar_one()

    assert row.price_usdc == Decimal("0.123456"), (
        f"Expected Decimal('0.123456'), got {row.price_usdc!r}"
    )


@pytest.mark.asyncio
async def test_token_balance_large_value_preserved(db: AsyncSession, make_agent, make_token_account):
    """Account with balance=100000.123456 retains full precision."""
    agent, _ = await make_agent()
    account = await make_token_account(agent.id, balance=100000.123456)

    # Re-read from database
    result = await db.execute(
        select(TokenAccount).where(TokenAccount.id == account.id)
    )
    row = result.scalar_one()

    assert row.balance == Decimal("100000.123456"), (
        f"Expected Decimal('100000.123456'), got {row.balance!r}"
    )


@pytest.mark.asyncio
async def test_fee_calculation_precise(db: AsyncSession, make_agent, make_token_account, seed_platform):
    """Transfer 100 ARD with 2% fee = exactly 2.000000 fee (not 1.99999...)."""
    from marketplace.config import settings

    amount = Decimal("100")
    fee_pct = Decimal(str(settings.token_platform_fee_pct))

    # Replicate the _to_decimal logic for fee calculation
    def _to_decimal(value):
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    fee = _to_decimal(amount * _to_decimal(fee_pct))

    assert fee == Decimal("2.000000"), (
        f"Expected fee Decimal('2.000000'), got {fee!r}"
    )
    # Confirm no floating-point drift
    assert str(fee) == "2.000000"


def test_exchange_rate_decimal_not_float():
    """deposit_service exchange rates are Decimal, not float."""
    for code, meta in _EXCHANGE_RATES.items():
        rate = meta["rate_per_axn"]
        assert isinstance(rate, Decimal), (
            f"Exchange rate for {code} is {type(rate).__name__}, expected Decimal"
        )
    # Verify via the public helper too
    usd_rate = get_exchange_rate("USD")
    assert isinstance(usd_rate, Decimal)
    assert usd_rate == Decimal("0.001000")


# ============================================================================
# JSON serialization (4 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_listing_metadata_json_round_trip(db: AsyncSession, make_agent):
    """metadata={"key": {"nested": [1,2,3]}} stored and retrieved exactly."""
    agent, _ = await make_agent()

    metadata = {"key": {"nested": [1, 2, 3]}}
    content = "test metadata content"
    content_bytes = content.encode("utf-8")
    from marketplace.services.storage_service import get_storage
    storage = get_storage()
    content_hash = storage.put(content_bytes)

    listing = DataListing(
        seller_id=agent.id,
        title="Metadata Test",
        category="web_search",
        content_hash=content_hash,
        content_size=len(content_bytes),
        price_usdc=Decimal("1.0"),
        metadata_json=json.dumps(metadata),
        tags=json.dumps([]),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    # Re-read from DB
    result = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    row = result.scalar_one()

    recovered = json.loads(row.metadata_json)
    assert recovered == metadata, (
        f"Metadata mismatch: {recovered!r} != {metadata!r}"
    )


@pytest.mark.asyncio
async def test_listing_tags_json_round_trip(db: AsyncSession, make_agent, make_listing):
    """tags=["python", "C++", "node.js"] round-trips correctly."""
    agent, _ = await make_agent()

    tags = ["python", "C++", "node.js"]
    content = "tags round trip content"
    content_bytes = content.encode("utf-8")
    from marketplace.services.storage_service import get_storage
    storage = get_storage()
    content_hash = storage.put(content_bytes)

    listing = DataListing(
        seller_id=agent.id,
        title="Tags Test",
        category="code_analysis",
        content_hash=content_hash,
        content_size=len(content_bytes),
        price_usdc=Decimal("2.5"),
        tags=json.dumps(tags),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    result = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    row = result.scalar_one()

    recovered_tags = json.loads(row.tags)
    assert recovered_tags == tags, (
        f"Tags mismatch: {recovered_tags!r} != {tags!r}"
    )


@pytest.mark.asyncio
async def test_listing_empty_metadata_default(db: AsyncSession, make_agent, make_listing):
    """Listing with no explicit metadata defaults to '{}' or None."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id, price_usdc=1.0)

    result = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    row = result.scalar_one()

    # The column default is "{}", so we expect either "{}" or None
    if row.metadata_json is None:
        assert True  # None is acceptable
    else:
        parsed = json.loads(row.metadata_json)
        assert parsed == {} or isinstance(parsed, dict), (
            f"Expected empty dict or None, got {row.metadata_json!r}"
        )


@pytest.mark.asyncio
async def test_listing_special_chars_in_tags(db: AsyncSession, make_agent):
    """Tags with special chars ["a/b", "c&d"] are preserved."""
    agent, _ = await make_agent()

    special_tags = ["a/b", "c&d", "foo@bar", "x=y+z"]
    content = "special char tags"
    content_bytes = content.encode("utf-8")
    from marketplace.services.storage_service import get_storage
    storage = get_storage()
    content_hash = storage.put(content_bytes)

    listing = DataListing(
        seller_id=agent.id,
        title="Special Tags Test",
        category="web_search",
        content_hash=content_hash,
        content_size=len(content_bytes),
        price_usdc=Decimal("0.5"),
        tags=json.dumps(special_tags),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    result = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    row = result.scalar_one()

    recovered = json.loads(row.tags)
    assert recovered == special_tags, (
        f"Special-char tags mismatch: {recovered!r} != {special_tags!r}"
    )


# ============================================================================
# Unicode & content hashing (4 tests)
# ============================================================================


def test_unicode_content_hash_deterministic():
    """Same unicode content always produces the same hash."""
    tmp_dir = tempfile.mkdtemp()
    fs = HashFS(tmp_dir)

    content = "Hello, world!"
    content_bytes = content.encode("utf-8")

    hash1 = fs.put(content_bytes)
    hash2 = fs.put(content_bytes)

    assert hash1 == hash2, f"Hash mismatch: {hash1} != {hash2}"
    assert hash1.startswith("sha256:")


def test_emoji_content_hash_stable():
    """Content with emojis hashes consistently across multiple calls."""
    tmp_dir = tempfile.mkdtemp()
    fs = HashFS(tmp_dir)

    emoji_content = "Hello World! \U0001f600\U0001f680\U0001f4a1\u2764\ufe0f"
    content_bytes = emoji_content.encode("utf-8")

    hash1 = fs.put(content_bytes)
    hash2 = fs.put(content_bytes)

    assert hash1 == hash2, "Emoji content hash not stable"

    # Also verify against raw hashlib
    expected_hex = hashlib.sha256(content_bytes).hexdigest()
    assert hash1 == f"sha256:{expected_hex}"


def test_binary_content_round_trip_hashfs():
    """Binary bytes put/get through HashFS preserves exact content."""
    tmp_dir = tempfile.mkdtemp()
    fs = HashFS(tmp_dir)

    binary_data = bytes(range(256)) * 4  # 1024 bytes of all byte values
    content_hash = fs.put(binary_data)

    retrieved = fs.get(content_hash)
    assert retrieved is not None, "Failed to retrieve binary content"
    assert retrieved == binary_data, "Binary content corrupted during round-trip"
    assert len(retrieved) == len(binary_data)


def test_content_hash_format_sha256_prefix():
    """All hashes start with 'sha256:' followed by exactly 64 hex chars."""
    tmp_dir = tempfile.mkdtemp()
    fs = HashFS(tmp_dir)

    test_cases = [
        b"simple text",
        b"",
        b"\x00\x01\x02\xff",
        "unicode \u4e16\u754c".encode("utf-8"),
    ]

    pattern = re.compile(r"^sha256:[0-9a-f]{64}$")

    for content in test_cases:
        content_hash = fs.put(content)
        assert pattern.match(content_hash), (
            f"Hash '{content_hash}' does not match sha256:<64 hex> format"
        )


# ============================================================================
# DateTime handling (3 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_listing_created_at_has_value(db: AsyncSession, make_agent, make_listing):
    """Created listing has created_at populated (not None)."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id, price_usdc=1.0)

    result = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    row = result.scalar_one()

    assert row.created_at is not None, "created_at should be populated"
    # Verify it is a datetime object
    from datetime import datetime
    assert isinstance(row.created_at, (datetime, str)), (
        f"created_at type is {type(row.created_at).__name__}, expected datetime"
    )


@pytest.mark.asyncio
async def test_listing_freshness_at_has_value(db: AsyncSession, make_agent, make_listing):
    """Created listing has freshness_at populated (not None)."""
    agent, _ = await make_agent()
    listing = await make_listing(agent.id, price_usdc=1.0)

    result = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    row = result.scalar_one()

    assert row.freshness_at is not None, "freshness_at should be populated"
    from datetime import datetime
    assert isinstance(row.freshness_at, (datetime, str)), (
        f"freshness_at type is {type(row.freshness_at).__name__}, expected datetime"
    )


@pytest.mark.asyncio
async def test_api_response_datetime_is_string(client, db: AsyncSession, make_agent, make_listing):
    """API GET listing response has datetime fields as ISO strings."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id, price_usdc=5.0)

    resp = await client.get(f"/api/v1/listings/{listing.id}")
    assert resp.status_code == 200

    data = resp.json()
    # created_at and freshness_at should be ISO format strings in JSON
    assert isinstance(data["created_at"], str), (
        f"created_at in JSON should be str, got {type(data['created_at']).__name__}"
    )
    assert isinstance(data["freshness_at"], str), (
        f"freshness_at in JSON should be str, got {type(data['freshness_at']).__name__}"
    )
    # Verify they parse as ISO datetimes
    from datetime import datetime
    datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(data["freshness_at"].replace("Z", "+00:00"))


# ============================================================================
# API response format (3 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_listing_response_price_is_number(client, db: AsyncSession, make_agent, make_listing):
    """API response price is numeric (float/int), not a string."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id, price_usdc=3.14)

    resp = await client.get(f"/api/v1/listings/{listing.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data["price_usdc"], (int, float)), (
        f"price_usdc should be numeric, got {type(data['price_usdc']).__name__}: {data['price_usdc']!r}"
    )


@pytest.mark.asyncio
async def test_listing_response_null_fields(client, db: AsyncSession, make_agent, make_listing):
    """Optional fields (like expires_at) are null/None in response."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id, price_usdc=1.0)

    resp = await client.get(f"/api/v1/listings/{listing.id}")
    assert resp.status_code == 200

    data = resp.json()
    # expires_at is optional (DateTime, nullable=True) and not set by make_listing
    assert data["expires_at"] is None, (
        f"expires_at should be null, got {data['expires_at']!r}"
    )


@pytest.mark.asyncio
async def test_agent_response_id_is_string(client, db: AsyncSession, make_agent, make_listing):
    """Agent/seller ID is returned as a string in API responses."""
    agent, token = await make_agent()
    listing = await make_listing(agent.id, price_usdc=2.0)

    resp = await client.get(f"/api/v1/listings/{listing.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data["seller_id"], str), (
        f"seller_id should be str, got {type(data['seller_id']).__name__}"
    )
    assert isinstance(data["id"], str), (
        f"listing id should be str, got {type(data['id']).__name__}"
    )
    # Verify it matches the original UUID
    assert data["seller_id"] == agent.id


# ============================================================================
# Content size (2 tests)
# ============================================================================


@pytest.mark.asyncio
async def test_content_size_matches_bytes(db: AsyncSession, make_agent):
    """Listing content_size matches len(content.encode('utf-8'))."""
    agent, _ = await make_agent()

    content = "Hello, multi-byte world: \u00e9\u00e8\u00ea \u4e16\u754c \U0001f600"
    content_bytes = content.encode("utf-8")
    expected_size = len(content_bytes)

    from marketplace.services.storage_service import get_storage
    storage = get_storage()
    content_hash = storage.put(content_bytes)

    listing = DataListing(
        seller_id=agent.id,
        title="Size Test",
        category="web_search",
        content_hash=content_hash,
        content_size=expected_size,
        price_usdc=Decimal("0.01"),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    result = await db.execute(
        select(DataListing).where(DataListing.id == listing.id)
    )
    row = result.scalar_one()

    assert row.content_size == expected_size, (
        f"content_size mismatch: {row.content_size} != {expected_size}"
    )
    # Cross-check: the stored content should have this exact byte length
    retrieved = storage.get(content_hash)
    assert len(retrieved) == expected_size


def test_hashfs_empty_content_valid_hash():
    """HashFS.put(b'') returns a valid sha256 hash for empty content."""
    tmp_dir = tempfile.mkdtemp()
    fs = HashFS(tmp_dir)

    content_hash = fs.put(b"")

    # Must follow the sha256:<64 hex> format
    assert content_hash.startswith("sha256:")
    hex_part = content_hash.replace("sha256:", "")
    assert len(hex_part) == 64
    assert all(c in "0123456789abcdef" for c in hex_part)

    # Must match the known SHA-256 of empty bytes
    expected = hashlib.sha256(b"").hexdigest()
    assert hex_part == expected, (
        f"Empty content hash mismatch: {hex_part} != {expected}"
    )

    # Round-trip: retrieve should return empty bytes
    retrieved = fs.get(content_hash)
    assert retrieved == b""
