import hashlib
from pathlib import Path


class HashFS:
    """Content-addressed file storage using SHA-256 hashes.

    Files are stored in a sharded directory structure:
        root/ab/cd/abcdef1234567890...

    The first `depth` segments of `width` hex characters each become
    subdirectories, preventing any single directory from holding too many files.
    """

    def __init__(self, root_dir: str, depth: int = 2, width: int = 2):
        self.root = Path(root_dir)
        self.depth = depth
        self.width = width
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, content: bytes) -> str:
        """Store content and return its prefixed SHA-256 hash."""
        hex_hash = hashlib.sha256(content).hexdigest()
        path = self._hash_to_path(hex_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
        return f"sha256:{hex_hash}"

    def get(self, content_hash: str) -> bytes | None:
        """Retrieve content by hash. Returns None if not found."""
        hex_hash = self._normalize_hash(content_hash)
        if hex_hash is None:
            return None
        path = self._safe_path(hex_hash)
        if path is not None and path.is_file():
            return path.read_bytes()
        return None

    def exists(self, content_hash: str) -> bool:
        """Check whether content with the given hash exists."""
        hex_hash = self._normalize_hash(content_hash)
        if hex_hash is None:
            return False
        path = self._safe_path(hex_hash)
        return bool(path is not None and path.is_file())

    def delete(self, content_hash: str) -> bool:
        """Delete content by hash. Returns True if deleted, False if not found."""
        hex_hash = self._normalize_hash(content_hash)
        if hex_hash is None:
            return False
        path = self._safe_path(hex_hash)
        if path is not None and path.is_file():
            path.unlink()
            return True
        return False

    def verify(self, content: bytes, expected_hash: str) -> bool:
        """Verify that content matches the expected hash."""
        hex_hash = self._normalize_hash(expected_hash)
        if hex_hash is None:
            return False
        actual = hashlib.sha256(content).hexdigest()
        return actual == hex_hash

    def compute_hash(self, content: bytes) -> str:
        """Compute and return the prefixed SHA-256 hash without storing."""
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    def size(self) -> int:
        """Total number of stored objects."""
        return sum(1 for _ in self.root.rglob("*") if _.is_file())

    def _hash_to_path(self, hex_hash: str) -> Path:
        parts = [
            hex_hash[i * self.width : (i + 1) * self.width]
            for i in range(self.depth)
        ]
        return self.root / Path(*parts) / hex_hash

    def _safe_path(self, hex_hash: str) -> Path | None:
        """Resolve a hash path and ensure it stays under the store root."""
        candidate = self._hash_to_path(hex_hash)
        try:
            root_resolved = self.root.resolve()
            resolved = candidate.resolve()
        except OSError:
            return None
        if root_resolved == resolved or root_resolved in resolved.parents:
            return resolved
        return None

    @classmethod
    def _normalize_hash(cls, content_hash: str) -> str | None:
        """Return lowercase SHA-256 hex if valid, otherwise None."""
        hex_hash = cls._strip_prefix(content_hash).lower()
        if len(hex_hash) != 64:
            return None
        if not all(c in "0123456789abcdef" for c in hex_hash):
            return None
        return hex_hash

    @staticmethod
    def _strip_prefix(content_hash: str) -> str:
        return content_hash.replace("sha256:", "")
