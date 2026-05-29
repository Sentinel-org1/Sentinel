"""
Jensen-Shannon Divergence detector for categorical/discrete features.
Symmetric variant of Kullback-Leibler divergence.

JS_div(P, Q) = 0.5 × KL(P||M) + 0.5 × KL(Q||M)
where M = 0.5 × (P + Q) is the mixture distribution

Interpretation:
  - JS_div < 0.05: No significant shift
  - 0.05 ≤ JS_div < 0.15: Small shift
  - JS_div ≥ 0.15: Significant shift (drift alert)

Ideal for categorical features with limited unique values.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial.distance import jensenshannon
from app.detectors.base import BaseDetector


class JSDetector(BaseDetector):
    """Jensen-Shannon divergence detector for batch drift.

    Best used for categorical or discrete features.
    """

    def __init__(self, min_samples: int = 50):
        """
        Args:
            min_samples: Minimum samples required for distribution estimation
        """
        self.min_samples = min_samples
        self.baseline_dist = None
        self.categories = None
        self.feature_name = None

    def fit(self, baseline: np.ndarray, feature_name: str = "feature") -> None:
        """
        Fit categorical distribution from baseline.

        Args:
            baseline: 1D array of baseline feature values (typically categorical/discrete)
            feature_name: Name of the feature (for logging)
        """
        if len(baseline) < self.min_samples:
            raise ValueError(f"baseline requires ≥{self.min_samples} samples, got {len(baseline)}")

        self.feature_name = feature_name

        # Get unique categories and their frequencies
        unique, counts = np.unique(baseline, return_counts=True)
        self.categories = unique
        self.baseline_dist = counts / len(baseline)

    def score(self, current: np.ndarray) -> float:
        """
        Compute Jensen-Shannon divergence between baseline and current distributions.

        Args:
            current: 1D array of current feature values

        Returns:
            JS divergence score (0 = identical, 1 = completely different)
        """
        if self.baseline_dist is None or self.categories is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        if len(current) < self.min_samples:
            raise ValueError(f"current requires ≥{self.min_samples} samples, got {len(current)}")

        # Get current distribution
        unique, counts = np.unique(current, return_counts=True)
        current_dist = np.zeros(len(self.categories))

        # Map counts to baseline categories
        for cat, cnt in zip(unique, counts):
            idx = np.where(self.categories == cat)[0]
            if len(idx) > 0:
                current_dist[idx] = cnt / len(current)

        # Compute Jensen-Shannon divergence
        js_div = float(jensenshannon(self.baseline_dist, current_dist))
        return js_div
