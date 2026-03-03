"""Azure Blob Storage adapter for content storage.

Re-enabled for v1.0 with the azure-storage-blob SDK.
Supports async upload/download/delete/exists operations.

Requires: AZURE_BLOB_CONNECTION and AZURE_BLOB_CONTAINER env vars.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    BlobServiceClient = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class AzureBlobStore:
    """Azure Blob Storage backend for content storage.

    Interface-compatible with HashFS: put() returns 'sha256:<hex>',
    get/exists/delete/get_url accept 'sha256:<hex>' or bare hex.
    """

    def __init__(self, connection_string: str, container_name: str = "content-store") -> None:
        if not connection_string:
            raise ValueError(
                "Azure Blob Storage requires AZURE_BLOB_CONNECTION. "
                "Set the connection string via environment variable."
            )
        self._connection_string = connection_string
        self._container_name = container_name
        self._client = None

    def _get_client(self):
        """Lazy-initialize the BlobServiceClient."""
        if self._client is None:
            try:
                from azure.storage.blob import BlobServiceClient

                self._client = BlobServiceClient.from_connection_string(
                    self._connection_string
                )
                # Ensure container exists
                container_client = self._client.get_container_client(self._container_name)
                try:
                    container_client.get_container_properties()
                except Exception:
                    self._client.create_container(self._container_name)
                    logger.info("Created blob container: %s", self._container_name)
            except ImportError:
                raise ImportError(
                    "azure-storage-blob is required. Install with: "
                    "pip install azure-storage-blob>=12.0"
                )
        return self._client

    def _blob_client(self, blob_name: str):
        """Get a BlobClient for a specific blob."""
        client = self._get_client()
        return client.get_blob_client(
            container=self._container_name, blob=blob_name
        )

    @staticmethod
    def _strip_prefix(content_hash: str) -> str:
        """Strip 'sha256:' prefix if present, returning bare hex."""
        if content_hash.startswith("sha256:"):
            return content_hash[7:]
        return content_hash

    def _blob_path(self, hex_hash: str) -> str:
        """Build the sharded blob path from a bare hex hash."""
        return f"sha256/{hex_hash[:2]}/{hex_hash[2:4]}/{hex_hash}"

    def put(self, content: bytes, content_hash: str | None = None) -> str:
        """Upload content to Azure Blob Storage.

        Returns 'sha256:<hex>' matching HashFS convention.
        """
        if content_hash is None:
            hex_hash = hashlib.sha256(content).hexdigest()
        else:
            hex_hash = self._strip_prefix(content_hash)

        blob_name = self._blob_path(hex_hash)
        blob_client = self._blob_client(blob_name)

        try:
            blob_client.upload_blob(content, overwrite=True)
            logger.debug("Uploaded blob: %s (%d bytes)", blob_name, len(content))
        except Exception:
            logger.exception("Failed to upload blob: %s", blob_name)
            raise

        return f"sha256:{hex_hash}"

    def get(self, content_hash: str) -> bytes | None:
        """Download content from Azure Blob Storage by hash."""
        hex_hash = self._strip_prefix(content_hash)
        blob_name = self._blob_path(hex_hash)
        blob_client = self._blob_client(blob_name)

        try:
            download = blob_client.download_blob()
            return download.readall()
        except Exception as e:
            if "BlobNotFound" in str(e) or "ResourceNotFoundError" in str(type(e)):
                return None
            logger.exception("Failed to download blob: %s", blob_name)
            raise

    def exists(self, content_hash: str) -> bool:
        """Check if content exists in Azure Blob Storage."""
        hex_hash = self._strip_prefix(content_hash)
        blob_name = self._blob_path(hex_hash)
        blob_client = self._blob_client(blob_name)

        try:
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    def delete(self, content_hash: str) -> bool:
        """Delete content from Azure Blob Storage."""
        hex_hash = self._strip_prefix(content_hash)
        blob_name = self._blob_path(hex_hash)
        blob_client = self._blob_client(blob_name)

        try:
            blob_client.delete_blob()
            logger.debug("Deleted blob: %s", blob_name)
            return True
        except Exception as e:
            if "BlobNotFound" in str(e) or "ResourceNotFoundError" in str(type(e)):
                return False
            logger.exception("Failed to delete blob: %s", blob_name)
            raise

    def get_url(self, content_hash: str) -> str:
        """Get the URL for a blob (without SAS token — internal use only)."""
        hex_hash = self._strip_prefix(content_hash)
        blob_name = self._blob_path(hex_hash)
        blob_client = self._blob_client(blob_name)
        return blob_client.url

    def verify(self, content: bytes, expected_hash: str) -> bool:
        """Verify that content matches the expected hash."""
        hex_hash = self._strip_prefix(expected_hash)
        actual = hashlib.sha256(content).hexdigest()
        return actual == hex_hash

    def compute_hash(self, content: bytes) -> str:
        """Compute and return the prefixed SHA-256 hash without storing."""
        return f"sha256:{hashlib.sha256(content).hexdigest()}"


class AzureBlobStorage:
    """Key-value blob storage interface backed by Azure Blob Storage."""

    def __init__(self, connection_string: str = "", container_name: str = "content-store") -> None:
        self._container_client = None
        if connection_string:
            try:
                from azure.storage.blob import BlobServiceClient
                client = BlobServiceClient.from_connection_string(connection_string)
                self._container_client = client.get_container_client(container_name)
            except ImportError:
                logger.warning("azure-storage-blob not installed")

    def put(self, key: str, data: bytes) -> None:
        blob_client = self._container_client.get_blob_client(key)
        blob_client.upload_blob(data, overwrite=True)

    def get(self, key: str) -> Optional[bytes]:
        blob_client = self._container_client.get_blob_client(key)
        download = blob_client.download_blob()
        return download.readall()

    def exists(self, key: str) -> bool:
        blob_client = self._container_client.get_blob_client(key)
        try:
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        blob_client = self._container_client.get_blob_client(key)
        blob_client.delete_blob()

    def get_url(self, key: str) -> str:
        blob_client = self._container_client.get_blob_client(key)
        return blob_client.url
