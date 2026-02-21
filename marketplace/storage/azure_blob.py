"""Azure Blob Storage adapter for content storage.

Re-enabled for v1.0 with the azure-storage-blob SDK.
Supports async upload/download/delete/exists operations.

Requires: AZURE_BLOB_CONNECTION and AZURE_BLOB_CONTAINER env vars.
"""

import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AzureBlobStore:
    """Azure Blob Storage backend for content storage."""

    def __init__(self, connection_string: str, container_name: str = "content-store"):
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

    def put(self, data: bytes, content_hash: Optional[str] = None) -> str:
        """Upload content to Azure Blob Storage.

        Returns the SHA-256 content hash used as the blob name.
        """
        if content_hash is None:
            content_hash = hashlib.sha256(data).hexdigest()

        blob_name = f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}"
        blob_client = self._blob_client(blob_name)

        try:
            blob_client.upload_blob(data, overwrite=True)
            logger.debug("Uploaded blob: %s (%d bytes)", blob_name, len(data))
        except Exception:
            logger.exception("Failed to upload blob: %s", blob_name)
            raise

        return content_hash

    def get(self, content_hash: str) -> Optional[bytes]:
        """Download content from Azure Blob Storage by hash."""
        blob_name = f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}"
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
        blob_name = f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}"
        blob_client = self._blob_client(blob_name)

        try:
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    def delete(self, content_hash: str) -> bool:
        """Delete content from Azure Blob Storage."""
        blob_name = f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}"
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
        blob_name = f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}"
        blob_client = self._blob_client(blob_name)
        return blob_client.url
