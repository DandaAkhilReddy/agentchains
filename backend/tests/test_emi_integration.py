"""
Integration tests for EMI calculator routes.

These tests supplement test_emi_routes.py with additional edge cases,
boundary conditions, and cross-field validations.

NOTE: The EMI API returns Decimal values serialized as strings.
Use float() to convert before numeric comparisons.
"""

import pytest
from httpx import AsyncClient


class TestEMICalculateIntegration:
    """Integration tests for POST /api/emi/calculate endpoint."""

    @pytest.mark.asyncio
    async def test_calculate_emi_short_tenure_12_months(self, async_client: AsyncClient):
        """Test EMI calculation with very short tenure (12 months)."""
        response = await async_client.post(
            "/api/emi/calculate",
            json={
                "principal": 100000,
                "annual_rate": 12.0,
                "tenure_months": 12,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["emi"]) > 0
        assert float(data["total_interest"]) > 0
        assert float(data["total_payment"]) > 100000
        # Short tenure means higher EMI
        assert float(data["emi"]) > 8000

    @pytest.mark.asyncio
    async def test_calculate_emi_long_tenure_360_months(self, async_client: AsyncClient):
        """Test EMI calculation with very long tenure (360 months / 30 years)."""
        response = await async_client.post(
            "/api/emi/calculate",
            json={
                "principal": 5000000,
                "annual_rate": 8.5,
                "tenure_months": 360,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["emi"]) > 0
        assert float(data["total_interest"]) > 0
        assert float(data["total_payment"]) > 5000000
        # Long tenure: total interest exceeds principal
        assert float(data["total_interest"]) > 5000000

    @pytest.mark.asyncio
    async def test_calculate_emi_total_payment_consistency(self, async_client: AsyncClient):
        """Test that total_payment roughly equals principal + total_interest."""
        response = await async_client.post(
            "/api/emi/calculate",
            json={
                "principal": 250000,
                "annual_rate": 10.5,
                "tenure_months": 60,
            },
        )
        assert response.status_code == 200
        data = response.json()

        total_payment = float(data["total_payment"])
        total_interest = float(data["total_interest"])
        # total_payment = principal + total_interest
        assert abs(total_payment - (250000 + total_interest)) < 1.0

    @pytest.mark.asyncio
    async def test_calculate_emi_large_prepayment(self, async_client: AsyncClient):
        """Test EMI calculation with large prepayment saves interest."""
        response = await async_client.post(
            "/api/emi/calculate",
            json={
                "principal": 500000,
                "annual_rate": 9.0,
                "tenure_months": 120,
                "monthly_prepayment": 10000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["emi"]) > 0
        assert float(data["interest_saved"]) > 0
        assert data["months_saved"] > 0
        # With large prepayment, should save significant interest
        assert float(data["interest_saved"]) > 50000

    @pytest.mark.asyncio
    async def test_calculate_emi_response_has_all_expected_fields(
        self, async_client: AsyncClient
    ):
        """Test that calculate EMI response contains all expected fields."""
        response = await async_client.post(
            "/api/emi/calculate",
            json={
                "principal": 300000,
                "annual_rate": 11.0,
                "tenure_months": 84,
                "monthly_prepayment": 2000,
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        expected_fields = [
            "emi",
            "total_interest",
            "total_payment",
            "interest_saved",
            "months_saved",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
            assert data[field] is not None


class TestEMIReverseCalculateIntegration:
    """Integration tests for POST /api/emi/reverse-calculate endpoint."""

    @pytest.mark.asyncio
    async def test_reverse_calculate_low_emi_gives_low_rate(
        self, async_client: AsyncClient
    ):
        """Test reverse calculation with very low EMI returns low interest rate."""
        response = await async_client.post(
            "/api/emi/reverse-calculate",
            json={
                "principal": 100000,
                "target_emi": 1700,
                "tenure_months": 60,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "estimated_rate" in data
        assert float(data["estimated_rate"]) < 5.0

    @pytest.mark.asyncio
    async def test_reverse_calculate_high_emi_gives_high_rate(
        self, async_client: AsyncClient
    ):
        """Test reverse calculation with very high EMI returns high interest rate."""
        response = await async_client.post(
            "/api/emi/reverse-calculate",
            json={
                "principal": 100000,
                "target_emi": 3000,
                "tenure_months": 60,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "estimated_rate" in data
        assert float(data["estimated_rate"]) > 15.0

    @pytest.mark.asyncio
    async def test_reverse_calculate_response_has_estimated_rate_field(
        self, async_client: AsyncClient
    ):
        """Test that reverse calculate response contains estimated_rate field."""
        response = await async_client.post(
            "/api/emi/reverse-calculate",
            json={
                "principal": 200000,
                "target_emi": 4500,
                "tenure_months": 60,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "estimated_rate" in data
        # Decimal serializes as string; verify it's a valid number
        rate = float(data["estimated_rate"])
        assert rate >= 0


class TestEMIAffordabilityIntegration:
    """Integration tests for POST /api/emi/affordability endpoint."""

    @pytest.mark.asyncio
    async def test_affordability_zero_budget_returns_error(
        self, async_client: AsyncClient
    ):
        """Test affordability with zero budget returns validation error."""
        response = await async_client.post(
            "/api/emi/affordability",
            json={
                "monthly_emi_budget": 0,
                "annual_rate": 10.0,
                "tenure_months": 60,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_affordability_high_rate_lower_principal_than_low_rate(
        self, async_client: AsyncClient
    ):
        """Test that high interest rate yields lower max_principal than low rate."""
        response_low = await async_client.post(
            "/api/emi/affordability",
            json={
                "monthly_emi_budget": 10000,
                "annual_rate": 7.0,
                "tenure_months": 120,
            },
        )
        assert response_low.status_code == 200
        data_low = response_low.json()

        response_high = await async_client.post(
            "/api/emi/affordability",
            json={
                "monthly_emi_budget": 10000,
                "annual_rate": 15.0,
                "tenure_months": 120,
            },
        )
        assert response_high.status_code == 200
        data_high = response_high.json()

        assert float(data_low["max_principal"]) > float(data_high["max_principal"])


class TestEMIValidationIntegration:
    """Integration tests for EMI route validation."""

    @pytest.mark.asyncio
    async def test_calculate_emi_negative_rate_returns_422(
        self, async_client: AsyncClient
    ):
        """Test that negative annual_rate returns 422 validation error."""
        response = await async_client.post(
            "/api/emi/calculate",
            json={
                "principal": 100000,
                "annual_rate": -5.0,
                "tenure_months": 60,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_calculate_emi_zero_tenure_returns_422(
        self, async_client: AsyncClient
    ):
        """Test that zero tenure_months returns 422 validation error."""
        response = await async_client.post(
            "/api/emi/calculate",
            json={
                "principal": 100000,
                "annual_rate": 10.0,
                "tenure_months": 0,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_reverse_calculate_negative_principal_validation(
        self, async_client: AsyncClient
    ):
        """Test reverse calculate with negative principal returns 422."""
        response = await async_client.post(
            "/api/emi/reverse-calculate",
            json={
                "principal": -100000,
                "target_emi": 2500,
                "tenure_months": 60,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_affordability_negative_tenure_validation(
        self, async_client: AsyncClient
    ):
        """Test affordability with negative tenure returns 422."""
        response = await async_client.post(
            "/api/emi/affordability",
            json={
                "monthly_emi_budget": 5000,
                "annual_rate": 10.0,
                "tenure_months": -12,
            },
        )
        assert response.status_code == 422
