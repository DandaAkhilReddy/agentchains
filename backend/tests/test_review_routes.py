"""Tests for /api/reviews/* routes — submit feedback, list own, public testimonials."""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.db.models import Review
from tests.conftest import MOCK_USER_ID

MOCK_REVIEW_ID = uuid.UUID("00000000-0000-4000-a000-000000000099")


def _make_column_stub(key: str):
    """Create a stub object with a .key attribute, mimicking SQLAlchemy Column."""
    col = MagicMock()
    col.key = key
    return col


# The columns that Review.__table__.columns would yield, matching the ORM model.
REVIEW_COLUMN_KEYS = [
    "id", "user_id", "review_type", "rating", "title", "content",
    "status", "admin_response", "is_public", "created_at", "updated_at",
]
REVIEW_TABLE_COLUMNS = [_make_column_stub(k) for k in REVIEW_COLUMN_KEYS]


def _make_mock_review(**overrides) -> MagicMock:
    """Create a mock Review ORM object with all required fields."""
    review = MagicMock(spec=Review)
    defaults = dict(
        id=MOCK_REVIEW_ID,
        user_id=MOCK_USER_ID,
        review_type="feedback",
        rating=4,
        title="Great app",
        content="Really helpful for managing my loans.",
        status="new",
        admin_response=None,
        is_public=False,
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(review, k, v)

    # Wire up __table__.columns so the route's dict comprehension works.
    table_mock = MagicMock()
    table_mock.columns = REVIEW_TABLE_COLUMNS
    review.__table__ = table_mock

    return review


# ---------------------------------------------------------------------------
# POST /api/reviews — submit review
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_feedback(async_client: AsyncClient):
    """POST /api/reviews with review_type=feedback creates and returns a review."""
    mock_review = _make_mock_review(
        review_type="feedback",
        rating=4,
        title="Nice feature",
        content="The optimizer is very useful.",
        status="new",
    )

    with patch("app.api.routes.reviews.ReviewRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_review)
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/reviews/",
            headers={"Authorization": "Bearer token"},
            json={
                "review_type": "feedback",
                "rating": 4,
                "title": "Nice feature",
                "content": "The optimizer is very useful.",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["review_type"] == "feedback"
    assert data["rating"] == 4
    assert data["title"] == "Nice feature"
    assert data["content"] == "The optimizer is very useful."
    assert data["user_display_name"] == "Test User"
    assert data["id"] == str(MOCK_REVIEW_ID)


@pytest.mark.asyncio
async def test_submit_testimonial(async_client: AsyncClient):
    """POST /api/reviews with review_type=testimonial creates with pending status."""
    mock_review = _make_mock_review(
        review_type="testimonial",
        rating=5,
        title="Excellent!",
        content="Saved me lakhs on my home loan.",
        status="pending",
    )

    with patch("app.api.routes.reviews.ReviewRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_review)
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/reviews/",
            headers={"Authorization": "Bearer token"},
            json={
                "review_type": "testimonial",
                "rating": 5,
                "title": "Excellent!",
                "content": "Saved me lakhs on my home loan.",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["review_type"] == "testimonial"
    assert data["rating"] == 5
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_submit_feature_request(async_client: AsyncClient):
    """POST /api/reviews with review_type=feature_request, no rating required."""
    mock_review = _make_mock_review(
        review_type="feature_request",
        rating=None,
        title="Add balance transfer comparison",
        content="Would love a tool to compare balance transfer offers from different banks.",
        status="new",
    )

    with patch("app.api.routes.reviews.ReviewRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=mock_review)
        MockRepo.return_value = mock_repo

        resp = await async_client.post(
            "/api/reviews/",
            headers={"Authorization": "Bearer token"},
            json={
                "review_type": "feature_request",
                "title": "Add balance transfer comparison",
                "content": "Would love a tool to compare balance transfer offers from different banks.",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["review_type"] == "feature_request"
    assert data["rating"] is None
    assert data["title"] == "Add balance transfer comparison"


@pytest.mark.asyncio
async def test_submit_invalid_review_type(async_client: AsyncClient):
    """POST /api/reviews with invalid review_type returns 422."""
    resp = await async_client.post(
        "/api/reviews/",
        headers={"Authorization": "Bearer token"},
        json={
            "review_type": "complaint",
            "title": "Something",
            "content": "Some content here.",
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_rating_too_high(async_client: AsyncClient):
    """POST /api/reviews with rating=6 returns 422 (max is 5)."""
    resp = await async_client.post(
        "/api/reviews/",
        headers={"Authorization": "Bearer token"},
        json={
            "review_type": "feedback",
            "rating": 6,
            "title": "Over the top",
            "content": "Rating out of range.",
        },
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_rating_too_low(async_client: AsyncClient):
    """POST /api/reviews with rating=0 returns 422 (min is 1)."""
    resp = await async_client.post(
        "/api/reviews/",
        headers={"Authorization": "Bearer token"},
        json={
            "review_type": "feedback",
            "rating": 0,
            "title": "Too low",
            "content": "Rating out of range.",
        },
    )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/reviews/mine — list own reviews
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_own_reviews(async_client: AsyncClient):
    """GET /api/reviews/mine returns the current user's reviews."""
    review_a = _make_mock_review(
        id=uuid.UUID("00000000-0000-4000-a000-000000000091"),
        review_type="feedback",
        title="First feedback",
        content="Content A",
        rating=3,
    )
    review_b = _make_mock_review(
        id=uuid.UUID("00000000-0000-4000-a000-000000000092"),
        review_type="feature_request",
        title="Second request",
        content="Content B",
        rating=None,
        status="new",
    )

    with patch("app.api.routes.reviews.ReviewRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[review_a, review_b])
        MockRepo.return_value = mock_repo

        resp = await async_client.get(
            "/api/reviews/mine",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["id"] == "00000000-0000-4000-a000-000000000091"
    assert data[0]["title"] == "First feedback"
    assert data[0]["user_display_name"] == "Test User"
    assert data[1]["id"] == "00000000-0000-4000-a000-000000000092"
    assert data[1]["review_type"] == "feature_request"


@pytest.mark.asyncio
async def test_list_own_reviews_empty(async_client: AsyncClient):
    """GET /api/reviews/mine returns empty list when user has no reviews."""
    with patch("app.api.routes.reviews.ReviewRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_by_user = AsyncMock(return_value=[])
        MockRepo.return_value = mock_repo

        resp = await async_client.get(
            "/api/reviews/mine",
            headers={"Authorization": "Bearer token"},
        )

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/reviews/public — approved public testimonials (no auth)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_reviews(async_client: AsyncClient):
    """GET /api/reviews/public returns approved public testimonials without auth."""
    mock_user_rel = MagicMock()
    mock_user_rel.display_name = "Happy Customer"

    public_review = _make_mock_review(
        id=uuid.UUID("00000000-0000-4000-a000-000000000077"),
        review_type="testimonial",
        rating=5,
        title="Amazing tool",
        content="Helped me save 2 lakhs on interest.",
        status="approved",
        is_public=True,
    )
    # The public endpoint accesses review.user.display_name
    public_review.user = mock_user_rel

    with patch("app.api.routes.reviews.ReviewRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_public = AsyncMock(return_value=[public_review])
        MockRepo.return_value = mock_repo

        resp = await async_client.get("/api/reviews/public")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["review_type"] == "testimonial"
    assert data[0]["is_public"] is True
    assert data[0]["status"] == "approved"
    assert data[0]["user_display_name"] == "Happy Customer"
    assert data[0]["rating"] == 5


@pytest.mark.asyncio
async def test_public_reviews_empty(async_client: AsyncClient):
    """GET /api/reviews/public returns empty list when no approved testimonials exist."""
    with patch("app.api.routes.reviews.ReviewRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_public = AsyncMock(return_value=[])
        MockRepo.return_value = mock_repo

        resp = await async_client.get("/api/reviews/public")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_public_reviews_user_none(async_client: AsyncClient):
    """GET /api/reviews/public handles review with no user gracefully."""
    orphan_review = _make_mock_review(
        id=uuid.UUID("00000000-0000-4000-a000-000000000078"),
        review_type="testimonial",
        rating=4,
        title="Good app",
        content="Works well.",
        status="approved",
        is_public=True,
    )
    # Simulate a deleted user (user relationship is None)
    orphan_review.user = None

    with patch("app.api.routes.reviews.ReviewRepository") as MockRepo:
        mock_repo = MagicMock()
        mock_repo.list_public = AsyncMock(return_value=[orphan_review])
        MockRepo.return_value = mock_repo

        resp = await async_client.get("/api/reviews/public")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["user_display_name"] is None
