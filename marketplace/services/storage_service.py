from marketplace.config import settings
from marketplace.storage.hashfs import HashFS

# Singleton storage instance
_storage = None


def get_storage():
    """Get or create the global storage instance (local HashFS)."""
    global _storage
    if _storage is None:
        _storage = HashFS(root_dir=settings.content_store_path)
    return _storage
