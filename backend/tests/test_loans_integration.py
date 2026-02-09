"""
Integration tests for loan routes - supplementary scenarios.

Complements test_loan_routes.py with additional edge cases and filters.
Uses the same mocking patterns as test_loan_routes.py (context manager
with patch, AsyncMock for repo methods, PUT for updates).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.db.models import Loan
from tests.conftest import MOCK_USER_ID

MOCK_LOAN_ID = UUID("00000000-0000-4000-a000-000000000002")


def _make_mock_loan(**overrides) -> MagicMock:
    """Helper to create mock loan objects with sensible defaults."""
    loan = MagicMock(spec=Loan)
    defaults = dict(
        id=MOCK_LOAN_ID,
        user_id=MOCK_USER_ID,
        bank_name="SBI",
        loan_type="home",
        principal_amount=5000000.0,
        outstanding_principal=4500000.0,
        interest_rate=8.5,
        interest_rate_type="floating",
        tenure_months=240,
        remaining_tenure_months=220,
        emi_amount=43391.0,
        emi_due_date=5,
        prepayment_penalty_pct=0.0,
        foreclosure_charges_pct=0.0,
        eligible_80c=True,
        eligible_24b=True,
        eligible_80e=False,
        eligible_80eea=False,
        disbursement_date=None,
        status="active",
        source="manual",
        source_scan_id=None,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(loan, k, v)
    return loan


# -- Full payload for creating a loan (all required fields) --
_FULL_CREATE_PAYLOAD = {
    "bank_name": "HDFC",
    "loan_type": "home",
    "principal_amount": 3000000.0,
    "outstanding_principal": 3000000.0,
    "interest_rate": 7.5,
    "tenure_months": 180,
    "remaining_tenure_months": 180,
    "emi_amount": 24000.0,
}


@pytest.mark.asyncio
async def test_create_loan_minimum_fields(async_client: AsyncClient) -> None:
    """Test creating a loan with full required fields."""
    created_loan = _make_mock_loan(**_FULL_CREATE_PAYLOAD)

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=created_loan)
        MockRepo.return_value = mock_repo

        response = await async_client.post(
            "/api/loans",
            headers={"Authorization": "Bearer token"},
            json=_FULL_CREATE_PAYLOAD,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["bank_name"] == "HDFC"
    assert data["loan_type"] == "home"


@pytest.mark.asyncio
async def test_create_personal_loan_no_tax_benefits(async_client: AsyncClient) -> None:
    """Test creating a personal loan with no tax benefit flags."""
    payload = {
        "bank_name": "ICICI",
        "loan_type": "personal",
        "principal_amount": 500000.0,
        "outstanding_principal": 450000.0,
        "interest_rate": 12.5,
        "tenure_months": 60,
        "remaining_tenure_months": 55,
        "emi_amount": 11200.0,
        "eligible_80c": False,
        "eligible_24b": False,
        "eligible_80e": False,
        "eligible_80eea": False,
    }
    created_loan = _make_mock_loan(
        **payload,
        interest_rate_type="fixed",
    )

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=created_loan)
        MockRepo.return_value = mock_repo

        response = await async_client.post(
            "/api/loans",
            headers={"Authorization": "Bearer token"},
            json=payload,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["loan_type"] == "personal"
    assert data["eligible_80c"] is False
    assert data["eligible_24b"] is False


@pytest.mark.asyncio
async def test_create_education_loan_with_80e(async_client: AsyncClient) -> None:
    """Test creating an education loan with 80E tax benefit eligibility."""
    payload = {
        "bank_name": "Axis Bank",
        "loan_type": "education",
        "principal_amount": 1000000.0,
        "outstanding_principal": 900000.0,
        "interest_rate": 9.5,
        "tenure_months": 120,
        "remaining_tenure_months": 110,
        "emi_amount": 12800.0,
        "eligible_80e": True,
    }
    created_loan = _make_mock_loan(**payload)

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=created_loan)
        MockRepo.return_value = mock_repo

        response = await async_client.post(
            "/api/loans",
            headers={"Authorization": "Bearer token"},
            json=payload,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["loan_type"] == "education"
    assert data["eligible_80e"] is True


@pytest.mark.asyncio
async def test_list_loans_multiple(async_client: AsyncClient) -> None:
    """Test listing multiple loans."""
    loan1 = _make_mock_loan(
        id=UUID("00000000-0000-4000-a000-000000000010"),
        bank_name="SBI",
        loan_type="home",
    )
    loan2 = _make_mock_loan(
        id=UUID("00000000-0000-4000-a000-000000000011"),
        bank_name="HDFC",
        loan_type="car",
    )
    loan3 = _make_mock_loan(
        id=UUID("00000000-0000-4000-a000-000000000012"),
        bank_name="ICICI",
        loan_type="personal",
    )

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[loan1, loan2, loan3])
        MockRepo.return_value = mock_repo

        response = await async_client.get(
            "/api/loans",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["bank_name"] == "SBI"
    assert data[1]["bank_name"] == "HDFC"
    assert data[2]["bank_name"] == "ICICI"


@pytest.mark.asyncio
async def test_list_loans_filter_by_status(async_client: AsyncClient) -> None:
    """Test listing loans filtered by status."""
    active_loan = _make_mock_loan(
        id=UUID("00000000-0000-4000-a000-000000000020"),
        status="active",
    )

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[active_loan])
        MockRepo.return_value = mock_repo

        response = await async_client.get(
            "/api/loans?status=active",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "active"


@pytest.mark.asyncio
async def test_list_loans_filter_by_type(async_client: AsyncClient) -> None:
    """Test listing loans filtered by loan type."""
    home_loan1 = _make_mock_loan(
        id=UUID("00000000-0000-4000-a000-000000000030"),
        loan_type="home",
    )
    home_loan2 = _make_mock_loan(
        id=UUID("00000000-0000-4000-a000-000000000031"),
        loan_type="home",
    )

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[home_loan1, home_loan2])
        MockRepo.return_value = mock_repo

        response = await async_client.get(
            "/api/loans?loan_type=home",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(loan["loan_type"] == "home" for loan in data)


@pytest.mark.asyncio
async def test_update_loan_interest_rate(async_client: AsyncClient) -> None:
    """Test updating a loan's interest rate (PUT, not PATCH)."""
    updated_loan = _make_mock_loan(interest_rate=7.5)

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock(return_value=updated_loan)
        MockRepo.return_value = mock_repo

        response = await async_client.put(
            f"/api/loans/{MOCK_LOAN_ID}",
            headers={"Authorization": "Bearer token"},
            json={"interest_rate": 7.5},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_loan_status_to_closed(async_client: AsyncClient) -> None:
    """Test updating a loan's status to closed."""
    updated_loan = _make_mock_loan(status="closed")

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock(return_value=updated_loan)
        MockRepo.return_value = mock_repo

        response = await async_client.put(
            f"/api/loans/{MOCK_LOAN_ID}",
            headers={"Authorization": "Bearer token"},
            json={"status": "closed"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"


@pytest.mark.asyncio
async def test_amortization_schedule_entry_count(async_client: AsyncClient) -> None:
    """Test that amortization schedule has correct number of entries."""
    loan = _make_mock_loan(remaining_tenure_months=220)

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=loan)
        MockRepo.return_value = mock_repo

        response = await async_client.get(
            f"/api/loans/{MOCK_LOAN_ID}/amortization",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "schedule" in data
    assert len(data["schedule"]) > 0
    assert len(data["schedule"]) <= 221


@pytest.mark.asyncio
async def test_amortization_first_entry_fields(async_client: AsyncClient) -> None:
    """Test that amortization schedule first entry has correct fields."""
    loan = _make_mock_loan(
        outstanding_principal=4500000.0,
        interest_rate=8.5,
        emi_amount=43391.0,
        remaining_tenure_months=220,
    )

    with patch("app.api.routes.loans.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=loan)
        MockRepo.return_value = mock_repo

        response = await async_client.get(
            f"/api/loans/{MOCK_LOAN_ID}/amortization",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "schedule" in data
    assert len(data["schedule"]) > 0

    first_entry = data["schedule"][0]
    assert "month" in first_entry
    assert "emi" in first_entry
    assert "principal" in first_entry
    assert "interest" in first_entry
    assert "balance" in first_entry
    assert first_entry["month"] == 1
    # EMI is calculated from principal/rate/tenure, not loan.emi_amount
    assert first_entry["emi"] > 0
    assert first_entry["balance"] < 4500000.0


@pytest.mark.asyncio
async def test_create_loan_validation_zero_principal(async_client: AsyncClient) -> None:
    """Test that creating a loan with zero principal is rejected."""
    payload = {
        "bank_name": "SBI",
        "loan_type": "home",
        "principal_amount": 0.0,
        "outstanding_principal": 0.0,
        "interest_rate": 8.5,
        "tenure_months": 240,
        "remaining_tenure_months": 240,
        "emi_amount": 43391.0,
    }

    response = await async_client.post(
        "/api/loans",
        headers={"Authorization": "Bearer token"},
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_loan_validation_negative_interest_rate(async_client: AsyncClient) -> None:
    """Test that creating a loan with negative interest rate is rejected."""
    payload = {
        "bank_name": "SBI",
        "loan_type": "home",
        "principal_amount": 5000000.0,
        "outstanding_principal": 4500000.0,
        "interest_rate": -1.5,
        "tenure_months": 240,
        "remaining_tenure_months": 240,
        "emi_amount": 43391.0,
    }

    response = await async_client.post(
        "/api/loans",
        headers={"Authorization": "Bearer token"},
        json=payload,
    )

    assert response.status_code == 422
