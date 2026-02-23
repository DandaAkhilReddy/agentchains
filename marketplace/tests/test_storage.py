"""Comprehensive tests for marketplace/storage/azure_blob.py and
marketplace/storage/hashfs.py.

Covers:
  - HashFS: put/get/exists/delete/verify/compute_hash/size, sharding layout,
    idempotency, _normalize_hash, _strip_prefix, _safe_path path-traversal
    guard, and root-directory creation.
  - AzureBlobStore: construction, lazy _get_client, _blob_client, put/get/
    exists/delete/get_url — all with proper mock isolation of the Azure SDK.
  - AzureBlobStorage: the secondary key-value interface (put/get/exists/
    delete/get_url) exercised via mocked container client.

All tests are async def (asyncio_mode = "auto" in pyproject.toml).
The Azure SDK is never imported at the network level — everything is patched
with unittest.mock.MagicMock / AsyncMock.
"""

import hashlib
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from marketplace.storage.hashfs import HashFS
from marketplace.storage.azure_blob import AzureBlobStore, AzureBlobStorage


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def _hex(data: bytes) -> str:
    """Return the bare SHA-256 hex digest for *data*."""
    return hashlib.sha256(data).hexdigest()


def _prefixed(data: bytes) -> str:
    """Return the sha256:<hex> prefixed hash for *data*."""
    return f"sha256:{_hex(data)}"


# ---------------------------------------------------------------------------
# HashFS fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    """Temporary directory; removed after every test."""
    d = tempfile.mkdtemp(prefix="hashfs_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def store(tmp_dir):
    """Fresh HashFS instance with default depth=2, width=2."""
    return HashFS(str(tmp_dir / "store"))


# ---------------------------------------------------------------------------
# AzureBlobStore fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_blob_client():
    """Return a mock BlobClient whose methods return canned values."""
    client = MagicMock()
    # download_blob().readall() pattern
    downloader = MagicMock()
    downloader.readall.return_value = b"blob-content"
    client.download_blob.return_value = downloader
    client.url = "https://example.blob.core.windows.net/content-store/sha256/ab/cd/abcdef"
    return client


@pytest.fixture
def fake_service_client(fake_blob_client):
    """Return a mock BlobServiceClient wired to fake_blob_client."""
    svc = MagicMock()
    container_client = MagicMock()
    # get_container_properties() succeeds → no need to create container
    container_client.get_container_properties.return_value = MagicMock()
    svc.get_container_client.return_value = container_client
    svc.get_blob_client.return_value = fake_blob_client
    return svc


@pytest.fixture
def azure_store(fake_service_client, fake_blob_client):
    """AzureBlobStore with its _get_client patched to return fake_service_client."""
    store = AzureBlobStore.__new__(AzureBlobStore)
    store._connection_string = "DefaultEndpointsProtocol=https;fake"
    store._container_name = "content-store"
    store._client = fake_service_client  # skip lazy init
    # Wire get_blob_client on the service level to always return fake_blob_client
    fake_service_client.get_blob_client.return_value = fake_blob_client
    return store


# ---------------------------------------------------------------------------
# AzureBlobStorage fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_container_client(fake_blob_client):
    """Mock container client whose get_blob_client returns fake_blob_client."""
    cc = MagicMock()
    cc.get_blob_client.return_value = fake_blob_client
    return cc


@pytest.fixture
def azure_kv_store(fake_container_client):
    """AzureBlobStorage instance with _container_client injected directly."""
    store = AzureBlobStorage.__new__(AzureBlobStorage)
    store._container_client = fake_container_client
    return store


# ===========================================================================
# HashFS — construction and root directory
# ===========================================================================

async def test_hashfs_creates_root_dir(tmp_dir):
    """HashFS.__init__ creates the root directory when it does not exist."""
    root = tmp_dir / "brand_new_root"
    assert not root.exists()
    HashFS(str(root))
    assert root.exists() and root.is_dir()


async def test_hashfs_default_params(store):
    """Default depth=2 and width=2 are assigned correctly."""
    assert store.depth == 2
    assert store.width == 2


async def test_hashfs_custom_depth_width(tmp_dir):
    """Custom depth and width are stored on the instance."""
    s = HashFS(str(tmp_dir / "s"), depth=3, width=4)
    assert s.depth == 3
    assert s.width == 4


# ===========================================================================
# HashFS — put
# ===========================================================================

async def test_put_returns_sha256_prefixed_hash(store):
    """put() returns a string beginning with 'sha256:' + 64 hex chars."""
    h = store.put(b"hello world")
    assert h.startswith("sha256:")
    hex_part = h[len("sha256:"):]
    assert len(hex_part) == 64
    int(hex_part, 16)  # must be valid hex


async def test_put_hash_matches_sha256_of_content(store):
    """put() returns the actual SHA-256 hash of the stored content."""
    content = b"agent payload data"
    h = store.put(content)
    assert h == _prefixed(content)


async def test_put_creates_sharded_path(store, tmp_dir):
    """put() writes the file at root/<h[0:2]>/<h[2:4]>/<fullhash>."""
    content = b"sharding test"
    hex_hash = _hex(content)
    store.put(content)
    expected = tmp_dir / "store" / hex_hash[0:2] / hex_hash[2:4] / hex_hash
    assert expected.exists()
    assert expected.read_bytes() == content


async def test_put_custom_depth3_width3(tmp_dir):
    """Custom depth=3 width=3 creates a three-level sharded directory."""
    s = HashFS(str(tmp_dir / "deep"), depth=3, width=3)
    content = b"deep shard"
    hex_hash = _hex(content)
    s.put(content)
    expected = (
        tmp_dir / "deep"
        / hex_hash[0:3]
        / hex_hash[3:6]
        / hex_hash[6:9]
        / hex_hash
    )
    assert expected.exists()


async def test_put_empty_bytes(store):
    """put() accepts empty bytes and returns a valid sha256 hash."""
    h = store.put(b"")
    assert h.startswith("sha256:")
    assert store.exists(h)


async def test_put_idempotent_second_call_no_duplicate(store):
    """Storing the same content twice returns identical hashes; size stays 1."""
    content = b"idempotent content"
    h1 = store.put(content)
    h2 = store.put(content)
    assert h1 == h2
    assert store.size() == 1


async def test_put_binary_content(store):
    """put() handles binary content with null and high bytes."""
    content = b"\x00\x01\xff\xfe"
    h = store.put(content)
    assert store.get(h) == content


async def test_put_large_content(store):
    """put() handles a 512 KB payload without error."""
    import os
    content = os.urandom(512 * 1024)
    h = store.put(content)
    assert store.get(h) == content


# ===========================================================================
# HashFS — get
# ===========================================================================

async def test_get_returns_stored_bytes(store):
    """get() returns exactly the bytes that were stored."""
    content = b"marketplace listing"
    h = store.put(content)
    assert store.get(h) == content


async def test_get_returns_none_for_unknown_hash(store):
    """get() returns None for a hash that was never stored."""
    fake = "sha256:" + "0" * 64
    assert store.get(fake) is None


async def test_get_accepts_bare_hex_hash(store):
    """get() also accepts a hash without the 'sha256:' prefix."""
    content = b"bare hash test"
    h = store.put(content)
    bare = h.replace("sha256:", "")
    assert store.get(bare) == content


async def test_get_returns_none_after_delete(store):
    """get() returns None for content that was deleted."""
    h = store.put(b"delete me")
    store.delete(h)
    assert store.get(h) is None


async def test_get_returns_none_for_invalid_hash(store):
    """get() returns None when hash length is wrong (< 64 hex chars)."""
    assert store.get("sha256:tooshort") is None


# ===========================================================================
# HashFS — exists
# ===========================================================================

async def test_exists_false_before_put(store):
    """exists() returns False for a hash not yet in the store."""
    h = _prefixed(b"not stored yet")
    assert store.exists(h) is False


async def test_exists_true_after_put(store):
    """exists() returns True immediately after put()."""
    h = store.put(b"exist check")
    assert store.exists(h) is True


async def test_exists_false_after_delete(store):
    """exists() returns False once the content is deleted."""
    h = store.put(b"ephemeral")
    store.delete(h)
    assert store.exists(h) is False


async def test_exists_false_for_invalid_hash(store):
    """exists() returns False for a malformed hash string."""
    assert store.exists("sha256:notvalidhex!@#$") is False


# ===========================================================================
# HashFS — delete
# ===========================================================================

async def test_delete_returns_true_for_existing(store):
    """delete() returns True when the content existed."""
    h = store.put(b"to delete")
    assert store.delete(h) is True


async def test_delete_returns_false_for_nonexistent(store):
    """delete() returns False for a hash that was never stored."""
    fake = "sha256:" + "f" * 64
    assert store.delete(fake) is False


async def test_delete_idempotent(store):
    """Deleting twice: first call True, second call False."""
    h = store.put(b"double delete")
    assert store.delete(h) is True
    assert store.delete(h) is False


async def test_delete_returns_false_for_invalid_hash(store):
    """delete() returns False for a malformed hash rather than raising."""
    assert store.delete("sha256:badlength") is False


# ===========================================================================
# HashFS — verify
# ===========================================================================

async def test_verify_correct_content_returns_true(store):
    """verify() returns True when content matches the expected hash."""
    content = b"verify me"
    h = store.put(content)
    assert store.verify(content, h) is True


async def test_verify_wrong_content_returns_false(store):
    """verify() returns False when content does not match the hash."""
    h = store.put(b"original")
    assert store.verify(b"tampered", h) is False


async def test_verify_invalid_hash_returns_false(store):
    """verify() returns False for a malformed hash string."""
    assert store.verify(b"data", "sha256:tooshort") is False


async def test_verify_prefixed_and_bare_hash_both_work(store):
    """verify() accepts both 'sha256:<hex>' and bare hex hash."""
    content = b"dual prefix test"
    h_prefixed = store.put(content)
    h_bare = h_prefixed.replace("sha256:", "")
    assert store.verify(content, h_prefixed) is True
    assert store.verify(content, h_bare) is True


# ===========================================================================
# HashFS — compute_hash
# ===========================================================================

async def test_compute_hash_returns_prefixed_hash(store):
    """compute_hash() returns a sha256:-prefixed 64-char hex hash."""
    h = store.compute_hash(b"compute only")
    assert h.startswith("sha256:")
    hex_part = h[len("sha256:"):]
    assert len(hex_part) == 64


async def test_compute_hash_does_not_store(store):
    """compute_hash() writes nothing to disk; size stays 0."""
    store.compute_hash(b"do not store")
    assert store.size() == 0


async def test_compute_hash_matches_put_hash(store):
    """compute_hash() and put() return identical hashes for the same content."""
    content = b"consistency"
    computed = store.compute_hash(content)
    stored = store.put(content)
    assert computed == stored


# ===========================================================================
# HashFS — size
# ===========================================================================

async def test_size_zero_initially(store):
    """size() is 0 for a freshly created store."""
    assert store.size() == 0


async def test_size_increments_after_put(store):
    """size() increments by 1 for each distinct piece of content."""
    store.put(b"a")
    assert store.size() == 1
    store.put(b"b")
    assert store.size() == 2


async def test_size_unchanged_by_idempotent_put(store):
    """Re-storing the same content does not increase size."""
    store.put(b"once")
    store.put(b"once")
    assert store.size() == 1


async def test_size_decrements_after_delete(store):
    """size() decrements after a successful delete."""
    h = store.put(b"shrink me")
    store.put(b"keep me")
    assert store.size() == 2
    store.delete(h)
    assert store.size() == 1


# ===========================================================================
# HashFS — _normalize_hash
# ===========================================================================

async def test_normalize_hash_strips_prefix_and_lowercases():
    """_normalize_hash returns lowercase hex without 'sha256:' prefix."""
    hex_hash = "A" * 64
    result = HashFS._normalize_hash(f"sha256:{hex_hash}")
    assert result == "a" * 64


async def test_normalize_hash_too_short_returns_none():
    """_normalize_hash returns None for a hex string shorter than 64 chars."""
    assert HashFS._normalize_hash("sha256:" + "a" * 63) is None


async def test_normalize_hash_too_long_returns_none():
    """_normalize_hash returns None for a hex string longer than 64 chars."""
    assert HashFS._normalize_hash("sha256:" + "a" * 65) is None


async def test_normalize_hash_non_hex_returns_none():
    """_normalize_hash returns None when non-hex chars are present."""
    bad = "g" * 64  # 'g' is not a valid hex character
    assert HashFS._normalize_hash(bad) is None


async def test_normalize_hash_valid_bare_hex():
    """_normalize_hash accepts a valid 64-char bare hex string (no prefix)."""
    valid = "deadbeef" * 8  # 64 chars
    result = HashFS._normalize_hash(valid)
    assert result == valid.lower()


# ===========================================================================
# HashFS — _strip_prefix
# ===========================================================================

async def test_strip_prefix_removes_sha256_prefix():
    """_strip_prefix removes 'sha256:' from a prefixed string."""
    hex_hash = "ab" * 32  # 64 chars
    assert HashFS._strip_prefix(f"sha256:{hex_hash}") == hex_hash


async def test_strip_prefix_no_prefix_unchanged():
    """_strip_prefix is a no-op when no 'sha256:' prefix is present."""
    raw = "ab" * 32
    assert HashFS._strip_prefix(raw) == raw


# ===========================================================================
# HashFS — _safe_path (path traversal guard)
# ===========================================================================

async def test_safe_path_traversal_returns_none(store):
    """_safe_path returns None for a hash that would escape the store root."""
    # Inject a hex-looking string that encodes path traversal
    malicious = "../../../etc/passwd" + "a" * 45  # not valid hex → None
    result = store._safe_path(malicious)
    assert result is None


async def test_safe_path_valid_hash_stays_under_root(store):
    """_safe_path returns a path that is a descendant of the store root."""
    content = b"valid path test"
    hex_hash = _hex(content)
    resolved = store._safe_path(hex_hash)
    assert resolved is not None
    assert store.root.resolve() in resolved.parents or resolved == store.root.resolve()


# ===========================================================================
# HashFS — multiple distinct items coexist
# ===========================================================================

async def test_multiple_items_coexist(store):
    """Storing N distinct items results in size() == N, all retrievable."""
    items = [b"alpha", b"beta", b"gamma", b"\x00" * 128, b"unicode\xe2\x98\x83"]
    hashes = [store.put(item) for item in items]
    assert len(set(hashes)) == len(items)
    for item, h in zip(items, hashes):
        assert store.get(h) == item
    assert store.size() == len(items)


# ===========================================================================
# AzureBlobStore — construction
# ===========================================================================

async def test_azure_blob_store_empty_connection_string_raises():
    """AzureBlobStore raises ValueError when connection_string is empty."""
    with pytest.raises(ValueError, match="AZURE_BLOB_CONNECTION"):
        AzureBlobStore(connection_string="")


async def test_azure_blob_store_stores_connection_string():
    """AzureBlobStore stores the connection string on the instance."""
    conn = "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=fake"
    with patch("marketplace.storage.azure_blob.BlobServiceClient"):
        s = AzureBlobStore(connection_string=conn)
    assert s._connection_string == conn


async def test_azure_blob_store_default_container_name():
    """AzureBlobStore defaults container_name to 'content-store'."""
    conn = "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=fake"
    with patch("marketplace.storage.azure_blob.BlobServiceClient"):
        s = AzureBlobStore(connection_string=conn)
    assert s._container_name == "content-store"


async def test_azure_blob_store_custom_container_name():
    """AzureBlobStore accepts a custom container_name."""
    conn = "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=fake"
    with patch("marketplace.storage.azure_blob.BlobServiceClient"):
        s = AzureBlobStore(connection_string=conn, container_name="my-bucket")
    assert s._container_name == "my-bucket"


# ===========================================================================
# AzureBlobStore — _get_client (lazy init)
# ===========================================================================

async def test_get_client_initializes_once(fake_service_client):
    """_get_client creates BlobServiceClient on first call and reuses it."""
    conn = "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=fake"
    with patch(
        "azure.storage.blob.BlobServiceClient"
    ) as MockBSC:
        MockBSC.from_connection_string.return_value = fake_service_client
        s = AzureBlobStore.__new__(AzureBlobStore)
        s._connection_string = conn
        s._container_name = "content-store"
        s._client = None

        c1 = s._get_client()
        c2 = s._get_client()

    assert c1 is c2
    MockBSC.from_connection_string.assert_called_once_with(conn)


async def test_get_client_creates_container_on_not_found(fake_service_client):
    """_get_client calls create_container when get_container_properties raises."""
    conn = "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=fake"
    container_client = MagicMock()
    # Simulate container not found
    container_client.get_container_properties.side_effect = Exception("ContainerNotFound")
    fake_service_client.get_container_client.return_value = container_client

    with patch(
        "azure.storage.blob.BlobServiceClient"
    ) as MockBSC:
        MockBSC.from_connection_string.return_value = fake_service_client
        s = AzureBlobStore.__new__(AzureBlobStore)
        s._connection_string = conn
        s._container_name = "content-store"
        s._client = None

        s._get_client()

    fake_service_client.create_container.assert_called_once_with("content-store")


# ===========================================================================
# AzureBlobStore — blob_name derivation
# ===========================================================================

async def test_blob_name_structure(azure_store):
    """Blob name is sha256/<h[0:2]>/<h[2:4]>/<fullhash>."""
    content = b"blob name test"
    hex_hash = _hex(content)
    expected_blob_name = f"sha256/{hex_hash[:2]}/{hex_hash[2:4]}/{hex_hash}"

    # Call put() and inspect the blob_client argument
    azure_store._blob_client = MagicMock(return_value=MagicMock(upload_blob=MagicMock()))
    azure_store.put(content)
    azure_store._blob_client.assert_called_once_with(expected_blob_name)


# ===========================================================================
# AzureBlobStore — put
# ===========================================================================

async def test_azure_put_returns_content_hash(azure_store, fake_blob_client):
    """put() returns the SHA-256 hex hash (without prefix) used as blob name."""
    content = b"upload me"
    hex_hash = _hex(content)

    result = azure_store.put(content)

    assert result == hex_hash
    fake_blob_client.upload_blob.assert_called_once_with(content, overwrite=True)


async def test_azure_put_accepts_explicit_hash(azure_store, fake_blob_client):
    """put() uses a caller-supplied content_hash instead of computing one."""
    content = b"pre-hashed content"
    explicit_hash = "a" * 64  # 64-char hex string

    result = azure_store.put(content, content_hash=explicit_hash)

    assert result == explicit_hash
    fake_blob_client.upload_blob.assert_called_once()


async def test_azure_put_propagates_upload_exception(azure_store, fake_blob_client):
    """put() re-raises exceptions from upload_blob."""
    fake_blob_client.upload_blob.side_effect = IOError("network failure")

    with pytest.raises(IOError, match="network failure"):
        azure_store.put(b"fail me")


# ===========================================================================
# AzureBlobStore — get
# ===========================================================================

async def test_azure_get_returns_content(azure_store, fake_blob_client):
    """get() returns the bytes returned by download_blob().readall()."""
    content = b"blob-content"
    downloader = MagicMock()
    downloader.readall.return_value = content
    fake_blob_client.download_blob.return_value = downloader

    result = azure_store.get("a" * 64)

    assert result == content


async def test_azure_get_returns_none_for_blob_not_found(azure_store, fake_blob_client):
    """get() returns None when the blob does not exist (BlobNotFound)."""
    fake_blob_client.download_blob.side_effect = Exception("BlobNotFound: resource missing")

    result = azure_store.get("b" * 64)

    assert result is None


async def test_azure_get_propagates_non_not_found_exception(azure_store, fake_blob_client):
    """get() re-raises exceptions that are not BlobNotFound errors."""
    fake_blob_client.download_blob.side_effect = IOError("disk full")

    with pytest.raises(IOError, match="disk full"):
        azure_store.get("c" * 64)


# ===========================================================================
# AzureBlobStore — exists
# ===========================================================================

async def test_azure_exists_true_when_blob_found(azure_store, fake_blob_client):
    """exists() returns True when get_blob_properties succeeds."""
    fake_blob_client.get_blob_properties.return_value = MagicMock()

    assert azure_store.exists("d" * 64) is True


async def test_azure_exists_false_when_exception(azure_store, fake_blob_client):
    """exists() returns False when get_blob_properties raises any exception."""
    fake_blob_client.get_blob_properties.side_effect = Exception("BlobNotFound")

    assert azure_store.exists("e" * 64) is False


# ===========================================================================
# AzureBlobStore — delete
# ===========================================================================

async def test_azure_delete_returns_true_on_success(azure_store, fake_blob_client):
    """delete() returns True when delete_blob succeeds."""
    fake_blob_client.delete_blob.return_value = None

    assert azure_store.delete("f" * 64) is True
    fake_blob_client.delete_blob.assert_called_once()


async def test_azure_delete_returns_false_for_blob_not_found(azure_store, fake_blob_client):
    """delete() returns False when blob does not exist (BlobNotFound)."""
    fake_blob_client.delete_blob.side_effect = Exception("BlobNotFound: gone")

    assert azure_store.delete("1" * 64) is False


async def test_azure_delete_propagates_non_not_found_exception(azure_store, fake_blob_client):
    """delete() re-raises non-BlobNotFound exceptions."""
    fake_blob_client.delete_blob.side_effect = IOError("permission denied")

    with pytest.raises(IOError, match="permission denied"):
        azure_store.delete("2" * 64)


# ===========================================================================
# AzureBlobStore — get_url
# ===========================================================================

async def test_azure_get_url_returns_blob_url(azure_store, fake_blob_client):
    """get_url() returns the .url attribute of the blob client."""
    expected_url = "https://example.blob.core.windows.net/content-store/sha256/ab/cd/abcdef"
    fake_blob_client.url = expected_url

    url = azure_store.get_url("ab" + "c" * 62)

    assert url == expected_url


# ===========================================================================
# AzureBlobStorage — construction (secondary KV interface)
# ===========================================================================

async def test_azure_blob_storage_empty_conn_string_no_client():
    """AzureBlobStorage with empty connection string leaves _container_client as None."""
    store = AzureBlobStorage(connection_string="")
    assert store._container_client is None


async def test_azure_blob_storage_sets_container_client():
    """AzureBlobStorage with valid connection string sets _container_client."""
    conn = "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=fake"
    fake_svc = MagicMock()
    fake_cc = MagicMock()
    fake_svc.get_container_client.return_value = fake_cc

    with patch(
        "azure.storage.blob.BlobServiceClient"
    ) as MockBSC:
        MockBSC.from_connection_string.return_value = fake_svc
        store = AzureBlobStorage(connection_string=conn, container_name="my-cont")

    assert store._container_client is fake_cc
    fake_svc.get_container_client.assert_called_once_with("my-cont")


# ===========================================================================
# AzureBlobStorage — put (KV interface)
# ===========================================================================

async def test_azure_kv_put_calls_upload_blob(azure_kv_store, fake_blob_client):
    """put() calls upload_blob with overwrite=True on the blob client."""
    azure_kv_store.put("my-key", b"my-data")
    fake_blob_client.upload_blob.assert_called_once_with(b"my-data", overwrite=True)


async def test_azure_kv_put_propagates_exception(azure_kv_store, fake_blob_client):
    """put() propagates exceptions raised by upload_blob."""
    fake_blob_client.upload_blob.side_effect = RuntimeError("quota exceeded")

    with pytest.raises(RuntimeError, match="quota exceeded"):
        azure_kv_store.put("k", b"v")


# ===========================================================================
# AzureBlobStorage — get (KV interface)
# ===========================================================================

async def test_azure_kv_get_returns_content(azure_kv_store, fake_blob_client):
    """get() returns bytes from download_blob().readall()."""
    downloader = MagicMock()
    downloader.readall.return_value = b"kv-content"
    fake_blob_client.download_blob.return_value = downloader

    result = azure_kv_store.get("some-key")

    assert result == b"kv-content"


async def test_azure_kv_get_propagates_exception(azure_kv_store, fake_blob_client):
    """get() propagates exceptions from download_blob."""
    fake_blob_client.download_blob.side_effect = KeyError("missing key")

    with pytest.raises(KeyError):
        azure_kv_store.get("ghost-key")


# ===========================================================================
# AzureBlobStorage — exists (KV interface)
# ===========================================================================

async def test_azure_kv_exists_true_when_properties_succeed(azure_kv_store, fake_blob_client):
    """exists() returns True when get_blob_properties does not raise."""
    fake_blob_client.get_blob_properties.return_value = MagicMock()

    assert azure_kv_store.exists("present-key") is True


async def test_azure_kv_exists_false_when_exception(azure_kv_store, fake_blob_client):
    """exists() returns False when get_blob_properties raises."""
    fake_blob_client.get_blob_properties.side_effect = Exception("not found")

    assert azure_kv_store.exists("absent-key") is False


# ===========================================================================
# AzureBlobStorage — delete (KV interface)
# ===========================================================================

async def test_azure_kv_delete_calls_delete_blob(azure_kv_store, fake_blob_client):
    """delete() calls delete_blob on the blob client."""
    azure_kv_store.delete("del-key")
    fake_blob_client.delete_blob.assert_called_once()


async def test_azure_kv_delete_propagates_exception(azure_kv_store, fake_blob_client):
    """delete() propagates exceptions from delete_blob."""
    fake_blob_client.delete_blob.side_effect = PermissionError("access denied")

    with pytest.raises(PermissionError, match="access denied"):
        azure_kv_store.delete("forbidden-key")


# ===========================================================================
# AzureBlobStorage — get_url (KV interface)
# ===========================================================================

async def test_azure_kv_get_url_returns_blob_url(azure_kv_store, fake_blob_client):
    """get_url() returns the .url property of the underlying blob client."""
    fake_blob_client.url = "https://example.blob.core.windows.net/c/my-key"

    url = azure_kv_store.get_url("my-key")

    assert url == "https://example.blob.core.windows.net/c/my-key"
