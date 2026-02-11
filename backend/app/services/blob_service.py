"""Local filesystem storage service — upload, URL, delete."""

import uuid
import logging
import shutil
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class BlobService:
    """Local filesystem storage for loan document uploads."""

    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        if self.upload_dir:
            self.upload_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_configured(self) -> bool:
        return bool(self.upload_dir)

    async def upload_file(
        self, content: bytes, filename: str, content_type: str, user_id: str
    ) -> str:
        """Save file to local filesystem.

        Returns: file path as a string (relative to upload_dir)
        """
        if not self.is_configured:
            raise RuntimeError("File storage not configured")

        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        blob_name = f"{user_id}/{uuid.uuid4()}.{ext}"

        file_path = self.upload_dir / blob_name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

        logger.info(f"Uploaded {len(content)} bytes to {file_path}")
        return str(file_path)

    async def generate_sas_url(self, blob_url: str, expiry_hours: int = 1) -> str:
        """Return the file path as-is (no SAS needed for local files)."""
        return blob_url

    async def delete_blob(self, blob_url: str) -> bool:
        """Delete a file by path."""
        try:
            path = Path(blob_url)
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"File deletion error: {e}")
            return False
