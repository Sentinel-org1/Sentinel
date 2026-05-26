"""
Isolation Forest anomaly detector.
Detects anomalous predictions (outliers) in multivariate feature space.

Anomaly score: the average path length to isolate a point in random trees.
Lower scores = more anomalous (easier to isolate).

Interpretation:
  - anomaly_score > -0.1: Normal (most predictions)
  - -0.1 ≥ anomaly_score > -0.2: Potential outlier
  - anomaly_score ≤ -0.2: Strong anomaly (alert)
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from app.detectors.base import BaseDetector


class IForestDetector(BaseDetector):
    """Isolation Forest detector for multivariate anomalies.

    Efficient anomaly detection in high-dimensional feature space.
    Uses random forests to isolate anomalies.
    """

    def __init__(self, contamination: float = 0.05, n_estimators: int = 100, random_state: int = 42):
        """
        Args:
            contamination: Expected proportion of anomalies (0 < contamination < 1)
            n_estimators: Number of isolation trees (default 100)
            random_state: Random seed for reproducibility
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.iforest = None
        self.feature_names = None

    def fit(self, baseline: np.ndarray, feature_names: list[str] | None = None) -> None:
        """
        Train IsolationForest on baseline data.

        Args:
            baseline: 2D array of shape (n_samples, n_features) or 1D array
            feature_names: Optional list of feature names
        """
        if baseline.ndim == 1:
            baseline = baseline.reshape(-1, 1)

        if len(baseline) < 50:
            raise ValueError(f"baseline requires ≥50 samples, got {len(baseline)}")

        self.feature_names = feature_names or [f"feature_{i}" for i in range(baseline.shape[1])]

        # Train IsolationForest
        self.iforest = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.iforest.fit(baseline)

    def score(self, current: np.ndarray) -> float | np.ndarray:
        """
        Compute anomaly scores for current predictions.

        Args:
            current: 2D array of shape (n_samples, n_features) or 1D array

        Returns:
            If input is 2D: array of anomaly scores (negative values = anomalies)
            If input is 1D: single float score
        """
        if self.iforest is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        is_1d = current.ndim == 1
        if is_1d:
            current = current.reshape(-1, 1)

        # score_samples returns negative values for anomalies
        scores = self.iforest.score_samples(current)
        
        # Return mean score if batch (matching original behavior)
        return float(np.mean(scores)) if len(scores) > 1 else float(scores[0])
