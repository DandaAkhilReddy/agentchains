"""Shared test fixtures for the Indian Loan Analyzer financial engine.

Provides reusable loan snapshots, sample data, and helper factories
used across test_financial_math, test_strategies, and test_optimization.
Also provides API-level fixtures for route testing via httpx.AsyncClient.
"""

import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

# Mock SDK modules that are not installed in the test environment
for _mod in [
    "firebase_admin", "firebase_admin.auth",
    "openai",
    "pdfplumber",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from app.core.strategies import LoanSnapshot
from app.db.models import User, Loan
from app.api.deps import get_current_user, get_optional_user
from app.db.session import get_db


# ---------------------------------------------------------------------------
# Mock user / DB fixtures for API testing
# ---------------------------------------------------------------------------

MOCK_USER_ID = uuid.UUID("00000000-0000-4000-a000-000000000001")
MOCK_USER_FIREBASE_UID = "firebase_test_user_123"


@pytest.fixture
def mock_user() -> MagicMock:
    """A mock User ORM instance for dependency injection."""
    user = MagicMock(spec=User)
    user.id = MOCK_USER_ID
    user.firebase_uid = MOCK_USER_FIREBASE_UID
    user.email = "test@example.com"
    user.phone = "+919876543210"
    user.display_name = "Test User"
    user.preferred_language = "en"
    user.tax_regime = "old"
    user.country = "IN"
    user.filing_status = "individual"
    user.annual_income = 1200000.0
    user.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return user


@pytest.fixture
def mock_db_session():
    """AsyncMock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_loan() -> MagicMock:
    """A mock Loan ORM instance."""
    loan = MagicMock(spec=Loan)
    loan.id = uuid.UUID("00000000-0000-4000-a000-000000000010")
    loan.user_id = MOCK_USER_ID
    loan.bank_name = "SBI"
    loan.loan_type = "home"
    loan.principal_amount = 5000000.0
    loan.outstanding_principal = 4500000.0
    loan.interest_rate = 8.5
    loan.interest_rate_type = "floating"
    loan.tenure_months = 240
    loan.remaining_tenure_months = 220
    loan.emi_amount = 43391.0
    loan.emi_due_date = 5
    loan.prepayment_penalty_pct = 0.0
    loan.foreclosure_charges_pct = 0.0
    loan.eligible_80c = True
    loan.eligible_24b = True
    loan.eligible_80e = False
    loan.eligible_80eea = False
    loan.disbursement_date = None
    loan.status = "active"
    loan.source = "manual"
    loan.source_scan_id = None
    loan.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    loan.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return loan


@pytest.fixture
async def async_client(mock_user, mock_db_session):
    """httpx AsyncClient wired to the FastAPI app with mocked auth + DB."""
    from app.main import app

    async def _override_get_current_user():
        return mock_user

    async def _override_get_optional_user():
        return mock_user

    async def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_optional_user] = _override_get_optional_user
    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Individual loan fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sbi_home_loan() -> LoanSnapshot:
    """SBI home loan: 50,00,000 at 8.5% for 240 months (20 years).

    Benchmark EMI ~ 43,391.
    Eligible for 80C (principal) and 24(b) (interest).
    Floating rate => 0% prepayment penalty per RBI 2014.
    """
    return LoanSnapshot(
        loan_id="sbi_home",
        bank_name="SBI",
        loan_type="home",
        outstanding_principal=Decimal("5000000"),
        interest_rate=Decimal("8.5"),
        emi_amount=Decimal("43391"),
        remaining_tenure_months=240,
        prepayment_penalty_pct=Decimal("0"),
        foreclosure_charges_pct=Decimal("0"),
        eligible_80c=True,
        eligible_24b=True,
        eligible_80e=False,
        eligible_80eea=False,
    )


@pytest.fixture
def hdfc_personal_loan() -> LoanSnapshot:
    """HDFC personal loan: 10,00,000 at 12% for 60 months (5 years).

    Benchmark EMI ~ 22,244.
    No tax benefits.
    Floating rate => 0% prepayment penalty.
    """
    return LoanSnapshot(
        loan_id="hdfc_personal",
        bank_name="HDFC",
        loan_type="personal",
        outstanding_principal=Decimal("1000000"),
        interest_rate=Decimal("12"),
        emi_amount=Decimal("22244"),
        remaining_tenure_months=60,
        prepayment_penalty_pct=Decimal("0"),
        foreclosure_charges_pct=Decimal("0"),
        eligible_80c=False,
        eligible_24b=False,
        eligible_80e=False,
        eligible_80eea=False,
    )


@pytest.fixture
def icici_car_loan() -> LoanSnapshot:
    """ICICI car loan: 8,00,000 at 9.5% for 84 months (7 years).

    No tax benefits. Floating rate.
    """
    return LoanSnapshot(
        loan_id="icici_car",
        bank_name="ICICI",
        loan_type="car",
        outstanding_principal=Decimal("800000"),
        interest_rate=Decimal("9.5"),
        emi_amount=Decimal("12757"),
        remaining_tenure_months=84,
        prepayment_penalty_pct=Decimal("0"),
        foreclosure_charges_pct=Decimal("0"),
        eligible_80c=False,
        eligible_24b=False,
        eligible_80e=False,
        eligible_80eea=False,
    )


@pytest.fixture
def education_loan() -> LoanSnapshot:
    """Education loan: 5,00,000 at 10% for 60 months.

    Eligible for 80E (interest deduction, no cap).
    """
    return LoanSnapshot(
        loan_id="edu_loan",
        bank_name="SBI",
        loan_type="education",
        outstanding_principal=Decimal("500000"),
        interest_rate=Decimal("10"),
        emi_amount=Decimal("10624"),
        remaining_tenure_months=60,
        prepayment_penalty_pct=Decimal("0"),
        foreclosure_charges_pct=Decimal("0"),
        eligible_80c=False,
        eligible_24b=False,
        eligible_80e=True,
        eligible_80eea=False,
    )


@pytest.fixture
def small_almost_done_loan() -> LoanSnapshot:
    """A tiny loan with only ~2 EMIs remaining.

    Used to test the SmartHybrid 3-EMI bump logic.
    Outstanding: 20,000, EMI: 10,500 => about 2 months left.
    """
    return LoanSnapshot(
        loan_id="small_closing",
        bank_name="AXIS",
        loan_type="personal",
        outstanding_principal=Decimal("20000"),
        interest_rate=Decimal("14"),
        emi_amount=Decimal("10500"),
        remaining_tenure_months=3,
        prepayment_penalty_pct=Decimal("0"),
        foreclosure_charges_pct=Decimal("0"),
        eligible_80c=False,
        eligible_24b=False,
        eligible_80e=False,
        eligible_80eea=False,
    )


@pytest.fixture
def fixed_rate_personal_loan() -> LoanSnapshot:
    """Fixed rate personal loan with foreclosure charges."""
    return LoanSnapshot(
        loan_id="fixed_personal",
        bank_name="BAJAJ",
        loan_type="personal",
        outstanding_principal=Decimal("300000"),
        interest_rate=Decimal("15"),
        emi_amount=Decimal("7137"),
        remaining_tenure_months=60,
        prepayment_penalty_pct=Decimal("4"),
        foreclosure_charges_pct=Decimal("4"),
        eligible_80c=False,
        eligible_24b=False,
        eligible_80e=False,
        eligible_80eea=False,
    )


# ---------------------------------------------------------------------------
# Multi-loan list fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def three_diverse_loans(
    sbi_home_loan, hdfc_personal_loan, icici_car_loan
) -> list[LoanSnapshot]:
    """Three loans with distinctly different rates:
    - Home: 8.5%
    - Car: 9.5%
    - Personal: 12%
    """
    return [sbi_home_loan, hdfc_personal_loan, icici_car_loan]


@pytest.fixture
def same_rate_loans() -> list[LoanSnapshot]:
    """Three loans all at 10% to verify strategies produce identical results."""
    base = dict(
        bank_name="SBI",
        loan_type="personal",
        interest_rate=Decimal("10"),
        prepayment_penalty_pct=Decimal("0"),
        foreclosure_charges_pct=Decimal("0"),
        eligible_80c=False,
        eligible_24b=False,
        eligible_80e=False,
        eligible_80eea=False,
    )
    return [
        LoanSnapshot(
            loan_id="same_a",
            outstanding_principal=Decimal("300000"),
            emi_amount=Decimal("6374"),
            remaining_tenure_months=60,
            **base,
        ),
        LoanSnapshot(
            loan_id="same_b",
            outstanding_principal=Decimal("500000"),
            emi_amount=Decimal("10624"),
            remaining_tenure_months=60,
            **base,
        ),
        LoanSnapshot(
            loan_id="same_c",
            outstanding_principal=Decimal("200000"),
            emi_amount=Decimal("4249"),
            remaining_tenure_months=60,
            **base,
        ),
    ]


@pytest.fixture
def smart_hybrid_loans(sbi_home_loan, hdfc_personal_loan, small_almost_done_loan) -> list[LoanSnapshot]:
    """Loan set designed to exercise SmartHybrid logic:
    - home 8.5% with 24(b) -> effective ~5.95% at 30% bracket
    - personal 12% no benefit -> effective 12%
    - small personal 14% about to close -> bump to top
    """
    return [sbi_home_loan, hdfc_personal_loan, small_almost_done_loan]
