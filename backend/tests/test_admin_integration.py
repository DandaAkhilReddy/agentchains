"""End-to-end integration tests for /api/admin/* routes.

Tests the full route chain including admin auth check with mocked
repositories and DB session. Covers:
- Admin stats endpoint
- Admin user listing
- API usage summary
- Review listing with filters
- Review status updates
- Review admin responses (feedback)
- Review deletion
- Non-admin 403 rejection on all endpoints
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db
from app.db.models import User, Review
from tests.conftest import MOCK_USER_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ADMIN_USER_ID = MOCK_USER_ID
NON_ADMIN_USER_ID = uuid.UUID("00000000-0000-4000-a000-000000000099")
REVIEW_ID = uuid.UUID("00000000-0000-4000-a000-000000000050")
NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_admin_user() -> MagicMock:
    """Create a mock admin user whose email is in ADMIN_EMAILS."""
    user = MagicMock(spec=User)
    user.id = ADMIN_USER_ID
    user.firebase_uid = "firebase_admin_123"
    user.email = "admin@test.com"  # in ADMIN_EMAILS
    user.phone = "+919876543210"
    user.display_name = "Admin User"
    user.preferred_language = "en"
    user.tax_regime = "old"
    user.country = "IN"
    user.filing_status = "individual"
    user.annual_income = 1200000.0
    user.created_at = NOW
    user.updated_at = NOW
    return user


def _make_non_admin_user() -> MagicMock:
    """Create a mock user whose email is NOT in ADMIN_EMAILS."""
    user = MagicMock(spec=User)
    user.id = NON_ADMIN_USER_ID
    user.firebase_uid = "firebase_regular_456"
    user.email = "regular@example.com"  # not in ADMIN_EMAILS
    user.phone = "+919999999999"
    user.display_name = "Regular User"
    user.preferred_language = "en"
    user.tax_regime = "old"
    user.country = "IN"
    user.filing_status = "individual"
    user.annual_income = 600000.0
    user.created_at = NOW
    user.updated_at = NOW
    return user


def _make_mock_review(
    review_id: uuid.UUID = REVIEW_ID,
    review_type: str = "feedback",
    status: str = "new",
    admin_response: str | None = None,
    is_public: bool = False,
) -> MagicMock:
    """Create a mock Review ORM instance with a fake __table__.columns."""
    review = MagicMock(spec=Review)
    review.id = review_id
    review.user_id = ADMIN_USER_ID
    review.review_type = review_type
    review.rating = 4
    review.title = "Great app"
    review.content = "Really helpful for managing loans"
    review.status = status
    review.admin_response = admin_response
    review.is_public = is_public
    review.created_at = NOW
    review.updated_at = NOW

    # Mock the user relationship for user_display_name
    review.user = MagicMock()
    review.user.display_name = "Admin User"

    # Mock __table__.columns so the dict-comprehension in the route works
    columns = []
    for key in [
        "id", "user_id", "review_type", "rating", "title", "content",
        "status", "admin_response", "is_public", "created_at", "updated_at",
    ]:
        col = MagicMock()
        col.key = key
        columns.append(col)
    review.__table__ = MagicMock()
    review.__table__.columns = columns

    return review


@pytest.fixture
def admin_user() -> MagicMock:
    return _make_admin_user()


@pytest.fixture
def non_admin_user() -> MagicMock:
    return _make_non_admin_user()


@pytest.fixture
def mock_db():
    """AsyncMock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
async def admin_client(admin_user, mock_db):
    """AsyncClient wired with an admin user (email in ADMIN_EMAILS)."""
    from app.main import app

    async def _override_user():
        return admin_user

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def non_admin_client(non_admin_user, mock_db):
    """AsyncClient wired with a non-admin user (email NOT in ADMIN_EMAILS)."""
    from app.main import app

    async def _override_user():
        return non_admin_user

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ============================================================================
# 1. Admin gets stats
# ============================================================================

@pytest.mark.asyncio
async def test_admin_get_stats(admin_client: AsyncClient, mock_db):
    """GET /api/admin/stats returns user_count, loan_count, scan_count, etc."""
    # Mock db.execute to return scalar results for each count query
    # The route calls db.execute(...).scalar() multiple times
    mock_results = [
        # user_count
        _scalar_result(42),
        # new_7d
        _scalar_result(5),
        # new_30d
        _scalar_result(15),
        # total_loans
        _scalar_result(100),
        # loans_by_type (returns .all())
        _all_result([("home", 60), ("personal", 30), ("car", 10)]),
        # total_scans
        _scalar_result(200),
        # scans_today
        _scalar_result(8),
        # scans_completed
        _scalar_result(180),
        # total_reviews
        _scalar_result(25),
    ]
    mock_db.execute = AsyncMock(side_effect=mock_results)

    resp = await admin_client.get(
        "/api/admin/stats",
        headers={"Authorization": "Bearer token"},
    )

    assert resp.status_code == 200
    data = resp.json()

    assert "user_count" in data
    assert data["user_count"] == 42
    assert "total_loans" in data
    assert data["total_loans"] == 100
    assert "total_scans" in data
    assert data["total_scans"] == 200
    assert "scan_success_rate" in data
    assert data["scan_success_rate"] == 90.0  # 180/200 * 100
    assert "total_reviews" in data
    assert data["total_reviews"] == 25
    assert "loans_by_type" in data
    assert data["loans_by_type"]["home"] == 60
    assert "new_users_7d" in data
    assert data["new_users_7d"] == 5
    assert "scans_today" in data
    assert data["scans_today"] == 8


# ============================================================================
# 2. Admin lists users
# ============================================================================

@pytest.mark.asyncio
async def test_admin_list_users(admin_client: AsyncClient, mock_db):
    """GET /api/admin/users returns a list of user objects with loan_count."""
    mock_user_rows = [
        MagicMock(
            id=ADMIN_USER_ID,
            email="admin@test.com",
            display_name="Admin User",
            created_at=NOW,
            loan_count=3,
        ),
        MagicMock(
            id=NON_ADMIN_USER_ID,
            email="regular@example.com",
            display_name="Regular User",
            created_at=NOW,
            loan_count=1,
        ),
    ]
    mock_db.execute = AsyncMock(return_value=_all_result(mock_user_rows))

    resp = await admin_client.get(
        "/api/admin/users",
        headers={"Authorization": "Bearer token"},
    )

    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data, list)
    assert len(data) == 2
    # Check first user has expected fields
    assert "id" in data[0]
    assert "email" in data[0]
    assert "display_name" in data[0]
    assert "created_at" in data[0]
    assert "loan_count" in data[0]
    assert data[0]["loan_count"] == 3


# ============================================================================
# 3. Admin gets usage
# ============================================================================

@pytest.mark.asyncio
async def test_admin_get_usage(admin_client: AsyncClient, mock_db):
    """GET /api/admin/usage returns services array with costs."""
    mock_summary = {
        "total_cost": 12.50,
        "total_calls": 350,
        "by_service": {
            "openai": {
                "call_count": 200,
                "total_cost": 8.50,
                "tokens_input": 50000,
                "tokens_output": 25000,
            },
            "azure_di": {
                "call_count": 150,
                "total_cost": 4.00,
                "tokens_input": 0,
                "tokens_output": 0,
            },
        },
    }
    mock_daily = [
        {"date": "2025-05-30", "service": "openai", "call_count": 10, "total_cost": 0.50},
        {"date": "2025-05-31", "service": "openai", "call_count": 15, "total_cost": 0.75},
    ]

    with patch("app.api.routes.admin.UsageLogRepository") as MockUsageRepo:
        mock_repo = MagicMock()
        mock_repo.get_summary = AsyncMock(return_value=mock_summary)
        mock_repo.get_daily_breakdown = AsyncMock(return_value=mock_daily)
        MockUsageRepo.return_value = mock_repo

        resp = await admin_client.get(
            "/api/admin/usage",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()

    assert "total_cost_30d" in data
    assert data["total_cost_30d"] == 12.50
    assert "total_calls_30d" in data
    assert data["total_calls_30d"] == 350
    assert "by_service" in data
    assert "openai" in data["by_service"]
    assert data["by_service"]["openai"]["total_cost"] == 8.50
    assert "daily_costs" in data
    assert len(data["daily_costs"]) == 2


# ============================================================================
# 4. Admin lists reviews (filterable by type)
# ============================================================================

@pytest.mark.asyncio
async def test_admin_list_reviews_no_filter(admin_client: AsyncClient, mock_db):
    """GET /api/admin/reviews returns all reviews."""
    reviews = [
        _make_mock_review(review_type="feedback"),
        _make_mock_review(
            review_id=uuid.UUID("00000000-0000-4000-a000-000000000051"),
            review_type="testimonial",
            status="pending",
        ),
    ]

    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.list_all = AsyncMock(return_value=reviews)
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.get(
            "/api/admin/reviews",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data, list)
    assert len(data) == 2
    mock_repo.list_all.assert_awaited_once_with(review_type=None, status=None)


@pytest.mark.asyncio
async def test_admin_list_reviews_filter_by_type(admin_client: AsyncClient, mock_db):
    """GET /api/admin/reviews?review_type=feedback returns only feedback reviews."""
    feedback_review = _make_mock_review(review_type="feedback")

    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.list_all = AsyncMock(return_value=[feedback_review])
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.get(
            "/api/admin/reviews?review_type=feedback",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["review_type"] == "feedback"
    mock_repo.list_all.assert_awaited_once_with(review_type="feedback", status=None)


@pytest.mark.asyncio
async def test_admin_list_reviews_filter_by_status(admin_client: AsyncClient, mock_db):
    """GET /api/admin/reviews?status=pending returns only pending reviews."""
    pending_review = _make_mock_review(review_type="testimonial", status="pending")

    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.list_all = AsyncMock(return_value=[pending_review])
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.get(
            "/api/admin/reviews?status=pending",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 1
    assert data[0]["status"] == "pending"
    mock_repo.list_all.assert_awaited_once_with(review_type=None, status="pending")


@pytest.mark.asyncio
async def test_admin_list_reviews_filter_by_type_and_status(admin_client: AsyncClient, mock_db):
    """GET /api/admin/reviews?review_type=testimonial&status=approved works."""
    approved_testimonial = _make_mock_review(
        review_type="testimonial", status="approved", is_public=True,
    )

    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.list_all = AsyncMock(return_value=[approved_testimonial])
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.get(
            "/api/admin/reviews?review_type=testimonial&status=approved",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 1
    assert data[0]["review_type"] == "testimonial"
    assert data[0]["status"] == "approved"
    mock_repo.list_all.assert_awaited_once_with(
        review_type="testimonial", status="approved",
    )


# ============================================================================
# 5. Admin updates review status
# ============================================================================

@pytest.mark.asyncio
async def test_admin_update_review_status(admin_client: AsyncClient, mock_db):
    """PUT /api/admin/reviews/{id} changes status from pending to approved."""
    updated_review = _make_mock_review(
        review_type="testimonial", status="approved", is_public=True,
    )

    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.update_status = AsyncMock(return_value=updated_review)
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.put(
            f"/api/admin/reviews/{REVIEW_ID}",
            headers={"Authorization": "Bearer token"},
            json={"status": "approved", "is_public": True},
        )

    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "approved"
    assert data["is_public"] is True
    mock_repo.update_status.assert_awaited_once_with(
        REVIEW_ID,
        status="approved",
        admin_response=None,
        is_public=True,
    )


@pytest.mark.asyncio
async def test_admin_update_review_not_found(admin_client: AsyncClient, mock_db):
    """PUT /api/admin/reviews/{id} returns 404 when review does not exist."""
    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.update_status = AsyncMock(return_value=None)
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.put(
            f"/api/admin/reviews/{REVIEW_ID}",
            headers={"Authorization": "Bearer token"},
            json={"status": "approved"},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Review not found"


# ============================================================================
# 6. Admin responds to feedback
# ============================================================================

@pytest.mark.asyncio
async def test_admin_respond_to_feedback(admin_client: AsyncClient, mock_db):
    """PUT /api/admin/reviews/{id} with admin_response saves the response."""
    response_text = "Thank you for your feedback! We are working on this."
    updated_review = _make_mock_review(
        review_type="feedback",
        status="acknowledged",
        admin_response=response_text,
    )

    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.update_status = AsyncMock(return_value=updated_review)
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.put(
            f"/api/admin/reviews/{REVIEW_ID}",
            headers={"Authorization": "Bearer token"},
            json={
                "status": "acknowledged",
                "admin_response": response_text,
            },
        )

    assert resp.status_code == 200
    data = resp.json()

    assert data["admin_response"] == response_text
    assert data["status"] == "acknowledged"
    mock_repo.update_status.assert_awaited_once_with(
        REVIEW_ID,
        status="acknowledged",
        admin_response=response_text,
        is_public=None,
    )


# ============================================================================
# 7. Admin deletes review
# ============================================================================

@pytest.mark.asyncio
async def test_admin_delete_review(admin_client: AsyncClient, mock_db):
    """DELETE /api/admin/reviews/{id} returns 200 on success."""
    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.delete = AsyncMock(return_value=True)
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.delete(
            f"/api/admin/reviews/{REVIEW_ID}",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    assert resp.json()["detail"] == "Review deleted"
    mock_repo.delete.assert_awaited_once_with(REVIEW_ID)


@pytest.mark.asyncio
async def test_admin_delete_review_not_found(admin_client: AsyncClient, mock_db):
    """DELETE /api/admin/reviews/{id} returns 404 when review does not exist."""
    with patch("app.api.routes.admin.ReviewRepository") as MockReviewRepo:
        mock_repo = MagicMock()
        mock_repo.delete = AsyncMock(return_value=False)
        MockReviewRepo.return_value = mock_repo

        resp = await admin_client.delete(
            f"/api/admin/reviews/{REVIEW_ID}",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Review not found"


# ============================================================================
# 8. Non-admin user -> all endpoints return 403
# ============================================================================

@pytest.mark.asyncio
async def test_non_admin_stats_returns_403(non_admin_client: AsyncClient):
    """GET /api/admin/stats returns 403 for non-admin users."""
    resp = await non_admin_client.get(
        "/api/admin/stats",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


@pytest.mark.asyncio
async def test_non_admin_users_returns_403(non_admin_client: AsyncClient):
    """GET /api/admin/users returns 403 for non-admin users."""
    resp = await non_admin_client.get(
        "/api/admin/users",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


@pytest.mark.asyncio
async def test_non_admin_usage_returns_403(non_admin_client: AsyncClient):
    """GET /api/admin/usage returns 403 for non-admin users."""
    resp = await non_admin_client.get(
        "/api/admin/usage",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


@pytest.mark.asyncio
async def test_non_admin_reviews_returns_403(non_admin_client: AsyncClient):
    """GET /api/admin/reviews returns 403 for non-admin users."""
    resp = await non_admin_client.get(
        "/api/admin/reviews",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


@pytest.mark.asyncio
async def test_non_admin_update_review_returns_403(non_admin_client: AsyncClient):
    """PUT /api/admin/reviews/{id} returns 403 for non-admin users."""
    resp = await non_admin_client.put(
        f"/api/admin/reviews/{REVIEW_ID}",
        headers={"Authorization": "Bearer token"},
        json={"status": "approved"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


@pytest.mark.asyncio
async def test_non_admin_delete_review_returns_403(non_admin_client: AsyncClient):
    """DELETE /api/admin/reviews/{id} returns 403 for non-admin users."""
    resp = await non_admin_client.delete(
        f"/api/admin/reviews/{REVIEW_ID}",
        headers={"Authorization": "Bearer token"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


# ============================================================================
# Helpers
# ============================================================================

def _scalar_result(value):
    """Create a mock execute result that returns `value` on .scalar()."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _all_result(rows):
    """Create a mock execute result that returns `rows` on .all()."""
    result = MagicMock()
    result.all.return_value = rows
    return result
