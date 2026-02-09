"""Integration tests for /api/scanner/* routes.

Supplements test_scanner_routes.py with comprehensive coverage of:
- Multiple file type uploads (PDF, PNG, JPEG)
- All scan job statuses (processing, completed, failed)
- Loan creation from extracted fields
- File size validation
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.db.models import ScanJob, Loan
from tests.conftest import MOCK_USER_ID

MOCK_JOB_ID = uuid.UUID("00000000-0000-4000-a000-000000000030")
MOCK_LOAN_ID = uuid.UUID("00000000-0000-4000-a000-000000000040")


# ---------------------------------------------------------------------------
# Upload Tests - File Type Acceptance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_accepts_pdf(async_client: AsyncClient):
    """POST /api/scanner/upload accepts PDF file type."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "uploaded"

    with patch("app.api.routes.scanner.BlobService") as MockBlob, \
         patch("app.api.routes.scanner.ScanJobRepository") as MockRepo, \
         patch("app.api.routes.scanner.ScannerService") as MockScanner:

        # Mock blob upload
        mock_blob = MagicMock()
        mock_blob.upload_file = AsyncMock(return_value="https://blob.url/doc.pdf")
        MockBlob.return_value = mock_blob

        # Mock repository
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_job)
        mock_repo.update_status = AsyncMock()
        MockRepo.return_value = mock_repo

        # Mock scanner service
        mock_scanner = MagicMock()
        mock_scanner.analyze_document = AsyncMock(return_value=[])
        MockScanner.return_value = mock_scanner

        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("loan_statement.pdf", b"fake pdf content", "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(MOCK_JOB_ID)
    assert data["status"] == "uploaded"
    mock_blob.upload_file.assert_called_once()
    mock_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_upload_accepts_png(async_client: AsyncClient):
    """POST /api/scanner/upload accepts PNG image file type."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "uploaded"

    with patch("app.api.routes.scanner.BlobService") as MockBlob, \
         patch("app.api.routes.scanner.ScanJobRepository") as MockRepo, \
         patch("app.api.routes.scanner.ScannerService") as MockScanner:

        mock_blob = MagicMock()
        mock_blob.upload_file = AsyncMock(return_value="https://blob.url/doc.png")
        MockBlob.return_value = mock_blob

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_job)
        mock_repo.update_status = AsyncMock()
        MockRepo.return_value = mock_repo

        mock_scanner = MagicMock()
        mock_scanner.analyze_document = AsyncMock(return_value=[])
        MockScanner.return_value = mock_scanner

        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("loan_screenshot.png", b"fake png bytes", "image/png")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(MOCK_JOB_ID)
    mock_blob.upload_file.assert_called_once()


@pytest.mark.asyncio
async def test_upload_accepts_jpeg(async_client: AsyncClient):
    """POST /api/scanner/upload accepts JPEG image file type."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "uploaded"

    with patch("app.api.routes.scanner.BlobService") as MockBlob, \
         patch("app.api.routes.scanner.ScanJobRepository") as MockRepo, \
         patch("app.api.routes.scanner.ScannerService") as MockScanner:

        mock_blob = MagicMock()
        mock_blob.upload_file = AsyncMock(return_value="https://blob.url/doc.jpg")
        MockBlob.return_value = mock_blob

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_job)
        mock_repo.update_status = AsyncMock()
        MockRepo.return_value = mock_repo

        mock_scanner = MagicMock()
        mock_scanner.analyze_document = AsyncMock(return_value=[])
        MockScanner.return_value = mock_scanner

        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("loan_photo.jpg", b"fake jpeg bytes", "image/jpeg")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(MOCK_JOB_ID)
    mock_blob.upload_file.assert_called_once()


@pytest.mark.asyncio
async def test_upload_rejects_large_file(async_client: AsyncClient):
    """POST /api/scanner/upload rejects files larger than 10MB."""
    # Create a file larger than 10MB (10 * 1024 * 1024 bytes)
    large_content = b"x" * (10 * 1024 * 1024 + 1)

    resp = await async_client.post(
        "/api/scanner/upload",
        headers={"Authorization": "Bearer token"},
        files={"file": ("huge_document.pdf", large_content, "application/pdf")},
    )

    assert resp.status_code == 400
    assert "10MB" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Get Scan Status Tests - Various Job States
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_scan_status_completed_with_fields(async_client: AsyncClient):
    """GET /api/scanner/status/{uuid} returns completed job with extracted fields."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "completed"
    mock_job.extracted_fields = {
        "bank_name": "SBI",
        "loan_type": "home",
        "outstanding_principal": "4500000",
        "interest_rate": "8.5",
    }
    mock_job.confidence_scores = {
        "bank_name": 0.98,
        "loan_type": 0.95,
        "outstanding_principal": 0.92,
        "interest_rate": 0.90,
    }
    mock_job.error_message = None
    mock_job.processing_time_ms = 1250
    mock_job.created_at = datetime(2026, 2, 9, 12, 0, 0, tzinfo=timezone.utc)

    with patch("app.api.routes.scanner.ScanJobRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_job)
        MockRepo.return_value = mock_repo

        resp = await async_client.get(
            f"/api/scanner/status/{MOCK_JOB_ID}",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(MOCK_JOB_ID)
    assert data["status"] == "completed"
    assert data["processing_time_ms"] == 1250
    assert len(data["extracted_fields"]) == 4

    # Verify field structure
    field_names = {f["field_name"] for f in data["extracted_fields"]}
    assert "bank_name" in field_names
    assert "loan_type" in field_names

    # Check one field in detail
    bank_field = next(f for f in data["extracted_fields"] if f["field_name"] == "bank_name")
    assert bank_field["value"] == "SBI"
    assert bank_field["confidence"] == 0.98


@pytest.mark.asyncio
async def test_get_scan_status_processing(async_client: AsyncClient):
    """GET /api/scanner/status/{uuid} returns processing job without extracted fields."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "processing"
    mock_job.extracted_fields = None
    mock_job.confidence_scores = None
    mock_job.error_message = None
    mock_job.processing_time_ms = None
    mock_job.created_at = datetime(2026, 2, 9, 12, 0, 0, tzinfo=timezone.utc)

    with patch("app.api.routes.scanner.ScanJobRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_job)
        MockRepo.return_value = mock_repo

        resp = await async_client.get(
            f"/api/scanner/status/{MOCK_JOB_ID}",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(MOCK_JOB_ID)
    assert data["status"] == "processing"
    assert data["extracted_fields"] is None
    assert data["error_message"] is None
    assert data["processing_time_ms"] is None


@pytest.mark.asyncio
async def test_get_scan_status_failed(async_client: AsyncClient):
    """GET /api/scanner/status/{uuid} returns failed job with error message."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "failed"
    mock_job.extracted_fields = None
    mock_job.confidence_scores = None
    mock_job.error_message = "Failed to extract text: Document is encrypted"
    mock_job.processing_time_ms = 850
    mock_job.created_at = datetime(2026, 2, 9, 12, 0, 0, tzinfo=timezone.utc)

    with patch("app.api.routes.scanner.ScanJobRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_job)
        MockRepo.return_value = mock_repo

        resp = await async_client.get(
            f"/api/scanner/status/{MOCK_JOB_ID}",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(MOCK_JOB_ID)
    assert data["status"] == "failed"
    assert data["error_message"] == "Failed to extract text: Document is encrypted"
    assert data["extracted_fields"] is None


# ---------------------------------------------------------------------------
# Confirm Scan Tests - Loan Creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_scan_creates_loan(async_client: AsyncClient):
    """POST /api/scanner/{uuid}/confirm creates loan from extracted fields."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "review_needed"

    mock_loan = MagicMock(spec=Loan)
    mock_loan.id = MOCK_LOAN_ID
    mock_loan.user_id = MOCK_USER_ID
    mock_loan.bank_name = "SBI"
    mock_loan.loan_type = "home"
    mock_loan.source = "scan"
    mock_loan.source_scan_id = MOCK_JOB_ID

    with patch("app.api.routes.scanner.ScanJobRepository") as MockScanRepo, \
         patch("app.api.routes.scanner.LoanRepository") as MockLoanRepo:

        mock_scan_repo = MagicMock()
        mock_scan_repo.get_by_id = AsyncMock(return_value=mock_job)
        mock_scan_repo.update_status = AsyncMock()
        MockScanRepo.return_value = mock_scan_repo

        mock_loan_repo = MagicMock()
        mock_loan_repo.create = AsyncMock(return_value=mock_loan)
        MockLoanRepo.return_value = mock_loan_repo

        resp = await async_client.post(
            f"/api/scanner/{MOCK_JOB_ID}/confirm",
            headers={"Authorization": "Bearer token"},
            json={
                "bank_name": "SBI",
                "loan_type": "home",
                "principal_amount": 5000000,
                "outstanding_principal": 4500000,
                "interest_rate": 8.5,
                "interest_rate_type": "floating",
                "tenure_months": 240,
                "remaining_tenure_months": 220,
                "emi_amount": 43391,
                "emi_due_date": 5,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["loan_id"] == str(MOCK_LOAN_ID)
    assert "Loan created from scan" in data["message"]

    # Verify loan was created with correct parameters
    mock_loan_repo.create.assert_called_once()
    call_kwargs = mock_loan_repo.create.call_args.kwargs
    assert call_kwargs["user_id"] == MOCK_USER_ID
    assert call_kwargs["bank_name"] == "SBI"
    assert call_kwargs["loan_type"] == "home"
    assert call_kwargs["outstanding_principal"] == 4500000
    assert call_kwargs["interest_rate"] == 8.5
    assert call_kwargs["source"] == "scan"
    assert call_kwargs["source_scan_id"] == MOCK_JOB_ID

    # Verify scan job status was updated
    mock_scan_repo.update_status.assert_called_once()
    update_call = mock_scan_repo.update_status.call_args
    assert update_call.args[0] == MOCK_JOB_ID
    assert update_call.args[1] == MOCK_USER_ID
    assert update_call.args[2] == "completed"
    assert update_call.kwargs["created_loan_id"] == MOCK_LOAN_ID


@pytest.mark.asyncio
async def test_confirm_scan_with_completed_status(async_client: AsyncClient):
    """POST /api/scanner/{uuid}/confirm succeeds even if job already completed."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "completed"  # Already completed

    mock_loan = MagicMock(spec=Loan)
    mock_loan.id = MOCK_LOAN_ID

    with patch("app.api.routes.scanner.ScanJobRepository") as MockScanRepo, \
         patch("app.api.routes.scanner.LoanRepository") as MockLoanRepo:

        mock_scan_repo = MagicMock()
        mock_scan_repo.get_by_id = AsyncMock(return_value=mock_job)
        mock_scan_repo.update_status = AsyncMock()
        MockScanRepo.return_value = mock_scan_repo

        mock_loan_repo = MagicMock()
        mock_loan_repo.create = AsyncMock(return_value=mock_loan)
        MockLoanRepo.return_value = mock_loan_repo

        resp = await async_client.post(
            f"/api/scanner/{MOCK_JOB_ID}/confirm",
            headers={"Authorization": "Bearer token"},
            json={
                "bank_name": "HDFC",
                "loan_type": "personal",
                "principal_amount": 1000000,
                "outstanding_principal": 800000,
                "interest_rate": 12.0,
                "interest_rate_type": "floating",
                "tenure_months": 60,
                "remaining_tenure_months": 48,
                "emi_amount": 22244,
                "emi_due_date": 15,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["loan_id"] == str(MOCK_LOAN_ID)

    # Verify loan was still created
    mock_loan_repo.create.assert_called_once()
    call_kwargs = mock_loan_repo.create.call_args.kwargs
    assert call_kwargs["bank_name"] == "HDFC"
    assert call_kwargs["loan_type"] == "personal"


@pytest.mark.asyncio
async def test_confirm_scan_with_optional_emi_due_date(async_client: AsyncClient):
    """POST /api/scanner/{uuid}/confirm handles optional emi_due_date field."""
    mock_job = MagicMock(spec=ScanJob)
    mock_job.id = MOCK_JOB_ID
    mock_job.status = "completed"

    mock_loan = MagicMock(spec=Loan)
    mock_loan.id = MOCK_LOAN_ID

    with patch("app.api.routes.scanner.ScanJobRepository") as MockScanRepo, \
         patch("app.api.routes.scanner.LoanRepository") as MockLoanRepo:

        mock_scan_repo = MagicMock()
        mock_scan_repo.get_by_id = AsyncMock(return_value=mock_job)
        mock_scan_repo.update_status = AsyncMock()
        MockScanRepo.return_value = mock_scan_repo

        mock_loan_repo = MagicMock()
        mock_loan_repo.create = AsyncMock(return_value=mock_loan)
        MockLoanRepo.return_value = mock_loan_repo

        # Omit emi_due_date field
        resp = await async_client.post(
            f"/api/scanner/{MOCK_JOB_ID}/confirm",
            headers={"Authorization": "Bearer token"},
            json={
                "bank_name": "ICICI",
                "loan_type": "car",
                "principal_amount": 800000,
                "outstanding_principal": 750000,
                "interest_rate": 9.5,
                "interest_rate_type": "floating",
                "tenure_months": 84,
                "remaining_tenure_months": 72,
                "emi_amount": 12757,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["loan_id"] == str(MOCK_LOAN_ID)

    # Verify loan was created with None for emi_due_date
    mock_loan_repo.create.assert_called_once()
    call_kwargs = mock_loan_repo.create.call_args.kwargs
    assert call_kwargs["emi_due_date"] is None
