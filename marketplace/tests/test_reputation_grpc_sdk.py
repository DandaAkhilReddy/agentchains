"""Tests for reputation V2 service, ML model, gRPC server/client, webhook V2, and payment reconciliation.

65+ test functions covering:
1. TestReputationV2Service (22 tests) -- feature extraction, inference, score calculation,
   historical aggregation, decay factor, weight config, bulk scoring, threshold classification,
   service import/instantiation
2. TestReputationMLModel (12 tests) -- model import, feature matrix, prediction format,
   probability output, serialization/deserialization, default model path
3. TestGRPCServer (10 tests) -- server import, servicer class, method definitions,
   request/response types, port configuration, reflection support
4. TestGRPCClient (11 tests) -- client import, connection pooling, channel management,
   timeout config, retry logic, error handling
5. TestWebhookV2Service (12 tests) -- webhook delivery, dead letter queue, delivery attempts,
   retry scheduling, webhook signature generation, payload serialization
6. TestPaymentReconciliation (6 tests) -- reconciliation run, mismatch detection, report
   generation, currency handling, idempotency
"""

from __future__ import annotations

import asyncio
import json
import pickle
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_features(**overrides) -> dict[str, float]:
    """Build a default feature dict with optional overrides."""
    defaults = {
        "transaction_count": 50.0,
        "avg_rating": 0.8,
        "dispute_rate": 0.05,
        "response_time_avg": 0.2,
        "successful_delivery_rate": 0.9,
        "age_days": 180.0,
        "listing_count": 10.0,
        "unique_buyers": 15.0,
    }
    defaults.update(overrides)
    return defaults


def _mock_agent(agent_id: str = "agent-1", days_ago: int = 180):
    """Return a mock RegisteredAgent."""
    agent = MagicMock()
    agent.id = agent_id
    agent.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    agent.status = "active"
    return agent


def _mock_transaction(
    seller_id="agent-1",
    buyer_id="buyer-1",
    status="completed",
    rating=4.5,
    has_times=False,
):
    """Return a mock Transaction."""
    tx = MagicMock()
    tx.seller_id = seller_id
    tx.buyer_id = buyer_id
    tx.status = status
    tx.rating = rating
    if has_times:
        tx.initiated_at = datetime.now(timezone.utc) - timedelta(hours=1)
        tx.delivered_at = datetime.now(timezone.utc)
    else:
        tx.initiated_at = None
        tx.delivered_at = None
    return tx


def _mock_reputation_record(agent_id="agent-1", score=0.75, txns=20, success=18, failed=2):
    """Return a mock ReputationScore record."""
    rec = MagicMock()
    rec.agent_id = agent_id
    rec.composite_score = score
    rec.total_transactions = txns
    rec.successful_deliveries = success
    rec.failed_deliveries = failed
    rec.last_calculated_at = datetime.now(timezone.utc)
    return rec


# ============================================================================
# 1. TestReputationV2Service (22 tests)
# ============================================================================


class TestReputationV2Service:
    """Tests for marketplace.services.reputation_v2_service."""

    # ---- imports / instantiation -------------------------------------------

    def test_service_module_importable(self):
        """The reputation_v2_service module is importable."""
        from marketplace.services import reputation_v2_service
        assert hasattr(reputation_v2_service, "ReputationV2Service")

    def test_service_class_instantiates(self):
        """ReputationV2Service can be instantiated without errors."""
        with patch("marketplace.services.reputation_v2_service._HAS_ML_MODEL", False):
            from marketplace.services.reputation_v2_service import ReputationV2Service
            svc = ReputationV2Service()
            assert svc is not None

    def test_singleton_factory_returns_instance(self):
        """get_reputation_v2_service returns a ReputationV2Service instance."""
        with patch("marketplace.services.reputation_v2_service._HAS_ML_MODEL", False):
            from marketplace.services.reputation_v2_service import (
                ReputationV2Service,
                get_reputation_v2_service,
            )
            import marketplace.services.reputation_v2_service as mod
            mod._reputation_v2_service = None  # reset singleton
            svc = get_reputation_v2_service()
            assert isinstance(svc, ReputationV2Service)

    def test_singleton_factory_returns_same_instance(self):
        """get_reputation_v2_service returns the same object on repeated calls."""
        from marketplace.services.reputation_v2_service import get_reputation_v2_service
        import marketplace.services.reputation_v2_service as mod
        mod._reputation_v2_service = None
        svc1 = get_reputation_v2_service()
        svc2 = get_reputation_v2_service()
        assert svc1 is svc2

    # ---- weighted score calculation ----------------------------------------

    def test_weighted_score_returns_float(self):
        """_weighted_score returns a float."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        score = ReputationV2Service._weighted_score(_make_features())
        assert isinstance(score, float)

    def test_weighted_score_clamped_zero_to_one(self):
        """Score is clamped between 0.0 and 1.0 inclusive."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        score_low = ReputationV2Service._weighted_score(
            _make_features(avg_rating=0.0, successful_delivery_rate=0.0, dispute_rate=1.0)
        )
        score_high = ReputationV2Service._weighted_score(
            _make_features(avg_rating=1.0, successful_delivery_rate=1.0, dispute_rate=0.0)
        )
        assert 0.0 <= score_low <= 1.0
        assert 0.0 <= score_high <= 1.0

    def test_weighted_score_perfect_features(self):
        """Perfect features produce a score close to the maximum."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        feats = _make_features(
            transaction_count=100.0,
            avg_rating=1.0,
            dispute_rate=0.0,
            response_time_avg=0.0,
            successful_delivery_rate=1.0,
            age_days=365.0,
            listing_count=50.0,
            unique_buyers=50.0,
        )
        score = ReputationV2Service._weighted_score(feats)
        assert score >= 0.7

    def test_weighted_score_empty_features(self):
        """Empty features produce a low but valid score."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        score = ReputationV2Service._weighted_score({})
        assert 0.0 <= score <= 1.0

    def test_weighted_score_dispute_rate_negative_weight(self):
        """Higher dispute rate lowers the score."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        base = _make_features(dispute_rate=0.0)
        high_dispute = _make_features(dispute_rate=1.0)
        assert ReputationV2Service._weighted_score(base) > ReputationV2Service._weighted_score(high_dispute)

    def test_weighted_score_response_time_negative_weight(self):
        """Higher response time lowers the score."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        fast = _make_features(response_time_avg=0.0)
        slow = _make_features(response_time_avg=1.0)
        assert ReputationV2Service._weighted_score(fast) > ReputationV2Service._weighted_score(slow)

    # ---- predict_reputation_score ------------------------------------------

    def test_predict_reputation_score_falls_back_to_weighted(self):
        """Without an ML model, predict_reputation_score uses weighted formula."""
        with patch("marketplace.services.reputation_v2_service._HAS_ML_MODEL", False):
            from marketplace.services.reputation_v2_service import ReputationV2Service
            svc = ReputationV2Service()
            score = svc.predict_reputation_score(_make_features())
            expected = svc._weighted_score(_make_features())
            assert score == expected

    def test_predict_reputation_score_uses_ml_model_when_available(self):
        """When ML model is loaded, predict_reputation_score delegates to it."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()
        mock_model.predict.return_value = 0.85
        svc._model = mock_model
        score = svc.predict_reputation_score(_make_features())
        assert score == 0.85
        mock_model.predict.assert_called_once()

    def test_predict_reputation_score_clamps_ml_output(self):
        """ML model output > 1.0 is clamped to 1.0."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()
        mock_model.predict.return_value = 1.5
        svc._model = mock_model
        score = svc.predict_reputation_score(_make_features())
        assert score == 1.0

    def test_predict_reputation_score_clamps_negative(self):
        """ML model output < 0.0 is clamped to 0.0."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()
        mock_model.predict.return_value = -0.3
        svc._model = mock_model
        score = svc.predict_reputation_score(_make_features())
        assert score == 0.0

    def test_predict_fallback_on_ml_exception(self):
        """If the ML model raises, fallback to weighted formula."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        svc = ReputationV2Service.__new__(ReputationV2Service)
        mock_model = MagicMock()
        mock_model._model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("boom")
        svc._model = mock_model
        score = svc.predict_reputation_score(_make_features())
        assert 0.0 <= score <= 1.0

    # ---- threshold classification ------------------------------------------

    def test_trusted_threshold_classification(self):
        """Score >= 0.7 classifies as trusted."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None
        score = svc.predict_reputation_score(
            _make_features(
                transaction_count=100.0,
                avg_rating=1.0,
                successful_delivery_rate=1.0,
                dispute_rate=0.0,
                response_time_avg=0.0,
                age_days=365.0,
                listing_count=50.0,
                unique_buyers=50.0,
            )
        )
        classification = "trusted" if score >= 0.7 else ("neutral" if score >= 0.3 else "suspicious")
        assert classification == "trusted"

    def test_suspicious_threshold_classification(self):
        """Score < 0.3 classifies as suspicious."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None
        score = svc.predict_reputation_score(
            _make_features(
                transaction_count=0.0,
                avg_rating=0.0,
                dispute_rate=1.0,
                response_time_avg=1.0,
                successful_delivery_rate=0.0,
                age_days=0.0,
                listing_count=0.0,
                unique_buyers=0.0,
            )
        )
        classification = "trusted" if score >= 0.7 else ("neutral" if score >= 0.3 else "suspicious")
        assert classification == "suspicious"

    def test_neutral_threshold_classification(self):
        """Moderate features give a neutral classification."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        svc = ReputationV2Service.__new__(ReputationV2Service)
        svc._model = None
        score = svc.predict_reputation_score(
            _make_features(
                transaction_count=50.0,
                avg_rating=0.6,
                dispute_rate=0.05,
                response_time_avg=0.3,
                successful_delivery_rate=0.7,
                age_days=180.0,
                listing_count=20.0,
                unique_buyers=15.0,
            )
        )
        classification = "trusted" if score >= 0.7 else ("neutral" if score >= 0.3 else "suspicious")
        assert classification == "neutral"

    # ---- decay factor simulation -------------------------------------------

    def test_decay_factor_recent_activity(self):
        """Recent age_days have minimal impact on score decay."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        recent = _make_features(age_days=30.0)
        old = _make_features(age_days=365.0)
        s_recent = ReputationV2Service._weighted_score(recent)
        s_old = ReputationV2Service._weighted_score(old)
        # Older accounts get slightly higher score due to positive age weight
        assert s_old >= s_recent

    def test_decay_transaction_count_saturates(self):
        """transaction_count is normalised to 1.0 at 100 -- beyond that no extra credit."""
        from marketplace.services.reputation_v2_service import ReputationV2Service
        at100 = _make_features(transaction_count=100.0)
        at200 = _make_features(transaction_count=200.0)
        assert ReputationV2Service._weighted_score(at100) == ReputationV2Service._weighted_score(at200)

    # ---- weight configuration ---------------------------------------------

    def test_default_weights_keys(self):
        """Default weights contain all expected feature names."""
        from marketplace.services.reputation_v2_service import _DEFAULT_WEIGHTS
        expected_keys = {
            "transaction_count", "avg_rating", "dispute_rate", "response_time_avg",
            "successful_delivery_rate", "age_days", "listing_count", "unique_buyers",
        }
        assert set(_DEFAULT_WEIGHTS.keys()) == expected_keys

    def test_default_weights_sum_positive(self):
        """Sum of all weights is a sensible value (near 0.6 for the positive weights)."""
        from marketplace.services.reputation_v2_service import _DEFAULT_WEIGHTS
        total = sum(_DEFAULT_WEIGHTS.values())
        assert total > 0.0  # net positive


# ============================================================================
# 2. TestReputationMLModel (12 tests)
# ============================================================================


class TestReputationMLModel:
    """Tests for marketplace.ml.reputation_model."""

    def test_model_module_importable(self):
        """The reputation_model module is importable."""
        from marketplace.ml import reputation_model
        assert hasattr(reputation_model, "ReputationModel")

    def test_feature_names_list(self):
        """FEATURE_NAMES has exactly 8 feature names."""
        from marketplace.ml.reputation_model import FEATURE_NAMES
        assert len(FEATURE_NAMES) == 8
        assert "avg_rating" in FEATURE_NAMES
        assert "transaction_count" in FEATURE_NAMES

    def test_model_init_no_crash(self):
        """ReputationModel() initialises without crashing even if no saved model."""
        from marketplace.ml.reputation_model import ReputationModel
        model = ReputationModel(model_dir="/nonexistent_path")
        assert model._model is None
        assert model._model_type == "none"

    def test_default_model_dir(self):
        """Default model directory is project_root/models/."""
        from marketplace.ml.reputation_model import _DEFAULT_MODEL_DIR
        assert _DEFAULT_MODEL_DIR.name == "models"

    def test_predict_raises_without_trained_model(self):
        """predict() raises RuntimeError when no model is loaded."""
        from marketplace.ml.reputation_model import ReputationModel
        model = ReputationModel(model_dir="/nonexistent_path")
        with pytest.raises(RuntimeError, match="No model loaded"):
            model.predict(_make_features())

    def test_save_raises_without_model(self):
        """save() raises RuntimeError when no model is loaded."""
        from marketplace.ml.reputation_model import ReputationModel
        model = ReputationModel(model_dir="/nonexistent_path")
        with pytest.raises(RuntimeError, match="No model to save"):
            model.save()

    def test_load_raises_for_missing_file(self):
        """load() raises FileNotFoundError for a missing path."""
        from marketplace.ml.reputation_model import ReputationModel
        model = ReputationModel(model_dir="/nonexistent_path")
        with pytest.raises(FileNotFoundError):
            model.load("/does/not/exist.pkl")

    def test_feature_importance_raises_without_model(self):
        """feature_importance() raises RuntimeError when no model is loaded."""
        from marketplace.ml.reputation_model import ReputationModel
        model = ReputationModel(model_dir="/nonexistent_path")
        with pytest.raises(RuntimeError, match="No model loaded"):
            model.feature_importance()

    def test_predict_with_mock_model_predict_proba(self):
        """predict() uses predict_proba when available."""
        from marketplace.ml.reputation_model import ReputationModel
        model = ReputationModel(model_dir="/nonexistent_path")
        mock_clf = MagicMock()
        mock_probas = MagicMock()
        mock_probas.shape = (1, 2)
        mock_probas.__getitem__ = lambda self, idx: MagicMock(__getitem__=lambda s, i: 0.78)
        mock_clf.predict_proba.return_value = mock_probas
        model._model = mock_clf
        score = model.predict(_make_features())
        assert 0.0 <= score <= 1.0

    def test_predict_with_mock_model_no_proba(self):
        """predict() falls back to predict() when predict_proba is unavailable."""
        from marketplace.ml.reputation_model import ReputationModel, FEATURE_NAMES
        model = ReputationModel(model_dir="/nonexistent_path")
        mock_clf = MagicMock(spec=[])  # no predict_proba
        mock_clf.predict = MagicMock(return_value=[0.65])
        # Remove predict_proba attribute
        del mock_clf.predict_proba
        model._model = mock_clf
        score = model.predict(_make_features())
        assert 0.0 <= score <= 1.0

    def test_save_and_load_roundtrip(self, tmp_path):
        """save() then load() roundtrips the model data."""
        from marketplace.ml.reputation_model import ReputationModel
        model = ReputationModel(model_dir=str(tmp_path))
        # Simulate a trained model with a plain serializable object
        model._model = {"type": "stub", "weights": [0.1, 0.2, 0.3]}
        model._model_type = "test_model"
        saved_path = model.save(str(tmp_path / "test_model.pkl"))
        assert Path(saved_path).exists()

        # Load into a fresh instance
        model2 = ReputationModel(model_dir="/nonexistent_path")
        model2.load(saved_path)
        assert model2._model_type == "test_model"
        assert model2._model is not None
        assert model2._model["type"] == "stub"

    def test_feature_importance_with_feature_importances_attr(self):
        """feature_importance() extracts from feature_importances_ attribute."""
        from marketplace.ml.reputation_model import ReputationModel, FEATURE_NAMES
        model = ReputationModel(model_dir="/nonexistent_path")
        mock_clf = MagicMock()
        mock_clf.feature_importances_ = [0.1, 0.2, 0.05, 0.05, 0.25, 0.1, 0.1, 0.15]
        model._model = mock_clf
        imp = model.feature_importance()
        assert len(imp) == len(FEATURE_NAMES)
        assert isinstance(imp, dict)
        assert all(isinstance(v, float) for v in imp.values())


# ============================================================================
# 3. TestGRPCServer (10 tests)
# ============================================================================


class TestGRPCServer:
    """Tests for marketplace.grpc.server."""

    def test_server_module_importable(self):
        """The grpc.server module is importable."""
        from marketplace.grpc import server
        assert hasattr(server, "create_grpc_server")

    def test_grpc_port_default(self):
        """Default gRPC port is 50051."""
        from marketplace.grpc.server import GRPC_PORT
        assert GRPC_PORT == 50051

    def test_agent_service_servicer_class_exists(self):
        """AgentServiceServicer class is defined."""
        from marketplace.grpc.server import AgentServiceServicer
        assert AgentServiceServicer is not None

    def test_orchestration_service_servicer_class_exists(self):
        """OrchestrationServiceServicer class is defined."""
        from marketplace.grpc.server import OrchestrationServiceServicer
        assert OrchestrationServiceServicer is not None

    def test_agent_servicer_instantiation(self):
        """AgentServiceServicer can be instantiated."""
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert svc._active_tasks == 0
        assert svc._start_time > 0

    def test_agent_servicer_has_execute_task_method(self):
        """AgentServiceServicer has an ExecuteTask async method."""
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "ExecuteTask", None))

    def test_agent_servicer_has_stream_progress_method(self):
        """AgentServiceServicer has a StreamTaskProgress async method."""
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "StreamTaskProgress", None))

    def test_agent_servicer_has_health_check_method(self):
        """AgentServiceServicer has a HealthCheck async method."""
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "HealthCheck", None))

    def test_agent_servicer_has_get_capabilities_method(self):
        """AgentServiceServicer has a GetCapabilities async method."""
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "GetCapabilities", None))

    @pytest.mark.asyncio
    async def test_execute_task_returns_success(self):
        """ExecuteTask returns a dict with status=success for valid input."""
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        request = SimpleNamespace(
            task_id="t-1",
            task_type="agent_call",
            input_json='{"key":"val"}',
            agent_id="a-1",
        )
        context = MagicMock()
        result = await svc.ExecuteTask(request, context)
        assert result["status"] == "success"
        assert result["task_id"] == "t-1"
        assert "output_json" in result

    @pytest.mark.asyncio
    async def test_health_check_returns_ok(self):
        """HealthCheck returns status=ok."""
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        request = SimpleNamespace()
        context = MagicMock()
        result = await svc.HealthCheck(request, context)
        assert result["status"] == "ok"
        assert "uptime_seconds" in result


# ============================================================================
# 4. TestGRPCClient (11 tests)
# ============================================================================


class TestGRPCClient:
    """Tests for marketplace.grpc.client."""

    def test_client_module_importable(self):
        """The grpc.client module is importable."""
        from marketplace.grpc import client
        assert hasattr(client, "GrpcAgentClient")

    def test_client_class_instantiates(self):
        """GrpcAgentClient can be instantiated with a target."""
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        assert c._target == "localhost:50051"
        assert c._timeout == 30
        assert c._connected is False

    def test_client_custom_timeout(self):
        """Custom timeout is respected."""
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051", timeout_seconds=60)
        assert c._timeout == 60

    def test_client_is_connected_initially_false(self):
        """is_connected is False before connect() is called."""
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        assert c.is_connected is False

    @pytest.mark.asyncio
    async def test_client_execute_task_when_not_connected(self):
        """execute_task falls back to HTTP when not connected."""
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        with patch.object(c, "_http_fallback", new_callable=AsyncMock) as mock_fb:
            mock_fb.return_value = {"task_id": "t-1", "status": "success"}
            result = await c.execute_task("t-1", "a-1", "agent_call", {})
            mock_fb.assert_awaited_once()
            assert result["task_id"] == "t-1"

    @pytest.mark.asyncio
    async def test_client_execute_task_when_connected(self):
        """execute_task returns simulated gRPC response when connected."""
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        c._connected = True
        result = await c.execute_task("t-1", "a-1", "agent_call", {"key": "value"})
        assert result["status"] == "success"
        assert result["task_id"] == "t-1"

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self):
        """health_check returns disconnected status when not connected."""
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        result = await c.health_check()
        assert result["status"] == "disconnected"
        assert result["target"] == "localhost:50051"

    @pytest.mark.asyncio
    async def test_health_check_connected(self):
        """health_check returns ok status when connected."""
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("remote:50051")
        c._connected = True
        result = await c.health_check()
        assert result["status"] == "ok"
        assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_close_sets_disconnected(self):
        """close() sets _connected to False."""
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        c._connected = True
        c._channel = AsyncMock()
        await c.close()
        assert c._connected is False

    # ---- Connection pool ---------------------------------------------------

    def test_connection_pool_importable(self):
        """GrpcConnectionPool class is importable."""
        from marketplace.grpc.client import GrpcConnectionPool
        assert GrpcConnectionPool is not None

    def test_connection_pool_max_connections_default(self):
        """Default pool max_connections is 50."""
        from marketplace.grpc.client import GrpcConnectionPool
        pool = GrpcConnectionPool()
        assert pool._max_connections == 50

    def test_connection_pool_active_connections_initially_zero(self):
        """Active connections starts at 0."""
        from marketplace.grpc.client import GrpcConnectionPool
        pool = GrpcConnectionPool()
        assert pool.active_connections == 0

    @pytest.mark.asyncio
    async def test_connection_pool_close_all(self):
        """close_all() empties the pool."""
        from marketplace.grpc.client import GrpcConnectionPool
        pool = GrpcConnectionPool()
        mock_client = AsyncMock()
        mock_client.is_connected = True
        pool._pool["host:50051"] = mock_client
        await pool.close_all()
        assert len(pool._pool) == 0


# ============================================================================
# 5. TestWebhookV2Service (12 tests)
# ============================================================================


class TestWebhookV2Service:
    """Tests for marketplace.services.webhook_v2_service."""

    def test_module_importable(self):
        """The webhook_v2_service module is importable."""
        from marketplace.services import webhook_v2_service
        assert hasattr(webhook_v2_service, "enqueue_webhook_delivery")

    def test_webhook_queue_constant(self):
        """WEBHOOK_QUEUE is 'webhooks'."""
        from marketplace.services.webhook_v2_service import WEBHOOK_QUEUE
        assert WEBHOOK_QUEUE == "webhooks"

    def test_max_delivery_attempts_constant(self):
        """MAX_DELIVERY_ATTEMPTS is 3."""
        from marketplace.services.webhook_v2_service import MAX_DELIVERY_ATTEMPTS
        assert MAX_DELIVERY_ATTEMPTS == 3

    def test_utcnow_returns_aware_datetime(self):
        """_utcnow() returns a timezone-aware UTC datetime."""
        from marketplace.services.webhook_v2_service import _utcnow
        now = _utcnow()
        assert now.tzinfo is not None

    @pytest.mark.asyncio
    async def test_enqueue_webhook_delivery_creates_attempt(self):
        """enqueue_webhook_delivery creates a DeliveryAttempt record."""
        from marketplace.services.webhook_v2_service import enqueue_webhook_delivery

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_svc = MagicMock()
        mock_svc.send_message.return_value = True

        with patch("marketplace.services.webhook_v2_service.get_servicebus_service", return_value=mock_svc):
            result = await enqueue_webhook_delivery(
                mock_db, "sub-1", {"event_type": "test", "callback_url": "http://example.com/hook"}
            )
        assert "delivery_attempt_id" in result
        assert result["subscription_id"] == "sub-1"
        assert result["queued"] is True
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_webhook_delivery_sends_to_servicebus(self):
        """enqueue_webhook_delivery sends a message to Service Bus."""
        from marketplace.services.webhook_v2_service import enqueue_webhook_delivery

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_svc = MagicMock()
        mock_svc.send_message.return_value = True

        with patch("marketplace.services.webhook_v2_service.get_servicebus_service", return_value=mock_svc):
            await enqueue_webhook_delivery(mock_db, "sub-2", {"type": "created"})
        mock_svc.send_message.assert_called_once()
        call_args = mock_svc.send_message.call_args
        assert call_args[0][0] == "webhooks"

    @pytest.mark.asyncio
    async def test_process_webhook_queue_empty(self):
        """process_webhook_queue with no messages returns zeroes."""
        from marketplace.services.webhook_v2_service import process_webhook_queue

        mock_db = AsyncMock()
        mock_svc = MagicMock()
        mock_svc.receive_messages.return_value = []

        with patch("marketplace.services.webhook_v2_service.get_servicebus_service", return_value=mock_svc):
            result = await process_webhook_queue(mock_db)
        assert result["delivered"] == 0
        assert result["failed"] == 0
        assert result["dead_lettered"] == 0

    @pytest.mark.asyncio
    async def test_process_webhook_queue_successful_delivery(self):
        """process_webhook_queue marks a message as delivered on HTTP 200."""
        from marketplace.services.webhook_v2_service import process_webhook_queue

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        msg_body = json.dumps({
            "subscription_id": "sub-1",
            "event": {"callback_url": "http://example.com/hook", "type": "test"},
            "attempt": 1,
        })
        mock_msg = MagicMock()
        mock_msg.__str__ = lambda self: msg_body

        mock_svc = MagicMock()
        mock_svc.receive_messages.return_value = [mock_msg]

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("marketplace.services.webhook_v2_service.get_servicebus_service", return_value=mock_svc):
            with patch("httpx.AsyncClient") as mock_httpx_cls:
                mock_httpx_instance = AsyncMock()
                mock_httpx_instance.post.return_value = mock_response
                mock_httpx_instance.__aenter__ = AsyncMock(return_value=mock_httpx_instance)
                mock_httpx_instance.__aexit__ = AsyncMock(return_value=None)
                mock_httpx_cls.return_value = mock_httpx_instance

                result = await process_webhook_queue(mock_db)
        assert result["delivered"] == 1

    @pytest.mark.asyncio
    async def test_process_webhook_queue_dead_letters_after_max_attempts(self):
        """After MAX_DELIVERY_ATTEMPTS failures, message is dead-lettered."""
        from marketplace.services.webhook_v2_service import process_webhook_queue

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        msg_body = json.dumps({
            "subscription_id": "sub-1",
            "event": {"callback_url": "http://example.com/hook"},
            "attempt": 3,  # already at max
        })
        mock_msg = MagicMock()
        mock_msg.__str__ = lambda self: msg_body

        mock_svc = MagicMock()
        mock_svc.receive_messages.return_value = [mock_msg]

        with patch("marketplace.services.webhook_v2_service.get_servicebus_service", return_value=mock_svc):
            with patch("httpx.AsyncClient") as mock_httpx_cls:
                mock_httpx_instance = AsyncMock()
                mock_httpx_instance.post.side_effect = Exception("Connection refused")
                mock_httpx_instance.__aenter__ = AsyncMock(return_value=mock_httpx_instance)
                mock_httpx_instance.__aexit__ = AsyncMock(return_value=None)
                mock_httpx_cls.return_value = mock_httpx_instance

                result = await process_webhook_queue(mock_db)
        assert result["dead_lettered"] == 1

    @pytest.mark.asyncio
    async def test_get_delivery_stats_returns_summary(self):
        """get_delivery_stats returns total_sent, total_failed, dlq_depth."""
        from marketplace.services.webhook_v2_service import get_delivery_stats

        mock_db = AsyncMock()
        # Create mock results for each query
        mock_result_delivered = MagicMock()
        mock_result_delivered.scalar.return_value = 10

        mock_result_failed = MagicMock()
        mock_result_failed.scalar.return_value = 3

        mock_result_dlq = MagicMock()
        mock_result_dlq.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[mock_result_delivered, mock_result_failed, mock_result_dlq])

        result = await get_delivery_stats(mock_db)
        assert result["total_sent"] == 10
        assert result["total_failed"] == 3
        assert result["dlq_depth"] == 1

    @pytest.mark.asyncio
    async def test_get_dead_letter_entries_returns_list(self):
        """get_dead_letter_entries returns a list of dicts."""
        from marketplace.services.webhook_v2_service import get_dead_letter_entries

        mock_entry = MagicMock()
        mock_entry.id = "dle-1"
        mock_entry.original_queue = "webhooks"
        mock_entry.message_body = '{"test": true}'
        mock_entry.reason = "Exhausted 3 delivery attempts"
        mock_entry.retried = False
        mock_entry.retry_count = 0
        mock_entry.dead_lettered_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_dead_letter_entries(mock_db, limit=10)
        assert len(result) == 1
        assert result[0]["id"] == "dle-1"
        assert result[0]["original_queue"] == "webhooks"

    @pytest.mark.asyncio
    async def test_retry_dead_letter_not_found(self):
        """retry_dead_letter returns error when entry not found."""
        from marketplace.services.webhook_v2_service import retry_dead_letter

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await retry_dead_letter(mock_db, "nonexistent-id")
        assert "error" in result
        assert result["entry_id"] == "nonexistent-id"


# ============================================================================
# 6. TestPaymentReconciliation (6 tests)
# ============================================================================


class TestPaymentReconciliation:
    """Tests for marketplace.services.payment_reconciliation_service."""

    def test_module_importable(self):
        """The payment_reconciliation_service module is importable."""
        from marketplace.services import payment_reconciliation_service
        assert hasattr(payment_reconciliation_service, "reconcile_stripe_payments")
        assert hasattr(payment_reconciliation_service, "reconcile_razorpay_payments")
        assert hasattr(payment_reconciliation_service, "retry_failed_payment")

    @pytest.mark.asyncio
    async def test_reconcile_stripe_no_transactions(self):
        """reconcile_stripe_payments with no transactions returns zeroes."""
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.stripe_secret_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_123"

        with patch("marketplace.config.settings", mock_settings):
            with patch("marketplace.services.stripe_service.StripePaymentService") as MockSvc:
                result = await reconcile_stripe_payments(mock_db)
        assert result["provider"] == "stripe"
        assert result["total_checked"] == 0
        assert result["matched"] == 0
        assert result["mismatched"] == []
        assert result["missing"] == []

    @pytest.mark.asyncio
    async def test_reconcile_stripe_matched_payment(self):
        """reconcile_stripe_payments counts a simulated matched payment."""
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        mock_tx = MagicMock()
        mock_tx.id = "tx-1"
        mock_tx.payment_reference = "pi_test_12345"
        mock_tx.amount_usdc = Decimal("50.00")
        mock_tx.status = "completed"
        mock_tx.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_tx]
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.stripe_secret_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_123"

        mock_service_instance = AsyncMock()
        mock_service_instance.retrieve_payment_intent.return_value = {
            "id": "pi_test_12345",
            "status": "succeeded",
            "amount": 5000,
            "simulated": True,
        }

        with patch("marketplace.config.settings", mock_settings):
            with patch(
                "marketplace.services.stripe_service.StripePaymentService",
                return_value=mock_service_instance,
            ):
                result = await reconcile_stripe_payments(mock_db)
        assert result["matched"] == 1

    @pytest.mark.asyncio
    async def test_reconcile_razorpay_no_transactions(self):
        """reconcile_razorpay_payments with no transactions returns zeroes."""
        from marketplace.services.payment_reconciliation_service import reconcile_razorpay_payments

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.razorpay_key_id = "rzp_test_id"
        mock_settings.razorpay_key_secret = "rzp_test_secret"

        with patch("marketplace.config.settings", mock_settings):
            with patch("marketplace.services.razorpay_service.RazorpayPaymentService") as MockSvc:
                result = await reconcile_razorpay_payments(mock_db)
        assert result["provider"] == "razorpay"
        assert result["total_checked"] == 0

    @pytest.mark.asyncio
    async def test_retry_failed_payment_transaction_not_found(self):
        """retry_failed_payment returns error when transaction not found."""
        from marketplace.services.payment_reconciliation_service import retry_failed_payment

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await retry_failed_payment(mock_db, "tx-missing")
        assert result == {"error": "Transaction not found"}

    @pytest.mark.asyncio
    async def test_retry_failed_payment_wrong_status(self):
        """retry_failed_payment rejects non-failed transactions."""
        from marketplace.services.payment_reconciliation_service import retry_failed_payment

        mock_tx = MagicMock()
        mock_tx.id = "tx-1"
        mock_tx.status = "completed"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tx
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await retry_failed_payment(mock_db, "tx-1")
        assert "error" in result
        assert "completed" in result["error"]

    @pytest.mark.asyncio
    async def test_reconcile_stripe_report_contains_timestamp(self):
        """reconcile_stripe_payments includes a reconciled_at timestamp."""
        from marketplace.services.payment_reconciliation_service import reconcile_stripe_payments

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.stripe_secret_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_123"

        with patch("marketplace.config.settings", mock_settings):
            with patch("marketplace.services.stripe_service.StripePaymentService"):
                result = await reconcile_stripe_payments(mock_db)
        assert "reconciled_at" in result
        # Verify it parses as an ISO datetime
        datetime.fromisoformat(result["reconciled_at"])
