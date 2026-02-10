"""Tests for /api/scanner/* routes — all require auth."""

import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

MOCK_JOB_ID = uuid.UUID("00000000-0000-4000-a000-000000000030")


@pytest.mark.asyncio
async def test_upload_invalid_type(async_client: AsyncClient):
    """POST /api/scanner/upload with unsupported content_type returns 400."""
    # Create a fake file with disallowed MIME type
    resp = await async_client.post(
        "/api/scanner/upload",
        headers={"Authorization": "Bearer token"},
        files={"file": ("malware.exe", b"fake content", "application/exe")},
    )
    assert resp.status_code == 400
    assert "not supported" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_scan_status_not_found(async_client: AsyncClient):
    """GET /api/scanner/status/{uuid} returns 404 when job not found."""
    with patch("app.api.routes.scanner.ScanJobRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        MockRepo.return_value = mock_repo

        resp = await async_client.get(
            f"/api/scanner/status/{MOCK_JOB_ID}",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Scan job not found"


@pytest.mark.asyncio
async def test_confirm_scan_not_found(async_client: AsyncClient):
    """POST /api/scanner/{uuid}/confirm returns 404 when job not found."""
    with patch("app.api.routes.scanner.ScanJobRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        MockRepo.return_value = mock_repo

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

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Scan job not found"


# ---------------------------------------------------------------------------
# Helpers for cross-field validation tests
# ---------------------------------------------------------------------------

MOCK_LOAN_ID = uuid.UUID("00000000-0000-4000-a000-000000000040")


def _make_field(name: str, value: str, confidence: float = 0.9):
    """Create a lightweight object mimicking scanner_service.ExtractedField."""
    obj = MagicMock()
    obj.field_name = name
    obj.value = value
    obj.confidence = confidence
    return obj


def _patch_upload_deps(scanner_fields):
    """Return a context-manager stack that patches BlobService, ScanJobRepository,
    ScannerService, LoanRepository, and UserRepository for the upload route.

    ``scanner_fields`` is the list of ExtractedField-like objects that
    ScannerService.analyze_with_ai will return.
    """
    from contextlib import ExitStack

    stack = ExitStack()

    # BlobService -- pretend upload succeeded
    mock_blob_cls = stack.enter_context(
        patch("app.api.routes.scanner.BlobService")
    )
    mock_blob = MagicMock()
    mock_blob.is_configured = True
    mock_blob.upload_file = AsyncMock(return_value="https://blob.test/file.pdf")
    mock_blob_cls.return_value = mock_blob

    # ScanJobRepository -- create returns a stub job, update_status is a no-op
    mock_scan_repo_cls = stack.enter_context(
        patch("app.api.routes.scanner.ScanJobRepository")
    )
    mock_scan_repo = MagicMock()
    mock_job = MagicMock()
    mock_job.id = MOCK_JOB_ID
    mock_scan_repo.create = AsyncMock(return_value=mock_job)
    mock_scan_repo.update_status = AsyncMock(return_value=None)
    mock_scan_repo_cls.return_value = mock_scan_repo

    # ScannerService -- only strategy 1 fires, returns our fields
    mock_scanner_cls = stack.enter_context(
        patch("app.api.routes.scanner.ScannerService")
    )
    mock_scanner = MagicMock()
    mock_scanner.analyze_with_ai = AsyncMock(return_value=scanner_fields)
    mock_scanner.ai_client = None          # skip strategy 2
    mock_scanner_cls.return_value = mock_scanner

    # LoanRepository -- create returns a stub loan
    mock_loan_repo_cls = stack.enter_context(
        patch("app.api.routes.scanner.LoanRepository")
    )
    mock_loan_repo = MagicMock()
    mock_loan = MagicMock()
    mock_loan.id = MOCK_LOAN_ID
    mock_loan_repo.create = AsyncMock(return_value=mock_loan)
    mock_loan_repo_cls.return_value = mock_loan_repo

    # UserRepository -- update is a no-op
    mock_user_repo_cls = stack.enter_context(
        patch("app.api.routes.scanner.UserRepository")
    )
    mock_user_repo = MagicMock()
    mock_user_repo.update = AsyncMock(return_value=None)
    mock_user_repo_cls.return_value = mock_user_repo

    return stack, mock_loan_repo


# ---------------------------------------------------------------------------
# Cross-field validation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_emi_gt_principal_gets_swapped(async_client: AsyncClient):
    """When EMI > principal the route swaps them so principal is the larger value."""
    fields = [
        _make_field("principal_amount", "20000"),    # smaller (actually the EMI)
        _make_field("emi_amount", "500000"),          # larger  (actually the principal)
        _make_field("interest_rate", "8.5"),
        _make_field("tenure_months", "240"),
        _make_field("loan_type", "home"),
    ]
    stack, mock_loan_repo = _patch_upload_deps(fields)

    with stack:
        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("doc.pdf", b"fake content", "application/pdf")},
        )

    assert resp.status_code == 200
    # LoanRepository.create must have been called with the SWAPPED values:
    # principal_amount should be the larger value (500000)
    call_kwargs = mock_loan_repo.create.call_args
    assert call_kwargs.kwargs["principal_amount"] == 500000.0
    assert call_kwargs.kwargs["emi_amount"] == 20000.0


@pytest.mark.asyncio
async def test_rate_gt_50_capped_to_default(async_client: AsyncClient):
    """An extracted interest rate above 50% is replaced with the country default."""
    fields = [
        _make_field("principal_amount", "1000000"),
        _make_field("interest_rate", "75"),           # absurdly high
        _make_field("tenure_months", "120"),
        _make_field("loan_type", "personal"),
    ]
    stack, mock_loan_repo = _patch_upload_deps(fields)

    with stack:
        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("doc.png", b"fake content", "image/png")},
        )

    assert resp.status_code == 200
    call_kwargs = mock_loan_repo.create.call_args
    # Default for IN is 8.5%
    assert call_kwargs.kwargs["interest_rate"] == 8.5


@pytest.mark.asyncio
async def test_principal_lt_3x_emi_no_swap(async_client: AsyncClient):
    """When principal < 3*EMI but EMI < principal, log warning but do NOT swap."""
    fields = [
        _make_field("principal_amount", "50000"),
        _make_field("emi_amount", "20000"),           # 50000 < 3*20000 => suspicious
        _make_field("interest_rate", "10"),
        _make_field("tenure_months", "60"),
        _make_field("loan_type", "personal"),
    ]
    stack, mock_loan_repo = _patch_upload_deps(fields)

    with stack:
        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("doc.pdf", b"fake content", "application/pdf")},
        )

    assert resp.status_code == 200
    call_kwargs = mock_loan_repo.create.call_args
    # Values stay as-is (no swap) even though ratio is suspicious
    assert call_kwargs.kwargs["principal_amount"] == 50000.0
    assert call_kwargs.kwargs["emi_amount"] == 20000.0


@pytest.mark.asyncio
async def test_currency_detection_returns_detected_country(async_client: AsyncClient):
    """When the scanner detects a currency, the response includes detected_country."""
    fields = [
        _make_field("principal_amount", "250000"),
        _make_field("interest_rate", "6.5"),
        _make_field("tenure_months", "360"),
        _make_field("loan_type", "home"),
        _make_field("detected_currency", "USD"),
    ]
    stack, _ = _patch_upload_deps(fields)

    with stack:
        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("doc.pdf", b"fake content", "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_country"] == "US"


@pytest.mark.asyncio
async def test_auto_calc_emi_when_missing(async_client: AsyncClient):
    """When EMI is missing but principal + rate + tenure are present, EMI is auto-calculated."""
    fields = [
        _make_field("principal_amount", "1000000"),
        _make_field("interest_rate", "12"),
        _make_field("tenure_months", "60"),
        _make_field("loan_type", "personal"),
        # no emi_amount field at all
    ]
    stack, mock_loan_repo = _patch_upload_deps(fields)

    with stack:
        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("doc.pdf", b"fake content", "application/pdf")},
        )

    assert resp.status_code == 200
    call_kwargs = mock_loan_repo.create.call_args
    emi = call_kwargs.kwargs["emi_amount"]
    # Standard EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
    # P=1000000, annual_rate=12%, monthly r=0.01, n=60
    # Expected ~ 22244.44
    assert 22200 < emi < 22300, f"Auto-calculated EMI {emi} not in expected range"


@pytest.mark.asyncio
async def test_empty_document_returns_empty_fields(async_client: AsyncClient):
    """When the scanner returns no fields, the response has no loan_id and an error message."""
    stack, mock_loan_repo = _patch_upload_deps([])  # empty fields list

    with stack:
        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("blank.pdf", b"fake content", "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["loan_id"] is None
    assert data["detected_country"] is None
    assert data["error"] is not None
    assert "extract" in data["error"].lower() or "manually" in data["error"].lower()
    # LoanRepository.create should NOT have been called
    mock_loan_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_valid_pdf_success(async_client: AsyncClient):
    """POST /api/scanner/upload with a valid PDF returns 200 with loan_id."""
    fields = [
        _make_field("principal_amount", "5000000"),
        _make_field("interest_rate", "8.5"),
        _make_field("tenure_months", "240"),
        _make_field("emi_amount", "43391"),
        _make_field("loan_type", "home"),
        _make_field("bank_name", "SBI"),
    ]
    stack, mock_loan_repo = _patch_upload_deps(fields)

    with stack:
        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("statement.pdf", b"fake pdf content", "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["loan_id"] is not None
    assert data["error"] is None
    mock_loan_repo.create.assert_called_once()
    call_kwargs = mock_loan_repo.create.call_args.kwargs
    assert call_kwargs["principal_amount"] == 5000000.0
    assert call_kwargs["emi_amount"] == 43391.0
    assert call_kwargs["bank_name"] == "SBI"


@pytest.mark.asyncio
async def test_upload_oversized_file_returns_400(async_client: AsyncClient):
    """POST /api/scanner/upload with >10MB file returns 400."""
    large_content = b"x" * (10 * 1024 * 1024 + 1)  # just over 10MB
    resp = await async_client.post(
        "/api/scanner/upload",
        headers={"Authorization": "Bearer token"},
        files={"file": ("big.pdf", large_content, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "10" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_non_loan_document_returns_empty_fields(async_client: AsyncClient):
    """A non-loan document that yields empty-string values should not create a loan."""
    # Scanner returns fields but all values are empty strings (non-loan document)
    fields = [
        _make_field("principal_amount", ""),
        _make_field("interest_rate", ""),
        _make_field("tenure_months", ""),
        _make_field("emi_amount", ""),
        _make_field("loan_type", "personal"),
        _make_field("bank_name", ""),
    ]
    stack, mock_loan_repo = _patch_upload_deps(fields)

    with stack:
        resp = await async_client.post(
            "/api/scanner/upload",
            headers={"Authorization": "Bearer token"},
            files={"file": ("receipt.jpg", b"fake content", "image/jpeg")},
        )

    assert resp.status_code == 200
    data = resp.json()
    # principal is 0, so LoanRepository.create should NOT have been called
    assert data["loan_id"] is None
    mock_loan_repo.create.assert_not_called()
