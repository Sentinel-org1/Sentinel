"""
CUSUM (Cumulative Sum Control Chart) sequential detector.
Online drift detection for streaming predictions.

C_t = max(0, C_{t-1} + x_t - μ_ref - k)
where μ_ref = reference mean, k = slack parameter, h = decision threshold

When C_t > h → drift detected

Parameters:
  - slack_parameter (k): typically 0.5 × std_dev (tunable)
  - threshold (h): typically 5 × std_dev (tunable)
"""
from __future__ import annotations

import numpy as np
from app.detectors.base import BaseDetector


class CUSUMDetector(BaseDetector):
    """CUSUM sequential detector for streaming drift."""

    def __init__(self, slack_param_multiplier: float = 0.5, threshold_multiplier: float = 5.0):
        """
        Args:
            slack_param_multiplier: k = slack_param_multiplier × σ (default 0.5)
            threshold_multiplier: h = threshold_multiplier × σ (default 5.0)
        """
        self.slack_param_multiplier = slack_param_multiplier
        self.threshold_multiplier = threshold_multiplier

        self.baseline_mean = None
        self.baseline_std = None
        self.slack_param = None
        self.threshold = None
        self.cusum_positive = 0.0
        self.cusum_negative = 0.0

    def fit(self, baseline: np.ndarray, feature_name: str = "feature") -> None:
        """
        Fit CUSUM to baseline statistics.

        Args:
            baseline: 1D array of baseline values
            feature_name: Name of the feature (for logging)
        """
        self.baseline_mean = float(np.mean(baseline))
        self.baseline_std = float(np.std(baseline))

        self.slack_param = self.slack_param_multiplier * self.baseline_std
        self.threshold = self.threshold_multiplier * self.baseline_std

        self.cusum_positive = 0.0
        self.cusum_negative = 0.0

    def score(self, current: np.ndarray) -> float:
        """
        Update CUSUM with new observation and return max(C_pos, C_neg).
        Scores each observation in current array sequentially.
        Returns the maximum CUSUM value reached.

        Args:
            current: 1D array of new observations

        Returns:
            Maximum CUSUM score (0 = no drift, >threshold = significant drift)
        """
        if self.baseline_mean is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        max_cusum = 0.0

        for obs in current:
            # Two-sided CUSUM: track both positive and negative deviations
            deviation = obs - self.baseline_mean

            # Positive CUSUM: detects upward shift
            self.cusum_positive = max(0.0, self.cusum_positive + deviation - self.slack_param)

            # Negative CUSUM: detects downward shift
            self.cusum_negative = min(0.0, self.cusum_negative + deviation + self.slack_param)

            current_max = max(self.cusum_positive, abs(self.cusum_negative))
            max_cusum = max(max_cusum, current_max)

        return max_cusum
