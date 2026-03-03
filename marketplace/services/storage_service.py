from __future__ import annotations

from marketplace.config import settings

# Singleton storage instance
_storage = None


def get_storage():
    """Get or create the global storage instance.

    Uses AzureBlobStore when AZURE_BLOB_CONNECTION is configured (production),
    falls back to local HashFS otherwise (local dev).
    """
    global _storage
    if _storage is None:
        if settings.azure_blob_connection:
            from marketplace.storage.azure_blob import AzureBlobStore

            _storage = AzureBlobStore(
                connection_string=settings.azure_blob_connection,
                container_name=settings.azure_blob_container,
            )
        else:
            from marketplace.storage.hashfs import HashFS

            _storage = HashFS(root_dir=settings.content_store_path)
    return _storage
