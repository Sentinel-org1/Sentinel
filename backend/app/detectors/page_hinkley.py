"""
Page-Hinkley Test sequential detector.
Online change point detection with forgetting factor for non-stationary environments.

M_t = Σ (x_i - μ_ref - ε)
U_t = M_t - min(M_1...M_t)

When U_t > threshold → drift detected

Parameters:
  - epsilon (ε): drift sensitivity (typically 0.5 × σ)
  - threshold (λ): decision threshold (typically 5 × σ)
  - forgetting_factor (α): for updating reference statistics (0 < α ≤ 1, default 0.95)
"""
from __future__ import annotations

import numpy as np
from app.detectors.base import BaseDetector


class PageHinkleyDetector(BaseDetector):
    """Page-Hinkley sequential detector for streaming drift.

    Adaptive detector with forgetting factor for non-stationary targets.
    """

    def __init__(
        self,
        epsilon_multiplier: float = 0.5,
        threshold_multiplier: float = 5.0,
        forgetting_factor: float = 0.95,
    ):
        """
        Args:
            epsilon_multiplier: ε = epsilon_multiplier × σ (sensitivity, default 0.5)
            threshold_multiplier: λ = threshold_multiplier × σ (default 5.0)
            forgetting_factor: α for updating reference (default 0.95, higher = slower adaptation)
        """
        self.epsilon_multiplier = epsilon_multiplier
        self.threshold_multiplier = threshold_multiplier
        self.forgetting_factor = forgetting_factor

        self.baseline_mean = None
        self.baseline_std = None
        self.epsilon = None
        self.threshold = None
        self.m_t = 0.0  # Cumulative sum
        self.m_min = 0.0  # Running minimum of M_t

    def fit(self, baseline: np.ndarray, feature_name: str = "feature") -> None:
        """
        Fit Page-Hinkley to baseline statistics.

        Args:
            baseline: 1D array of baseline values
            feature_name: Name of the feature (for logging)
        """
        self.baseline_mean = float(np.mean(baseline))
        self.baseline_std = float(np.std(baseline))

        self.epsilon = self.epsilon_multiplier * self.baseline_std
        self.threshold = self.threshold_multiplier * self.baseline_std

        self.m_t = 0.0
        self.m_min = 0.0

    def score(self, current: np.ndarray) -> float:
        """
        Update Page-Hinkley with new observations.
        Returns the maximum U_t (detection statistic) reached.

        Args:
            current: 1D array of new observations

        Returns:
            Maximum U_t score (0 = no drift, >threshold = significant drift)
        """
        if self.baseline_mean is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        max_u_t = 0.0

        for obs in current:
            # Update cumulative sum: M_t += (x_t - μ - ε)
            self.m_t += obs - self.baseline_mean - self.epsilon

            # Update running minimum
            if self.m_t < self.m_min:
                self.m_min = self.m_t

            # Detection statistic: U_t = M_t - min(M_1...M_t)
            u_t = self.m_t - self.m_min
            max_u_t = max(max_u_t, u_t)

            # Adaptive forgetting: gradually update reference mean with new observations
            # This makes the detector less sensitive to slow concept drift
            delta = obs - self.baseline_mean
            self.baseline_mean += (1 - self.forgetting_factor) * delta

        return max_u_t
