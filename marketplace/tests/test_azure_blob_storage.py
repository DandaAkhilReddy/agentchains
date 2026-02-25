"""Tests for AzureBlobStore and AzureBlobStorage adapters.

All Azure SDK calls are mocked -- no real Azure connections required.
Covers: put, get, exists, delete, get_url, lazy client init, error paths.
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from marketplace.storage.azure_blob import AzureBlobStorage, AzureBlobStore


# ---------------------------------------------------------------------------
# AzureBlobStore tests
# ---------------------------------------------------------------------------


class TestAzureBlobStoreInit:
    """Constructor validation and lazy client initialization."""

    def test_raises_on_empty_connection_string(self):
        with pytest.raises(ValueError, match="AZURE_BLOB_CONNECTION"):
            AzureBlobStore(connection_string="")

    def test_stores_connection_string_and_container(self):
        store = AzureBlobStore(connection_string="fake-conn", container_name="my-bucket")
        assert store._connection_string == "fake-conn"
        assert store._container_name == "my-bucket"
        assert store._client is None  # lazy init

    def test_default_container_name(self):
        store = AzureBlobStore(connection_string="fake-conn")
        assert store._container_name == "content-store"


class TestAzureBlobStoreGetClient:
    """Tests for lazy BlobServiceClient initialization."""

    @patch("marketplace.storage.azure_blob.BlobServiceClient", new=None)
    def test_raises_import_error_when_sdk_missing(self):
        store = AzureBlobStore(connection_string="fake-conn")
        # Patch the import inside _get_client to raise ImportError
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            with pytest.raises(ImportError, match="azure-storage-blob"):
                store._get_client()

    def test_creates_container_if_not_exists(self):
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_container.get_container_properties.side_effect = Exception("NotFound")
        mock_blob_service.get_container_client.return_value = mock_container

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_blob_service
            store = AzureBlobStore(connection_string="fake-conn")
            client = store._get_client()

        assert client is mock_blob_service
        mock_blob_service.create_container.assert_called_once_with("content-store")

    def test_reuses_existing_container(self):
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_container.get_container_properties.return_value = {}  # exists
        mock_blob_service.get_container_client.return_value = mock_container

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_blob_service
            store = AzureBlobStore(connection_string="fake-conn")
            store._get_client()

        mock_blob_service.create_container.assert_not_called()

    def test_lazy_init_called_once(self):
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_container.get_container_properties.return_value = {}
        mock_blob_service.get_container_client.return_value = mock_container

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_blob_service
            store = AzureBlobStore(connection_string="fake-conn")
            store._get_client()
            store._get_client()

        # from_connection_string called only once due to lazy init
        mock_cls.from_connection_string.assert_called_once()


class TestAzureBlobStorePut:
    """Tests for AzureBlobStore.put()."""

    def _make_store(self):
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_container.get_container_properties.return_value = {}
        mock_blob_service.get_container_client.return_value = mock_container

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_blob_service
            store = AzureBlobStore(connection_string="fake-conn")
            store._get_client()  # force init
        return store, mock_blob_service

    def test_put_computes_hash_and_uploads(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_client.get_blob_client.return_value = mock_blob

        data = b"test data for azure"
        expected_hash = hashlib.sha256(data).hexdigest()

        result_hash = store.put(data)
        assert result_hash == expected_hash
        mock_blob.upload_blob.assert_called_once_with(data, overwrite=True)

    def test_put_uses_provided_hash(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_client.get_blob_client.return_value = mock_blob

        data = b"test data"
        custom_hash = "a" * 64

        result = store.put(data, content_hash=custom_hash)
        assert result == custom_hash

    def test_put_blob_name_format(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_client.get_blob_client.return_value = mock_blob

        data = b"test"
        content_hash = hashlib.sha256(data).hexdigest()
        store.put(data)

        expected_blob_name = f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}"
        mock_client.get_blob_client.assert_called_with(
            container="content-store", blob=expected_blob_name
        )

    def test_put_raises_on_upload_failure(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_blob.upload_blob.side_effect = Exception("upload failed")
        mock_client.get_blob_client.return_value = mock_blob

        with pytest.raises(Exception, match="upload failed"):
            store.put(b"data")


class TestAzureBlobStoreGet:
    """Tests for AzureBlobStore.get()."""

    def _make_store(self):
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_container.get_container_properties.return_value = {}
        mock_blob_service.get_container_client.return_value = mock_container

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_blob_service
            store = AzureBlobStore(connection_string="fake-conn")
            store._get_client()
        return store, mock_blob_service

    def test_get_returns_data(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_download = MagicMock()
        mock_download.readall.return_value = b"retrieved data"
        mock_blob.download_blob.return_value = mock_download
        mock_client.get_blob_client.return_value = mock_blob

        result = store.get("a" * 64)
        assert result == b"retrieved data"

    def test_get_returns_none_for_blob_not_found(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = Exception("BlobNotFound")
        mock_client.get_blob_client.return_value = mock_blob

        result = store.get("a" * 64)
        assert result is None

    def test_get_returns_none_for_resource_not_found_error(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()

        class ResourceNotFoundError(Exception):
            pass

        mock_blob.download_blob.side_effect = ResourceNotFoundError("gone")
        mock_client.get_blob_client.return_value = mock_blob

        result = store.get("a" * 64)
        assert result is None

    def test_get_raises_on_unexpected_error(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_blob.download_blob.side_effect = RuntimeError("unexpected")
        mock_client.get_blob_client.return_value = mock_blob

        with pytest.raises(RuntimeError, match="unexpected"):
            store.get("a" * 64)


class TestAzureBlobStoreExists:
    """Tests for AzureBlobStore.exists()."""

    def _make_store(self):
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_container.get_container_properties.return_value = {}
        mock_blob_service.get_container_client.return_value = mock_container

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_blob_service
            store = AzureBlobStore(connection_string="fake-conn")
            store._get_client()
        return store, mock_blob_service

    def test_exists_returns_true(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_blob.get_blob_properties.return_value = {}
        mock_client.get_blob_client.return_value = mock_blob

        assert store.exists("a" * 64) is True

    def test_exists_returns_false_on_exception(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_blob.get_blob_properties.side_effect = Exception("not found")
        mock_client.get_blob_client.return_value = mock_blob

        assert store.exists("a" * 64) is False


class TestAzureBlobStoreDelete:
    """Tests for AzureBlobStore.delete()."""

    def _make_store(self):
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_container.get_container_properties.return_value = {}
        mock_blob_service.get_container_client.return_value = mock_container

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_blob_service
            store = AzureBlobStore(connection_string="fake-conn")
            store._get_client()
        return store, mock_blob_service

    def test_delete_returns_true_on_success(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_client.get_blob_client.return_value = mock_blob

        assert store.delete("a" * 64) is True
        mock_blob.delete_blob.assert_called_once()

    def test_delete_returns_false_for_not_found(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_blob.delete_blob.side_effect = Exception("BlobNotFound")
        mock_client.get_blob_client.return_value = mock_blob

        assert store.delete("a" * 64) is False

    def test_delete_raises_on_unexpected_error(self):
        store, mock_client = self._make_store()
        mock_blob = MagicMock()
        mock_blob.delete_blob.side_effect = RuntimeError("unexpected")
        mock_client.get_blob_client.return_value = mock_blob

        with pytest.raises(RuntimeError, match="unexpected"):
            store.delete("a" * 64)


class TestAzureBlobStoreGetUrl:
    """Tests for AzureBlobStore.get_url()."""

    def test_get_url_returns_blob_url(self):
        mock_blob_service = MagicMock()
        mock_container = MagicMock()
        mock_container.get_container_properties.return_value = {}
        mock_blob_service.get_container_client.return_value = mock_container

        mock_blob = MagicMock()
        mock_blob.url = "https://storage.blob.core.windows.net/content-store/sha256/aa/bb/aabb"
        mock_blob_service.get_blob_client.return_value = mock_blob

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_blob_service
            store = AzureBlobStore(connection_string="fake-conn")
            store._get_client()

        url = store.get_url("a" * 64)
        assert url == mock_blob.url


# ---------------------------------------------------------------------------
# AzureBlobStorage (key-value interface) tests
# ---------------------------------------------------------------------------


class TestAzureBlobStorageInit:
    """AzureBlobStorage constructor tests."""

    def test_empty_connection_string_sets_none_client(self):
        storage = AzureBlobStorage(connection_string="")
        assert storage._container_client is None

    @patch("marketplace.storage.azure_blob.BlobServiceClient", new=None)
    def test_import_error_sets_none_client(self):
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            storage = AzureBlobStorage(connection_string="fake-conn")
        assert storage._container_client is None

    def test_valid_connection_creates_container_client(self):
        mock_service = MagicMock()
        mock_container = MagicMock()
        mock_service.get_container_client.return_value = mock_container

        with patch(
            "azure.storage.blob.BlobServiceClient"
        ) as mock_cls:
            mock_cls.from_connection_string.return_value = mock_service
            storage = AzureBlobStorage(connection_string="fake-conn", container_name="test-bucket")

        assert storage._container_client is mock_container


class TestAzureBlobStorageOperations:
    """Tests for AzureBlobStorage put/get/exists/delete/get_url."""

    def _make_storage(self):
        mock_container = MagicMock()
        storage = AzureBlobStorage.__new__(AzureBlobStorage)
        storage._container_client = mock_container
        return storage, mock_container

    def test_put_uploads_with_overwrite(self):
        storage, mock_container = self._make_storage()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        storage.put("my-key", b"my-data")
        mock_container.get_blob_client.assert_called_once_with("my-key")
        mock_blob.upload_blob.assert_called_once_with(b"my-data", overwrite=True)

    def test_get_returns_data(self):
        storage, mock_container = self._make_storage()
        mock_blob = MagicMock()
        mock_download = MagicMock()
        mock_download.readall.return_value = b"blob-data"
        mock_blob.download_blob.return_value = mock_download
        mock_container.get_blob_client.return_value = mock_blob

        result = storage.get("my-key")
        assert result == b"blob-data"

    def test_exists_returns_true(self):
        storage, mock_container = self._make_storage()
        mock_blob = MagicMock()
        mock_blob.get_blob_properties.return_value = {}
        mock_container.get_blob_client.return_value = mock_blob

        assert storage.exists("my-key") is True

    def test_exists_returns_false_on_exception(self):
        storage, mock_container = self._make_storage()
        mock_blob = MagicMock()
        mock_blob.get_blob_properties.side_effect = Exception("not found")
        mock_container.get_blob_client.return_value = mock_blob

        assert storage.exists("my-key") is False

    def test_delete_calls_delete_blob(self):
        storage, mock_container = self._make_storage()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        storage.delete("my-key")
        mock_blob.delete_blob.assert_called_once()

    def test_get_url_returns_blob_url(self):
        storage, mock_container = self._make_storage()
        mock_blob = MagicMock()
        mock_blob.url = "https://example.blob.core.windows.net/test-bucket/my-key"
        mock_container.get_blob_client.return_value = mock_blob

        url = storage.get_url("my-key")
        assert url == mock_blob.url
