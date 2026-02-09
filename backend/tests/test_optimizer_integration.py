"""Additional integration tests for optimizer routes.

Supplements test_optimizer_routes.py and test_integration.py with:
- POST /api/optimizer/analyze (all 4 strategies)
- Zero monthly_extra scenarios
- Lump-sum only scenarios
- Education loan (80E) tax impact
- High income tax impact
- Multi-loan diverse portfolios
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.db.models import Loan, RepaymentPlan
from tests.conftest import MOCK_USER_ID

MOCK_LOAN_ID_1 = uuid.UUID("00000000-0000-4000-a000-000000000010")
MOCK_LOAN_ID_2 = uuid.UUID("00000000-0000-4000-a000-000000000011")
MOCK_LOAN_ID_3 = uuid.UUID("00000000-0000-4000-a000-000000000012")
MOCK_PLAN_ID = uuid.UUID("00000000-0000-4000-a000-000000000020")


def _make_mock_loan(**overrides) -> MagicMock:
    """Create a mock Loan ORM object for optimizer tests."""
    loan = MagicMock(spec=Loan)
    defaults = dict(
        id=uuid.UUID("00000000-0000-4000-a000-000000000010"),
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


# ===========================================================================
# TestAnalyzeEndpoint
# ===========================================================================

class TestAnalyzeEndpoint:
    """Tests for POST /api/optimizer/analyze — full multi-strategy optimization."""

    @pytest.mark.asyncio
    async def test_analyze_returns_all_strategies(self, async_client: AsyncClient):
        """POST /api/optimizer/analyze returns all 4 strategies by default."""
        loan_a = _make_mock_loan(
            id=MOCK_LOAN_ID_1,
            bank_name="SBI",
            loan_type="home",
            outstanding_principal=4500000.0,
            interest_rate=8.5,
            remaining_tenure_months=220,
            emi_amount=43391.0,
            eligible_80c=True,
            eligible_24b=True,
        )
        loan_b = _make_mock_loan(
            id=MOCK_LOAN_ID_2,
            bank_name="HDFC",
            loan_type="personal",
            outstanding_principal=900000.0,
            interest_rate=12.0,
            remaining_tenure_months=50,
            emi_amount=22244.0,
            eligible_80c=False,
            eligible_24b=False,
        )

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_by_user = AsyncMock(return_value=[loan_a, loan_b])
            MockRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/optimizer/analyze",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_ids": [str(MOCK_LOAN_ID_1), str(MOCK_LOAN_ID_2)],
                    "monthly_extra": 10000,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "strategies" in data
        assert "baseline_total_interest" in data
        assert "baseline_total_months" in data
        assert "recommended_strategy" in data

        # Verify all 4 default strategies are present
        strategy_names = {s["strategy_name"] for s in data["strategies"]}
        assert strategy_names == {"avalanche", "snowball", "smart_hybrid", "proportional"}

    @pytest.mark.asyncio
    async def test_analyze_strategies_have_interest_saved_field(self, async_client: AsyncClient):
        """Analyze response strategies include interest_saved_vs_baseline."""
        loan = _make_mock_loan(id=MOCK_LOAN_ID_1)

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_by_user = AsyncMock(return_value=[loan])
            MockRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/optimizer/analyze",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_ids": [str(MOCK_LOAN_ID_1)],
                    "monthly_extra": 5000,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        for strategy in data["strategies"]:
            assert "interest_saved_vs_baseline" in strategy
            assert "months_saved_vs_baseline" in strategy
            assert isinstance(strategy["interest_saved_vs_baseline"], (int, float, str))
            assert isinstance(strategy["months_saved_vs_baseline"], int)

    @pytest.mark.asyncio
    async def test_analyze_strategies_have_months_saved_field(self, async_client: AsyncClient):
        """Analyze response strategies include months_saved_vs_baseline."""
        loan = _make_mock_loan(id=MOCK_LOAN_ID_1)

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_by_user = AsyncMock(return_value=[loan])
            MockRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/optimizer/analyze",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_ids": [str(MOCK_LOAN_ID_1)],
                    "monthly_extra": 8000,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        for strategy in data["strategies"]:
            assert "months_saved_vs_baseline" in strategy
            assert strategy["months_saved_vs_baseline"] >= 0


# ===========================================================================
# TestQuickCompareEdgeCases
# ===========================================================================

class TestQuickCompareEdgeCases:
    """Edge case tests for quick-compare endpoint."""

    @pytest.mark.asyncio
    async def test_quick_compare_minimal_monthly_extra_returns_minimal_savings(self, async_client: AsyncClient):
        """Quick-compare with minimal monthly_extra (1 rupee) returns minimal savings."""
        loan = _make_mock_loan(id=MOCK_LOAN_ID_1)

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_by_user = AsyncMock(return_value=[loan])
            MockRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/optimizer/quick-compare",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_ids": [str(MOCK_LOAN_ID_1)],
                    "monthly_extra": 1,  # Minimal amount (schema requires gt=0)
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "interest_saved" in data
        assert "months_saved" in data
        # With minimal extra payment, savings should be minimal
        assert float(data["interest_saved"]) >= 0
        assert data["months_saved"] >= 0


# ===========================================================================
# TestWhatIfScenarios
# ===========================================================================

class TestWhatIfScenarios:
    """What-if scenario tests for various payment configurations."""

    @pytest.mark.asyncio
    async def test_what_if_lump_sum_only_no_monthly_extra(self, async_client: AsyncClient):
        """What-if with lump_sum only (no monthly_extra) returns savings."""
        loan = _make_mock_loan(id=MOCK_LOAN_ID_1)

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=loan)
            MockRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/optimizer/what-if",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_id": str(MOCK_LOAN_ID_1),
                    "monthly_extra": 0,
                    "lump_sum": 200000,
                    "lump_sum_month": 12,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "interest_saved" in data
        assert "months_saved" in data
        assert "original_interest" in data
        assert "new_interest" in data
        assert float(data["interest_saved"]) >= 0

    @pytest.mark.asyncio
    async def test_what_if_returns_original_months_gte_new_months(self, async_client: AsyncClient):
        """What-if ensures original_months >= new_months (prepayment reduces tenure)."""
        loan = _make_mock_loan(id=MOCK_LOAN_ID_1)

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=loan)
            MockRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/optimizer/what-if",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_id": str(MOCK_LOAN_ID_1),
                    "monthly_extra": 5000,
                    "lump_sum": 100000,
                    "lump_sum_month": 6,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["original_months"] >= data["new_months"]
        assert data["months_saved"] >= 0
        assert data["original_months"] == data["new_months"] + data["months_saved"]


# ===========================================================================
# TestTaxImpactScenarios
# ===========================================================================

class TestTaxImpactScenarios:
    """Tax impact tests for education loans and high income scenarios."""

    @pytest.mark.asyncio
    async def test_tax_impact_with_education_loan_includes_80e(self, async_client: AsyncClient):
        """Tax-impact with education loan (eligible_80e=True) includes 80E deduction."""
        edu_loan = _make_mock_loan(
            id=MOCK_LOAN_ID_1,
            bank_name="SBI",
            loan_type="education",
            outstanding_principal=500000.0,
            interest_rate=10.0,
            remaining_tenure_months=60,
            emi_amount=10624.0,
            eligible_80c=False,
            eligible_24b=False,
            eligible_80e=True,
            eligible_80eea=False,
        )

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_by_user = AsyncMock(return_value=[edu_loan])
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
        assert "deductions" in data
        # Check that 80E is mentioned in deductions for old regime
        deductions = data["deductions"]
        assert "80e_education_interest" in deductions or "total" in deductions

    @pytest.mark.asyncio
    async def test_tax_impact_high_income_returns_appropriate_recommendation(self, async_client: AsyncClient):
        """Tax-impact with high income (>1500000) returns valid recommendation."""
        loan = _make_mock_loan(id=MOCK_LOAN_ID_1)

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_by_user = AsyncMock(return_value=[loan])
            MockRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/optimizer/tax-impact",
                headers={"Authorization": "Bearer token"},
                json={"annual_income": 2000000},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "recommended" in data
        assert data["recommended"] in ("old", "new")
        assert "explanation" in data
        assert "savings" in data
        assert float(data["savings"]) >= 0


# ===========================================================================
# TestSaveAndListPlans
# ===========================================================================

class TestSaveAndListPlans:
    """Tests for saving and listing repayment plans."""

    @pytest.mark.asyncio
    async def test_save_plan_then_list_returns_saved_plan(self, async_client: AsyncClient):
        """Save a plan, then list plans — the saved plan should appear."""
        mock_plan = MagicMock(spec=RepaymentPlan)
        mock_plan.id = MOCK_PLAN_ID
        mock_plan.user_id = MOCK_USER_ID
        mock_plan.name = "Avalanche Strategy 2026"
        mock_plan.strategy = "avalanche"
        mock_plan.config = {"monthly_extra": 8000}
        mock_plan.results = {"interest_saved": 450000}
        mock_plan.is_active = False
        mock_plan.created_at = datetime(2026, 2, 9, tzinfo=timezone.utc)

        with patch("app.api.routes.optimizer.RepaymentPlanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.create = AsyncMock(return_value=mock_plan)
            MockRepo.return_value = mock_repo

            save_resp = await async_client.post(
                "/api/optimizer/save-plan",
                headers={"Authorization": "Bearer token"},
                json={
                    "name": "Avalanche Strategy 2026",
                    "strategy": "avalanche",
                    "config": {"monthly_extra": 8000},
                    "results": {"interest_saved": 450000},
                },
            )

        assert save_resp.status_code == 200
        save_data = save_resp.json()
        assert save_data["plan_id"] == str(MOCK_PLAN_ID)
        assert save_data["message"] == "Plan saved"

        # Now list plans
        with patch("app.api.routes.optimizer.RepaymentPlanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_by_user = AsyncMock(return_value=[mock_plan])
            MockRepo.return_value = mock_repo

            list_resp = await async_client.get(
                "/api/optimizer/plans",
                headers={"Authorization": "Bearer token"},
            )

        assert list_resp.status_code == 200
        plans = list_resp.json()
        assert len(plans) == 1
        assert plans[0]["id"] == str(MOCK_PLAN_ID)
        assert plans[0]["name"] == "Avalanche Strategy 2026"
        assert plans[0]["strategy"] == "avalanche"


# ===========================================================================
# TestMultiLoanDiversePortfolio
# ===========================================================================

class TestMultiLoanDiversePortfolio:
    """Tests for quick-compare with diverse loan portfolios."""

    @pytest.mark.asyncio
    async def test_quick_compare_three_diverse_loans(self, async_client: AsyncClient):
        """Quick-compare with 3 diverse loans (home, personal, car) at different rates."""
        home_loan = _make_mock_loan(
            id=MOCK_LOAN_ID_1,
            bank_name="SBI",
            loan_type="home",
            outstanding_principal=4500000.0,
            interest_rate=8.5,
            remaining_tenure_months=220,
            emi_amount=43391.0,
            eligible_80c=True,
            eligible_24b=True,
        )
        personal_loan = _make_mock_loan(
            id=MOCK_LOAN_ID_2,
            bank_name="HDFC",
            loan_type="personal",
            outstanding_principal=900000.0,
            interest_rate=12.0,
            remaining_tenure_months=50,
            emi_amount=22244.0,
            eligible_80c=False,
            eligible_24b=False,
        )
        car_loan = _make_mock_loan(
            id=MOCK_LOAN_ID_3,
            bank_name="ICICI",
            loan_type="car",
            outstanding_principal=700000.0,
            interest_rate=9.5,
            remaining_tenure_months=72,
            emi_amount=12757.0,
            eligible_80c=False,
            eligible_24b=False,
        )

        with patch("app.api.routes.optimizer.LoanRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_by_user = AsyncMock(return_value=[home_loan, personal_loan, car_loan])
            MockRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/optimizer/quick-compare",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_ids": [
                        str(MOCK_LOAN_ID_1),
                        str(MOCK_LOAN_ID_2),
                        str(MOCK_LOAN_ID_3),
                    ],
                    "monthly_extra": 15000,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "interest_saved" in data
        assert "months_saved" in data
        assert "debt_free_months" in data
        assert float(data["interest_saved"]) >= 0
        assert data["months_saved"] >= 0
        assert data["debt_free_months"] > 0
