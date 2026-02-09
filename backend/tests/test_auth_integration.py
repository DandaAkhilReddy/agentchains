"""Integration tests for /api/auth/* routes with comprehensive scenarios.

This file covers additional auth endpoint scenarios beyond the basic tests
in test_auth_routes.py, including:
- Individual field updates (preferred_language, tax_regime, country, filing_status, annual_income)
- Multiple field updates in a single request
- Empty update requests
- Complete response field validation
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

from tests.conftest import MOCK_USER_ID


@pytest.mark.asyncio
async def test_update_preferred_language(async_client: AsyncClient, mock_user):
    """PUT /api/auth/me updates preferred_language to hindi."""
    updated_user = MagicMock()
    updated_user.id = MOCK_USER_ID
    updated_user.email = "test@example.com"
    updated_user.phone = "+919876543210"
    updated_user.display_name = "Test User"
    updated_user.preferred_language = "hi"
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
            json={"preferred_language": "hi"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["preferred_language"] == "hi"
    mock_repo_instance.update.assert_awaited_once_with(
        MOCK_USER_ID, preferred_language="hi"
    )


@pytest.mark.asyncio
async def test_update_tax_regime_to_new(async_client: AsyncClient, mock_user):
    """PUT /api/auth/me updates tax_regime to 'new'."""
    updated_user = MagicMock()
    updated_user.id = MOCK_USER_ID
    updated_user.email = "test@example.com"
    updated_user.phone = "+919876543210"
    updated_user.display_name = "Test User"
    updated_user.preferred_language = "en"
    updated_user.tax_regime = "new"
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
            json={"tax_regime": "new"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["tax_regime"] == "new"
    mock_repo_instance.update.assert_awaited_once_with(
        MOCK_USER_ID, tax_regime="new"
    )


@pytest.mark.asyncio
async def test_update_country_to_us(async_client: AsyncClient, mock_user):
    """PUT /api/auth/me updates country to 'US'."""
    updated_user = MagicMock()
    updated_user.id = MOCK_USER_ID
    updated_user.email = "test@example.com"
    updated_user.phone = "+919876543210"
    updated_user.display_name = "Test User"
    updated_user.preferred_language = "en"
    updated_user.tax_regime = "old"
    updated_user.country = "US"
    updated_user.filing_status = "individual"
    updated_user.annual_income = 1200000.0

    with patch("app.api.routes.auth.UserRepository") as MockRepo:
        mock_repo_instance = MagicMock()
        mock_repo_instance.update = AsyncMock(return_value=updated_user)
        MockRepo.return_value = mock_repo_instance

        resp = await async_client.put(
            "/api/auth/me",
            headers={"Authorization": "Bearer token"},
            json={"country": "US"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["country"] == "US"
    mock_repo_instance.update.assert_awaited_once_with(
        MOCK_USER_ID, country="US"
    )


@pytest.mark.asyncio
async def test_update_filing_status(async_client: AsyncClient, mock_user):
    """PUT /api/auth/me updates filing_status to 'married_joint'."""
    updated_user = MagicMock()
    updated_user.id = MOCK_USER_ID
    updated_user.email = "test@example.com"
    updated_user.phone = "+919876543210"
    updated_user.display_name = "Test User"
    updated_user.preferred_language = "en"
    updated_user.tax_regime = "old"
    updated_user.country = "IN"
    updated_user.filing_status = "married_joint"
    updated_user.annual_income = 1200000.0

    with patch("app.api.routes.auth.UserRepository") as MockRepo:
        mock_repo_instance = MagicMock()
        mock_repo_instance.update = AsyncMock(return_value=updated_user)
        MockRepo.return_value = mock_repo_instance

        resp = await async_client.put(
            "/api/auth/me",
            headers={"Authorization": "Bearer token"},
            json={"filing_status": "married_joint"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["filing_status"] == "married_joint"
    mock_repo_instance.update.assert_awaited_once_with(
        MOCK_USER_ID, filing_status="married_joint"
    )


@pytest.mark.asyncio
async def test_update_annual_income(async_client: AsyncClient, mock_user):
    """PUT /api/auth/me updates annual_income to 2500000.0."""
    updated_user = MagicMock()
    updated_user.id = MOCK_USER_ID
    updated_user.email = "test@example.com"
    updated_user.phone = "+919876543210"
    updated_user.display_name = "Test User"
    updated_user.preferred_language = "en"
    updated_user.tax_regime = "old"
    updated_user.country = "IN"
    updated_user.filing_status = "individual"
    updated_user.annual_income = 2500000.0

    with patch("app.api.routes.auth.UserRepository") as MockRepo:
        mock_repo_instance = MagicMock()
        mock_repo_instance.update = AsyncMock(return_value=updated_user)
        MockRepo.return_value = mock_repo_instance

        resp = await async_client.put(
            "/api/auth/me",
            headers={"Authorization": "Bearer token"},
            json={"annual_income": 2500000.0},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["annual_income"] == 2500000.0
    mock_repo_instance.update.assert_awaited_once_with(
        MOCK_USER_ID, annual_income=2500000.0
    )


@pytest.mark.asyncio
async def test_update_profile_empty_body(async_client: AsyncClient, mock_user):
    """PUT /api/auth/me with empty body returns 200 with unchanged user."""
    resp = await async_client.put(
        "/api/auth/me",
        headers={"Authorization": "Bearer token"},
        json={},
    )

    assert resp.status_code == 200
    data = resp.json()
    # Should return the original mock_user data unchanged
    assert data["id"] == str(MOCK_USER_ID)
    assert data["email"] == "test@example.com"
    assert data["display_name"] == "Test User"
    assert data["preferred_language"] == "en"
    assert data["tax_regime"] == "old"


@pytest.mark.asyncio
async def test_get_profile_includes_all_fields(async_client: AsyncClient, mock_user):
    """GET /api/auth/me includes country and filing_status fields."""
    resp = await async_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer token"},
    )

    assert resp.status_code == 200
    data = resp.json()

    # Verify all expected fields are present
    assert data["id"] == str(MOCK_USER_ID)
    assert data["email"] == "test@example.com"
    assert data["phone"] == "+919876543210"
    assert data["display_name"] == "Test User"
    assert data["preferred_language"] == "en"
    assert data["tax_regime"] == "old"
    assert data["country"] == "IN"
    assert data["filing_status"] == "individual"
    assert data["annual_income"] == 1200000.0


@pytest.mark.asyncio
async def test_update_multiple_fields(async_client: AsyncClient, mock_user):
    """PUT /api/auth/me with multiple fields updates all of them."""
    updated_user = MagicMock()
    updated_user.id = MOCK_USER_ID
    updated_user.email = "test@example.com"
    updated_user.phone = "+919876543210"
    updated_user.display_name = "Updated Name"
    updated_user.preferred_language = "te"
    updated_user.tax_regime = "new"
    updated_user.country = "US"
    updated_user.filing_status = "married_separate"
    updated_user.annual_income = 3000000.0

    with patch("app.api.routes.auth.UserRepository") as MockRepo:
        mock_repo_instance = MagicMock()
        mock_repo_instance.update = AsyncMock(return_value=updated_user)
        MockRepo.return_value = mock_repo_instance

        resp = await async_client.put(
            "/api/auth/me",
            headers={"Authorization": "Bearer token"},
            json={
                "display_name": "Updated Name",
                "preferred_language": "te",
                "tax_regime": "new",
                "country": "US",
                "filing_status": "married_separate",
                "annual_income": 3000000.0,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Updated Name"
    assert data["preferred_language"] == "te"
    assert data["tax_regime"] == "new"
    assert data["country"] == "US"
    assert data["filing_status"] == "married_separate"
    assert data["annual_income"] == 3000000.0

    # Verify the repository was called with all fields
    mock_repo_instance.update.assert_awaited_once_with(
        MOCK_USER_ID,
        display_name="Updated Name",
        preferred_language="te",
        tax_regime="new",
        country="US",
        filing_status="married_separate",
        annual_income=3000000.0,
    )


@pytest.mark.asyncio
async def test_verify_token_response_includes_all_fields(async_client: AsyncClient, mock_user):
    """POST /api/auth/verify-token response includes all expected user fields."""
    resp = await async_client.post(
        "/api/auth/verify-token",
        headers={"Authorization": "Bearer token"},
    )

    assert resp.status_code == 200
    data = resp.json()

    # Verify all expected fields are present
    assert data["id"] == str(MOCK_USER_ID)
    assert data["email"] == "test@example.com"
    assert data["phone"] == "+919876543210"
    assert data["display_name"] == "Test User"
    assert data["preferred_language"] == "en"
    assert data["tax_regime"] == "old"
    assert data["country"] == "IN"
    assert data["filing_status"] == "individual"
    assert data["annual_income"] == 1200000.0
