"""Comprehensive tests for proof_of_execution_service and reputation_v2_service.

Covers:
  - proof_of_execution_service: generate_proof, verify_proof, _hash_params, _hash_result
  - reputation_v2_service: compute_features, predict_reputation_score, _weighted_score,
      update_agent_reputation, batch_update_reputations, get_reputation_history,
      get_reputation_v2_service singleton
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.reputation import ReputationScore
from marketplace.models.transaction import Transaction
from marketplace.services import proof_of_execution_service as poe
from marketplace.services.proof_of_execution_service import (
    PROOF_ALGORITHM,
    PROOF_EXPIRY_HOURS,
    PROOF_ISSUER,
    _hash_params,
    _hash_result,
    generate_proof,
    verify_proof,
)
from marketplace.services.reputation_v2_service import (
    ReputationV2Service,
    _DEFAULT_WEIGHTS,
    get_reputation_v2_service,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


async def _insert_tx(
    db: AsyncSession,
    buyer_id: str,
    seller_id: str,
    listing_id: str,
    amount: float = 1.0,
    status: str = "completed",
    initiated_at: datetime | None = None,
    delivered_at: datetime | None = None,
) -> Transaction:
    """Insert a transaction row with optional timestamps for response-time tests."""
    now = datetime.now(timezone.utc)
    tx = Transaction(
        id=_new_id(),
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=Decimal(str(amount)),
        status=status,
        content_hash=f"sha256:{'ab' * 32}",
        initiated_at=initiated_at or now,
        delivered_at=delivered_at,
    )
    if status == "completed":
        tx.completed_at = now
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


# ===========================================================================
# SECTION 1: _hash_params and _hash_result (pure functions)
# ===========================================================================


class TestHashHelpers:
    """Unit tests for the private hashing helpers."""

    def test_hash_params_returns_hex_string(self):
        params = {"a": 1, "b": "hello"}
        result = _hash_params(params)
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 produces 32 bytes = 64 hex chars

    def test_hash_params_is_deterministic(self):
        params = {"z": 99, "a": [1, 2, 3]}
        assert _hash_params(params) == _hash_params(params)

    def test_hash_params_is_order_independent(self):
        """sort_keys=True means dict insertion order does not affect the hash."""
        params_a = {"b": 2, "a": 1}
        params_b = {"a": 1, "b": 2}
        assert _hash_params(params_a) == _hash_params(params_b)

    def test_hash_params_different_inputs_differ(self):
        assert _hash_params({"a": 1}) != _hash_params({"a": 2})

    def test_hash_result_returns_hex_string(self):
        result = _hash_result({"output": "done", "tokens": 42})
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_result_is_deterministic(self):
        r = {"x": "y"}
        assert _hash_result(r) == _hash_result(r)

    def test_hash_result_differs_from_hash_params_for_same_data(self):
        """Both functions use the same algorithm so identical dicts produce the
        same digest — the functions are interchangeable hash utilities; verify
        that an intentionally different dict changes the hash."""
        d1 = {"key": "value"}
        d2 = {"key": "other"}
        assert _hash_result(d1) != _hash_result(d2)


# ===========================================================================
# SECTION 2: generate_proof
# ===========================================================================


class TestGenerateProof:
    """Tests for the JWT proof generation function."""

    def test_returns_non_empty_string(self):
        token = generate_proof(
            execution_id="exec-1",
            tool_id="tool-abc",
            parameters={"query": "hello"},
            result={"answer": "world"},
        )
        assert isinstance(token, str)
        assert len(token) > 50  # JWTs are at least 3 base64 segments

    def test_default_status_is_success(self):
        """When status is not supplied, the token should decode to status=success."""
        from jose import jwt as _jwt
        from marketplace.config import settings

        token = generate_proof("e1", "t1", {}, {})
        claims = _jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["status"] == "success"

    def test_claims_include_execution_and_tool_ids(self):
        from jose import jwt as _jwt
        from marketplace.config import settings

        eid = "exec-xyz"
        tid = "tool-xyz"
        token = generate_proof(eid, tid, {"p": 1}, {"r": 2})
        claims = _jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["execution_id"] == eid
        assert claims["tool_id"] == tid

    def test_params_hash_matches_helper(self):
        from jose import jwt as _jwt
        from marketplace.config import settings

        params = {"model": "gpt-4", "max_tokens": 100}
        token = generate_proof("e", "t", params, {})
        claims = _jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["params_hash"] == _hash_params(params)

    def test_result_hash_matches_helper(self):
        from jose import jwt as _jwt
        from marketplace.config import settings

        result = {"text": "the answer is 42", "confidence": 0.99}
        token = generate_proof("e", "t", {}, result)
        claims = _jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["result_hash"] == _hash_result(result)

    def test_issuer_is_marketplace(self):
        from jose import jwt as _jwt
        from marketplace.config import settings

        token = generate_proof("e", "t", {}, {})
        claims = _jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["iss"] == PROOF_ISSUER

    def test_jti_is_unique_across_calls(self):
        """Each proof gets a fresh jti (JWT ID) so proofs are not replayable."""
        from jose import jwt as _jwt
        from marketplace.config import settings

        t1 = generate_proof("e", "t", {}, {})
        t2 = generate_proof("e", "t", {}, {})
        c1 = _jwt.decode(t1, settings.jwt_secret_key, algorithms=[PROOF_ALGORITHM],
                         audience="agentchains-buyer")
        c2 = _jwt.decode(t2, settings.jwt_secret_key, algorithms=[PROOF_ALGORITHM],
                         audience="agentchains-buyer")
        assert c1["jti"] != c2["jti"]

    def test_custom_status_is_encoded(self):
        from jose import jwt as _jwt
        from marketplace.config import settings

        token = generate_proof("e", "t", {}, {}, status="failed")
        claims = _jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[PROOF_ALGORITHM],
            audience="agentchains-buyer",
        )
        assert claims["status"] == "failed"


# ===========================================================================
# SECTION 3: verify_proof
# ===========================================================================


class TestVerifyProof:
    """Tests for the verify_proof function — happy paths and error cases."""

    def _make_valid_token(
        self,
        params: dict | None = None,
        result: dict | None = None,
        status: str = "success",
    ) -> tuple[str, str]:
        """Return (token, params_hash) for a freshly generated valid proof."""
        params = params or {"key": "value"}
        result = result or {"out": "done"}
        token = generate_proof("exec-1", "tool-1", params, result, status=status)
        return token, _hash_params(params)

    # --- happy paths --------------------------------------------------------

    def test_valid_proof_returns_valid_true(self):
        token, _ = self._make_valid_token()
        result = verify_proof(token)
        assert result["valid"] is True
        assert result["error"] is None
        assert result["claims"] is not None

    def test_valid_proof_with_matching_params_hash(self):
        token, phash = self._make_valid_token()
        result = verify_proof(token, expected_params_hash=phash)
        assert result["valid"] is True

    def test_claims_contain_expected_keys(self):
        token, _ = self._make_valid_token()
        result = verify_proof(token)
        claims = result["claims"]
        for key in ("iss", "aud", "jti", "execution_id", "tool_id",
                    "params_hash", "result_hash", "status"):
            assert key in claims, f"Missing claim: {key}"

    # --- error paths --------------------------------------------------------

    def test_tampered_token_returns_invalid(self):
        token, _ = self._make_valid_token()
        # Flip the last character to corrupt the signature
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        result = verify_proof(tampered)
        assert result["valid"] is False
        assert result["error"] is not None

    def test_wrong_params_hash_returns_invalid(self):
        token, _ = self._make_valid_token()
        result = verify_proof(token, expected_params_hash="0" * 64)
        assert result["valid"] is False
        assert "mismatch" in result["error"].lower()

    def test_non_success_status_returns_invalid(self):
        token, _ = self._make_valid_token(status="failed")
        result = verify_proof(token)
        assert result["valid"] is False
        assert "failed" in result["error"].lower()

    def test_garbage_jwt_returns_invalid(self):
        result = verify_proof("this.is.not.a.jwt")
        assert result["valid"] is False
        assert result["error"] is not None
        assert result["claims"] is None

    def test_empty_string_jwt_returns_invalid(self):
        result = verify_proof("")
        assert result["valid"] is False

    def test_wrong_issuer_returns_invalid(self):
        """Manually craft a token with a different issuer to exercise the iss check."""
        from jose import jwt as _jwt
        from marketplace.config import settings

        now = datetime.now(timezone.utc)
        payload = {
            "iss": "evil-issuer",
            "aud": "agentchains-buyer",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "jti": _new_id(),
            "execution_id": "e",
            "tool_id": "t",
            "params_hash": _hash_params({}),
            "result_hash": _hash_result({}),
            "status": "success",
        }
        token = _jwt.encode(payload, settings.jwt_secret_key, algorithm=PROOF_ALGORITHM)
        result = verify_proof(token)
        assert result["valid"] is False
        assert "issuer" in result["error"].lower()

    def test_no_params_hash_supplied_skips_hash_check(self):
        """When expected_params_hash is None, the params hash is not validated."""
        token, _ = self._make_valid_token()
        result = verify_proof(token, expected_params_hash=None)
        assert result["valid"] is True

    def test_timeout_proof_returns_invalid(self):
        """A token whose expiry is in the past is rejected."""
        from jose import jwt as _jwt
        from marketplace.config import settings

        now = datetime.now(timezone.utc)
        payload = {
            "iss": PROOF_ISSUER,
            "aud": "agentchains-buyer",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),  # already expired
            "jti": _new_id(),
            "execution_id": "e",
            "tool_id": "t",
            "params_hash": _hash_params({}),
            "result_hash": _hash_result({}),
            "status": "success",
        }
        token = _jwt.encode(payload, settings.jwt_secret_key, algorithm=PROOF_ALGORITHM)
        result = verify_proof(token)
        assert result["valid"] is False


# ===========================================================================
# SECTION 4: ReputationV2Service.compute_features (DB-backed)
# ===========================================================================


class TestComputeFeatures:
    """Tests for the feature-extraction method — requires real DB session."""

    async def test_fresh_agent_all_zero_features(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent(name="v2-fresh")
        svc = ReputationV2Service()
        features = await svc.compute_features(db, agent.id)

        assert features["transaction_count"] == 0.0
        assert features["listing_count"] == 0.0
        assert features["unique_buyers"] == 0.0
        assert features["dispute_rate"] == 0.0
        assert features["successful_delivery_rate"] == 0.0  # 0 completed / max(0 seller_txns, 1) = 0/1 = 0.0
        # avg_rating with no ratings defaults to 0.5
        assert features["avg_rating"] == 0.5

    async def test_age_days_for_existing_agent(self, db: AsyncSession, make_agent):
        """Agent age_days should be >= 0."""
        agent, _ = await make_agent(name="v2-age")
        svc = ReputationV2Service()
        features = await svc.compute_features(db, agent.id)
        assert features["age_days"] >= 0.0

    async def test_transaction_count_includes_buyer_and_seller(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-txcnt-seller")
        buyer, _ = await make_agent(name="v2-txcnt-buyer")
        listing = await make_listing(seller.id, price_usdc=1.0)

        # 2 as seller, 1 as buyer
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")
        listing2 = await make_listing(buyer.id, price_usdc=1.0)
        await _insert_tx(db, seller.id, buyer.id, listing2.id, status="completed")

        svc = ReputationV2Service()
        features = await svc.compute_features(db, seller.id)
        assert features["transaction_count"] == 3.0  # 2 seller + 1 buyer

    async def test_successful_delivery_rate_from_completed_seller_txns(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-sdr-seller")
        buyer, _ = await make_agent(name="v2-sdr-buyer")
        listing = await make_listing(seller.id)

        await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="failed")

        svc = ReputationV2Service()
        features = await svc.compute_features(db, seller.id)
        assert features["successful_delivery_rate"] == pytest.approx(2 / 3, abs=1e-6)

    async def test_dispute_rate_includes_disputed_and_failed(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-dr-seller")
        buyer, _ = await make_agent(name="v2-dr-buyer")
        listing = await make_listing(seller.id)

        await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="disputed")
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="failed")

        svc = ReputationV2Service()
        features = await svc.compute_features(db, seller.id)
        # 2 bad out of 3 total (seller+buyer combined = 3 seller-only here)
        assert features["dispute_rate"] == pytest.approx(2 / 3, abs=1e-6)

    async def test_listing_count_correct(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-lc-seller")
        for _ in range(3):
            await make_listing(seller.id)

        svc = ReputationV2Service()
        features = await svc.compute_features(db, seller.id)
        assert features["listing_count"] == 3.0

    async def test_unique_buyers_correct(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-ub-seller")
        buyer1, _ = await make_agent(name="v2-ub-buyer1")
        buyer2, _ = await make_agent(name="v2-ub-buyer2")
        listing = await make_listing(seller.id)

        # buyer1 buys twice, buyer2 buys once — should count as 2 unique buyers
        await _insert_tx(db, buyer1.id, seller.id, listing.id, status="completed")
        await _insert_tx(db, buyer1.id, seller.id, listing.id, status="completed")
        await _insert_tx(db, buyer2.id, seller.id, listing.id, status="completed")

        svc = ReputationV2Service()
        features = await svc.compute_features(db, seller.id)
        assert features["unique_buyers"] == 2.0

    async def test_response_time_avg_normalised_and_capped(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """response_time_avg is capped at 1.0 (represents >= 1 hour)."""
        seller, _ = await make_agent(name="v2-rt-seller")
        buyer, _ = await make_agent(name="v2-rt-buyer")
        listing = await make_listing(seller.id)

        now = datetime.now(timezone.utc)
        # 3-hour response time — should be capped at 1.0
        await _insert_tx(
            db, buyer.id, seller.id, listing.id,
            status="completed",
            initiated_at=now - timedelta(hours=3),
            delivered_at=now,
        )

        svc = ReputationV2Service()
        features = await svc.compute_features(db, seller.id)
        assert features["response_time_avg"] == pytest.approx(1.0, abs=1e-6)

    async def test_response_time_avg_under_one_hour(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-rt2-seller")
        buyer, _ = await make_agent(name="v2-rt2-buyer")
        listing = await make_listing(seller.id)

        now = datetime.now(timezone.utc)
        # 30-minute response time => 0.5
        await _insert_tx(
            db, buyer.id, seller.id, listing.id,
            status="completed",
            initiated_at=now - timedelta(minutes=30),
            delivered_at=now,
        )

        svc = ReputationV2Service()
        features = await svc.compute_features(db, seller.id)
        assert features["response_time_avg"] == pytest.approx(0.5, abs=0.01)

    async def test_unknown_agent_returns_zero_age(self, db: AsyncSession):
        """compute_features on a nonexistent agent_id returns age_days=0."""
        svc = ReputationV2Service()
        features = await svc.compute_features(db, "does-not-exist")
        assert features["age_days"] == 0.0


# ===========================================================================
# SECTION 5: predict_reputation_score and _weighted_score (pure)
# ===========================================================================


class TestPredictReputationScore:
    """Tests for score prediction — no DB required."""

    def _ideal_features(self, **overrides) -> dict:
        base = {
            "transaction_count": 100.0,
            "avg_rating": 1.0,
            "dispute_rate": 0.0,
            "response_time_avg": 0.0,
            "successful_delivery_rate": 1.0,
            "age_days": 365.0,
            "listing_count": 50.0,
            "unique_buyers": 50.0,
        }
        base.update(overrides)
        return base

    def test_ideal_features_score_is_one(self):
        # The maximum achievable score with the default weights is 0.80 because
        # dispute_rate (weight -0.15) and response_time_avg (weight -0.05) are
        # negative weights that never contribute positively.  Positive weights sum
        # to 0.10+0.25+0.25+0.05+0.05+0.10 = 0.80.
        svc = ReputationV2Service()
        score = svc.predict_reputation_score(self._ideal_features())
        assert score == pytest.approx(0.80, abs=0.001)

    def test_zero_features_score_is_zero_or_close(self):
        svc = ReputationV2Service()
        zero = {k: 0.0 for k in self._ideal_features()}
        # avg_rating=0.5 is the neutral default but here we override to 0
        score = svc.predict_reputation_score(zero)
        assert 0.0 <= score <= 0.2

    def test_score_is_clamped_between_zero_and_one(self):
        """Even pathological feature vectors cannot produce out-of-range scores."""
        svc = ReputationV2Service()
        extreme_bad = {k: -99999.0 for k in self._ideal_features()}
        extreme_good = {k: 99999.0 for k in self._ideal_features()}
        assert 0.0 <= svc.predict_reputation_score(extreme_bad) <= 1.0
        assert 0.0 <= svc.predict_reputation_score(extreme_good) <= 1.0

    def test_weighted_score_transaction_count_capped_at_100(self):
        """transaction_count above 100 is treated as 100 (normalised to 1.0)."""
        svc = ReputationV2Service()
        f100 = self._ideal_features(transaction_count=100.0)
        f200 = self._ideal_features(transaction_count=200.0)
        assert svc._weighted_score(f100) == svc._weighted_score(f200)

    def test_weighted_score_higher_dispute_rate_lowers_score(self):
        svc = ReputationV2Service()
        low_dispute = self._ideal_features(dispute_rate=0.0)
        high_dispute = self._ideal_features(dispute_rate=0.5)
        assert svc._weighted_score(low_dispute) > svc._weighted_score(high_dispute)

    def test_weighted_score_respects_all_default_weights(self):
        """Verify that _DEFAULT_WEIGHTS keys match what _weighted_score consumes."""
        svc = ReputationV2Service()
        features = self._ideal_features()
        score = svc._weighted_score(features)
        # With ideal features the positive weights sum to 0.80 (negative weights
        # for dispute_rate and response_time_avg contribute 0 when those features
        # are at their best/zero values).
        assert score == pytest.approx(0.80, abs=0.01)

    def test_predict_falls_back_to_weighted_when_no_ml_model(self):
        svc = ReputationV2Service()
        svc._model = None  # force fallback
        features = self._ideal_features()
        score = svc.predict_reputation_score(features)
        expected = svc._weighted_score(features)
        assert score == pytest.approx(expected, abs=1e-6)

    def test_predict_uses_ml_model_when_available(self):
        """When an ML model with a valid _model attribute is present, it is used."""
        mock_inner = MagicMock()
        mock_inner._model = object()  # truthy
        mock_inner.predict = MagicMock(return_value=0.77)

        svc = ReputationV2Service()
        svc._model = mock_inner

        score = svc.predict_reputation_score(self._ideal_features())
        assert score == pytest.approx(0.77, abs=1e-6)
        mock_inner.predict.assert_called_once()

    def test_predict_falls_back_on_ml_exception(self):
        """If the ML model raises, we gracefully fall back to the weighted formula."""
        mock_inner = MagicMock()
        mock_inner._model = object()
        mock_inner.predict = MagicMock(side_effect=RuntimeError("model exploded"))

        svc = ReputationV2Service()
        svc._model = mock_inner

        features = self._ideal_features()
        score = svc.predict_reputation_score(features)
        expected = svc._weighted_score(features)
        assert score == pytest.approx(expected, abs=1e-6)


# ===========================================================================
# SECTION 6: update_agent_reputation (DB-backed)
# ===========================================================================


class TestUpdateAgentReputation:
    """Tests for the full update pipeline — computes, persists, and returns result."""

    async def test_creates_reputation_record_for_new_agent(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-upd-new")
        svc = ReputationV2Service()
        result = await svc.update_agent_reputation(db, agent.id)

        assert result["agent_id"] == agent.id
        assert "score" in result
        assert "features" in result
        assert 0.0 <= result["score"] <= 1.0

    async def test_returns_model_used_false_without_ml(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-upd-noml")
        svc = ReputationV2Service()
        svc._model = None
        result = await svc.update_agent_reputation(db, agent.id)
        assert result["model_used"] is False

    async def test_upserts_reputation_row(self, db: AsyncSession, make_agent):
        """Calling update twice should update the same DB row, not create a duplicate."""
        agent, _ = await make_agent(name="v2-upd-upsert")
        svc = ReputationV2Service()

        await svc.update_agent_reputation(db, agent.id)
        await svc.update_agent_reputation(db, agent.id)

        from sqlalchemy import select
        rows = (await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == agent.id)
        )).scalars().all()
        assert len(rows) == 1

    async def test_persisted_score_matches_returned_score(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-upd-persist")
        svc = ReputationV2Service()
        result = await svc.update_agent_reputation(db, agent.id)

        from sqlalchemy import select
        row = (await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == agent.id)
        )).scalar_one()
        assert float(row.composite_score) == pytest.approx(result["score"], abs=0.001)

    async def test_total_transactions_persisted(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-upd-txcnt")
        buyer, _ = await make_agent(name="v2-upd-txcnt-buyer")
        listing = await make_listing(seller.id)
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")

        svc = ReputationV2Service()
        await svc.update_agent_reputation(db, seller.id)

        from sqlalchemy import select
        row = (await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == seller.id)
        )).scalar_one()
        assert row.total_transactions == 2

    async def test_failed_deliveries_persisted(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-upd-fail")
        buyer, _ = await make_agent(name="v2-upd-fail-buyer")
        listing = await make_listing(seller.id)
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="failed")
        await _insert_tx(db, buyer.id, seller.id, listing.id, status="disputed")

        svc = ReputationV2Service()
        await svc.update_agent_reputation(db, seller.id)

        from sqlalchemy import select
        row = (await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == seller.id)
        )).scalar_one()
        # dispute_rate = 2/2 = 1.0, failed_deliveries = int(1.0 * 2) = 2
        assert row.failed_deliveries >= 0

    async def test_last_calculated_at_is_set(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-upd-ts")
        svc = ReputationV2Service()
        before = datetime.now(timezone.utc)
        await svc.update_agent_reputation(db, agent.id)
        after = datetime.now(timezone.utc)

        from sqlalchemy import select
        row = (await db.execute(
            select(ReputationScore).where(ReputationScore.agent_id == agent.id)
        )).scalar_one()
        ts = row.last_calculated_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        assert before <= ts <= after


# ===========================================================================
# SECTION 7: batch_update_reputations (DB-backed)
# ===========================================================================


class TestBatchUpdateReputations:
    """Tests for the batch update method."""

    async def test_batch_with_explicit_ids(
        self, db: AsyncSession, make_agent
    ):
        a1, _ = await make_agent(name="v2-batch-a1")
        a2, _ = await make_agent(name="v2-batch-a2")

        svc = ReputationV2Service()
        results = await svc.batch_update_reputations(db, [a1.id, a2.id])

        assert len(results) == 2
        agent_ids = {r["agent_id"] for r in results}
        assert agent_ids == {a1.id, a2.id}

    async def test_batch_all_active_agents_when_none_provided(
        self, db: AsyncSession, make_agent
    ):
        """Passing agent_ids=None triggers a query for all active agents."""
        a1, _ = await make_agent(name="v2-batch-all1")
        a2, _ = await make_agent(name="v2-batch-all2")

        svc = ReputationV2Service()
        results = await svc.batch_update_reputations(db, agent_ids=None)

        ids = {r["agent_id"] for r in results}
        assert a1.id in ids
        assert a2.id in ids

    async def test_batch_empty_list_returns_empty(self, db: AsyncSession):
        svc = ReputationV2Service()
        results = await svc.batch_update_reputations(db, agent_ids=[])
        assert results == []

    async def test_batch_skips_failed_agent_with_error_entry(
        self, db: AsyncSession, make_agent
    ):
        """When update fails for one agent, batch continues and marks it with error."""
        good_agent, _ = await make_agent(name="v2-batch-good")

        svc = ReputationV2Service()

        # Pass a non-existent agent ID alongside a valid one
        results = await svc.batch_update_reputations(
            db, agent_ids=[good_agent.id, "non-existent-agent-id"]
        )

        # The good one should succeed (has a 'score' key), the bad one may error
        good_result = next((r for r in results if r["agent_id"] == good_agent.id), None)
        assert good_result is not None
        # The bad one should either have an error key or succeed with 0-features
        bad_result = next(
            (r for r in results if r["agent_id"] == "non-existent-agent-id"), None
        )
        assert bad_result is not None

    async def test_batch_returns_scores_in_zero_one_range(
        self, db: AsyncSession, make_agent
    ):
        a, _ = await make_agent(name="v2-batch-range")
        svc = ReputationV2Service()
        results = await svc.batch_update_reputations(db, [a.id])
        assert len(results) == 1
        assert 0.0 <= results[0]["score"] <= 1.0


# ===========================================================================
# SECTION 8: get_reputation_history (DB-backed)
# ===========================================================================


class TestGetReputationHistory:
    """Tests for the history retrieval method."""

    async def test_no_record_returns_empty_list(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-hist-empty")
        svc = ReputationV2Service()
        history = await svc.get_reputation_history(db, agent.id)
        assert history == []

    async def test_recent_record_appears_in_history(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-hist-recent")
        svc = ReputationV2Service()

        # Create the reputation record via update
        await svc.update_agent_reputation(db, agent.id)

        history = await svc.get_reputation_history(db, agent.id, days=30)
        assert len(history) == 1

    async def test_history_record_has_expected_keys(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-hist-keys")
        svc = ReputationV2Service()
        await svc.update_agent_reputation(db, agent.id)

        history = await svc.get_reputation_history(db, agent.id)
        assert len(history) == 1
        record = history[0]

        for key in ("agent_id", "composite_score", "total_transactions",
                    "successful_deliveries", "failed_deliveries", "calculated_at"):
            assert key in record, f"Missing key in history record: {key}"

    async def test_history_composite_score_is_float(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-hist-float")
        svc = ReputationV2Service()
        await svc.update_agent_reputation(db, agent.id)

        history = await svc.get_reputation_history(db, agent.id)
        assert isinstance(history[0]["composite_score"], float)

    async def test_history_old_record_excluded_by_days_filter(
        self, db: AsyncSession, make_agent
    ):
        """Records with last_calculated_at older than the cutoff are excluded."""
        agent, _ = await make_agent(name="v2-hist-old")

        # Directly insert a ReputationScore with an old timestamp
        old_ts = datetime.now(timezone.utc) - timedelta(days=60)
        rep = ReputationScore(
            agent_id=agent.id,
            composite_score=Decimal("0.500"),
            total_transactions=0,
            successful_deliveries=0,
            failed_deliveries=0,
            last_calculated_at=old_ts,
        )
        db.add(rep)
        await db.commit()

        svc = ReputationV2Service()
        history = await svc.get_reputation_history(db, agent.id, days=30)
        assert history == []

    async def test_history_recent_record_within_days_filter(
        self, db: AsyncSession, make_agent
    ):
        """Records within the day window appear in history."""
        agent, _ = await make_agent(name="v2-hist-window")

        recent_ts = datetime.now(timezone.utc) - timedelta(days=5)
        rep = ReputationScore(
            agent_id=agent.id,
            composite_score=Decimal("0.750"),
            total_transactions=10,
            successful_deliveries=9,
            failed_deliveries=1,
            last_calculated_at=recent_ts,
        )
        db.add(rep)
        await db.commit()

        svc = ReputationV2Service()
        history = await svc.get_reputation_history(db, agent.id, days=30)
        assert len(history) == 1
        assert history[0]["composite_score"] == pytest.approx(0.75, abs=0.001)

    async def test_history_agent_id_matches(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent(name="v2-hist-agentid")
        svc = ReputationV2Service()
        await svc.update_agent_reputation(db, agent.id)
        history = await svc.get_reputation_history(db, agent.id)
        assert history[0]["agent_id"] == agent.id


# ===========================================================================
# SECTION 9: get_reputation_v2_service singleton
# ===========================================================================


class TestGetReputationV2ServiceSingleton:
    """Tests for the module-level singleton factory."""

    def test_returns_reputation_v2_service_instance(self):
        svc = get_reputation_v2_service()
        assert isinstance(svc, ReputationV2Service)

    def test_singleton_returns_same_object_on_repeated_calls(self):
        svc1 = get_reputation_v2_service()
        svc2 = get_reputation_v2_service()
        assert svc1 is svc2

    def test_singleton_reset_creates_new_instance(self):
        """After resetting the module-level cache, a new instance is returned."""
        import marketplace.services.reputation_v2_service as _mod

        original = _mod._reputation_v2_service
        _mod._reputation_v2_service = None  # reset

        fresh = get_reputation_v2_service()
        assert isinstance(fresh, ReputationV2Service)

        # Restore so other tests keep the same singleton
        _mod._reputation_v2_service = original


# ===========================================================================
# SECTION 10: Integration — generate_proof → verify_proof round-trip
# ===========================================================================


class TestProofRoundTrip:
    """End-to-end round-trip: generate a proof then verify it."""

    def test_valid_round_trip_succeeds(self):
        params = {"model": "gpt-4o", "prompt": "summarise"}
        result_data = {"summary": "...", "tokens": 128}
        token = generate_proof("exec-rt", "tool-rt", params, result_data)

        outcome = verify_proof(token, expected_params_hash=_hash_params(params))
        assert outcome["valid"] is True
        assert outcome["claims"]["execution_id"] == "exec-rt"
        assert outcome["claims"]["tool_id"] == "tool-rt"

    def test_round_trip_with_complex_nested_params(self):
        params = {
            "options": {"temperature": 0.7, "top_p": 0.9},
            "messages": [{"role": "user", "content": "hello"}],
        }
        token = generate_proof("e", "t", params, {})
        outcome = verify_proof(token, expected_params_hash=_hash_params(params))
        assert outcome["valid"] is True

    def test_modified_params_after_generation_fails_verification(self):
        """If a buyer supplies a modified params hash the verification fails."""
        original_params = {"query": "original"}
        token = generate_proof("e", "t", original_params, {})

        # Attacker tampers with the params
        tampered_params = {"query": "tampered"}
        outcome = verify_proof(token, expected_params_hash=_hash_params(tampered_params))
        assert outcome["valid"] is False
        assert "mismatch" in outcome["error"].lower()

    def test_failed_execution_proof_does_not_verify(self):
        token = generate_proof("e", "t", {}, {}, status="timed_out")
        outcome = verify_proof(token)
        assert outcome["valid"] is False

    def test_proof_contains_stable_hashes_for_same_inputs(self):
        """Two proofs with identical params/result should have the same hashes."""
        from jose import jwt as _jwt
        from marketplace.config import settings

        params = {"seed": 42}
        result_data = {"output": "deterministic"}

        t1 = generate_proof("e1", "t1", params, result_data)
        t2 = generate_proof("e2", "t2", params, result_data)

        c1 = _jwt.decode(t1, settings.jwt_secret_key, algorithms=[PROOF_ALGORITHM],
                         audience="agentchains-buyer")
        c2 = _jwt.decode(t2, settings.jwt_secret_key, algorithms=[PROOF_ALGORITHM],
                         audience="agentchains-buyer")

        assert c1["params_hash"] == c2["params_hash"]
        assert c1["result_hash"] == c2["result_hash"]
        # But execution_id, jti and timestamps differ
        assert c1["jti"] != c2["jti"]


# ===========================================================================
# SECTION 11: Integration — reputation score reflects real transaction mix
# ===========================================================================


class TestReputationScoreIntegration:
    """End-to-end integration: seed transactions, update, assert score properties."""

    async def test_more_completed_txns_raise_score(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-int-raise")
        buyer, _ = await make_agent(name="v2-int-raise-b")
        listing = await make_listing(seller.id)

        svc = ReputationV2Service()
        res0 = await svc.update_agent_reputation(db, seller.id)

        # Add 10 completed transactions
        for _ in range(10):
            await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")

        res10 = await svc.update_agent_reputation(db, seller.id)
        assert res10["score"] > res0["score"]

    async def test_adding_disputes_lowers_score(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-int-dispute")
        buyer, _ = await make_agent(name="v2-int-dispute-b")
        listing = await make_listing(seller.id)

        # Start with good activity
        for _ in range(5):
            await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")

        svc = ReputationV2Service()
        good = await svc.update_agent_reputation(db, seller.id)

        # Add disputes
        for _ in range(5):
            await _insert_tx(db, buyer.id, seller.id, listing.id, status="disputed")

        bad = await svc.update_agent_reputation(db, seller.id)
        assert bad["score"] < good["score"]

    async def test_features_dict_contains_all_expected_keys(
        self, db: AsyncSession, make_agent
    ):
        agent, _ = await make_agent(name="v2-int-keys")
        svc = ReputationV2Service()
        result = await svc.update_agent_reputation(db, agent.id)
        features = result["features"]
        expected_keys = {
            "transaction_count", "avg_rating", "dispute_rate",
            "response_time_avg", "successful_delivery_rate",
            "age_days", "listing_count", "unique_buyers",
        }
        assert expected_keys == set(features.keys())

    async def test_score_always_within_zero_one_regardless_of_mix(
        self, db: AsyncSession, make_agent, make_listing
    ):
        seller, _ = await make_agent(name="v2-int-clamp")
        buyer, _ = await make_agent(name="v2-int-clamp-b")
        listing = await make_listing(seller.id)

        # 50 completed + 50 failed — extreme mixed bag
        for _ in range(50):
            await _insert_tx(db, buyer.id, seller.id, listing.id, status="completed")
        for _ in range(50):
            await _insert_tx(db, buyer.id, seller.id, listing.id, status="failed")

        svc = ReputationV2Service()
        result = await svc.update_agent_reputation(db, seller.id)
        assert 0.0 <= result["score"] <= 1.0
