#!/usr/bin/env python3
"""Offline training pipeline for the AgentChains reputation ML model.

Usage:
    python scripts/train_reputation_model.py [--data <path>] [--output <path>] [--use-lightgbm]

Generates synthetic training data when no CSV is provided, trains the model,
evaluates on a held-out split, and saves to ``models/reputation_model.pkl``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from marketplace.ml.reputation_model import FEATURE_NAMES, ReputationModel  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

_RNG = np.random.default_rng(42)


def _generate_synthetic_data(n_samples: int = 5000) -> tuple[np.ndarray, np.ndarray]:
    """Create synthetic reputation training data.

    Returns:
        (features, labels) — features shape (n_samples, 8), labels shape (n_samples,)
    """
    features = np.column_stack(
        [
            _RNG.integers(0, 500, size=n_samples),           # transaction_count
            _RNG.uniform(1.0, 5.0, size=n_samples),          # avg_rating
            _RNG.uniform(0.0, 0.3, size=n_samples),          # dispute_rate
            _RNG.uniform(0.5, 48.0, size=n_samples),         # response_time_avg (hours)
            _RNG.uniform(0.5, 1.0, size=n_samples),          # successful_delivery_rate
            _RNG.integers(1, 1000, size=n_samples),           # age_days
            _RNG.integers(0, 50, size=n_samples),             # listing_count
            _RNG.integers(0, 200, size=n_samples),            # unique_buyers
        ]
    )

    # Label heuristic: good agents have high rating, low disputes, high delivery
    score = (
        0.30 * (features[:, 1] / 5.0)               # avg_rating
        + 0.25 * (1.0 - features[:, 2] / 0.3)       # inverse dispute_rate
        + 0.20 * features[:, 4]                      # successful_delivery_rate
        + 0.10 * np.clip(features[:, 0] / 500, 0, 1)  # transaction_count
        + 0.10 * (1.0 - np.clip(features[:, 3] / 48, 0, 1))  # inverse response_time
        + 0.05 * np.clip(features[:, 5] / 1000, 0, 1)  # age_days
    )
    labels = (score >= 0.55).astype(int)

    logger.info(
        "Generated %d synthetic samples — %d positive (%.1f%%), %d negative (%.1f%%)",
        n_samples,
        labels.sum(),
        100 * labels.mean(),
        n_samples - labels.sum(),
        100 * (1 - labels.mean()),
    )
    return features, labels


def _load_csv_data(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Load training data from a CSV file.

    Expects columns matching FEATURE_NAMES plus a ``label`` column.
    """
    try:
        import pandas as pd  # type: ignore[import]
    except ImportError:
        logger.error("pandas is required to load CSV data: pip install pandas")
        sys.exit(1)

    df = pd.read_csv(path)
    missing = [c for c in FEATURE_NAMES if c not in df.columns]
    if missing:
        logger.error("CSV is missing columns: %s", missing)
        sys.exit(1)
    if "label" not in df.columns:
        logger.error("CSV is missing 'label' column")
        sys.exit(1)

    features = df[FEATURE_NAMES].values
    labels = df["label"].values
    logger.info("Loaded %d rows from %s", len(labels), path)
    return features, labels


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def train(
    data_path: str | None = None,
    output_path: str | None = None,
    use_lightgbm: bool = True,
) -> None:
    """Run the full training pipeline."""

    # Load data
    if data_path:
        features, labels = _load_csv_data(data_path)
    else:
        logger.info("No data file provided — generating synthetic training data.")
        features, labels = _generate_synthetic_data()

    # Train/test split (80/20)
    n_train = int(len(labels) * 0.8)
    indices = _RNG.permutation(len(labels))
    train_idx, test_idx = indices[:n_train], indices[n_train:]

    X_train, y_train = features[train_idx], labels[train_idx]
    X_test, y_test = features[test_idx], labels[test_idx]

    logger.info("Train set: %d samples, Test set: %d samples", len(y_train), len(y_test))

    # Train
    model = ReputationModel()
    summary = model.train(X_train, y_train, use_lightgbm=use_lightgbm)
    logger.info("Training summary: %s", summary)

    # Evaluate
    correct = 0
    for i, idx in enumerate(test_idx):
        feat_dict = dict(zip(FEATURE_NAMES, features[idx]))
        pred_score = model.predict(feat_dict)
        pred_label = 1 if pred_score >= 0.5 else 0
        if pred_label == labels[idx]:
            correct += 1

    accuracy = correct / len(test_idx) if len(test_idx) > 0 else 0.0
    logger.info("Test accuracy: %.4f (%d/%d)", accuracy, correct, len(test_idx))

    # Feature importance
    importance = model.feature_importance()
    logger.info("Feature importances:")
    for name, imp in sorted(importance.items(), key=lambda x: -x[1]):
        logger.info("  %-28s %.4f", name, imp)

    # Save
    save_path = model.save(output_path)
    logger.info("Model saved to %s", save_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the AgentChains reputation model")
    parser.add_argument("--data", type=str, default=None, help="Path to CSV training data")
    parser.add_argument("--output", type=str, default=None, help="Output path for the model pickle")
    parser.add_argument(
        "--use-lightgbm",
        action="store_true",
        default=True,
        help="Prefer LightGBM over scikit-learn (default: True)",
    )
    parser.add_argument(
        "--no-lightgbm",
        action="store_true",
        default=False,
        help="Force scikit-learn GradientBoostingClassifier",
    )
    args = parser.parse_args()

    use_lgbm = args.use_lightgbm and not args.no_lightgbm
    train(data_path=args.data, output_path=args.output, use_lightgbm=use_lgbm)


if __name__ == "__main__":
    main()
