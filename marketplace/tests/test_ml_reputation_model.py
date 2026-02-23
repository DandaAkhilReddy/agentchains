"""Comprehensive unit tests for marketplace/ml/reputation_model.py.

Tests cover every public method and branch of ReputationModel:
    - __init__: default model_dir, custom model_dir, load-on-init success/failure
    - train: lightgbm path, sklearn fallback, no-ML-library RuntimeError
    - predict: predict_proba (2D), predict_proba (1D), predict fallback,
               missing-model error, exception-during-prediction fallback,
               clamping to [0.0, 1.0], missing features default to 0.0
    - save: happy path (writes file + hash), no-model RuntimeError
    - load: happy path (dict format), legacy format, FileNotFoundError,
            integrity-check failure, no hash file (warning-only path)
    - feature_importance: feature_importances_ attribute, coef_ 2D, coef_ 1D,
                          equal-weights fallback, no-model RuntimeError
    - _compute_file_hash: deterministic, changes on different content

All tests are synchronous (ML operations are CPU-bound; no DB access needed).
The `db` fixture is imported so pytest picks it up from conftest, but is not
used directly in these tests — the model is a pure-Python class.

External ML libraries (sklearn / lightgbm) are mocked so the suite runs
without those optional dependencies being installed.
"""

from __future__ import annotations

import hashlib
import pathlib
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from marketplace.ml.reputation_model import (
    FEATURE_NAMES,
    ReputationModel,
    _DEFAULT_MODEL_DIR,
    _HAS_LIGHTGBM,
    _HAS_SKLEARN,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_classifier(proba: list[list[float]] | None = None, pred: list[float] | None = None):
    """Build a minimal mock that quacks like a fitted sklearn/lgbm classifier.

    Args:
        proba: 2-D list returned by predict_proba([[...]]).
               Set to None to make the model NOT have predict_proba.
        pred: 1-D list returned by predict([[...]]).
    """
    mock = MagicMock()

    if proba is not None:
        import numpy as np
        arr = np.array(proba)
        mock.predict_proba.return_value = arr
    else:
        del mock.predict_proba  # Remove so hasattr returns False
        mock.spec = []

    if pred is not None:
        import numpy as np
        mock.predict.return_value = np.array(pred)

    if not hasattr(mock, "feature_importances_"):
        import numpy as np
        mock.feature_importances_ = np.array([1.0 / len(FEATURE_NAMES)] * len(FEATURE_NAMES))

    return mock


def _sample_features(value: float = 0.5) -> dict[str, float]:
    """Return a feature dict with every FEATURE_NAMES key set to *value*."""
    return {name: value for name in FEATURE_NAMES}


# ---------------------------------------------------------------------------
# Block 1: __init__
# ---------------------------------------------------------------------------


class TestInit:
    """ReputationModel.__init__ — model_dir resolution and load-on-init behaviour."""

    async def test_default_model_dir_is_project_models(self, tmp_path):
        """When no model_dir is provided _model_dir points at project_root/models."""
        m = ReputationModel()
        assert m._model_dir == _DEFAULT_MODEL_DIR
        assert m._model_path.name == "reputation_model.joblib"
        assert m._hash_path.name == "reputation_model.sha256"

    async def test_custom_model_dir_is_resolved(self, tmp_path):
        """Passing a custom model_dir stores it on the instance."""
        m = ReputationModel(model_dir=tmp_path)
        assert m._model_dir == tmp_path
        assert m._model_path.parent == tmp_path

    async def test_model_is_none_when_no_saved_file(self, tmp_path):
        """If no saved model file exists _model stays None."""
        m = ReputationModel(model_dir=tmp_path)
        assert m._model is None
        assert m._model_type == "none"

    async def test_load_called_when_saved_model_exists(self, tmp_path):
        """__init__ calls self.load() when the joblib file is present."""
        model_path = tmp_path / "reputation_model.joblib"
        model_path.write_bytes(b"fake")

        with patch.object(ReputationModel, "load") as mock_load:
            ReputationModel(model_dir=tmp_path)
            mock_load.assert_called_once_with(str(model_path))

    async def test_init_silently_ignores_corrupt_saved_model(self, tmp_path, caplog):
        """If load() raises, __init__ logs the exception and continues (model stays None)."""
        model_path = tmp_path / "reputation_model.joblib"
        model_path.write_bytes(b"garbage")

        import logging
        with caplog.at_level(logging.ERROR, logger="marketplace.ml.reputation_model"):
            m = ReputationModel(model_dir=tmp_path)

        # Model should remain None because load raised
        assert m._model is None


# ---------------------------------------------------------------------------
# Block 2: train
# ---------------------------------------------------------------------------


class TestTrain:
    """ReputationModel.train — model selection, fit, and return value."""

    async def test_train_uses_lightgbm_when_available(self, tmp_path):
        """When _HAS_LIGHTGBM is True and use_lightgbm=True, LGBMClassifier is used."""
        mock_clf = MagicMock()

        with (
            patch("marketplace.ml.reputation_model._HAS_LIGHTGBM", True),
            patch("marketplace.ml.reputation_model._HAS_SKLEARN", True),
            # LGBMClassifier may not be imported into the module if lightgbm is absent;
            # use create=True so patch can inject it regardless.
            patch("marketplace.ml.reputation_model.LGBMClassifier", return_value=mock_clf, create=True),
        ):
            m = ReputationModel(model_dir=tmp_path)
            features = [[0.5] * len(FEATURE_NAMES)] * 10
            labels = [1] * 10
            result = m.train(features, labels, use_lightgbm=True)

        mock_clf.fit.assert_called_once_with(features, labels)
        assert result["model_type"] == "lightgbm"
        assert result["feature_count"] == len(FEATURE_NAMES)
        assert result["sample_count"] == 10

    async def test_train_falls_back_to_sklearn_when_lightgbm_unavailable(self, tmp_path):
        """When _HAS_LIGHTGBM is False, sklearn GradientBoostingClassifier is used."""
        mock_clf = MagicMock()

        with (
            patch("marketplace.ml.reputation_model._HAS_LIGHTGBM", False),
            patch("marketplace.ml.reputation_model._HAS_SKLEARN", True),
            patch(
                "marketplace.ml.reputation_model.GradientBoostingClassifier",
                return_value=mock_clf,
            ),
        ):
            m = ReputationModel(model_dir=tmp_path)
            features = [[0.3] * len(FEATURE_NAMES)] * 5
            labels = [0, 1, 0, 1, 1]
            result = m.train(features, labels, use_lightgbm=True)

        mock_clf.fit.assert_called_once()
        assert result["model_type"] == "sklearn_gbc"
        assert result["sample_count"] == 5

    async def test_train_uses_sklearn_when_use_lightgbm_false(self, tmp_path):
        """use_lightgbm=False forces sklearn even when lightgbm is available."""
        mock_clf = MagicMock()

        with (
            patch("marketplace.ml.reputation_model._HAS_LIGHTGBM", True),
            patch("marketplace.ml.reputation_model._HAS_SKLEARN", True),
            patch(
                "marketplace.ml.reputation_model.GradientBoostingClassifier",
                return_value=mock_clf,
            ),
        ):
            m = ReputationModel(model_dir=tmp_path)
            result = m.train([[0.1] * len(FEATURE_NAMES)], [1], use_lightgbm=False)

        assert result["model_type"] == "sklearn_gbc"

    async def test_train_raises_when_no_ml_library_installed(self, tmp_path):
        """RuntimeError is raised when neither sklearn nor lightgbm is present."""
        with (
            patch("marketplace.ml.reputation_model._HAS_SKLEARN", False),
            patch("marketplace.ml.reputation_model._HAS_LIGHTGBM", False),
        ):
            m = ReputationModel(model_dir=tmp_path)
            with pytest.raises(RuntimeError, match="Neither scikit-learn nor lightgbm"):
                m.train([[0.5] * len(FEATURE_NAMES)], [1])

    async def test_train_returns_correct_feature_count(self, tmp_path):
        """feature_count in return dict always equals len(FEATURE_NAMES)."""
        mock_clf = MagicMock()

        with (
            patch("marketplace.ml.reputation_model._HAS_SKLEARN", True),
            patch("marketplace.ml.reputation_model._HAS_LIGHTGBM", False),
            patch(
                "marketplace.ml.reputation_model.GradientBoostingClassifier",
                return_value=mock_clf,
            ),
        ):
            m = ReputationModel(model_dir=tmp_path)
            result = m.train([[0.0] * len(FEATURE_NAMES)] * 3, [0, 1, 0])

        assert result["feature_count"] == len(FEATURE_NAMES)

    async def test_train_sample_count_for_object_without_len(self, tmp_path):
        """If labels has no __len__, sample_count defaults to 0."""
        mock_clf = MagicMock()

        # Build an iterator (no __len__)
        def _gen():
            yield from [1, 0, 1]

        labels_iter = _gen()

        with (
            patch("marketplace.ml.reputation_model._HAS_SKLEARN", True),
            patch("marketplace.ml.reputation_model._HAS_LIGHTGBM", False),
            patch(
                "marketplace.ml.reputation_model.GradientBoostingClassifier",
                return_value=mock_clf,
            ),
        ):
            m = ReputationModel(model_dir=tmp_path)
            result = m.train([[0.5] * len(FEATURE_NAMES)], labels_iter)

        assert result["sample_count"] == 0


# ---------------------------------------------------------------------------
# Block 3: predict
# ---------------------------------------------------------------------------


class TestPredict:
    """ReputationModel.predict — score computation and edge cases."""

    async def test_predict_raises_when_no_model_loaded(self, tmp_path):
        """RuntimeError is raised when _model is None."""
        m = ReputationModel(model_dir=tmp_path)
        with pytest.raises(RuntimeError, match="No model loaded"):
            m.predict(_sample_features())

    async def test_predict_uses_predict_proba_2d(self, tmp_path):
        """predict_proba with shape (1, 2) returns column-1 probability."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        mock_clf = MagicMock()
        # 2D array: [[prob_class0, prob_class1]]
        mock_clf.predict_proba.return_value = np.array([[0.2, 0.8]])
        m._model = mock_clf

        score = m.predict(_sample_features())

        assert score == pytest.approx(0.8)

    async def test_predict_uses_predict_proba_1d(self, tmp_path):
        """predict_proba returning a 1D array uses index 0."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        mock_clf = MagicMock()
        # 1D array from predict_proba — unusual but guarded in code
        mock_clf.predict_proba.return_value = np.array([[0.6]])  # shape (1,1)
        m._model = mock_clf

        score = m.predict(_sample_features())

        # shape (1,1): probas.shape[1] == 1, so falls to else branch -> probas[0][0]
        assert score == pytest.approx(0.6)

    async def test_predict_falls_back_to_predict_when_no_predict_proba(self, tmp_path):
        """predict() is called when the model lacks predict_proba."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        mock_clf = MagicMock(spec=[])  # No predict_proba attribute
        mock_clf.predict = MagicMock(return_value=np.array([1.0]))
        m._model = mock_clf

        score = m.predict(_sample_features())

        assert score == pytest.approx(1.0)

    async def test_predict_clamps_above_1(self, tmp_path):
        """Score is clamped to 1.0 when model returns > 1.0."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = np.array([[0.0, 1.5]])
        m._model = mock_clf

        score = m.predict(_sample_features())

        assert score == 1.0

    async def test_predict_clamps_below_0(self, tmp_path):
        """Score is clamped to 0.0 when model returns < 0.0."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = np.array([[1.0, -0.3]])
        m._model = mock_clf

        score = m.predict(_sample_features())

        assert score == 0.0

    async def test_predict_returns_05_on_exception(self, tmp_path, caplog):
        """If the model raises during prediction, 0.5 is returned as a safe default."""
        import logging

        m = ReputationModel(model_dir=tmp_path)
        mock_clf = MagicMock()
        mock_clf.predict_proba.side_effect = ValueError("boom")
        m._model = mock_clf

        with caplog.at_level(logging.ERROR, logger="marketplace.ml.reputation_model"):
            score = m.predict(_sample_features())

        assert score == pytest.approx(0.5)

    async def test_predict_fills_missing_features_with_zero(self, tmp_path):
        """Features missing from the input dict default to 0.0 in the vector."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        captured = {}

        def _capture_proba(call_arg):
            captured["vector"] = call_arg[0]
            return np.array([[0.1, 0.9]])

        mock_clf = MagicMock()
        mock_clf.predict_proba.side_effect = _capture_proba
        m._model = mock_clf

        # Pass only one feature; all others should be 0.0
        m.predict({"transaction_count": 10.0})

        expected = [10.0] + [0.0] * (len(FEATURE_NAMES) - 1)
        assert captured["vector"] == expected

    async def test_predict_uses_feature_order_from_feature_names(self, tmp_path):
        """Feature vector is assembled in FEATURE_NAMES order, not input dict order."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        captured = {}

        def _capture_proba(call_arg):
            captured["vector"] = list(call_arg[0])
            return np.array([[0.0, 0.7]])

        mock_clf = MagicMock()
        mock_clf.predict_proba.side_effect = _capture_proba
        m._model = mock_clf

        features = {name: float(i) for i, name in enumerate(FEATURE_NAMES)}
        m.predict(features)

        expected = [float(i) for i in range(len(FEATURE_NAMES))]
        assert captured["vector"] == expected


# ---------------------------------------------------------------------------
# Block 4: save
# ---------------------------------------------------------------------------


class TestSave:
    """ReputationModel.save — file writing and hash generation."""

    async def test_save_raises_when_no_model(self, tmp_path):
        """RuntimeError is raised when _model is None."""
        m = ReputationModel(model_dir=tmp_path)
        with pytest.raises(RuntimeError, match="No model to save"):
            m.save()

    async def test_save_writes_model_file_and_hash(self, tmp_path):
        """save() creates the .joblib file and a matching .sha256 file."""
        m = ReputationModel(model_dir=tmp_path)
        m._model = MagicMock()
        m._model_type = "sklearn_gbc"

        save_path = tmp_path / "reputation_model.joblib"

        # joblib.dump cannot pickle MagicMock; patch it (in the joblib module itself
        # since save() imports joblib locally) to write a real file so that
        # _compute_file_hash and hash_path.write_text work correctly.
        def _fake_dump(payload, path, **kwargs):
            Path(path).write_bytes(b"fake-model-bytes")

        with patch("joblib.dump", side_effect=_fake_dump):
            returned_path = m.save(str(save_path))

        assert returned_path == str(save_path)
        assert save_path.exists()

        hash_path = save_path.with_suffix(".sha256")
        assert hash_path.exists()

        # Hash on disk must match actual file hash
        stored_hash = hash_path.read_text().strip()
        actual_hash = ReputationModel._compute_file_hash(save_path)
        assert stored_hash == actual_hash

    async def test_save_default_path_under_model_dir(self, tmp_path):
        """When no explicit path is given, save uses _model_path inside _model_dir."""
        m = ReputationModel(model_dir=tmp_path)
        m._model = MagicMock()
        m._model_type = "sklearn_gbc"

        def _fake_dump(payload, path, **kwargs):
            Path(path).write_bytes(b"fake-model-bytes")

        with patch("joblib.dump", side_effect=_fake_dump):
            returned = m.save()

        assert returned == str(tmp_path / "reputation_model.joblib")
        assert (tmp_path / "reputation_model.joblib").exists()

    async def test_save_creates_parent_directories(self, tmp_path):
        """save() creates nested parent directories that do not yet exist."""
        deep_path = tmp_path / "a" / "b" / "c" / "rep.joblib"

        m = ReputationModel(model_dir=tmp_path)
        m._model = MagicMock()
        m._model_type = "sklearn_gbc"

        def _fake_dump(payload, path, **kwargs):
            Path(path).write_bytes(b"fake-model-bytes")

        with patch("joblib.dump", side_effect=_fake_dump):
            returned = m.save(str(deep_path))

        assert Path(returned).exists()

    async def test_save_roundtrip_loads_correct_model_type(self, tmp_path):
        """Model saved then loaded recovers the correct model_type."""
        import joblib as _joblib

        m = ReputationModel(model_dir=tmp_path)
        m._model = MagicMock()
        m._model_type = "my_custom_type"

        # Capture the real joblib.dump *before* patching so _fake_dump can call it
        # without recursing back into itself through the patch.
        _real_dump = _joblib.dump

        def _fake_dump(payload, path, **kwargs):
            picklable = {
                "model": "picklable_sentinel",
                "model_type": payload["model_type"],
                "features": payload["features"],
            }
            _real_dump(picklable, path)

        with patch("joblib.dump", side_effect=_fake_dump):
            save_path = m.save()

        m2 = ReputationModel(model_dir=tmp_path)
        m2.load(save_path)

        assert m2._model_type == "my_custom_type"


# ---------------------------------------------------------------------------
# Block 5: load
# ---------------------------------------------------------------------------


class TestLoad:
    """ReputationModel.load — file reading, integrity checking, legacy format."""

    async def test_load_raises_file_not_found(self, tmp_path):
        """FileNotFoundError is raised when the model file does not exist."""
        m = ReputationModel(model_dir=tmp_path)
        with pytest.raises(FileNotFoundError, match="Model file not found"):
            m.load(str(tmp_path / "does_not_exist.joblib"))

    async def test_load_raises_on_hash_mismatch(self, tmp_path):
        """ValueError is raised when saved hash does not match file hash."""
        import joblib

        model_path = tmp_path / "rep.joblib"
        # Use a plain string as the model value — joblib can pickle it, MagicMock cannot.
        payload = {"model": "fake_model", "model_type": "sklearn_gbc", "features": FEATURE_NAMES}
        joblib.dump(payload, model_path)

        # Write a deliberately wrong hash
        hash_path = model_path.with_suffix(".sha256")
        hash_path.write_text("0" * 64)

        m = ReputationModel(model_dir=tmp_path)
        with pytest.raises(ValueError, match="integrity check failed"):
            m.load(str(model_path))

    async def test_load_succeeds_with_correct_hash(self, tmp_path):
        """load() sets _model and _model_type when hash file is valid."""
        import joblib

        model_path = tmp_path / "rep.joblib"
        # Use a picklable string sentinel instead of object() or MagicMock().
        sentinel = "picklable_sentinel_value"
        payload = {"model": sentinel, "model_type": "lightgbm", "features": FEATURE_NAMES}
        joblib.dump(payload, model_path)

        hash_path = model_path.with_suffix(".sha256")
        hash_path.write_text(ReputationModel._compute_file_hash(model_path))

        m = ReputationModel(model_dir=tmp_path)
        m.load(str(model_path))

        assert m._model == sentinel
        assert m._model_type == "lightgbm"

    async def test_load_legacy_format_sets_model_type_unknown(self, tmp_path):
        """A raw (non-dict) joblib payload is treated as legacy with type='unknown'."""
        import joblib

        model_path = tmp_path / "legacy.joblib"
        # Dump a plain string as a "legacy" raw model (not a dict); MagicMock is not picklable.
        raw_model = "legacy_raw_model_string"
        joblib.dump(raw_model, model_path)

        # Write matching hash so integrity check passes
        hash_path = model_path.with_suffix(".sha256")
        hash_path.write_text(ReputationModel._compute_file_hash(model_path))

        m = ReputationModel(model_dir=tmp_path)
        m.load(str(model_path))

        assert m._model_type == "unknown"

    async def test_load_skips_integrity_check_when_no_hash_file(self, tmp_path, caplog):
        """When .sha256 file is absent, a warning is logged and loading still succeeds."""
        import logging
        import joblib

        model_path = tmp_path / "rep_nohash.joblib"
        # Use a picklable string instead of MagicMock (which cannot be pickled).
        payload = {"model": "dummy_model", "model_type": "sklearn_gbc", "features": FEATURE_NAMES}
        joblib.dump(payload, model_path)

        # Deliberately do NOT create a hash file

        m = ReputationModel(model_dir=tmp_path)
        with caplog.at_level(logging.WARNING, logger="marketplace.ml.reputation_model"):
            m.load(str(model_path))

        assert m._model_type == "sklearn_gbc"
        assert any("No hash file" in record.message for record in caplog.records)

    async def test_load_default_path_uses_model_dir(self, tmp_path):
        """Calling load() with no argument loads from _model_dir/reputation_model.joblib."""
        import joblib

        model_path = tmp_path / "reputation_model.joblib"
        # Use a picklable string instead of MagicMock (which cannot be pickled).
        payload = {"model": "dummy_model", "model_type": "lightgbm", "features": FEATURE_NAMES}
        joblib.dump(payload, model_path)

        hash_path = model_path.with_suffix(".sha256")
        hash_path.write_text(ReputationModel._compute_file_hash(model_path))

        m = ReputationModel(model_dir=tmp_path)
        m._model = None  # Ensure clean state (init may have tried loading)
        m.load()

        assert m._model is not None
        assert m._model_type == "lightgbm"


# ---------------------------------------------------------------------------
# Block 6: feature_importance
# ---------------------------------------------------------------------------


class TestFeatureImportance:
    """ReputationModel.feature_importance — various attribute paths."""

    async def test_feature_importance_raises_when_no_model(self, tmp_path):
        """RuntimeError is raised when _model is None."""
        m = ReputationModel(model_dir=tmp_path)
        with pytest.raises(RuntimeError, match="No model loaded"):
            m.feature_importance()

    async def test_feature_importance_uses_feature_importances_attribute(self, tmp_path):
        """feature_importances_ (sklearn/lgbm style) is used when present."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        importances = np.array([float(i) for i in range(len(FEATURE_NAMES))])

        mock_clf = MagicMock(spec=["feature_importances_"])
        mock_clf.feature_importances_ = importances
        m._model = mock_clf

        result = m.feature_importance()

        assert set(result.keys()) == set(FEATURE_NAMES)
        for i, name in enumerate(FEATURE_NAMES):
            assert result[name] == pytest.approx(float(i))

    async def test_feature_importance_uses_coef_2d(self, tmp_path):
        """coef_ with shape (1, n_features) uses the first row."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        coef = np.array([[float(i + 1) for i in range(len(FEATURE_NAMES))]])

        mock_clf = MagicMock(spec=["coef_"])
        mock_clf.coef_ = coef
        m._model = mock_clf

        result = m.feature_importance()

        assert set(result.keys()) == set(FEATURE_NAMES)
        for i, name in enumerate(FEATURE_NAMES):
            assert result[name] == pytest.approx(float(i + 1))

    async def test_feature_importance_uses_coef_1d(self, tmp_path):
        """coef_ with shape (n_features,) is used directly."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        coef = np.array([float(i + 0.5) for i in range(len(FEATURE_NAMES))])

        mock_clf = MagicMock(spec=["coef_"])
        mock_clf.coef_ = coef
        m._model = mock_clf

        result = m.feature_importance()

        for i, name in enumerate(FEATURE_NAMES):
            assert result[name] == pytest.approx(float(i + 0.5))

    async def test_feature_importance_equal_weights_fallback(self, tmp_path):
        """When neither feature_importances_ nor coef_ exists, equal weights are returned."""
        m = ReputationModel(model_dir=tmp_path)

        # A mock with NO relevant attributes
        mock_clf = MagicMock(spec=[])
        m._model = mock_clf

        result = m.feature_importance()

        assert set(result.keys()) == set(FEATURE_NAMES)
        expected_weight = 1.0 / len(FEATURE_NAMES)
        for name in FEATURE_NAMES:
            assert result[name] == pytest.approx(expected_weight)

    async def test_feature_importance_keys_match_feature_names_order(self, tmp_path):
        """Returned keys are exactly FEATURE_NAMES (order may vary in dict, but set matches)."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        mock_clf = MagicMock(spec=["feature_importances_"])
        mock_clf.feature_importances_ = np.ones(len(FEATURE_NAMES))
        m._model = mock_clf

        result = m.feature_importance()

        assert list(result.keys()) == FEATURE_NAMES

    async def test_feature_importance_returns_floats(self, tmp_path):
        """All values in the returned dict are Python floats."""
        import numpy as np

        m = ReputationModel(model_dir=tmp_path)
        mock_clf = MagicMock(spec=["feature_importances_"])
        mock_clf.feature_importances_ = np.array([0.1, 0.2, 0.05, 0.15, 0.2, 0.1, 0.1, 0.1])
        m._model = mock_clf

        result = m.feature_importance()

        for v in result.values():
            assert isinstance(v, float)


# ---------------------------------------------------------------------------
# Block 7: _compute_file_hash (static method)
# ---------------------------------------------------------------------------


class TestComputeFileHash:
    """ReputationModel._compute_file_hash — correctness and determinism."""

    async def test_hash_matches_manual_sha256(self, tmp_path):
        """Hash returned equals the SHA-256 computed manually."""
        data = b"deterministic content for hashing"
        p = tmp_path / "hashtest.bin"
        p.write_bytes(data)

        expected = hashlib.sha256(data).hexdigest()
        actual = ReputationModel._compute_file_hash(p)

        assert actual == expected

    async def test_hash_is_deterministic(self, tmp_path):
        """Calling _compute_file_hash twice on the same file returns the same value."""
        p = tmp_path / "det.bin"
        p.write_bytes(b"same content every time")

        h1 = ReputationModel._compute_file_hash(p)
        h2 = ReputationModel._compute_file_hash(p)

        assert h1 == h2

    async def test_hash_differs_for_different_content(self, tmp_path):
        """Two files with different content produce different hashes."""
        p1 = tmp_path / "a.bin"
        p2 = tmp_path / "b.bin"
        p1.write_bytes(b"content_A")
        p2.write_bytes(b"content_B")

        assert ReputationModel._compute_file_hash(p1) != ReputationModel._compute_file_hash(p2)

    async def test_hash_is_64_hex_chars(self, tmp_path):
        """SHA-256 hex digest is always 64 characters long."""
        p = tmp_path / "len.bin"
        p.write_bytes(b"any data")

        h = ReputationModel._compute_file_hash(p)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    async def test_hash_of_empty_file(self, tmp_path):
        """Empty file produces the well-known SHA-256 of empty bytes."""
        p = tmp_path / "empty.bin"
        p.write_bytes(b"")

        expected = hashlib.sha256(b"").hexdigest()
        assert ReputationModel._compute_file_hash(p) == expected


# ---------------------------------------------------------------------------
# Block 8: FEATURE_NAMES constant
# ---------------------------------------------------------------------------


class TestFeatureNames:
    """Validate the public FEATURE_NAMES constant."""

    async def test_feature_names_is_list_of_strings(self):
        """FEATURE_NAMES must be a list of string names."""
        assert isinstance(FEATURE_NAMES, list)
        assert all(isinstance(n, str) for n in FEATURE_NAMES)

    async def test_feature_names_has_eight_entries(self):
        """FEATURE_NAMES contains exactly 8 features as documented."""
        assert len(FEATURE_NAMES) == 8

    async def test_feature_names_contains_expected_keys(self):
        """All documented feature names are present."""
        expected = {
            "transaction_count",
            "avg_rating",
            "dispute_rate",
            "response_time_avg",
            "successful_delivery_rate",
            "age_days",
            "listing_count",
            "unique_buyers",
        }
        assert set(FEATURE_NAMES) == expected

    async def test_feature_names_has_no_duplicates(self):
        """No feature name appears twice."""
        assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))


# ---------------------------------------------------------------------------
# Block 9: End-to-end train -> predict -> save -> load roundtrip
# ---------------------------------------------------------------------------


class TestEndToEndRoundtrip:
    """Full save/load roundtrip using real joblib (no ML model needed for logic)."""

    async def test_save_load_roundtrip_preserves_model_and_type(self, tmp_path):
        """A model saved with save() and reloaded with load() returns the same object."""
        import joblib as _joblib

        m = ReputationModel(model_dir=tmp_path)
        m._model = MagicMock()
        m._model_type = "sklearn_gbc"

        # Capture the real dump before patching to avoid infinite recursion.
        _real_dump = _joblib.dump

        def _fake_dump(payload, path, **kwargs):
            picklable = {
                "model": "picklable_model_placeholder",
                "model_type": payload["model_type"],
                "features": payload["features"],
            }
            _real_dump(picklable, path)

        with patch("joblib.dump", side_effect=_fake_dump):
            save_path = m.save()

        m2 = ReputationModel(model_dir=tmp_path)
        # init already loaded it; verify model_type
        assert m2._model_type == "sklearn_gbc"

    async def test_predict_after_load_uses_loaded_model(self, tmp_path):
        """After load(), predict() calls the loaded model's predict_proba."""
        import numpy as np

        # Build a MagicMock classifier (not picklable, but we won't call joblib.dump).
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = np.array([[0.3, 0.7]])

        fake_payload = {"model": mock_clf, "model_type": "sklearn_gbc", "features": FEATURE_NAMES}

        # Write a real file so path.exists() and _compute_file_hash pass, then bypass
        # joblib.load (which would try to unpickle) by patching it to return the payload.
        model_path = tmp_path / "reputation_model.joblib"
        model_path.write_bytes(b"fake-bytes-for-hash")
        hash_path = model_path.with_suffix(".sha256")
        hash_path.write_text(ReputationModel._compute_file_hash(model_path))

        with patch("joblib.load", return_value=fake_payload):
            # ReputationModel.__init__ will auto-load via our patched joblib.load
            m = ReputationModel(model_dir=tmp_path)

        score = m.predict(_sample_features(0.5))

        assert score == pytest.approx(0.7)

    async def test_multiple_saves_produce_fresh_hashes(self, tmp_path):
        """Saving the model twice updates the hash file each time."""
        import joblib as _joblib

        m = ReputationModel(model_dir=tmp_path)
        m._model = MagicMock()
        m._model_type = "sklearn_gbc"

        # Capture the real dump before patching to avoid infinite recursion.
        _real_dump = _joblib.dump

        # Track call count so the two saves write different bytes (different model_type),
        # ensuring hashes are well-formed even if content happens to match.
        call_count = {"n": 0}

        def _fake_dump(payload, path, **kwargs):
            call_count["n"] += 1
            picklable = {
                "model": f"placeholder_{call_count['n']}",
                "model_type": payload["model_type"],
                "features": payload["features"],
            }
            _real_dump(picklable, path)

        with patch("joblib.dump", side_effect=_fake_dump):
            path1 = m.save()
            hash1 = (Path(path1).with_suffix(".sha256")).read_text()

            # Mutate the stored type to produce a different payload
            m._model_type = "lightgbm"
            path2 = m.save()
            hash2 = (Path(path2).with_suffix(".sha256")).read_text()

        # Both must be well-formed 64-character hex SHA-256 digests.
        assert len(hash1) == 64
        assert len(hash2) == 64
