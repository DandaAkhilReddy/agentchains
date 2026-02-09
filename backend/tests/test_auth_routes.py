"""Tests for /api/auth/* routes — all require auth."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

from tests.conftest import MOCK_USER_ID


@pytest.mark.asyncio
async def test_verify_token(async_client: AsyncClient, mock_user):
    """POST /api/auth/verify-token returns user profile from mocked auth."""
    resp = await async_client.post(
        "/api/auth/verify-token",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(MOCK_USER_ID)
    assert data["email"] == "test@example.com"
    assert data["display_name"] == "Test User"


@pytest.mark.asyncio
async def test_get_profile(async_client: AsyncClient, mock_user):
    """GET /api/auth/me returns user profile fields."""
    resp = await async_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(MOCK_USER_ID)
    assert data["email"] == "test@example.com"
    assert data["phone"] == "+919876543210"
    assert data["display_name"] == "Test User"
    assert data["preferred_language"] == "en"
    assert data["tax_regime"] == "old"


@pytest.mark.asyncio
async def test_update_profile(async_client: AsyncClient, mock_user):
    """PUT /api/auth/me with display_name update calls UserRepository.update."""
    # Create a mock user with updated name
    updated_user = MagicMock()
    updated_user.id = MOCK_USER_ID
    updated_user.email = "test@example.com"
    updated_user.phone = "+919876543210"
    updated_user.display_name = "New Name"
    updated_user.preferred_language = "en"
    updated_user.tax_regime = "old"
    updated_user.country = "IN"
    updated_user.filing_status = "individual"
    updated_user.annual_income = 1200000.0

    with patch("app.api.routes.auth.UserRepository") as MockRepo:
        mock_repo_instance = MagicMock()
        mock_repo_instance.update = AsyncMock(return_value=updated_user)
        MockRepo.return_value = mock_repo_instance

        resp = await async_client.put(
            "/api/auth/me",
            headers={"Authorization": "Bearer token"},
            json={"display_name": "New Name"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "New Name"
    mock_repo_instance.update.assert_awaited_once_with(
        MOCK_USER_ID, display_name="New Name"
    )
