"""Azure Blob Storage adapter — DEPRECATED. Replaced by local HashFS.

This module is retained as a stub to prevent import errors in tests.
The active storage backend is configured in storage_service.py (HashFS only).
"""


class AzureBlobStore:
    """Stub for the removed Azure Blob Storage backend."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Azure Blob Storage has been removed. Use HashFS (local) storage instead."
        )
