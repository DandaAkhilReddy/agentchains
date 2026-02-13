"""Comprehensive tests for the AgentChains marketplace Storage Layer.

Covers HashFS content-addressed storage (sharding, put/get round-trip,
idempotency, verify, compute_hash, exists, delete, size) and the
get_storage() factory function.

20 tests total — all synchronous, each using its own temp-directory-based
HashFS instance for full isolation.
"""

import hashlib
import shutil
import tempfile
from pathlib import Path

import pytest

from marketplace.storage.hashfs import HashFS


@pytest.fixture
def store_dir():
    """Create a temp directory for HashFS, clean up after test."""
    d = tempfile.mkdtemp(prefix="hashfs_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. Sharding: default depth=2 width=2 creates root/ab/cd/abcdef... path
# ---------------------------------------------------------------------------

def test_sharding_default_depth2_width2(store_dir):
    """Default depth=2 width=2 produces root/<2chars>/<2chars>/<fullhash>."""
    store = HashFS(str(store_dir / "store"))
    content = b"hello sharding"
    hex_hash = hashlib.sha256(content).hexdigest()

    store.put(content)

    # Expected path: root / hex_hash[0:2] / hex_hash[2:4] / hex_hash
    expected = store_dir / "store" / hex_hash[0:2] / hex_hash[2:4] / hex_hash
    assert expected.exists(), f"Expected sharded path {expected} to exist"
    assert expected.read_bytes() == content


# ---------------------------------------------------------------------------
# 2. Sharding: custom depth=3 width=3 creates deeper paths
# ---------------------------------------------------------------------------

def test_sharding_custom_depth3_width3(store_dir):
    """depth=3 width=3 produces root/<3chars>/<3chars>/<3chars>/<fullhash>."""
    store = HashFS(str(store_dir / "store"), depth=3, width=3)
    content = b"deeper sharding test"
    hex_hash = hashlib.sha256(content).hexdigest()

    store.put(content)

    expected = (
        store_dir / "store"
        / hex_hash[0:3]
        / hex_hash[3:6]
        / hex_hash[6:9]
        / hex_hash
    )
    assert expected.exists(), f"Expected deeper sharded path {expected} to exist"
    assert expected.read_bytes() == content


# ---------------------------------------------------------------------------
# 3. Put/get round-trip: empty bytes b""
# ---------------------------------------------------------------------------

def test_put_get_roundtrip_empty_bytes(store_dir):
    """Storing and retrieving empty bytes returns b''."""
    store = HashFS(str(store_dir / "store"))
    content = b""
    content_hash = store.put(content)
    retrieved = store.get(content_hash)
    assert retrieved == content


# ---------------------------------------------------------------------------
# 4. Put/get round-trip: binary content with null and high bytes
# ---------------------------------------------------------------------------

def test_put_get_roundtrip_binary(store_dir):
    r"""Storing and retrieving binary content b'\x00\x01\xff' works."""
    store = HashFS(str(store_dir / "store"))
    content = b"\x00\x01\xff"
    content_hash = store.put(content)
    retrieved = store.get(content_hash)
    assert retrieved == content


# ---------------------------------------------------------------------------
# 5. Put/get round-trip: unicode content encoded to UTF-8
# ---------------------------------------------------------------------------

def test_put_get_roundtrip_unicode(store_dir):
    """Storing and retrieving UTF-8 encoded unicode content works."""
    store = HashFS(str(store_dir / "store"))
    text = "Hello \u0928\u092e\u0938\u094d\u0924\u0947 \u4e16\u754c \U0001f30d"
    content = text.encode("utf-8")
    content_hash = store.put(content)
    retrieved = store.get(content_hash)
    assert retrieved == content
    assert retrieved.decode("utf-8") == text


# ---------------------------------------------------------------------------
# 6. Idempotent put: same content twice returns same hash, no duplication
# ---------------------------------------------------------------------------

def test_idempotent_put_same_content_twice(store_dir):
    """Putting the same content twice returns the same hash and does not
    create duplicate files."""
    store = HashFS(str(store_dir / "store"))
    content = b"idempotent content"

    hash1 = store.put(content)
    hash2 = store.put(content)

    assert hash1 == hash2
    assert store.size() == 1  # only one file on disk


# ---------------------------------------------------------------------------
# 7. Put returns sha256:-prefixed hash with 64 hex chars after prefix
# ---------------------------------------------------------------------------

def test_put_returns_sha256_prefixed_hash(store_dir):
    """Hash string starts with 'sha256:' followed by exactly 64 hex chars."""
    store = HashFS(str(store_dir / "store"))
    content_hash = store.put(b"prefix test")

    assert content_hash.startswith("sha256:")
    hex_part = content_hash[len("sha256:"):]
    assert len(hex_part) == 64
    # Validate it is valid hexadecimal
    int(hex_part, 16)


# ---------------------------------------------------------------------------
# 8. Get returns None for a nonexistent hash
# ---------------------------------------------------------------------------

def test_get_returns_none_for_nonexistent(store_dir):
    """get() returns None when the hash does not exist in the store."""
    store = HashFS(str(store_dir / "store"))
    fake_hash = "sha256:" + "a" * 64
    assert store.get(fake_hash) is None


# ---------------------------------------------------------------------------
# 9. Get after delete returns None
# ---------------------------------------------------------------------------

def test_get_after_delete_returns_none(store_dir):
    """After deleting stored content, get() returns None."""
    store = HashFS(str(store_dir / "store"))
    content = b"delete me"
    content_hash = store.put(content)

    assert store.get(content_hash) == content  # exists before delete
    store.delete(content_hash)
    assert store.get(content_hash) is None  # gone after delete


# ---------------------------------------------------------------------------
# 10. Verify: correct content returns True
# ---------------------------------------------------------------------------

def test_verify_correct_content_returns_true(store_dir):
    """verify() returns True when content matches the expected hash."""
    store = HashFS(str(store_dir / "store"))
    content = b"verify me"
    content_hash = store.put(content)

    assert store.verify(content, content_hash) is True


# ---------------------------------------------------------------------------
# 11. Verify: wrong content returns False
# ---------------------------------------------------------------------------

def test_verify_wrong_content_returns_false(store_dir):
    """verify() returns False when content does not match the expected hash."""
    store = HashFS(str(store_dir / "store"))
    content_hash = store.put(b"original content")

    assert store.verify(b"different content", content_hash) is False


# ---------------------------------------------------------------------------
# 12. compute_hash: returns prefixed hash without storing anything
# ---------------------------------------------------------------------------

def test_compute_hash_does_not_store(store_dir):
    """compute_hash() returns a sha256:-prefixed hash but writes nothing."""
    store = HashFS(str(store_dir / "store"))
    content = b"compute only"

    computed = store.compute_hash(content)

    assert computed.startswith("sha256:")
    assert store.size() == 0  # nothing stored
    assert store.get(computed) is None


# ---------------------------------------------------------------------------
# 13. compute_hash matches put hash for the same content
# ---------------------------------------------------------------------------

def test_compute_hash_matches_put_hash(store_dir):
    """compute_hash() and put() return the same hash for identical content."""
    store = HashFS(str(store_dir / "store"))
    content = b"consistency check"

    computed = store.compute_hash(content)
    stored = store.put(content)

    assert computed == stored


# ---------------------------------------------------------------------------
# 14. exists: True after put, False before put
# ---------------------------------------------------------------------------

def test_exists_true_after_put_false_before(store_dir):
    """exists() is False for unknown hash and True after put()."""
    store = HashFS(str(store_dir / "store"))
    content = b"existence test"

    content_hash = store.compute_hash(content)
    assert store.exists(content_hash) is False  # before put

    store.put(content)
    assert store.exists(content_hash) is True  # after put


# ---------------------------------------------------------------------------
# 15. delete: existing returns True, nonexistent returns False
# ---------------------------------------------------------------------------

def test_delete_returns_correct_bool(store_dir):
    """delete() returns True when content existed, False when it did not."""
    store = HashFS(str(store_dir / "store"))
    content = b"delete bool test"
    content_hash = store.put(content)

    assert store.delete(content_hash) is True   # existed
    assert store.delete(content_hash) is False  # already gone
    # Also a completely fabricated hash
    assert store.delete("sha256:" + "f" * 64) is False


# ---------------------------------------------------------------------------
# 16. size: increments after put, decrements after delete
# ---------------------------------------------------------------------------

def test_size_increments_and_decrements(store_dir):
    """size() tracks the number of stored objects correctly."""
    store = HashFS(str(store_dir / "store"))

    assert store.size() == 0

    h1 = store.put(b"first")
    assert store.size() == 1

    h2 = store.put(b"second")
    assert store.size() == 2

    # Idempotent put should not increase count
    store.put(b"first")
    assert store.size() == 2

    store.delete(h1)
    assert store.size() == 1

    store.delete(h2)
    assert store.size() == 0


# ---------------------------------------------------------------------------
# 17. _strip_prefix: removes "sha256:" prefix correctly
# ---------------------------------------------------------------------------

def test_strip_prefix_removes_sha256_prefix():
    """_strip_prefix static method removes the 'sha256:' prefix."""
    hex_hash = "abcdef" * 10 + "abcd"  # 64 chars
    prefixed = f"sha256:{hex_hash}"

    result = HashFS._strip_prefix(prefixed)
    assert result == hex_hash

    # When no prefix is present, string is returned unchanged
    result_no_prefix = HashFS._strip_prefix(hex_hash)
    assert result_no_prefix == hex_hash


# ---------------------------------------------------------------------------
# 18. get_storage() factory: returns an object when no azure connection string
# ---------------------------------------------------------------------------

def test_get_storage_factory_returns_object(store_dir, monkeypatch):
    """get_storage() returns a non-None storage instance (HashFS) when
    AZURE_STORAGE_CONNECTION_STRING is empty."""
    import marketplace.services.storage_service as svc

    # Reset the module-level singleton so the factory runs fresh
    monkeypatch.setattr(svc, "_storage", None)

    from marketplace.config import settings
    monkeypatch.setattr(settings, "content_store_path", str(store_dir / "factory_store"))

    storage = svc.get_storage()
    assert storage is not None
    assert isinstance(storage, HashFS)

    # Clean up: reset singleton so other tests are not affected
    monkeypatch.setattr(svc, "_storage", None)


# ---------------------------------------------------------------------------
# 19. Root directory created on init
# ---------------------------------------------------------------------------

def test_root_directory_created_on_init(store_dir):
    """HashFS __init__ creates the root directory if it does not exist."""
    root = store_dir / "brand_new_store"
    assert not root.exists()

    HashFS(str(root))

    assert root.exists()
    assert root.is_dir()


# ---------------------------------------------------------------------------
# 20. Multiple distinct contents produce different hashes and coexist
# ---------------------------------------------------------------------------

def test_multiple_distinct_contents_coexist(store_dir):
    """Different contents produce different hashes and can all be retrieved."""
    store = HashFS(str(store_dir / "store"))

    items = [
        b"alpha",
        b"beta",
        b"gamma",
        b"\x00" * 1024,
        "unicode data \u2603".encode("utf-8"),
    ]

    hashes = []
    for item in items:
        h = store.put(item)
        hashes.append(h)

    # All hashes are unique
    assert len(set(hashes)) == len(items)

    # All round-trip correctly
    for item, h in zip(items, hashes):
        assert store.get(h) == item

    assert store.size() == len(items)
