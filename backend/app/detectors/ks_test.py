"""
Kolmogorov-Smirnov (KS) Test detector.
Compares empirical CDFs of baseline and current distributions.

KS statistic = max|F_baseline(x) - F_current(x)|

Interpretation:
  - KS < 0.1: No significant shift
  - 0.1 ≤ KS < 0.2: Small shift
  - KS ≥ 0.2: Significant shift (drift alert)

Non-parametric, works with any univariate distribution.
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from app.detectors.base import BaseDetector


class KSDetector(BaseDetector):
    """KS-test drift detector for batch drift.

    Compares empirical cumulative distribution functions (CDFs).
    """

    def __init__(self, min_samples: int = 50):
        """
        Args:
            min_samples: Minimum samples required for statistical validity
        """
        self.min_samples = min_samples
        self.baseline = None
        self.feature_name = None

    def fit(self, baseline: np.ndarray, feature_name: str = "feature") -> None:
        """
        Store baseline distribution.

        Args:
            baseline: 1D array of baseline feature values
            feature_name: Name of the feature (for logging)
        """
        if len(baseline) < self.min_samples:
            raise ValueError(f"baseline requires ≥{self.min_samples} samples, got {len(baseline)}")

        self.baseline = baseline.copy()
        self.feature_name = feature_name

    def score(self, current: np.ndarray) -> float:
        """
        Compute KS statistic between baseline and current CDFs.

        Args:
            current: 1D array of current feature values

        Returns:
            KS statistic (0 = identical, 1 = completely different)
        """
        if self.baseline is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        if len(current) < self.min_samples:
            raise ValueError(f"current requires ≥{self.min_samples} samples, got {len(current)}")

        ks_stat, _ = stats.ks_2samp(self.baseline, current)
        return float(ks_stat)
