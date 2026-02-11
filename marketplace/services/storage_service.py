from marketplace.config import settings

# Singleton storage instance
_storage = None


def get_storage():
    """Get or create the global storage instance.

    Uses Azure Blob Storage when AZURE_STORAGE_CONNECTION_STRING is set,
    otherwise falls back to local HashFS.
    """
    global _storage
    if _storage is None:
        if settings.azure_storage_connection_string:
            from marketplace.storage.azure_blob import AzureBlobStore
            _storage = AzureBlobStore(
                connection_string=settings.azure_storage_connection_string,
                container_name=settings.azure_storage_container,
            )
        else:
            from marketplace.storage.hashfs import HashFS
            _storage = HashFS(root_dir=settings.content_store_path)
    return _storage
