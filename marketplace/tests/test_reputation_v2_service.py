"""Unit tests for reputation_v2_service — ML-powered reputation scoring with
feature extraction, weighted formula, ML model fallback, batch updates,
and history retrieval.

30 tests across 6 describe blocks:

1. _weighted_score (normalisation, edge cases, weight application)
2. predict_reputation_score (ML model vs fallback, clamping)
3. compute_features (no data, with transactions, ratings, response times)
4. update_agent_reputation (create new, update existing, persist scores)
5. batch_update_reputations (all agents, subset, error handling)
6. get_reputation_history (within window, outside window, empty)

Uses the real service against an in-memory SQLite DB via shared conftest fixtures.
ML model is mocked since it's an optional dependency.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.reputation import ReputationScore
from marketplace.models.transaction import Transaction
from marketplace.services.reputation_v2_service import (
    ReputationV2Service,
    _DEFAULT_WEIGHTS,
    get_reputation_v2_service,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


async def _create_agent(
    db: AsyncSession,
    *,
    status: str = "active",
    created_at: datetime | None = None,
) -> RegisteredAgent:
    agent = RegisteredAgent(
        id=_id(),
        name=f"rep-agent-{_id()[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test",
        status=status,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _create_listing(
    db: AsyncSession,
    seller_id: str,
) -> DataListing:
    listing = DataListing(
        id=_id(),
        seller_id=seller_id,
        title=f"Test Listing {_id()[:6]}",
        category="web_search",
        content_hash=f"sha256:{'ab' * 32}",
        content_size=100,
        price_usdc=Decimal("1.0"),
        status="active",
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing


async def _create_transaction(
    db: AsyncSession,
    buyer_id: str,
    seller_id: str,
    listing_id: str,
    *,
    status: str = "completed",
    rating: float | None = None,
    initiated_at: datetime | None = None,
    delivered_at: datetime | None = None,
) -> Transaction:
    tx = Transaction(
        id=_id(),
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=Decimal("1.0"),
        status=status,
        content_hash=f"sha256:{'cd' * 32}",
        initiated_at=initiated_at or datetime.now(timezone.utc),
        delivered_at=delivered_at,
    )
    if status == "completed":
        tx.completed_at = datetime.now(timezone.utc)
    if rating is not None:
        tx.rating = rating
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


# ===================================================================
# 1. _weighted_score (6 tests)
# ===================================================================

class TestWeightedScore:
    """Static _weighted_score method computes normalised weighted reputation."""

    def test_all_zeros_returns_zero(self) -> None:
        features = {k: 0.0 for k in _DEFAULT_WEIGHTS}
        score = ReputationV2Service._weighted_score(features)
        assert score == 0.0

    def test_perfect_features_positive_score(self) -> None:
        features = {
            "transaction_count": 100.0,
            "avg_rating": 1.0,
            "dispute_rate": 0.0,
            "response_time_avg": 0.0,
            "successful_delivery_rate": 1.0,
            "age_days": 365.0,
            "listing_count": 50.0,
            "unique_buyers": 50.0,
        }
        score = ReputationV2Service._weighted_score(features)
        assert 0.7 <= score <= 1.0

    def test_high_dispute_rate_lowers_score(self) -> None:
        base = {
            "transaction_count": 50.0,
            "avg_rating": 0.8,
            "dispute_rate": 0.0,
            "response_time_avg": 0.0,
            "successful_delivery_rate": 0.9,
            "age_days": 180.0,
            "listing_count": 10.0,
            "unique_buyers": 10.0,
        }
        good_score = ReputationV2Service._weighted_score(base)

        bad = dict(base)
        bad["dispute_rate"] = 0.8
        bad_score = ReputationV2Service._weighted_score(bad)

        assert bad_score < good_score

    def test_clamped_to_zero_one(self) -> None:
        # Extreme negative weights should still clamp
        features = {
            "transaction_count": 0.0,
            "avg_rating": 0.0,
            "dispute_rate": 1.0,
            "response_time_avg": 1.0,
            "successful_delivery_rate": 0.0,
            "age_days": 0.0,
            "listing_count": 0.0,
            "unique_buyers": 0.0,
        }
        score = ReputationV2Service._weighted_score(features)
        assert 0.0 <= score <= 1.0

    def test_transaction_count_normalises_at_100(self) -> None:
        features_50 = {k: 0.0 for k in _DEFAULT_WEIGHTS}
        features_50["transaction_count"] = 50.0

        features_200 = dict(features_50)
        features_200["transaction_count"] = 200.0

        score_50 = ReputationV2Service._weighted_score(features_50)
        score_200 = ReputationV2Service._weighted_score(features_200)
        # 200 transactions normalises to 1.0 (capped at 100), same as 100+
        # But 50 normalises to 0.5, so score_50 < score_200
        assert score_50 < score_200

    def test_missing_features_use_defaults(self) -> None:
        # Partial features dict — should not crash
        score = ReputationV2Service._weighted_score({"avg_rating": 0.9})
        assert 0.0 <= score <= 1.0


# ===================================================================
# 2. predict_reputation_score (3 tests)
# ===================================================================

class TestPredictReputationScore:
    """predict_reputation_score delegates to ML model or falls back to weighted."""

    def test_no_model_uses_weighted(self) -> None:
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        features = {
            "transaction_count": 50.0,
            "avg_rating": 0.8,
            "dispute_rate": 0.1,
            "response_time_avg": 0.2,
            "successful_delivery_rate": 0.9,
            "age_days": 100.0,
            "listing_count": 5.0,
            "unique_buyers": 5.0,
        }
        score = svc.predict_reputation_score(features)
        expected = ReputationV2Service._weighted_score(features)
        assert score == expected

    def test_ml_model_prediction_used_when_available(self) -> None:
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()  # non-None -> model is loaded
        mock_model.predict.return_value = 0.85
        svc._model = mock_model

        features = {k: 0.5 for k in _DEFAULT_WEIGHTS}
        score = svc.predict_reputation_score(features)
        assert score == 0.85
        mock_model.predict.assert_called_once_with(features)

    def test_ml_model_failure_falls_back_to_weighted(self) -> None:
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("model crashed")
        svc._model = mock_model

        features = {k: 0.5 for k in _DEFAULT_WEIGHTS}
        score = svc.predict_reputation_score(features)
        expected = ReputationV2Service._weighted_score(features)
        assert score == expected

    def test_score_clamped_when_model_returns_above_one(self) -> None:
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()
        mock_model.predict.return_value = 1.5  # above 1.0
        svc._model = mock_model

        features = {k: 0.5 for k in _DEFAULT_WEIGHTS}
        score = svc.predict_reputation_score(features)
        assert score == 1.0

    def test_score_clamped_when_model_returns_negative(self) -> None:
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()
        mock_model.predict.return_value = -0.3
        svc._model = mock_model

        features = {k: 0.5 for k in _DEFAULT_WEIGHTS}
        score = svc.predict_reputation_score(features)
        assert score == 0.0


# ===================================================================
# 3. compute_features (5 tests)
# ===================================================================

class TestComputeFeatures:
    """compute_features extracts reputation features from DB records."""

    async def test_no_data_returns_defaults(self, db: AsyncSession) -> None:
        agent = await _create_agent(db)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        features = await svc.compute_features(db, agent.id)
        assert features["transaction_count"] == 0.0
        assert features["avg_rating"] == 0.5  # default
        assert features["dispute_rate"] == 0.0
        assert features["successful_delivery_rate"] == 0.0
        assert features["listing_count"] == 0.0
        assert features["unique_buyers"] == 0.0

    async def test_age_days_computed_from_created_at(
        self, db: AsyncSession
    ) -> None:
        old_date = datetime.now(timezone.utc) - timedelta(days=30)
        agent = await _create_agent(db, created_at=old_date)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        features = await svc.compute_features(db, agent.id)
        assert features["age_days"] >= 29  # allow slight timing slack

    async def test_transaction_counts_include_buyer_and_seller(
        self, db: AsyncSession
    ) -> None:
        seller = await _create_agent(db)
        buyer = await _create_agent(db)
        listing = await _create_listing(db, seller.id)

        # seller has 2 seller txns
        await _create_transaction(db, buyer.id, seller.id, listing.id, status="completed")
        await _create_transaction(db, buyer.id, seller.id, listing.id, status="completed")

        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None
        features = await svc.compute_features(db, seller.id)
        assert features["transaction_count"] == 2.0
        assert features["successful_delivery_rate"] == 1.0

    async def test_dispute_rate_calculation(self, db: AsyncSession) -> None:
        seller = await _create_agent(db)
        buyer = await _create_agent(db)
        listing = await _create_listing(db, seller.id)

        await _create_transaction(db, buyer.id, seller.id, listing.id, status="completed")
        await _create_transaction(db, buyer.id, seller.id, listing.id, status="disputed")
        await _create_transaction(db, buyer.id, seller.id, listing.id, status="failed")

        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None
        features = await svc.compute_features(db, seller.id)
        # 2 disputed/failed out of 3 total
        assert abs(features["dispute_rate"] - 2 / 3) < 0.01

    async def test_listing_count_and_unique_buyers(
        self, db: AsyncSession
    ) -> None:
        seller = await _create_agent(db)
        buyer1 = await _create_agent(db)
        buyer2 = await _create_agent(db)
        listing1 = await _create_listing(db, seller.id)
        listing2 = await _create_listing(db, seller.id)

        await _create_transaction(db, buyer1.id, seller.id, listing1.id)
        await _create_transaction(db, buyer2.id, seller.id, listing2.id)

        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None
        features = await svc.compute_features(db, seller.id)
        assert features["listing_count"] == 2.0
        assert features["unique_buyers"] == 2.0


# ===================================================================
# 4. update_agent_reputation (4 tests)
# ===================================================================

class TestUpdateAgentReputation:
    """update_agent_reputation computes and persists a reputation score."""

    async def test_creates_new_reputation_record(self, db: AsyncSession) -> None:
        agent = await _create_agent(db)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        result = await svc.update_agent_reputation(db, agent.id)
        assert result["agent_id"] == agent.id
        assert 0.0 <= result["score"] <= 1.0
        assert result["model_used"] is False

        # Verify persisted
        rep = (
            await db.execute(
                select(ReputationScore).where(
                    ReputationScore.agent_id == agent.id
                )
            )
        ).scalar_one()
        assert rep is not None
        assert float(rep.composite_score) == round(result["score"], 3)

    async def test_updates_existing_reputation_record(
        self, db: AsyncSession
    ) -> None:
        agent = await _create_agent(db)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        # First update
        r1 = await svc.update_agent_reputation(db, agent.id)

        # Add some transactions to change the score
        buyer = await _create_agent(db)
        listing = await _create_listing(db, agent.id)
        await _create_transaction(db, buyer.id, agent.id, listing.id, status="completed")

        # Second update
        r2 = await svc.update_agent_reputation(db, agent.id)
        assert r2["features"]["transaction_count"] > r1["features"]["transaction_count"]

        # Only one ReputationScore record
        count = (
            await db.execute(
                select(ReputationScore).where(
                    ReputationScore.agent_id == agent.id
                )
            )
        ).scalars().all()
        assert len(count) == 1

    async def test_features_returned_in_result(self, db: AsyncSession) -> None:
        agent = await _create_agent(db)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        result = await svc.update_agent_reputation(db, agent.id)
        assert "features" in result
        assert set(result["features"].keys()) == set(_DEFAULT_WEIGHTS.keys())

    async def test_model_used_flag_true_when_ml_model_active(
        self, db: AsyncSession
    ) -> None:
        agent = await _create_agent(db)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()
        mock_model.predict.return_value = 0.75
        svc._model = mock_model

        result = await svc.update_agent_reputation(db, agent.id)
        assert result["model_used"] is True


# ===================================================================
# 5. batch_update_reputations (4 tests)
# ===================================================================

class TestBatchUpdateReputations:
    """batch_update_reputations updates multiple agents."""

    async def test_explicit_agent_ids(self, db: AsyncSession) -> None:
        agent1 = await _create_agent(db)
        agent2 = await _create_agent(db)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        results = await svc.batch_update_reputations(
            db, agent_ids=[agent1.id, agent2.id]
        )
        assert len(results) == 2
        ids = {r["agent_id"] for r in results}
        assert ids == {agent1.id, agent2.id}

    async def test_none_agent_ids_updates_all_active(
        self, db: AsyncSession
    ) -> None:
        agent1 = await _create_agent(db, status="active")
        agent2 = await _create_agent(db, status="active")
        _inactive = await _create_agent(db, status="suspended")

        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        results = await svc.batch_update_reputations(db, agent_ids=None)
        result_ids = {r["agent_id"] for r in results}
        assert agent1.id in result_ids
        assert agent2.id in result_ids
        assert _inactive.id not in result_ids

    async def test_error_in_one_agent_does_not_block_others(
        self, db: AsyncSession
    ) -> None:
        agent1 = await _create_agent(db)
        agent2 = await _create_agent(db)

        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        original_update = svc.update_agent_reputation
        call_count = 0

        async def _patched_update(db_session: AsyncSession, agent_id: str):
            nonlocal call_count
            call_count += 1
            if agent_id == agent1.id:
                raise RuntimeError("simulated failure")
            return await original_update(db_session, agent_id)

        svc.update_agent_reputation = _patched_update

        results = await svc.batch_update_reputations(
            db, agent_ids=[agent1.id, agent2.id]
        )
        assert len(results) == 2
        error_result = next(r for r in results if r["agent_id"] == agent1.id)
        assert error_result["error"] == "update_failed"

        success_result = next(r for r in results if r["agent_id"] == agent2.id)
        assert "score" in success_result

    async def test_empty_agent_ids_returns_empty(self, db: AsyncSession) -> None:
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        results = await svc.batch_update_reputations(db, agent_ids=[])
        assert results == []


# ===================================================================
# 6. get_reputation_history (3 tests)
# ===================================================================

class TestGetReputationHistory:
    """get_reputation_history returns score snapshots within a time window."""

    async def test_returns_recent_record(self, db: AsyncSession) -> None:
        agent = await _create_agent(db)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        # Create a reputation record by updating
        await svc.update_agent_reputation(db, agent.id)

        history = await svc.get_reputation_history(db, agent.id, days=30)
        assert len(history) == 1
        assert history[0]["agent_id"] == agent.id
        assert "composite_score" in history[0]
        assert "calculated_at" in history[0]

    async def test_outside_window_returns_empty(self, db: AsyncSession) -> None:
        agent = await _create_agent(db)

        # Manually insert an old reputation record
        old_rep = ReputationScore(
            agent_id=agent.id,
            composite_score=Decimal("0.700"),
            total_transactions=10,
            successful_deliveries=8,
            failed_deliveries=2,
            last_calculated_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.add(old_rep)
        await db.commit()

        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        history = await svc.get_reputation_history(db, agent.id, days=30)
        assert len(history) == 0

    async def test_no_records_returns_empty(self, db: AsyncSession) -> None:
        agent = await _create_agent(db)
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None

        history = await svc.get_reputation_history(db, agent.id)
        assert history == []


# ===================================================================
# 7. SINGLETON FACTORY (1 test)
# ===================================================================

class TestGetReputationV2Service:
    """get_reputation_v2_service returns a singleton instance."""

    def test_returns_same_instance(self) -> None:
        # Reset the module-level singleton for a clean test
        import marketplace.services.reputation_v2_service as mod
        mod._reputation_v2_service = None

        svc1 = get_reputation_v2_service()
        svc2 = get_reputation_v2_service()
        assert svc1 is svc2

        # Clean up
        mod._reputation_v2_service = None
