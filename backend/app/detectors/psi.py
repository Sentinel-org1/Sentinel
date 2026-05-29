"""
Population Stability Index (PSI) detector.
Measures shift in univariate distributions via histogram divergence.

PSI = Σ (A_i - E_i) × ln(A_i / E_i)
where A_i = actual % in bin i, E_i = expected % in bin i

Interpretation:
  - PSI < 0.1: No significant shift
  - 0.1 ≤ PSI < 0.25: Small shift
  - PSI ≥ 0.25: Significant shift (drift alert)
"""
from __future__ import annotations

import numpy as np
from app.detectors.base import BaseDetector


class PSIDetector(BaseDetector):
    """Population Stability Index detector for batch drift."""

    def __init__(self, n_bins: int = 10, min_samples: int = 50):
        """
        Args:
            n_bins: Number of histogram bins for distribution
            min_samples: Minimum samples required in current window
        """
        self.n_bins = n_bins
        self.min_samples = min_samples
        self.bin_edges = None
        self.baseline_dist = None
        self.feature_name = None

    def fit(self, baseline: np.ndarray, feature_name: str = "feature") -> None:
        """
        Fit histogram bins and baseline distribution.

        Args:
            baseline: 1D array of baseline feature values
            feature_name: Name of the feature (for logging)
        """
        if len(baseline) < self.min_samples:
            raise ValueError(f"baseline requires ≥{self.min_samples} samples, got {len(baseline)}")

        self.feature_name = feature_name
        # Create bins from baseline percentiles
        self.bin_edges = np.percentile(
            baseline,
            np.linspace(0, 100, self.n_bins + 1)
        )
        # Avoid duplicate edges (important for low-cardinality features)
        self.bin_edges = np.unique(self.bin_edges)
        self.n_bins = len(self.bin_edges) - 1

        # Compute baseline distribution
        baseline_counts, _ = np.histogram(baseline, bins=self.bin_edges)
        self.baseline_dist = baseline_counts / len(baseline)

    def score(self, current: np.ndarray) -> float:
        """
        Compute PSI between baseline and current distributions.

        Args:
            current: 1D array of current feature values

        Returns:
            PSI score (0 = no shift, >0.25 = significant shift)
        """
        if self.baseline_dist is None or self.bin_edges is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        if len(current) < self.min_samples:
            raise ValueError(f"current requires ≥{self.min_samples} samples, got {len(current)}")

        current_counts, _ = np.histogram(current, bins=self.bin_edges)
        current_dist = current_counts / len(current)

        # Avoid log(0) by adding small epsilon
        epsilon = 1e-10
        baseline_safe = np.maximum(self.baseline_dist, epsilon)
        current_safe = np.maximum(current_dist, epsilon)

        psi = np.sum((current_safe - baseline_safe) * np.log(current_safe / baseline_safe))
        return float(psi)
