"""Tests for app.services.scanner_service — regex extraction and helpers.

These tests exercise the pure-function extraction logic (no Azure calls).
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock the Azure SDK modules before importing scanner_service
_azure_mocks = {}
for mod_name in [
    "azure", "azure.ai", "azure.ai.documentintelligence",
    "azure.ai.documentintelligence.models", "azure.core",
    "azure.core.credentials",
]:
    if mod_name not in sys.modules:
        _azure_mocks[mod_name] = MagicMock()
        sys.modules[mod_name] = _azure_mocks[mod_name]

from app.services.scanner_service import (
    ExtractedField,
    ScannerService,
    _clean_amount,
    _extract_with_patterns,
    BANK_NORMALIZER_IN,
    LOAN_TYPE_NORMALIZER,
    PATTERNS_IN,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def scanner():
    """ScannerService with client=None (Document Intelligence not configured)."""
    with patch("app.services.scanner_service.settings") as mock_settings:
        mock_settings.azure_doc_intel_endpoint = ""
        mock_settings.azure_doc_intel_key = ""
        svc = ScannerService()
        assert svc.client is None
        return svc


def _find_field(fields: list[ExtractedField], name: str) -> ExtractedField | None:
    """Return the first ExtractedField matching field_name, or None."""
    for f in fields:
        if f.field_name == name:
            return f
    return None


# ---------------------------------------------------------------------------
# Bank name extraction
# ---------------------------------------------------------------------------


class TestBankNameExtraction:

    def test_extract_bank_name_sbi(self, scanner):
        text = "Loan statement from State Bank of India, Branch: Hyderabad"
        fields = scanner._extract_fields(text)
        bank = _find_field(fields, "bank_name")
        assert bank is not None
        assert bank.value == "SBI"
        assert bank.confidence == pytest.approx(0.85)

    def test_extract_bank_name_hdfc(self, scanner):
        text = "HDFC Bank Personal Loan Statement"
        fields = scanner._extract_fields(text)
        bank = _find_field(fields, "bank_name")
        assert bank is not None
        assert bank.value == "HDFC"

    def test_extract_bank_name_icici(self, scanner):
        text = "Welcome to ICICI Bank loan services"
        fields = scanner._extract_fields(text)
        bank = _find_field(fields, "bank_name")
        assert bank is not None
        assert bank.value == "ICICI"

    def test_extract_bank_name_pnb(self, scanner):
        text = "Punjab National Bank home loan agreement"
        fields = scanner._extract_fields(text)
        bank = _find_field(fields, "bank_name")
        assert bank is not None
        assert bank.value == "PNB"


# ---------------------------------------------------------------------------
# Interest rate extraction
# ---------------------------------------------------------------------------


class TestInterestRateExtraction:

    def test_extract_interest_rate_with_label(self, scanner):
        text = "Rate of interest: 8.5% p.a."
        fields = scanner._extract_fields(text)
        rate = _find_field(fields, "interest_rate")
        assert rate is not None
        assert rate.value == "8.5"

    def test_extract_interest_rate_per_annum(self, scanner):
        text = "Interest charged at 11.25% per annum"
        fields = scanner._extract_fields(text)
        rate = _find_field(fields, "interest_rate")
        assert rate is not None
        assert rate.value == "11.25"

    def test_extract_interest_rate_roi(self, scanner):
        text = "ROI: 9.75%"
        fields = scanner._extract_fields(text)
        rate = _find_field(fields, "interest_rate")
        assert rate is not None
        assert rate.value == "9.75"


# ---------------------------------------------------------------------------
# Principal / amount extraction
# ---------------------------------------------------------------------------


class TestPrincipalExtraction:

    def test_extract_principal_rupee_symbol(self, scanner):
        text = "Loan amount: \u20b925,00,000"
        fields = scanner._extract_fields(text)
        principal = _find_field(fields, "principal_amount")
        assert principal is not None
        assert principal.value == "2500000"

    def test_extract_principal_colon_format(self, scanner):
        text = "Sanctioned Amount: 10,00,000"
        fields = scanner._extract_fields(text)
        principal = _find_field(fields, "principal_amount")
        assert principal is not None
        assert principal.value == "1000000"


# ---------------------------------------------------------------------------
# EMI extraction
# ---------------------------------------------------------------------------


class TestEMIExtraction:

    def test_extract_emi(self, scanner):
        text = "EMI: \u20b943,391"
        fields = scanner._extract_fields(text)
        emi = _find_field(fields, "emi_amount")
        assert emi is not None
        assert emi.value == "43391"

    def test_extract_emi_monthly_installment(self, scanner):
        text = "Monthly installment: \u20b922,244"
        fields = scanner._extract_fields(text)
        emi = _find_field(fields, "emi_amount")
        assert emi is not None
        assert emi.value == "22244"


# ---------------------------------------------------------------------------
# Tenure extraction
# ---------------------------------------------------------------------------


class TestTenureExtraction:

    def test_extract_tenure_months(self, scanner):
        text = "Tenure: 240 months"
        fields = scanner._extract_fields(text)
        tenure = _find_field(fields, "tenure_months")
        assert tenure is not None
        assert tenure.value == "240"

    def test_extract_tenure_years(self, scanner):
        text = "Loan term: 20 years"
        fields = scanner._extract_fields(text)
        tenure = _find_field(fields, "tenure_months")
        assert tenure is not None
        assert tenure.value == "20"


# ---------------------------------------------------------------------------
# Loan type extraction
# ---------------------------------------------------------------------------


class TestLoanTypeExtraction:

    def test_extract_loan_type_home(self, scanner):
        text = "This is a Home Loan agreement"
        fields = scanner._extract_fields(text)
        lt = _find_field(fields, "loan_type")
        assert lt is not None
        assert lt.value == "home"

    def test_extract_loan_type_personal(self, scanner):
        text = "Personal Loan statement for the month of January"
        fields = scanner._extract_fields(text)
        lt = _find_field(fields, "loan_type")
        assert lt is not None
        assert lt.value == "personal"

    def test_extract_loan_type_car(self, scanner):
        text = "Your Car Loan account summary"
        fields = scanner._extract_fields(text)
        lt = _find_field(fields, "loan_type")
        assert lt is not None
        assert lt.value == "car"

    def test_extract_loan_type_education(self, scanner):
        text = "Education Loan disbursement notice"
        fields = scanner._extract_fields(text)
        lt = _find_field(fields, "loan_type")
        assert lt is not None
        assert lt.value == "education"


# ---------------------------------------------------------------------------
# _clean_amount helper
# ---------------------------------------------------------------------------


class TestCleanAmount:

    def test_clean_amount_indian_format(self):
        assert _clean_amount("25,00,000") == "2500000"

    def test_clean_amount_western_format(self):
        assert _clean_amount("2,500,000") == "2500000"

    def test_clean_amount_no_commas(self):
        assert _clean_amount("43391") == "43391"

    def test_clean_amount_with_spaces(self):
        assert _clean_amount(" 1,00,000 ") == "100000"

    def test_clean_amount_decimals(self):
        assert _clean_amount("25,00,000.50") == "2500000.50"


# ---------------------------------------------------------------------------
# No match on empty or irrelevant text
# ---------------------------------------------------------------------------


class TestNoMatch:

    def test_empty_text(self, scanner):
        fields = scanner._extract_fields("")
        assert fields == []

    def test_irrelevant_text(self, scanner):
        fields = scanner._extract_fields("The quick brown fox jumps over the lazy dog.")
        assert fields == []


# ---------------------------------------------------------------------------
# _extract_with_patterns low-level tests
# ---------------------------------------------------------------------------


class TestExtractWithPatterns:

    def test_returns_empty_on_no_match(self):
        value, confidence = _extract_with_patterns("nothing here", "principal", PATTERNS_IN)
        assert value == ""
        assert confidence == 0.0

    def test_returns_match_with_085_confidence(self):
        value, confidence = _extract_with_patterns("Loan amount: 5,00,000", "principal", PATTERNS_IN)
        assert value == "5,00,000"
        assert confidence == pytest.approx(0.85)

    def test_unknown_field_returns_empty(self):
        value, confidence = _extract_with_patterns("any text", "nonexistent_field", PATTERNS_IN)
        assert value == ""
        assert confidence == 0.0
