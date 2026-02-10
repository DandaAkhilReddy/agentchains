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
        hex_hash = self._strip_prefix(content_hash)
        path = self._hash_to_path(hex_hash)
        if path.exists():
            return path.read_bytes()
        return None

    def exists(self, content_hash: str) -> bool:
        """Check whether content with the given hash exists."""
        hex_hash = self._strip_prefix(content_hash)
        return self._hash_to_path(hex_hash).exists()

    def delete(self, content_hash: str) -> bool:
        """Delete content by hash. Returns True if deleted, False if not found."""
        hex_hash = self._strip_prefix(content_hash)
        path = self._hash_to_path(hex_hash)
        if path.exists():
            path.unlink()
            return True
        return False

    def verify(self, content: bytes, expected_hash: str) -> bool:
        """Verify that content matches the expected hash."""
        hex_hash = self._strip_prefix(expected_hash)
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

    @staticmethod
    def _strip_prefix(content_hash: str) -> str:
        return content_hash.replace("sha256:", "")
