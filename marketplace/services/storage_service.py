from marketplace.config import settings
from marketplace.storage.hashfs import HashFS

# Singleton storage instance
_storage: HashFS | None = None


def get_storage() -> HashFS:
    """Get or create the global HashFS storage instance."""
    global _storage
    if _storage is None:
        _storage = HashFS(root_dir=settings.content_store_path)
    return _storage
