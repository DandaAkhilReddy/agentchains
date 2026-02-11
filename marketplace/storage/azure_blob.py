"""Azure Blob Storage backend — drop-in replacement for HashFS.

Content-addressed storage using SHA-256 hashes. Blobs are named with the same
sharded structure as HashFS: ab/cd/abcdef1234567890...
"""

import hashlib

from azure.storage.blob import BlobServiceClient, ContainerClient


class AzureBlobStore:
    """Content-addressed storage backed by Azure Blob Storage."""

    def __init__(self, connection_string: str, container_name: str):
        self._blob_service = BlobServiceClient.from_connection_string(connection_string)
        self._container: ContainerClient = self._blob_service.get_container_client(container_name)
        # Ensure container exists
        try:
            self._container.get_container_properties()
        except Exception:
            self._container.create_container()

    def put(self, content: bytes) -> str:
        """Store content and return its prefixed SHA-256 hash."""
        hex_hash = hashlib.sha256(content).hexdigest()
        blob_name = self._hash_to_blob_name(hex_hash)
        blob_client = self._container.get_blob_client(blob_name)
        if not self._blob_exists(blob_client):
            blob_client.upload_blob(content, overwrite=False)
        return f"sha256:{hex_hash}"

    def get(self, content_hash: str) -> bytes | None:
        """Retrieve content by hash. Returns None if not found."""
        hex_hash = self._strip_prefix(content_hash)
        blob_name = self._hash_to_blob_name(hex_hash)
        blob_client = self._container.get_blob_client(blob_name)
        try:
            return blob_client.download_blob().readall()
        except Exception:
            return None

    def exists(self, content_hash: str) -> bool:
        """Check whether content with the given hash exists."""
        hex_hash = self._strip_prefix(content_hash)
        blob_name = self._hash_to_blob_name(hex_hash)
        blob_client = self._container.get_blob_client(blob_name)
        return self._blob_exists(blob_client)

    def delete(self, content_hash: str) -> bool:
        """Delete content by hash. Returns True if deleted."""
        hex_hash = self._strip_prefix(content_hash)
        blob_name = self._hash_to_blob_name(hex_hash)
        blob_client = self._container.get_blob_client(blob_name)
        try:
            blob_client.delete_blob()
            return True
        except Exception:
            return False

    def verify(self, content: bytes, expected_hash: str) -> bool:
        """Verify that content matches the expected hash."""
        hex_hash = self._strip_prefix(expected_hash)
        actual = hashlib.sha256(content).hexdigest()
        return actual == hex_hash

    def compute_hash(self, content: bytes) -> str:
        """Compute the prefixed SHA-256 hash without storing."""
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    def size(self) -> int:
        """Total number of stored objects."""
        return sum(1 for _ in self._container.list_blobs())

    @staticmethod
    def _hash_to_blob_name(hex_hash: str) -> str:
        """Convert hash to sharded blob path: ab/cd/abcdef..."""
        return f"{hex_hash[:2]}/{hex_hash[2:4]}/{hex_hash}"

    @staticmethod
    def _strip_prefix(content_hash: str) -> str:
        return content_hash.replace("sha256:", "")

    @staticmethod
    def _blob_exists(blob_client) -> bool:
        try:
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False
