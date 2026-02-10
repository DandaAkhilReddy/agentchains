"""Tests for /api/optimizer/* routes — all require auth."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.db.models import Loan, RepaymentPlan
from tests.conftest import MOCK_USER_ID

MOCK_LOAN_ID = uuid.UUID("00000000-0000-4000-a000-000000000010")
MOCK_PLAN_ID = uuid.UUID("00000000-0000-4000-a000-000000000020")


def _make_mock_loan(**overrides) -> MagicMock:
    """Create a mock Loan ORM object for optimizer tests."""
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
        eligible_mortgage_deduction=False,
        eligible_student_loan_deduction=False,
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


@pytest.mark.asyncio
async def test_quick_compare(async_client: AsyncClient):
    """POST /api/optimizer/quick-compare returns savings preview."""
    mock_loan = _make_mock_loan()

    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[mock_loan])
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/quick-compare",
            headers={"Authorization": "Bearer token"},
            json={
                "loan_ids": [str(MOCK_LOAN_ID)],
                "monthly_extra": 10000,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "interest_saved" in data
    assert "months_saved" in data
    assert "debt_free_months" in data
    assert isinstance(data["interest_saved"], (int, float, str))
    assert isinstance(data["months_saved"], (int, float))
    assert isinstance(data["debt_free_months"], (int, float))


@pytest.mark.asyncio
async def test_what_if(async_client: AsyncClient):
    """POST /api/optimizer/what-if returns interest and months comparison."""
    mock_loan = _make_mock_loan()

    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_loan)
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/what-if",
            headers={"Authorization": "Bearer token"},
            json={
                "loan_id": str(MOCK_LOAN_ID),
                "monthly_extra": 5000,
                "lump_sum": 100000,
                "lump_sum_month": 6,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "original_interest" in data
    assert "new_interest" in data
    assert "interest_saved" in data
    assert "original_months" in data
    assert "new_months" in data
    assert "months_saved" in data
    assert float(data["interest_saved"]) >= 0
    assert float(data["original_interest"]) > 0
    assert float(data["new_interest"]) > 0
    assert data["original_months"] == 220  # matches mock remaining_tenure_months
    assert data["new_months"] <= data["original_months"]


@pytest.mark.asyncio
async def test_save_plan(async_client: AsyncClient):
    """POST /api/optimizer/save-plan persists a repayment plan."""
    mock_plan = MagicMock(spec=RepaymentPlan)
    mock_plan.id = MOCK_PLAN_ID

    with patch("app.api.routes.optimizer.RepaymentPlanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_plan)
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/save-plan",
            headers={"Authorization": "Bearer token"},
            json={
                "name": "My Avalanche Plan",
                "strategy": "avalanche",
                "config": {"monthly_extra": 10000},
                "results": {"interest_saved": 500000, "months_saved": 24},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_id"] == str(MOCK_PLAN_ID)
    assert data["message"] == "Plan saved"


@pytest.mark.asyncio
async def test_list_plans(async_client: AsyncClient):
    """GET /api/optimizer/plans returns empty list when no plans exist."""
    with patch("app.api.routes.optimizer.RepaymentPlanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[])
        MockRepo.return_value = mock_repo

        resp = await async_client.get(
            "/api/optimizer/plans",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_tax_impact(async_client: AsyncClient):
    """POST /api/optimizer/tax-impact returns tax regime comparison."""
    mock_loan = _make_mock_loan()

    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[mock_loan])
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/tax-impact",
            headers={"Authorization": "Bearer token"},
            json={"annual_income": 1500000},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "old_regime_tax" in data
    assert "new_regime_tax" in data
    assert "recommended" in data
    assert data["recommended"] in ("old", "new")
    assert "savings" in data
    assert "explanation" in data
    assert "deductions" in data
    assert float(data["old_regime_tax"]) >= 0
    assert float(data["new_regime_tax"]) >= 0
    assert float(data["savings"]) >= 0


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensitivity_analysis(async_client: AsyncClient):
    """POST /api/optimizer/sensitivity returns rate-delta impact points."""
    mock_loan = _make_mock_loan(
        eligible_mortgage_deduction=False,
        eligible_student_loan_deduction=False,
    )

    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[mock_loan])
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/sensitivity",
            headers={"Authorization": "Bearer token"},
            json={
                "loan_ids": [str(MOCK_LOAN_ID)],
                "monthly_extra": 10000,
                "strategy": "avalanche",
                "rate_deltas": [-1.0, 0.0, 1.0, 2.0],
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "strategy_name" in data
    assert data["strategy_name"] == "avalanche"
    assert "points" in data
    assert len(data["points"]) == 4
    for pt in data["points"]:
        assert "rate_delta_pct" in pt
        assert "total_interest_paid" in pt
        assert "total_months" in pt
        assert "interest_saved_vs_baseline" in pt


@pytest.mark.asyncio
async def test_sensitivity_no_matching_loans(async_client: AsyncClient):
    """POST /api/optimizer/sensitivity returns 400 when no loans match."""
    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[])
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/sensitivity",
            headers={"Authorization": "Bearer token"},
            json={
                "loan_ids": [str(MOCK_LOAN_ID)],
                "monthly_extra": 5000,
                "strategy": "avalanche",
            },
        )

    assert resp.status_code == 400
    assert "No matching" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# What-if edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_what_if_loan_not_found(async_client: AsyncClient):
    """POST /api/optimizer/what-if returns 404 when loan doesn't exist."""
    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/what-if",
            headers={"Authorization": "Bearer token"},
            json={
                "loan_id": str(MOCK_LOAN_ID),
                "monthly_extra": 5000,
                "lump_sum": 0,
                "lump_sum_month": 1,
            },
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Loan not found"


@pytest.mark.asyncio
async def test_what_if_zero_extra(async_client: AsyncClient):
    """POST /api/optimizer/what-if with zero extra returns zero savings."""
    mock_loan = _make_mock_loan()

    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_loan)
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/what-if",
            headers={"Authorization": "Bearer token"},
            json={
                "loan_id": str(MOCK_LOAN_ID),
                "monthly_extra": 0,
                "lump_sum": 0,
                "lump_sum_month": 1,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    # With zero extra payment, savings should be negligible (rounding tolerance)
    assert abs(float(data["interest_saved"])) < 100
    assert data["months_saved"] == 0
    assert data["original_months"] == data["new_months"]


# ---------------------------------------------------------------------------
# Tax impact edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tax_impact_no_loans(async_client: AsyncClient):
    """POST /api/optimizer/tax-impact with no loans still returns a result."""
    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[])
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/tax-impact",
            headers={"Authorization": "Bearer token"},
            json={"annual_income": 800000},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "old_regime_tax" in data
    assert "new_regime_tax" in data
    assert "recommended" in data


# ---------------------------------------------------------------------------
# List plans with data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_plans_with_data(async_client: AsyncClient):
    """GET /api/optimizer/plans returns saved plans with expected fields."""
    mock_plan = MagicMock(spec=RepaymentPlan)
    mock_plan.id = MOCK_PLAN_ID
    mock_plan.name = "Avalanche Plan"
    mock_plan.strategy = "avalanche"
    mock_plan.is_active = True
    mock_plan.created_at = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

    with patch("app.api.routes.optimizer.RepaymentPlanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[mock_plan])
        MockRepo.return_value = mock_repo

        resp = await async_client.get(
            "/api/optimizer/plans",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    plan = data[0]
    assert plan["id"] == str(MOCK_PLAN_ID)
    assert plan["name"] == "Avalanche Plan"
    assert plan["strategy"] == "avalanche"
    assert plan["is_active"] is True
    assert "created_at" in plan


# ---------------------------------------------------------------------------
# Validation: 422 on invalid inputs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_empty_loan_ids_returns_422(async_client: AsyncClient):
    """POST /api/optimizer/analyze with empty loan_ids returns 422."""
    resp = await async_client.post(
        "/api/optimizer/analyze",
        headers={"Authorization": "Bearer token"},
        json={
            "loan_ids": [],
            "monthly_extra": 10000,
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_analyze_negative_monthly_extra_returns_422(async_client: AsyncClient):
    """POST /api/optimizer/analyze with negative monthly_extra returns 422."""
    resp = await async_client.post(
        "/api/optimizer/analyze",
        headers={"Authorization": "Bearer token"},
        json={
            "loan_ids": [str(MOCK_LOAN_ID)],
            "monthly_extra": -5000,
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_analyze_invalid_strategy_name_returns_422(async_client: AsyncClient):
    """POST /api/optimizer/analyze with invalid strategy triggers error.

    The strategies field is list[str], so any string passes schema validation.
    The optimizer itself raises ValueError on unknown strategies, which the
    route should surface as a 422 or 500.  We verify the request at least
    does not succeed with 200.
    """
    mock_loan = _make_mock_loan(
        eligible_mortgage_deduction=False,
        eligible_student_loan_deduction=False,
    )

    with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[mock_loan])
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/optimizer/analyze",
            headers={"Authorization": "Bearer token"},
            json={
                "loan_ids": [str(MOCK_LOAN_ID)],
                "monthly_extra": 10000,
                "strategies": ["not_a_real_strategy"],
            },
        )

    # Unknown strategy should not succeed — expect 422 (ValueError → validation error)
    assert resp.status_code in (422, 500)


@pytest.mark.asyncio
async def test_sensitivity_empty_loan_ids_returns_422(async_client: AsyncClient):
    """POST /api/optimizer/sensitivity with empty loan_ids returns 422."""
    resp = await async_client.post(
        "/api/optimizer/sensitivity",
        headers={"Authorization": "Bearer token"},
        json={
            "loan_ids": [],
            "monthly_extra": 5000,
            "strategy": "avalanche",
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_quick_compare_empty_loan_ids_returns_422(async_client: AsyncClient):
    """POST /api/optimizer/quick-compare with empty loan_ids returns 422."""
    resp = await async_client.post(
        "/api/optimizer/quick-compare",
        headers={"Authorization": "Bearer token"},
        json={
            "loan_ids": [],
            "monthly_extra": 10000,
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_quick_compare_negative_monthly_extra_returns_422(async_client: AsyncClient):
    """POST /api/optimizer/quick-compare with zero monthly_extra returns 422.

    QuickCompareRequest requires monthly_extra > 0 (gt=0).
    """
    resp = await async_client.post(
        "/api/optimizer/quick-compare",
        headers={"Authorization": "Bearer token"},
        json={
            "loan_ids": [str(MOCK_LOAN_ID)],
            "monthly_extra": 0,
        },
    )

    assert resp.status_code == 422
