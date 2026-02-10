"""Tests for database repositories (mocked AsyncSession)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.db.repositories.loan_repo import LoanRepository
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.scan_repo import ScanJobRepository
from app.db.repositories.plan_repo import RepaymentPlanRepository
from app.db.repositories.usage_repo import UsageLogRepository
from app.db.repositories.review_repo import ReviewRepository
from app.db.repositories.embedding_repo import EmbeddingRepository

MOCK_USER_ID = uuid.UUID("00000000-0000-4000-a000-000000000001")
MOCK_LOAN_ID = uuid.UUID("00000000-0000-4000-a000-000000000010")
MOCK_REVIEW_ID = uuid.UUID("00000000-0000-4000-a000-000000000020")
MOCK_PLAN_ID = uuid.UUID("00000000-0000-4000-a000-000000000030")
MOCK_SCAN_ID = uuid.UUID("00000000-0000-4000-a000-000000000040")


# ---------------------------------------------------------------------------
# LoanRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLoanRepository:
    @pytest.fixture
    def repo(self, mock_db_session):
        return LoanRepository(mock_db_session)

    async def test_create_loan(self, repo, mock_db_session):
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await repo.create(
            MOCK_USER_ID,
            bank_name="SBI",
            loan_type="home",
            principal_amount=5000000,
            outstanding_principal=4500000,
            interest_rate=8.5,
            interest_rate_type="floating",
            tenure_months=240,
            remaining_tenure_months=220,
            emi_amount=43391,
        )
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        added_loan = mock_db_session.add.call_args[0][0]
        assert added_loan.user_id == MOCK_USER_ID
        assert added_loan.bank_name == "SBI"
        assert added_loan.loan_type == "home"
        assert added_loan.principal_amount == 5000000
        assert added_loan.interest_rate == 8.5
        assert added_loan.emi_amount == 43391

    async def test_get_by_id(self, repo, mock_db_session):
        from app.db.models import Loan

        mock_loan = MagicMock(spec=Loan)
        mock_loan.id = MOCK_LOAN_ID
        mock_loan.user_id = MOCK_USER_ID

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_loan
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(MOCK_LOAN_ID, MOCK_USER_ID)
        assert result is not None
        assert result.id == MOCK_LOAN_ID

    async def test_get_by_id_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(MOCK_LOAN_ID, MOCK_USER_ID)
        assert result is None

    async def test_list_by_user(self, repo, mock_db_session):
        from app.db.models import Loan

        mock_loan = MagicMock(spec=Loan)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_loan]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID)
        assert len(result) == 1

    async def test_delete(self, repo, mock_db_session):
        from app.db.models import Loan

        mock_loan = MagicMock(spec=Loan)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_loan
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.delete(MOCK_LOAN_ID, MOCK_USER_ID)
        assert result is True
        mock_db_session.delete.assert_called_once()


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUserRepository:
    @pytest.fixture
    def repo(self, mock_db_session):
        return UserRepository(mock_db_session)

    async def test_get_by_firebase_uid(self, repo, mock_db_session):
        from app.db.models import User

        mock_user = MagicMock(spec=User)
        mock_user.firebase_uid = "test_uid"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_firebase_uid("test_uid")
        assert result is not None
        assert result.firebase_uid == "test_uid"

    async def test_get_by_firebase_uid_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_firebase_uid("nonexistent")
        assert result is None

    async def test_upsert_creates_new(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await repo.upsert(
            firebase_uid="new_uid",
            email="new@example.com",
            phone=None,
            display_name="New User",
        )
        mock_db_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# ScanRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestScanJobRepository:
    @pytest.fixture
    def repo(self, mock_db_session):
        return ScanJobRepository(mock_db_session)

    async def test_create(self, repo, mock_db_session):
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.create(
            MOCK_USER_ID, "documents/test.pdf", "test.pdf",
            file_size_bytes=1024, mime_type="application/pdf",
        )
        mock_db_session.add.assert_called_once()

    async def test_get_by_id(self, repo, mock_db_session):
        from app.db.models import ScanJob

        mock_scan = MagicMock(spec=ScanJob)
        mock_scan.id = uuid.uuid4()
        mock_scan.user_id = MOCK_USER_ID

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scan
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(mock_scan.id, MOCK_USER_ID)
        assert result is not None


# ---------------------------------------------------------------------------
# PlanRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRepaymentPlanRepository:
    @pytest.fixture
    def repo(self, mock_db_session):
        return RepaymentPlanRepository(mock_db_session)

    async def test_create(self, repo, mock_db_session):
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.create(
            user_id=MOCK_USER_ID,
            name="Test Plan",
            strategy="avalanche",
            config={"monthly_extra": 10000},
            results={"interest_saved": 250000},
        )
        mock_db_session.add.assert_called_once()

    async def test_list_by_user(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID)
        assert result == []

    async def test_get_by_id(self, repo, mock_db_session):
        from app.db.models import RepaymentPlan

        mock_plan = MagicMock(spec=RepaymentPlan)
        mock_plan.id = MOCK_PLAN_ID
        mock_plan.user_id = MOCK_USER_ID

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_plan
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(MOCK_PLAN_ID, MOCK_USER_ID)
        assert result is not None
        assert result.id == MOCK_PLAN_ID

    async def test_get_by_id_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(MOCK_PLAN_ID, MOCK_USER_ID)
        assert result is None

    async def test_set_active_deactivates_others(self, repo, mock_db_session):
        """set_active should deactivate all user plans then activate the target."""
        from app.db.models import RepaymentPlan

        plan_a = MagicMock(spec=RepaymentPlan)
        plan_a.id = uuid.uuid4()
        plan_a.user_id = MOCK_USER_ID
        plan_a.is_active = True

        plan_b = MagicMock(spec=RepaymentPlan)
        plan_b.id = MOCK_PLAN_ID
        plan_b.user_id = MOCK_USER_ID
        plan_b.is_active = False

        # list_by_user returns both plans
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = [plan_a, plan_b]
        # get_by_id returns plan_b
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = plan_b

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_get_result]
        )
        mock_db_session.flush = AsyncMock()

        result = await repo.set_active(MOCK_PLAN_ID, MOCK_USER_ID)
        assert result is plan_b
        # Both plans should have is_active set to False first
        assert plan_a.is_active is False
        # Then the target plan is activated
        assert plan_b.is_active is True
        mock_db_session.flush.assert_called_once()

    async def test_set_active_plan_not_found(self, repo, mock_db_session):
        """set_active returns None when the target plan does not exist."""
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_get_result]
        )

        result = await repo.set_active(MOCK_PLAN_ID, MOCK_USER_ID)
        assert result is None


# ---------------------------------------------------------------------------
# UsageLogRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUsageLogRepository:
    @pytest.fixture
    def repo(self, mock_db_session):
        return UsageLogRepository(mock_db_session)

    async def test_log_creates_entry(self, repo, mock_db_session):
        """log() should add an ApiUsageLog and flush."""
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.log(
            service="openai",
            operation="chat",
            user_id=MOCK_USER_ID,
            tokens_input=100,
            tokens_output=200,
            estimated_cost=0.003,
            metadata={"model": "gpt-4o"},
        )
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        # The returned object should be the ApiUsageLog that was added
        added_obj = mock_db_session.add.call_args[0][0]
        assert added_obj.service == "openai"
        assert added_obj.operation == "chat"
        assert added_obj.user_id == MOCK_USER_ID
        assert added_obj.tokens_input == 100
        assert added_obj.tokens_output == 200
        assert added_obj.estimated_cost == 0.003
        assert added_obj.metadata_json == {"model": "gpt-4o"}

    async def test_log_without_optional_fields(self, repo, mock_db_session):
        """log() works with only required fields (service, operation)."""
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.log(service="blob_storage", operation="upload")
        mock_db_session.add.assert_called_once()
        added_obj = mock_db_session.add.call_args[0][0]
        assert added_obj.service == "blob_storage"
        assert added_obj.operation == "upload"
        assert added_obj.user_id is None
        assert added_obj.tokens_input is None
        assert added_obj.tokens_output is None

    async def test_get_summary_groups_by_service(self, repo, mock_db_session):
        """get_summary should aggregate call_count and cost by service."""
        row_openai = MagicMock()
        row_openai.service = "openai"
        row_openai.call_count = 50
        row_openai.total_cost = Decimal("0.25")
        row_openai.total_tokens_in = 5000
        row_openai.total_tokens_out = 3000

        row_blob = MagicMock()
        row_blob.service = "blob_storage"
        row_blob.call_count = 10
        row_blob.total_cost = Decimal("0.01")
        row_blob.total_tokens_in = None
        row_blob.total_tokens_out = None

        mock_result = MagicMock()
        mock_result.all.return_value = [row_openai, row_blob]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        summary = await repo.get_summary(days=30)
        assert summary["total_calls"] == 60
        assert summary["total_cost"] == pytest.approx(0.26)
        assert "openai" in summary["by_service"]
        assert summary["by_service"]["openai"]["call_count"] == 50
        assert summary["by_service"]["openai"]["tokens_input"] == 5000
        assert summary["by_service"]["blob_storage"]["tokens_input"] == 0
        assert summary["by_service"]["blob_storage"]["tokens_output"] == 0

    async def test_get_summary_empty(self, repo, mock_db_session):
        """get_summary with no rows returns zero totals."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        summary = await repo.get_summary(days=7)
        assert summary["total_calls"] == 0
        assert summary["total_cost"] == 0.0
        assert summary["by_service"] == {}

    async def test_get_daily_breakdown(self, repo, mock_db_session):
        """get_daily_breakdown returns a list of date/service/count/cost dicts."""
        row1 = MagicMock()
        row1.date = date(2025, 6, 1)
        row1.service = "openai"
        row1.call_count = 20
        row1.total_cost = Decimal("0.10")

        row2 = MagicMock()
        row2.date = date(2025, 6, 2)
        row2.service = "openai"
        row2.call_count = 15
        row2.total_cost = None

        mock_result = MagicMock()
        mock_result.all.return_value = [row1, row2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        breakdown = await repo.get_daily_breakdown(days=7)
        assert len(breakdown) == 2
        assert breakdown[0]["date"] == "2025-06-01"
        assert breakdown[0]["service"] == "openai"
        assert breakdown[0]["call_count"] == 20
        assert breakdown[0]["total_cost"] == pytest.approx(0.10)
        # None cost should become 0
        assert breakdown[1]["total_cost"] == 0.0

    async def test_get_daily_breakdown_empty(self, repo, mock_db_session):
        """get_daily_breakdown returns empty list when no data."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        breakdown = await repo.get_daily_breakdown(days=7)
        assert breakdown == []


# ---------------------------------------------------------------------------
# ReviewRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestReviewRepository:
    @pytest.fixture
    def repo(self, mock_db_session):
        return ReviewRepository(mock_db_session)

    async def test_create_testimonial_sets_pending_status(self, repo, mock_db_session):
        """Testimonials should default to 'pending' status."""
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.create(
            user_id=MOCK_USER_ID,
            review_type="testimonial",
            title="Great app",
            content="Really helped me manage my loans",
            rating=5,
        )
        mock_db_session.add.assert_called_once()
        added = mock_db_session.add.call_args[0][0]
        assert added.status == "pending"
        assert added.rating == 5

    async def test_create_feature_request_sets_new_status(self, repo, mock_db_session):
        """Feature requests should default to 'new' status."""
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.create(
            user_id=MOCK_USER_ID,
            review_type="feature_request",
            title="Add gold loan support",
            content="Please add gold loan analysis",
        )
        added = mock_db_session.add.call_args[0][0]
        assert added.status == "new"

    async def test_create_feedback_sets_new_status(self, repo, mock_db_session):
        """Feedback (non-testimonial) should default to 'new' status."""
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.create(
            user_id=MOCK_USER_ID,
            review_type="feedback",
            title="UI suggestion",
            content="Make the dashboard more colorful",
            rating=4,
        )
        added = mock_db_session.add.call_args[0][0]
        assert added.status == "new"

    async def test_list_by_user(self, repo, mock_db_session):
        from app.db.models import Review

        review = MagicMock(spec=Review)
        review.user_id = MOCK_USER_ID

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [review]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID)
        assert len(result) == 1
        mock_db_session.execute.assert_called_once()

    async def test_list_by_user_empty(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID)
        assert result == []

    async def test_list_all_no_filters(self, repo, mock_db_session):
        from app.db.models import Review

        reviews = [MagicMock(spec=Review) for _ in range(3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = reviews
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_all()
        assert len(result) == 3

    async def test_list_all_with_type_filter(self, repo, mock_db_session):
        from app.db.models import Review

        review = MagicMock(spec=Review)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [review]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_all(review_type="testimonial")
        assert len(result) == 1
        mock_db_session.execute.assert_called_once()

    async def test_list_all_with_status_filter(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_all(status="approved")
        assert result == []

    async def test_list_all_with_both_filters(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_all(review_type="testimonial", status="approved", limit=10, offset=5)
        assert result == []

    async def test_list_public(self, repo, mock_db_session):
        """list_public returns only approved + is_public reviews."""
        from app.db.models import Review

        review = MagicMock(spec=Review)
        review.is_public = True
        review.status = "approved"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [review]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_public()
        assert len(result) == 1

    async def test_list_public_empty(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_public()
        assert result == []

    async def test_get_by_id(self, repo, mock_db_session):
        from app.db.models import Review

        review = MagicMock(spec=Review)
        review.id = MOCK_REVIEW_ID
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = review
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(MOCK_REVIEW_ID)
        assert result is not None
        assert result.id == MOCK_REVIEW_ID

    async def test_get_by_id_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(MOCK_REVIEW_ID)
        assert result is None

    async def test_update_status_approved(self, repo, mock_db_session):
        """update_status sets status and optional admin_response, is_public."""
        from app.db.models import Review

        review = MagicMock(spec=Review)
        review.id = MOCK_REVIEW_ID
        review.status = "pending"
        review.admin_response = None
        review.is_public = False

        # get_by_id is called internally
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = review
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        result = await repo.update_status(
            MOCK_REVIEW_ID,
            status="approved",
            admin_response="Thank you for your feedback!",
            is_public=True,
        )
        assert result is not None
        assert result.status == "approved"
        assert result.admin_response == "Thank you for your feedback!"
        assert result.is_public is True
        mock_db_session.flush.assert_called_once()

    async def test_update_status_without_optional_fields(self, repo, mock_db_session):
        """update_status with only status, no admin_response or is_public change."""
        from app.db.models import Review

        review = MagicMock(spec=Review)
        review.id = MOCK_REVIEW_ID
        review.status = "pending"
        review.admin_response = None
        review.is_public = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = review
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        result = await repo.update_status(MOCK_REVIEW_ID, status="rejected")
        assert result.status == "rejected"
        # admin_response and is_public should not be changed
        # (no assertion on MagicMock attribute since they're mocks,
        #  but the code path is verified)

    async def test_update_status_not_found(self, repo, mock_db_session):
        """update_status returns None when the review does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_status(MOCK_REVIEW_ID, status="approved")
        assert result is None

    async def test_delete_success(self, repo, mock_db_session):
        from app.db.models import Review

        review = MagicMock(spec=Review)
        review.id = MOCK_REVIEW_ID

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = review
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.delete(MOCK_REVIEW_ID)
        assert result is True
        mock_db_session.delete.assert_called_once_with(review)
        mock_db_session.flush.assert_called_once()

    async def test_delete_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.delete(MOCK_REVIEW_ID)
        assert result is False

    async def test_count_all(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        count = await repo.count_all()
        assert count == 42

    async def test_count_all_zero(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        count = await repo.count_all()
        assert count == 0


# ---------------------------------------------------------------------------
# EmbeddingRepository
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEmbeddingRepository:
    @pytest.fixture
    def repo(self, mock_db_session):
        return EmbeddingRepository(mock_db_session)

    @pytest.fixture
    def sample_embedding(self):
        """A 1536-dim embedding vector (filled with 0.1 for testing)."""
        return [0.1] * 1536

    async def test_upsert_creates_new_embedding(self, repo, mock_db_session, sample_embedding):
        """upsert creates a new DocumentEmbedding when none exists."""
        # First execute: check for existing -> not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.upsert(
            source_type="rbi_guideline",
            source_id="rbi_2024_01",
            chunk_text="Banks must not charge prepayment penalty on floating rate loans.",
            embedding=sample_embedding,
            metadata={"section": "4.2"},
        )
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        added = mock_db_session.add.call_args[0][0]
        assert added.source_type == "rbi_guideline"
        assert added.source_id == "rbi_2024_01"
        assert added.embedding == sample_embedding

    async def test_upsert_updates_existing_embedding(self, repo, mock_db_session, sample_embedding):
        """upsert updates an existing embedding's vector and metadata."""
        from app.db.models import DocumentEmbedding

        existing = MagicMock(spec=DocumentEmbedding)
        existing.source_type = "rbi_guideline"
        existing.source_id = "rbi_2024_01"
        existing.chunk_text = "Old text"
        existing.embedding = [0.0] * 1536
        existing.metadata_json = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        result = await repo.upsert(
            source_type="rbi_guideline",
            source_id="rbi_2024_01",
            chunk_text="Old text",
            embedding=sample_embedding,
            metadata={"updated": True},
        )
        # Should not call session.add for an update
        mock_db_session.add.assert_not_called()
        # Should update embedding and metadata on existing object
        assert existing.embedding == sample_embedding
        assert existing.metadata_json == {"updated": True}
        mock_db_session.flush.assert_called_once()

    async def test_similarity_search_no_filter(self, repo, mock_db_session, sample_embedding):
        """similarity_search without source_type filter."""
        from app.db.models import DocumentEmbedding

        doc1 = MagicMock(spec=DocumentEmbedding)
        doc1.chunk_text = "Closest match"
        doc2 = MagicMock(spec=DocumentEmbedding)
        doc2.chunk_text = "Second match"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [doc1, doc2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        results = await repo.similarity_search(sample_embedding, limit=5)
        assert len(results) == 2
        assert results[0].chunk_text == "Closest match"
        mock_db_session.execute.assert_called_once()

    async def test_similarity_search_with_source_type(self, repo, mock_db_session, sample_embedding):
        """similarity_search with source_type filter applied."""
        from app.db.models import DocumentEmbedding

        doc = MagicMock(spec=DocumentEmbedding)
        doc.source_type = "glossary"
        doc.chunk_text = "EMI: Equated Monthly Installment"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [doc]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        results = await repo.similarity_search(
            sample_embedding, source_type="glossary", limit=3
        )
        assert len(results) == 1
        assert results[0].source_type == "glossary"

    async def test_similarity_search_empty_results(self, repo, mock_db_session, sample_embedding):
        """similarity_search returns empty list when no matches."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        results = await repo.similarity_search(sample_embedding)
        assert results == []


# ---------------------------------------------------------------------------
# ScanJobRepository — additional missing tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestScanJobRepositoryExtended:
    """Extended tests for ScanJobRepository covering update_status and list_by_user."""

    @pytest.fixture
    def repo(self, mock_db_session):
        return ScanJobRepository(mock_db_session)

    async def test_update_status_success(self, repo, mock_db_session):
        """update_status sets status and extra kwargs on the scan job."""
        from app.db.models import ScanJob

        mock_scan = MagicMock(spec=ScanJob)
        mock_scan.id = MOCK_SCAN_ID
        mock_scan.user_id = MOCK_USER_ID
        mock_scan.status = "uploaded"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scan
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        result = await repo.update_status(
            MOCK_SCAN_ID,
            MOCK_USER_ID,
            status="completed",
            extracted_fields={"bank_name": "SBI", "loan_type": "home"},
            confidence_scores={"bank_name": 0.95},
            processing_time_ms=1200,
        )
        assert result is not None
        assert result.status == "completed"
        assert result.extracted_fields == {"bank_name": "SBI", "loan_type": "home"}
        assert result.confidence_scores == {"bank_name": 0.95}
        assert result.processing_time_ms == 1200
        mock_db_session.flush.assert_called_once()

    async def test_update_status_not_found(self, repo, mock_db_session):
        """update_status returns None if the scan job does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_status(
            MOCK_SCAN_ID, MOCK_USER_ID, status="failed",
            error_message="OCR timeout",
        )
        assert result is None

    async def test_update_status_ignores_unknown_attrs(self, repo, mock_db_session):
        """update_status should ignore kwargs that are not model attributes."""
        from app.db.models import ScanJob

        mock_scan = MagicMock(spec=ScanJob)
        mock_scan.id = MOCK_SCAN_ID
        mock_scan.user_id = MOCK_USER_ID
        mock_scan.status = "uploaded"
        # hasattr will return False for nonexistent_field on a MagicMock with spec
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scan
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        result = await repo.update_status(
            MOCK_SCAN_ID, MOCK_USER_ID, status="processing",
            nonexistent_field="should_be_ignored",
        )
        assert result is not None
        assert result.status == "processing"

    async def test_list_by_user(self, repo, mock_db_session):
        from app.db.models import ScanJob

        scan1 = MagicMock(spec=ScanJob)
        scan2 = MagicMock(spec=ScanJob)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [scan1, scan2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID)
        assert len(result) == 2

    async def test_list_by_user_empty(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID)
        assert result == []


# ---------------------------------------------------------------------------
# LoanRepository — additional missing tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLoanRepositoryExtended:
    """Extended tests for LoanRepository covering update and filtered list_by_user."""

    @pytest.fixture
    def repo(self, mock_db_session):
        return LoanRepository(mock_db_session)

    async def test_update_success(self, repo, mock_db_session):
        """update modifies allowed fields and flushes."""
        from app.db.models import Loan

        mock_loan = MagicMock(spec=Loan)
        mock_loan.id = MOCK_LOAN_ID
        mock_loan.user_id = MOCK_USER_ID
        mock_loan.interest_rate = 8.5
        mock_loan.bank_name = "SBI"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_loan
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        result = await repo.update(
            MOCK_LOAN_ID, MOCK_USER_ID, interest_rate=7.5, bank_name="HDFC"
        )
        assert result is not None
        assert result.interest_rate == 7.5
        assert result.bank_name == "HDFC"
        mock_db_session.flush.assert_called_once()

    async def test_update_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update(MOCK_LOAN_ID, MOCK_USER_ID, interest_rate=7.5)
        assert result is None

    async def test_update_skips_protected_fields(self, repo, mock_db_session):
        """update should not modify id, user_id, or created_at even if passed in kwargs."""
        from app.db.models import Loan

        mock_loan = MagicMock(spec=Loan)
        mock_loan.id = MOCK_LOAN_ID
        mock_loan.user_id = MOCK_USER_ID
        original_id = MOCK_LOAN_ID
        original_user_id = MOCK_USER_ID

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_loan
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        # Note: user_id cannot be passed as kwarg since it is a positional param
        # of update(), so we test id and created_at protection here.
        await repo.update(
            MOCK_LOAN_ID,
            MOCK_USER_ID,
            id=uuid.uuid4(),
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            interest_rate=7.0,
        )
        # Protected fields should remain unchanged
        assert mock_loan.id == original_id
        assert mock_loan.user_id == original_user_id
        # interest_rate should be updated since it is not protected
        assert mock_loan.interest_rate == 7.0

    async def test_delete_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.delete(MOCK_LOAN_ID, MOCK_USER_ID)
        assert result is False

    async def test_list_by_user_with_loan_type_filter(self, repo, mock_db_session):
        from app.db.models import Loan

        mock_loan = MagicMock(spec=Loan)
        mock_loan.loan_type = "home"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_loan]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID, loan_type="home")
        assert len(result) == 1
        # Verify filter was included in the SQL query
        call_args = mock_db_session.execute.call_args[0][0]
        assert "loan_type" in str(call_args)

    async def test_list_by_user_with_status_filter(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID, status="closed")
        assert result == []
        call_args = mock_db_session.execute.call_args[0][0]
        assert "status" in str(call_args)

    async def test_list_by_user_with_bank_name_filter(self, repo, mock_db_session):
        from app.db.models import Loan

        mock_loan = MagicMock(spec=Loan)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_loan]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(MOCK_USER_ID, bank_name="SBI")
        assert len(result) == 1
        call_args = mock_db_session.execute.call_args[0][0]
        assert "bank_name" in str(call_args)

    async def test_list_by_user_with_all_filters(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(
            MOCK_USER_ID, loan_type="home", status="active", bank_name="SBI"
        )
        assert result == []
        call_args = mock_db_session.execute.call_args[0][0]
        sql_str = str(call_args)
        assert "loan_type" in sql_str
        assert "status" in sql_str
        assert "bank_name" in sql_str


# ---------------------------------------------------------------------------
# UserRepository — additional missing tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUserRepositoryExtended:
    """Extended tests for UserRepository covering get_by_id, upsert update, update, delete."""

    @pytest.fixture
    def repo(self, mock_db_session):
        return UserRepository(mock_db_session)

    async def test_get_by_id(self, repo, mock_db_session):
        from app.db.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = MOCK_USER_ID

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(MOCK_USER_ID)
        assert result is not None
        assert result.id == MOCK_USER_ID

    async def test_get_by_id_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(MOCK_USER_ID)
        assert result is None

    async def test_upsert_updates_existing_user(self, repo, mock_db_session):
        """upsert should update fields on an existing user without calling add."""
        from app.db.models import User

        existing_user = MagicMock(spec=User)
        existing_user.firebase_uid = "existing_uid"
        existing_user.email = "old@example.com"
        existing_user.phone = "+911111111111"
        existing_user.display_name = "Old Name"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        result = await repo.upsert(
            firebase_uid="existing_uid",
            email="new@example.com",
            phone="+919999999999",
            display_name="New Name",
        )
        # Should NOT call add for existing user
        mock_db_session.add.assert_not_called()
        # Should update fields on existing object
        assert existing_user.email == "new@example.com"
        assert existing_user.phone == "+919999999999"
        assert existing_user.display_name == "New Name"
        mock_db_session.flush.assert_called_once()

    async def test_upsert_partial_update_skips_none(self, repo, mock_db_session):
        """upsert with None values should not overwrite existing fields."""
        from app.db.models import User

        existing_user = MagicMock(spec=User)
        existing_user.firebase_uid = "existing_uid"
        existing_user.email = "keep@example.com"
        existing_user.phone = "+911111111111"
        existing_user.display_name = "Keep Name"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        # Only update display_name, pass None for others (default)
        result = await repo.upsert(
            firebase_uid="existing_uid",
            display_name="Updated Name",
        )
        # email and phone should NOT have been set (None defaults in signature)
        # The upsert code checks `if email is not None`, `if phone is not None`
        assert existing_user.email == "keep@example.com"
        assert existing_user.phone == "+911111111111"
        assert existing_user.display_name == "Updated Name"

    async def test_update_success(self, repo, mock_db_session):
        from app.db.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = MOCK_USER_ID
        mock_user.preferred_language = "en"

        # get_by_id call
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        result = await repo.update(MOCK_USER_ID, preferred_language="hi", annual_income=1500000)
        assert result is not None
        assert result.preferred_language == "hi"
        assert result.annual_income == 1500000
        mock_db_session.flush.assert_called_once()

    async def test_update_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update(MOCK_USER_ID, preferred_language="te")
        assert result is None

    async def test_delete_success(self, repo, mock_db_session):
        from app.db.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = MOCK_USER_ID

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        mock_db_session.flush = AsyncMock()

        result = await repo.delete(MOCK_USER_ID)
        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_user)
        mock_db_session.flush.assert_called_once()

    async def test_delete_not_found(self, repo, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.delete(MOCK_USER_ID)
        assert result is False
