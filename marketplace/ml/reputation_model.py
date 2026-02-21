"""Reputation ML model wrapper — trains and predicts agent reputation scores.

Uses GradientBoostingClassifier from scikit-learn or LGBMClassifier from
lightgbm when available.  Falls back gracefully when neither is installed.
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful import of ML libraries
# ---------------------------------------------------------------------------
_HAS_SKLEARN = False
_HAS_LIGHTGBM = False

try:
    from sklearn.ensemble import GradientBoostingClassifier  # type: ignore[import]

    _HAS_SKLEARN = True
except ImportError:
    logger.info("scikit-learn is not installed — ReputationModel ML training unavailable.")

try:
    from lightgbm import LGBMClassifier  # type: ignore[import]

    _HAS_LIGHTGBM = True
except ImportError:
    logger.info("lightgbm is not installed — LGBMClassifier unavailable, will use sklearn if present.")


# Default model storage directory (project_root/models/)
_DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"

# Feature names in the expected order
FEATURE_NAMES = [
    "transaction_count",
    "avg_rating",
    "dispute_rate",
    "response_time_avg",
    "successful_delivery_rate",
    "age_days",
    "listing_count",
    "unique_buyers",
]


class ReputationModel:
    """Wrapper around an ML model for agent reputation prediction.

    Supports training, prediction, saving, loading, and feature importance.
    Attempts to load a saved model on initialisation from the models/ directory.
    """

    def __init__(self, model_dir: str | Path | None = None) -> None:
        """Initialise the reputation model.

        Args:
            model_dir: Directory containing saved models. Defaults to project_root/models/.
        """
        self._model: Any = None
        self._model_type: str = "none"
        self._model_dir = Path(model_dir) if model_dir else _DEFAULT_MODEL_DIR
        self._model_path = self._model_dir / "reputation_model.pkl"

        # Try to load a saved model on init
        if self._model_path.exists():
            try:
                self.load(str(self._model_path))
            except Exception:
                logger.exception("Failed to load saved reputation model from %s", self._model_path)

    def train(
        self,
        features_df: Any,
        labels: Any,
        use_lightgbm: bool = True,
    ) -> dict[str, Any]:
        """Train a reputation model on the provided features and labels.

        Args:
            features_df: A pandas DataFrame or 2D array-like of features.
                         Columns should match FEATURE_NAMES.
            labels: Binary labels (0=bad, 1=good) or continuous labels.
            use_lightgbm: Prefer LGBMClassifier if available.

        Returns:
            Dict with training summary (model_type, feature_count, sample_count).

        Raises:
            RuntimeError: If neither scikit-learn nor lightgbm is available.
        """
        if not _HAS_SKLEARN and not _HAS_LIGHTGBM:
            raise RuntimeError(
                "Neither scikit-learn nor lightgbm is installed. "
                "Install at least one: pip install scikit-learn lightgbm"
            )

        sample_count = len(labels) if hasattr(labels, "__len__") else 0

        if use_lightgbm and _HAS_LIGHTGBM:
            self._model = LGBMClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                num_leaves=31,
                random_state=42,
                verbose=-1,
            )
            self._model_type = "lightgbm"
        elif _HAS_SKLEARN:
            self._model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
            )
            self._model_type = "sklearn_gbc"
        else:
            raise RuntimeError("No ML library available for training.")

        self._model.fit(features_df, labels)
        logger.info(
            "Trained %s reputation model on %d samples with %d features.",
            self._model_type,
            sample_count,
            len(FEATURE_NAMES),
        )

        return {
            "model_type": self._model_type,
            "feature_count": len(FEATURE_NAMES),
            "sample_count": sample_count,
        }

    def predict(self, features: dict[str, float]) -> float:
        """Predict a reputation score (0.0-1.0) for a single agent.

        Args:
            features: Dict of feature name -> value matching FEATURE_NAMES.

        Returns:
            Predicted reputation score between 0.0 and 1.0.

        Raises:
            RuntimeError: If no model has been trained or loaded.
        """
        if self._model is None:
            raise RuntimeError("No model loaded. Train or load a model first.")

        # Build feature vector in the correct order
        feature_vector = [features.get(name, 0.0) for name in FEATURE_NAMES]

        try:
            # Use predict_proba if available (returns probability of positive class)
            if hasattr(self._model, "predict_proba"):
                probas = self._model.predict_proba([feature_vector])
                # Return probability of class 1 (good reputation)
                if hasattr(probas, "shape") and len(probas.shape) > 1 and probas.shape[1] > 1:
                    score = float(probas[0][1])
                else:
                    score = float(probas[0][0])
            else:
                # Fall back to predict (returns class label)
                pred = self._model.predict([feature_vector])
                score = float(pred[0])
        except Exception:
            logger.exception("Prediction failed — returning 0.5 as default.")
            score = 0.5

        return max(0.0, min(1.0, score))

    def save(self, path: str | None = None) -> str:
        """Save the trained model to disk.

        Args:
            path: File path to save to. Defaults to models/reputation_model.pkl.

        Returns:
            The path where the model was saved.

        Raises:
            RuntimeError: If no model is loaded.
        """
        if self._model is None:
            raise RuntimeError("No model to save. Train a model first.")

        save_path = Path(path) if path else self._model_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "wb") as f:
            pickle.dump(
                {
                    "model": self._model,
                    "model_type": self._model_type,
                    "features": FEATURE_NAMES,
                },
                f,
            )

        logger.info("Saved reputation model to %s", save_path)
        return str(save_path)

    def load(self, path: str | None = None) -> None:
        """Load a model from disk.

        Args:
            path: File path to load from. Defaults to models/reputation_model.pkl.

        Raises:
            FileNotFoundError: If the model file does not exist.
        """
        load_path = Path(path) if path else self._model_path

        if not load_path.exists():
            raise FileNotFoundError(f"Model file not found: {load_path}")

        with open(load_path, "rb") as f:
            data = pickle.load(f)  # noqa: S301

        if isinstance(data, dict):
            self._model = data.get("model")
            self._model_type = data.get("model_type", "unknown")
        else:
            # Legacy format: raw model object
            self._model = data
            self._model_type = "unknown"

        logger.info("Loaded reputation model (%s) from %s", self._model_type, load_path)

    def feature_importance(self) -> dict[str, float]:
        """Return feature importances from the trained model.

        Returns:
            Dict mapping feature names to their importance scores.

        Raises:
            RuntimeError: If no model is loaded.
        """
        if self._model is None:
            raise RuntimeError("No model loaded. Train or load a model first.")

        importances: list[float] = []

        if hasattr(self._model, "feature_importances_"):
            importances = [float(x) for x in self._model.feature_importances_]
        elif hasattr(self._model, "coef_"):
            coef = self._model.coef_
            if hasattr(coef, "shape") and len(coef.shape) > 1:
                importances = [float(x) for x in coef[0]]
            else:
                importances = [float(x) for x in coef]
        else:
            # Return equal weights as fallback
            importances = [1.0 / len(FEATURE_NAMES)] * len(FEATURE_NAMES)

        return dict(zip(FEATURE_NAMES, importances))
