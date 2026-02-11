"""Tests for local filesystem BlobService (blob_service.py).

Covers upload, generate_sas_url, delete_blob, and is_configured.
Uses pytest tmp_path for isolated filesystem testing.
"""

import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helper: build a BlobService with controlled settings
# ---------------------------------------------------------------------------


def _make_service(upload_dir: str = "./uploads"):
    """Create a BlobService instance with patched settings."""
    mock_settings = MagicMock()
    mock_settings.upload_dir = upload_dir

    with patch("app.services.blob_service.settings", mock_settings):
        from app.services.blob_service import BlobService
        svc = BlobService()
    return svc


# ===========================================================================
# TestInit
# ===========================================================================


class TestInit:
    """BlobService.__init__ behaviour."""

    def test_configured_when_upload_dir_set(self, tmp_path):
        svc = _make_service(str(tmp_path / "uploads"))
        assert svc.is_configured is True

    def test_upload_dir_is_created(self, tmp_path):
        target = tmp_path / "new_uploads"
        svc = _make_service(str(target))
        assert target.exists()

    def test_is_configured_returns_true_with_valid_dir(self, tmp_path):
        svc = _make_service(str(tmp_path))
        assert svc.is_configured is True


# ===========================================================================
# TestUploadFile
# ===========================================================================


class TestUploadFile:
    """BlobService.upload_file tests."""

    @pytest.mark.asyncio
    async def test_upload_writes_file(self, tmp_path):
        svc = _make_service(str(tmp_path))
        content = b"PDF_CONTENT_HERE"

        result = await svc.upload_file(
            content=content,
            filename="statement.pdf",
            content_type="application/pdf",
            user_id="user1",
        )

        assert isinstance(result, str)
        written = Path(result)
        assert written.exists()
        assert written.read_bytes() == content

    @pytest.mark.asyncio
    async def test_upload_path_contains_user_id(self, tmp_path):
        svc = _make_service(str(tmp_path))

        result = await svc.upload_file(
            content=b"data",
            filename="file.pdf",
            content_type="application/pdf",
            user_id="user42",
        )

        assert "user42" in result

    @pytest.mark.asyncio
    async def test_upload_preserves_extension(self, tmp_path):
        svc = _make_service(str(tmp_path))

        result = await svc.upload_file(
            content=b"img",
            filename="photo.png",
            content_type="image/png",
            user_id="u",
        )

        assert result.endswith(".png")

    @pytest.mark.asyncio
    async def test_upload_no_extension_defaults_to_bin(self, tmp_path):
        svc = _make_service(str(tmp_path))

        result = await svc.upload_file(
            content=b"data",
            filename="noext",
            content_type="application/octet-stream",
            user_id="u",
        )

        assert result.endswith(".bin")

    @pytest.mark.asyncio
    async def test_upload_creates_user_subdirectory(self, tmp_path):
        svc = _make_service(str(tmp_path))

        await svc.upload_file(b"data", "f.pdf", "application/pdf", "newuser")

        user_dir = tmp_path / "newuser"
        assert user_dir.exists()
        assert user_dir.is_dir()

    @pytest.mark.asyncio
    async def test_upload_returns_unique_names(self, tmp_path):
        svc = _make_service(str(tmp_path))

        r1 = await svc.upload_file(b"a", "f.pdf", "application/pdf", "u")
        r2 = await svc.upload_file(b"b", "f.pdf", "application/pdf", "u")

        assert r1 != r2


# ===========================================================================
# TestGenerateSasUrl
# ===========================================================================


class TestGenerateSasUrl:
    """BlobService.generate_sas_url tests — local files need no SAS."""

    @pytest.mark.asyncio
    async def test_returns_path_as_is(self, tmp_path):
        svc = _make_service(str(tmp_path))
        path = str(tmp_path / "user1" / "file.pdf")
        result = await svc.generate_sas_url(path)
        assert result == path

    @pytest.mark.asyncio
    async def test_expiry_param_is_ignored(self, tmp_path):
        svc = _make_service(str(tmp_path))
        path = str(tmp_path / "file.pdf")
        result = await svc.generate_sas_url(path, expiry_hours=24)
        assert result == path


# ===========================================================================
# TestDeleteBlob
# ===========================================================================


class TestDeleteBlob:
    """BlobService.delete_blob tests."""

    @pytest.mark.asyncio
    async def test_delete_existing_file_returns_true(self, tmp_path):
        svc = _make_service(str(tmp_path))
        # Create a file to delete
        file_path = tmp_path / "user1" / "doc.pdf"
        file_path.parent.mkdir(parents=True)
        file_path.write_bytes(b"content")

        result = await svc.delete_blob(str(file_path))

        assert result is True
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file_returns_false(self, tmp_path):
        svc = _make_service(str(tmp_path))

        result = await svc.delete_blob(str(tmp_path / "no_such_file.pdf"))

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_invalid_path_returns_false(self, tmp_path):
        svc = _make_service(str(tmp_path))

        result = await svc.delete_blob("")

        assert result is False
