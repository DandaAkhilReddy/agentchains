"""Tests for HashFS content-addressed file storage.

Pure filesystem tests using tmp_path -- no database required.
Covers: put, get, exists, delete, verify, compute_hash, size, path traversal safety.
"""

import hashlib

import pytest

from marketplace.storage.hashfs import HashFS


@pytest.fixture
def store(tmp_path):
    """Create a HashFS instance in a temporary directory."""
    return HashFS(str(tmp_path / "content_store"))


@pytest.fixture
def sample_data():
    """Return deterministic sample content and its expected hash."""
    data = b"Hello, HashFS content-addressed storage!"
    hex_hash = hashlib.sha256(data).hexdigest()
    return data, f"sha256:{hex_hash}", hex_hash


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestHashFSInit:
    def test_creates_root_directory(self, tmp_path):
        root = tmp_path / "new_store"
        assert not root.exists()
        HashFS(str(root))
        assert root.exists()
        assert root.is_dir()

    def test_custom_depth_and_width(self, tmp_path):
        store = HashFS(str(tmp_path / "store"), depth=3, width=4)
        assert store.depth == 3
        assert store.width == 4

    def test_default_depth_and_width(self, store):
        assert store.depth == 2
        assert store.width == 2


# ---------------------------------------------------------------------------
# put
# ---------------------------------------------------------------------------


class TestHashFSPut:
    def test_put_returns_prefixed_hash(self, store, sample_data):
        data, expected_hash, _ = sample_data
        result = store.put(data)
        assert result == expected_hash

    def test_put_creates_file(self, store, sample_data):
        data, content_hash, hex_hash = sample_data
        store.put(data)

        # Verify the sharded path structure
        path = store.root / hex_hash[:2] / hex_hash[2:4] / hex_hash
        assert path.exists()
        assert path.read_bytes() == data

    def test_put_idempotent(self, store, sample_data):
        data, content_hash, _ = sample_data
        h1 = store.put(data)
        h2 = store.put(data)
        assert h1 == h2

    def test_put_does_not_overwrite_existing(self, store, sample_data):
        data, _, hex_hash = sample_data
        store.put(data)

        # Verify file content isn't changed on second put
        path = store.root / hex_hash[:2] / hex_hash[2:4] / hex_hash
        original_mtime = path.stat().st_mtime
        store.put(data)
        assert path.stat().st_mtime == original_mtime

    def test_put_empty_content(self, store):
        result = store.put(b"")
        assert result.startswith("sha256:")
        assert store.exists(result) is True

    def test_put_large_content(self, store):
        data = b"x" * (1024 * 1024)  # 1MB
        content_hash = store.put(data)
        assert store.get(content_hash) == data


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestHashFSGet:
    def test_get_returns_stored_content(self, store, sample_data):
        data, content_hash, _ = sample_data
        store.put(data)
        result = store.get(content_hash)
        assert result == data

    def test_get_with_bare_hex_hash(self, store, sample_data):
        data, _, hex_hash = sample_data
        store.put(data)
        result = store.get(hex_hash)
        assert result == data

    def test_get_returns_none_for_missing(self, store):
        result = store.get("sha256:" + "a" * 64)
        assert result is None

    def test_get_returns_none_for_invalid_hash(self, store):
        assert store.get("not-a-valid-hash") is None

    def test_get_returns_none_for_short_hash(self, store):
        assert store.get("sha256:abc") is None

    def test_get_returns_none_for_non_hex_hash(self, store):
        assert store.get("sha256:" + "g" * 64) is None

    def test_get_case_insensitive(self, store, sample_data):
        data, _, hex_hash = sample_data
        store.put(data)
        result = store.get("sha256:" + hex_hash.upper())
        assert result == data


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


class TestHashFSExists:
    def test_exists_true_for_stored(self, store, sample_data):
        data, content_hash, _ = sample_data
        store.put(data)
        assert store.exists(content_hash) is True

    def test_exists_false_for_missing(self, store):
        assert store.exists("sha256:" + "a" * 64) is False

    def test_exists_false_for_invalid_hash(self, store):
        assert store.exists("invalid") is False

    def test_exists_false_for_empty_string(self, store):
        assert store.exists("") is False


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestHashFSDelete:
    def test_delete_removes_file(self, store, sample_data):
        data, content_hash, _ = sample_data
        store.put(data)
        assert store.exists(content_hash) is True

        result = store.delete(content_hash)
        assert result is True
        assert store.exists(content_hash) is False

    def test_delete_returns_false_for_missing(self, store):
        assert store.delete("sha256:" + "a" * 64) is False

    def test_delete_returns_false_for_invalid_hash(self, store):
        assert store.delete("bad-hash") is False

    def test_get_after_delete_returns_none(self, store, sample_data):
        data, content_hash, _ = sample_data
        store.put(data)
        store.delete(content_hash)
        assert store.get(content_hash) is None


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


class TestHashFSVerify:
    def test_verify_matching_content(self, store, sample_data):
        data, content_hash, _ = sample_data
        assert store.verify(data, content_hash) is True

    def test_verify_mismatched_content(self, store, sample_data):
        _, content_hash, _ = sample_data
        assert store.verify(b"different data", content_hash) is False

    def test_verify_invalid_hash(self, store):
        assert store.verify(b"data", "invalid") is False


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------


class TestHashFSComputeHash:
    def test_compute_hash_returns_prefixed(self, store):
        data = b"compute this"
        result = store.compute_hash(data)
        expected = "sha256:" + hashlib.sha256(data).hexdigest()
        assert result == expected

    def test_compute_hash_does_not_store(self, store):
        data = b"ephemeral"
        content_hash = store.compute_hash(data)
        assert store.exists(content_hash) is False


# ---------------------------------------------------------------------------
# size
# ---------------------------------------------------------------------------


class TestHashFSSize:
    def test_size_empty_store(self, store):
        assert store.size() == 0

    def test_size_after_puts(self, store):
        store.put(b"one")
        store.put(b"two")
        store.put(b"three")
        assert store.size() == 3

    def test_size_after_delete(self, store):
        h = store.put(b"deletable")
        assert store.size() == 1
        store.delete(h)
        assert store.size() == 0

    def test_size_deduplication(self, store):
        store.put(b"same")
        store.put(b"same")
        assert store.size() == 1


# ---------------------------------------------------------------------------
# Path traversal safety
# ---------------------------------------------------------------------------


class TestHashFSSafePath:
    def test_rejects_path_traversal_in_hash(self, store):
        """Hashes with path traversal components should normalize to None."""
        malicious = "../../etc/passwd" + "a" * 50  # invalid hex anyway
        assert store.get(malicious) is None
        assert store.exists(malicious) is False
        assert store.delete(malicious) is False

    def test_safe_path_blocks_escape(self, store):
        """Direct _safe_path call with a valid-length but dangerous hex should be blocked."""
        # A valid 64-char hex but the path should stay under root
        valid_hex = "a" * 64
        path = store._safe_path(valid_hex)
        if path is not None:
            assert store.root.resolve() in path.parents or store.root.resolve() == path


# ---------------------------------------------------------------------------
# _normalize_hash
# ---------------------------------------------------------------------------


class TestNormalizeHash:
    def test_strips_sha256_prefix(self):
        hex_hash = "a" * 64
        result = HashFS._normalize_hash(f"sha256:{hex_hash}")
        assert result == hex_hash

    def test_accepts_bare_hex(self):
        hex_hash = "b" * 64
        assert HashFS._normalize_hash(hex_hash) == hex_hash

    def test_lowercases(self):
        hex_hash = "ABCDEF" + "0" * 58
        result = HashFS._normalize_hash(hex_hash)
        assert result == hex_hash.lower()

    def test_rejects_wrong_length(self):
        assert HashFS._normalize_hash("abc") is None

    def test_rejects_non_hex(self):
        assert HashFS._normalize_hash("g" * 64) is None

    def test_rejects_empty(self):
        assert HashFS._normalize_hash("") is None
