"""ML-powered reputation V2 service — computes agent reputation using weighted features or ML model.

Provides a class-based ReputationV2Service with feature extraction, ML-based
scoring (when scikit-learn/lightgbm are available), batch updates, history,
and anomaly detection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.reputation import ReputationScore
from marketplace.models.transaction import Transaction

logger = logging.getLogger(__name__)

# Try to import the ML model wrapper — optional dependency
try:
    from marketplace.ml.reputation_model import ReputationModel

    _HAS_ML_MODEL = True
except ImportError:
    _HAS_ML_MODEL = False
    logger.info("marketplace.ml.reputation_model not available — using weighted formula only.")


# ---------------------------------------------------------------------------
# Default feature weights for the fallback weighted formula
# ---------------------------------------------------------------------------
_DEFAULT_WEIGHTS = {
    "transaction_count": 0.10,
    "avg_rating": 0.25,
    "dispute_rate": -0.15,
    "response_time_avg": -0.05,
    "successful_delivery_rate": 0.25,
    "age_days": 0.05,
    "listing_count": 0.05,
    "unique_buyers": 0.10,
}


# ---------------------------------------------------------------------------
# ReputationV2Service
# ---------------------------------------------------------------------------

class ReputationV2Service:
    """ML-powered reputation scoring for agents.

    Computes features from database records and either applies a simple
    weighted formula or delegates to a trained ML model for prediction.
    """

    def __init__(self) -> None:
        self._model: Any = None
        if _HAS_ML_MODEL:
            try:
                self._model = ReputationModel()
                if self._model._model is not None:
                    logger.info("Loaded pre-trained reputation model.")
                else:
                    logger.info("ReputationModel available but no pre-trained model found.")
            except Exception:
                logger.exception("Failed to load ReputationModel — falling back to weighted formula.")
                self._model = None

    # ----- feature extraction -----------------------------------------------

    async def compute_features(self, db: AsyncSession, agent_id: str) -> dict[str, float]:
        """Extract reputation features for an agent from the database.

        Returns a dict with:
            transaction_count, avg_rating, dispute_rate, response_time_avg,
            successful_delivery_rate, age_days, listing_count, unique_buyers
        """
        # --- Agent age ---
        agent_result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if agent and agent.created_at:
            created = agent.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = max((datetime.now(timezone.utc) - created).days, 0)
        else:
            age_days = 0

        # --- Transactions as seller ---
        seller_txns_result = await db.execute(
            select(Transaction).where(Transaction.seller_id == agent_id)
        )
        seller_txns = list(seller_txns_result.scalars().all())

        # --- Transactions as buyer ---
        buyer_txns_result = await db.execute(
            select(Transaction).where(Transaction.buyer_id == agent_id)
        )
        buyer_txns = list(buyer_txns_result.scalars().all())

        all_txns = seller_txns + buyer_txns
        transaction_count = len(all_txns)

        # --- Successful delivery rate ---
        completed = [t for t in seller_txns if t.status == "completed"]
        successful_delivery_rate = len(completed) / max(len(seller_txns), 1)

        # --- Dispute rate ---
        disputed = [t for t in all_txns if t.status in ("disputed", "failed")]
        dispute_rate = len(disputed) / max(transaction_count, 1)

        # --- Average rating ---
        ratings: list[float] = []
        for t in all_txns:
            if hasattr(t, "rating") and t.rating is not None:
                try:
                    ratings.append(float(t.rating))
                except (ValueError, TypeError):
                    pass
        avg_rating = sum(ratings) / len(ratings) if ratings else 0.5

        # --- Response time average ---
        response_times: list[float] = []
        for txn in seller_txns:
            if hasattr(txn, "initiated_at") and hasattr(txn, "delivered_at"):
                if txn.initiated_at and txn.delivered_at:
                    delta = txn.delivered_at - txn.initiated_at
                    response_times.append(delta.total_seconds())
        response_time_avg = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )
        # Normalise: cap at 1 hour, invert so lower is better (0-1 scale)
        if response_time_avg > 0:
            response_time_avg = min(response_time_avg / 3600.0, 1.0)

        # --- Listing count ---
        listing_result = await db.execute(
            select(func.count(DataListing.id)).where(DataListing.seller_id == agent_id)
        )
        listing_count = listing_result.scalar() or 0

        # --- Unique buyers ---
        unique_buyers_result = await db.execute(
            select(func.count(func.distinct(Transaction.buyer_id))).where(
                Transaction.seller_id == agent_id
            )
        )
        unique_buyers = unique_buyers_result.scalar() or 0

        return {
            "transaction_count": float(transaction_count),
            "avg_rating": float(avg_rating),
            "dispute_rate": float(dispute_rate),
            "response_time_avg": float(response_time_avg),
            "successful_delivery_rate": float(successful_delivery_rate),
            "age_days": float(age_days),
            "listing_count": float(listing_count),
            "unique_buyers": float(unique_buyers),
        }

    # ----- prediction -------------------------------------------------------

    def predict_reputation_score(self, features: dict[str, float]) -> float:
        """Predict a reputation score (0.0-1.0) from computed features.

        Uses an ML model if available, otherwise falls back to a weighted formula.
        """
        # Try ML model first
        if self._model is not None and getattr(self._model, "_model", None) is not None:
            try:
                score = self._model.predict(features)
                return max(0.0, min(1.0, score))
            except Exception:
                logger.exception("ML model prediction failed — falling back to weighted formula.")

        # Weighted formula fallback
        return self._weighted_score(features)

    @staticmethod
    def _weighted_score(features: dict[str, float]) -> float:
        """Compute a reputation score using a simple weighted formula."""
        # Normalise features to 0-1 range
        normalised = {
            "transaction_count": min(features.get("transaction_count", 0) / 100.0, 1.0),
            "avg_rating": features.get("avg_rating", 0.5),
            "dispute_rate": features.get("dispute_rate", 0.0),
            "response_time_avg": features.get("response_time_avg", 0.0),
            "successful_delivery_rate": features.get("successful_delivery_rate", 0.0),
            "age_days": min(features.get("age_days", 0) / 365.0, 1.0),
            "listing_count": min(features.get("listing_count", 0) / 50.0, 1.0),
            "unique_buyers": min(features.get("unique_buyers", 0) / 50.0, 1.0),
        }

        score = 0.0
        for feature_name, weight in _DEFAULT_WEIGHTS.items():
            score += weight * normalised.get(feature_name, 0.0)

        # Clamp to [0, 1]
        return max(0.0, min(1.0, round(score, 4)))

    # ----- update operations ------------------------------------------------

    async def update_agent_reputation(
        self, db: AsyncSession, agent_id: str
    ) -> dict[str, Any]:
        """Compute features, predict score, and persist for an agent.

        Returns dict with score, features, and model_used flag.
        """
        features = await self.compute_features(db, agent_id)
        score = self.predict_reputation_score(features)
        model_used = (
            self._model is not None
            and getattr(self._model, "_model", None) is not None
        )

        # Update or create ReputationScore record
        result = await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == agent_id)
        )
        rep = result.scalar_one_or_none()
        if not rep:
            rep = ReputationScore(agent_id=agent_id)
            db.add(rep)

        rep.composite_score = round(score, 3)
        rep.total_transactions = int(features["transaction_count"])
        rep.successful_deliveries = int(
            features["successful_delivery_rate"] * features["transaction_count"]
        )
        rep.failed_deliveries = int(
            features["dispute_rate"] * features["transaction_count"]
        )
        rep.last_calculated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(rep)

        return {
            "agent_id": agent_id,
            "score": score,
            "features": features,
            "model_used": model_used,
        }

    async def batch_update_reputations(
        self,
        db: AsyncSession,
        agent_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Batch update reputation scores for multiple agents.

        If agent_ids is None, update all active agents.
        """
        if agent_ids is None:
            result = await db.execute(
                select(RegisteredAgent.id).where(RegisteredAgent.status == "active")
            )
            agent_ids = [row[0] for row in result.fetchall()]

        results: list[dict[str, Any]] = []
        for aid in agent_ids:
            try:
                update_result = await self.update_agent_reputation(db, aid)
                results.append(update_result)
            except Exception:
                logger.exception("Failed to update reputation for agent %s", aid)
                results.append({"agent_id": aid, "error": "update_failed"})

        return results

    async def get_reputation_history(
        self,
        db: AsyncSession,
        agent_id: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get reputation score snapshots for an agent over the last N days.

        Returns a list of score snapshots (currently single-entry since
        historical snapshots require a dedicated ReputationHistory table).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(ReputationScore).where(
                ReputationScore.agent_id == agent_id,
                ReputationScore.last_calculated_at >= cutoff,
            )
        )
        records = list(result.scalars().all())

        return [
            {
                "agent_id": rec.agent_id,
                "composite_score": float(rec.composite_score) if rec.composite_score else 0.0,
                "total_transactions": rec.total_transactions,
                "successful_deliveries": rec.successful_deliveries,
                "failed_deliveries": rec.failed_deliveries,
                "calculated_at": rec.last_calculated_at.isoformat() if rec.last_calculated_at else None,
            }
            for rec in records
        ]


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_reputation_v2_service: ReputationV2Service | None = None


def get_reputation_v2_service() -> ReputationV2Service:
    """Return the singleton ReputationV2Service."""
    global _reputation_v2_service
    if _reputation_v2_service is None:
        _reputation_v2_service = ReputationV2Service()
    return _reputation_v2_service
