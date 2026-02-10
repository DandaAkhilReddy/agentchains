"""Tests for /api/admin/* routes — all require admin auth."""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

import pytest
from httpx import AsyncClient

from app.api.deps import get_admin_user, get_current_user
from app.db.models import Review, User
from tests.conftest import MOCK_USER_ID


MOCK_REVIEW_ID = uuid.UUID("00000000-0000-4000-a000-000000000020")
MOCK_REVIEW_ID_2 = uuid.UUID("00000000-0000-4000-a000-000000000021")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_review(**overrides) -> MagicMock:
    """Create a mock Review ORM object with all required columns."""
    review = MagicMock(spec=Review)
    defaults = dict(
        id=MOCK_REVIEW_ID,
        user_id=MOCK_USER_ID,
        review_type="feedback",
        rating=4,
        title="Great app",
        content="Really helped me manage my loans.",
        status="pending",
        admin_response=None,
        is_public=False,
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(review, k, v)

    # Mock the user relationship for user_display_name resolution
    mock_user = MagicMock()
    mock_user.display_name = "Test User"
    review.user = mock_user

    # Mock __table__.columns so the dict-comprehension in the route works
    mock_columns = []
    for key in [
        "id", "user_id", "review_type", "rating", "title", "content",
        "status", "admin_response", "is_public", "created_at", "updated_at",
    ]:
        col = MagicMock()
        col.key = key
        mock_columns.append(col)
    mock_table = MagicMock()
    mock_table.columns = mock_columns
    review.__table__ = mock_table

    return review


def _make_mock_result_row(*, user_id, email, display_name, created_at, loan_count):
    """Create a mock Row returned by the users query."""
    row = MagicMock()
    row.id = user_id
    row.email = email
    row.display_name = display_name
    row.created_at = created_at
    row.loan_count = loan_count
    return row


def _make_mock_scalar_result(value):
    """Create a mock result whose .scalar() returns value."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


# ---------------------------------------------------------------------------
# Admin client fixture (admin user override)
# ---------------------------------------------------------------------------

@pytest.fixture
async def admin_client(mock_user, mock_db_session):
    """httpx AsyncClient wired with an admin user (email in ADMIN_EMAILS)."""
    from app.main import app
    from app.db.session import get_db
    from app.api.deps import get_current_user, get_optional_user

    # Ensure the mock user has an admin email
    mock_user.email = "admin@test.com"

    async def _override_get_current_user():
        return mock_user

    async def _override_get_optional_user():
        return mock_user

    async def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_optional_user] = _override_get_optional_user
    app.dependency_overrides[get_db] = _override_get_db

    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def non_admin_client(mock_user, mock_db_session):
    """httpx AsyncClient wired with a non-admin user."""
    from app.main import app
    from app.db.session import get_db
    from app.api.deps import get_current_user, get_optional_user

    # Non-admin email
    mock_user.email = "regularuser@example.com"

    async def _override_get_current_user():
        return mock_user

    async def _override_get_optional_user():
        return mock_user

    async def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_optional_user] = _override_get_optional_user
    app.dependency_overrides[get_db] = _override_get_db

    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ===========================================================================
# GET /api/admin/stats
# ===========================================================================

class TestGetStats:

    @pytest.mark.asyncio
    async def test_stats_success(self, admin_client: AsyncClient, mock_db_session):
        """GET /api/admin/stats returns dashboard metrics."""
        # The route calls db.execute(...).scalar() multiple times and
        # db.execute(...).all() once for loan_type_rows.
        loan_type_result = MagicMock()
        loan_type_result.all.return_value = [("home", 5), ("personal", 3)]

        # Sequence of execute return values matching the route's query order:
        # 1. user_count        -> scalar() = 10
        # 2. new_7d            -> scalar() = 2
        # 3. new_30d           -> scalar() = 5
        # 4. total_loans       -> scalar() = 8
        # 5. loan_type_rows    -> .all() = [("home", 5), ("personal", 3)]
        # 6. total_scans       -> scalar() = 20
        # 7. scans_today       -> scalar() = 3
        # 8. scans_completed   -> scalar() = 18
        # 9. total_reviews     -> scalar() = 12
        mock_db_session.execute = AsyncMock(side_effect=[
            _make_mock_scalar_result(10),   # user_count
            _make_mock_scalar_result(2),    # new_7d
            _make_mock_scalar_result(5),    # new_30d
            _make_mock_scalar_result(8),    # total_loans
            loan_type_result,               # loan_type_rows
            _make_mock_scalar_result(20),   # total_scans
            _make_mock_scalar_result(3),    # scans_today
            _make_mock_scalar_result(18),   # scans_completed
            _make_mock_scalar_result(12),   # total_reviews
        ])

        resp = await admin_client.get(
            "/api/admin/stats",
            headers={"Authorization": "Bearer token"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_count"] == 10
        assert data["new_users_7d"] == 2
        assert data["new_users_30d"] == 5
        assert data["total_loans"] == 8
        assert data["loans_by_type"] == {"home": 5, "personal": 3}
        assert data["total_scans"] == 20
        assert data["scans_today"] == 3
        assert data["scan_success_rate"] == 90.0  # 18/20 * 100
        assert data["total_reviews"] == 12

    @pytest.mark.asyncio
    async def test_stats_zero_scans(self, admin_client: AsyncClient, mock_db_session):
        """scan_success_rate should be 0.0 when total_scans is 0."""
        mock_db_session.execute = AsyncMock(side_effect=[
            _make_mock_scalar_result(0),    # user_count
            _make_mock_scalar_result(0),    # new_7d
            _make_mock_scalar_result(0),    # new_30d
            _make_mock_scalar_result(0),    # total_loans
            MagicMock(all=MagicMock(return_value=[])),  # loan_type_rows
            _make_mock_scalar_result(0),    # total_scans
            _make_mock_scalar_result(0),    # scans_today
            _make_mock_scalar_result(0),    # scans_completed
            _make_mock_scalar_result(0),    # total_reviews
        ])

        resp = await admin_client.get(
            "/api/admin/stats",
            headers={"Authorization": "Bearer token"},
        )

        assert resp.status_code == 200
        assert resp.json()["scan_success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_non_admin_forbidden(self, non_admin_client: AsyncClient):
        """Non-admin user gets 403 on /api/admin/stats."""
        resp = await non_admin_client.get(
            "/api/admin/stats",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Admin access required"


# ===========================================================================
# GET /api/admin/users
# ===========================================================================

class TestListUsers:

    @pytest.mark.asyncio
    async def test_list_users_success(self, admin_client: AsyncClient, mock_db_session):
        """GET /api/admin/users returns a list of users with loan counts."""
        user_rows = [
            _make_mock_result_row(
                user_id=MOCK_USER_ID,
                email="user1@example.com",
                display_name="User One",
                created_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
                loan_count=3,
            ),
            _make_mock_result_row(
                user_id=uuid.UUID("00000000-0000-4000-a000-000000000002"),
                email="user2@example.com",
                display_name="User Two",
                created_at=datetime(2025, 2, 15, tzinfo=timezone.utc),
                loan_count=0,
            ),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = user_rows
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await admin_client.get(
            "/api/admin/users",
            headers={"Authorization": "Bearer token"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["email"] == "user1@example.com"
        assert data[0]["loan_count"] == 3
        assert data[1]["display_name"] == "User Two"
        assert data[1]["loan_count"] == 0

    @pytest.mark.asyncio
    async def test_list_users_empty(self, admin_client: AsyncClient, mock_db_session):
        """GET /api/admin/users returns empty list when no users exist."""
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await admin_client.get(
            "/api/admin/users",
            headers={"Authorization": "Bearer token"},
        )

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_users_non_admin_forbidden(self, non_admin_client: AsyncClient):
        """Non-admin user gets 403 on /api/admin/users."""
        resp = await non_admin_client.get(
            "/api/admin/users",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 403


# ===========================================================================
# GET /api/admin/usage
# ===========================================================================

class TestGetUsage:

    @pytest.mark.asyncio
    async def test_usage_success(self, admin_client: AsyncClient):
        """GET /api/admin/usage returns cost and call summaries."""
        mock_summary = {
            "total_cost": 12.50,
            "total_calls": 250,
            "by_service": {
                "openai": {"call_count": 200, "total_cost": 10.0, "tokens_input": 50000, "tokens_output": 20000},
                "doc_intel": {"call_count": 50, "total_cost": 2.5, "tokens_input": 0, "tokens_output": 0},
            },
        }
        mock_daily = [
            {"date": "2025-06-01", "service": "openai", "call_count": 10, "total_cost": 0.5},
            {"date": "2025-06-01", "service": "doc_intel", "call_count": 3, "total_cost": 0.15},
        ]

        with patch("app.api.routes.admin.UsageLogRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_summary = AsyncMock(return_value=mock_summary)
            mock_repo.get_daily_breakdown = AsyncMock(return_value=mock_daily)
            MockRepo.return_value = mock_repo

            resp = await admin_client.get(
                "/api/admin/usage",
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_30d"] == 12.50
        assert data["total_calls_30d"] == 250
        assert "openai" in data["by_service"]
        assert data["by_service"]["openai"]["call_count"] == 200
        assert len(data["daily_costs"]) == 2

    @pytest.mark.asyncio
    async def test_usage_empty(self, admin_client: AsyncClient):
        """GET /api/admin/usage returns zeros when no usage exists."""
        with patch("app.api.routes.admin.UsageLogRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_summary = AsyncMock(return_value={
                "total_cost": 0.0,
                "total_calls": 0,
                "by_service": {},
            })
            mock_repo.get_daily_breakdown = AsyncMock(return_value=[])
            MockRepo.return_value = mock_repo

            resp = await admin_client.get(
                "/api/admin/usage",
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost_30d"] == 0.0
        assert data["total_calls_30d"] == 0
        assert data["by_service"] == {}
        assert data["daily_costs"] == []

    @pytest.mark.asyncio
    async def test_usage_non_admin_forbidden(self, non_admin_client: AsyncClient):
        """Non-admin user gets 403 on /api/admin/usage."""
        resp = await non_admin_client.get(
            "/api/admin/usage",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 403


# ===========================================================================
# GET /api/admin/reviews
# ===========================================================================

class TestListReviews:

    @pytest.mark.asyncio
    async def test_list_reviews_success(self, admin_client: AsyncClient):
        """GET /api/admin/reviews returns all reviews."""
        reviews = [
            _make_mock_review(),
            _make_mock_review(
                id=MOCK_REVIEW_ID_2,
                review_type="testimonial",
                title="Loved it",
                content="Helped me save lakhs!",
                rating=5,
                status="approved",
                is_public=True,
            ),
        ]

        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_all = AsyncMock(return_value=reviews)
            MockRepo.return_value = mock_repo

            resp = await admin_client.get(
                "/api/admin/reviews",
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == str(MOCK_REVIEW_ID)
        assert data[0]["review_type"] == "feedback"
        assert data[0]["user_display_name"] == "Test User"
        assert data[1]["id"] == str(MOCK_REVIEW_ID_2)
        assert data[1]["review_type"] == "testimonial"
        assert data[1]["is_public"] is True

    @pytest.mark.asyncio
    async def test_list_reviews_filter_by_type(self, admin_client: AsyncClient):
        """GET /api/admin/reviews?review_type=testimonial filters correctly."""
        testimonial = _make_mock_review(
            review_type="testimonial",
            status="approved",
        )

        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_all = AsyncMock(return_value=[testimonial])
            MockRepo.return_value = mock_repo

            resp = await admin_client.get(
                "/api/admin/reviews?review_type=testimonial",
                headers={"Authorization": "Bearer token"},
            )

            # Verify the repo was called with the correct filter
            mock_repo.list_all.assert_called_once_with(
                review_type="testimonial", status=None,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["review_type"] == "testimonial"

    @pytest.mark.asyncio
    async def test_list_reviews_filter_by_status(self, admin_client: AsyncClient):
        """GET /api/admin/reviews?status=pending filters by status."""
        pending_review = _make_mock_review(status="pending")

        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_all = AsyncMock(return_value=[pending_review])
            MockRepo.return_value = mock_repo

            resp = await admin_client.get(
                "/api/admin/reviews?status=pending",
                headers={"Authorization": "Bearer token"},
            )

            mock_repo.list_all.assert_called_once_with(
                review_type=None, status="pending",
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_reviews_filter_by_type_and_status(self, admin_client: AsyncClient):
        """GET /api/admin/reviews?review_type=feedback&status=new filters by both."""
        review = _make_mock_review(review_type="feedback", status="new")

        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_all = AsyncMock(return_value=[review])
            MockRepo.return_value = mock_repo

            resp = await admin_client.get(
                "/api/admin/reviews?review_type=feedback&status=new",
                headers={"Authorization": "Bearer token"},
            )

            mock_repo.list_all.assert_called_once_with(
                review_type="feedback", status="new",
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_list_reviews_empty(self, admin_client: AsyncClient):
        """GET /api/admin/reviews returns empty list when no reviews exist."""
        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.list_all = AsyncMock(return_value=[])
            MockRepo.return_value = mock_repo

            resp = await admin_client.get(
                "/api/admin/reviews",
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_reviews_non_admin_forbidden(self, non_admin_client: AsyncClient):
        """Non-admin user gets 403 on /api/admin/reviews."""
        resp = await non_admin_client.get(
            "/api/admin/reviews",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 403


# ===========================================================================
# PUT /api/admin/reviews/{review_id}
# ===========================================================================

class TestUpdateReview:

    @pytest.mark.asyncio
    async def test_update_review_status(self, admin_client: AsyncClient):
        """PUT /api/admin/reviews/{id} updates the review status."""
        updated_review = _make_mock_review(status="approved", is_public=True)

        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.update_status = AsyncMock(return_value=updated_review)
            MockRepo.return_value = mock_repo

            resp = await admin_client.put(
                f"/api/admin/reviews/{MOCK_REVIEW_ID}",
                headers={"Authorization": "Bearer token"},
                json={"status": "approved", "is_public": True},
            )

            mock_repo.update_status.assert_called_once_with(
                MOCK_REVIEW_ID,
                status="approved",
                admin_response=None,
                is_public=True,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["is_public"] is True

    @pytest.mark.asyncio
    async def test_update_review_admin_response(self, admin_client: AsyncClient):
        """PUT /api/admin/reviews/{id} adds an admin response."""
        updated_review = _make_mock_review(
            status="approved",
            admin_response="Thank you for your feedback!",
        )

        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.update_status = AsyncMock(return_value=updated_review)
            MockRepo.return_value = mock_repo

            resp = await admin_client.put(
                f"/api/admin/reviews/{MOCK_REVIEW_ID}",
                headers={"Authorization": "Bearer token"},
                json={
                    "status": "approved",
                    "admin_response": "Thank you for your feedback!",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["admin_response"] == "Thank you for your feedback!"

    @pytest.mark.asyncio
    async def test_update_review_not_found(self, admin_client: AsyncClient):
        """PUT /api/admin/reviews/{id} returns 404 when review not found."""
        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.update_status = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            resp = await admin_client.put(
                f"/api/admin/reviews/{MOCK_REVIEW_ID}",
                headers={"Authorization": "Bearer token"},
                json={"status": "approved"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Review not found"

    @pytest.mark.asyncio
    async def test_update_review_non_admin_forbidden(self, non_admin_client: AsyncClient):
        """Non-admin user gets 403 on PUT /api/admin/reviews/{id}."""
        resp = await non_admin_client.put(
            f"/api/admin/reviews/{MOCK_REVIEW_ID}",
            headers={"Authorization": "Bearer token"},
            json={"status": "approved"},
        )
        assert resp.status_code == 403


# ===========================================================================
# DELETE /api/admin/reviews/{review_id}
# ===========================================================================

class TestDeleteReview:

    @pytest.mark.asyncio
    async def test_delete_review_success(self, admin_client: AsyncClient):
        """DELETE /api/admin/reviews/{id} deletes the review."""
        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.delete = AsyncMock(return_value=True)
            MockRepo.return_value = mock_repo

            resp = await admin_client.delete(
                f"/api/admin/reviews/{MOCK_REVIEW_ID}",
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 200
        assert resp.json()["detail"] == "Review deleted"

    @pytest.mark.asyncio
    async def test_delete_review_not_found(self, admin_client: AsyncClient):
        """DELETE /api/admin/reviews/{id} returns 404 when review not found."""
        with patch("app.api.routes.admin.ReviewRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.delete = AsyncMock(return_value=False)
            MockRepo.return_value = mock_repo

            resp = await admin_client.delete(
                f"/api/admin/reviews/{MOCK_REVIEW_ID}",
                headers={"Authorization": "Bearer token"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Review not found"

    @pytest.mark.asyncio
    async def test_delete_review_non_admin_forbidden(self, non_admin_client: AsyncClient):
        """Non-admin user gets 403 on DELETE /api/admin/reviews/{id}."""
        resp = await non_admin_client.delete(
            f"/api/admin/reviews/{MOCK_REVIEW_ID}",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 403
