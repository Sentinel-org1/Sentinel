"""
NOVEL #1: Adaptive EWMA Control Limits

Exponentially Weighted Moving Average (EWMA) for drift thresholds.
Instead of fixed constants, thresholds adapt to recent variance.

S_t = λ × x_t + (1 - λ) × S_{t-1}
Control limits = μ_ref ± k × σ_ewma

where:
  - λ = smoothing factor (0.2 by default, higher = more responsive)
  - k = multiplier (typically 3.0 for 3-sigma control limits)
  - x_t = current drift metric (PSI, KS statistic, etc.)

Benefit: Captures localized variance instead of using global baseline std.
Reduces false positives in noisy environments.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger()


class EWMAThresholds:
    """Manages adaptive EWMA-based control limits per detector and metric."""

    def __init__(
        self,
        alpha: float = 0.2,
        sigma_multiplier: float = 3.0,
        lookback_window: int = 100,
    ):
        """
        Args:
            alpha: Smoothing factor (0 < α ≤ 1, default 0.2)
            sigma_multiplier: Control limit width (default 3.0 for 3σ)
            lookback_window: How many observations to use for initial EWMA
        """
        self.alpha = alpha
        self.sigma_multiplier = sigma_multiplier
        self.lookback_window = lookback_window

    def initialize_ewma(self, baseline_scores: list[float]) -> dict:
        """
        Initialize EWMA from baseline observations.

        Args:
            baseline_scores: Recent historical drift metric scores

        Returns:
            dict with keys: 'ewma_mean', 'ewma_std', 'threshold'
        """
        if len(baseline_scores) == 0:
            baseline_scores = [0.0]

        # Use most recent observations (up to lookback_window)
        recent = baseline_scores[-self.lookback_window :]

        ewma_mean = float(np.mean(recent))
        ewma_std = float(np.std(recent)) if len(recent) > 1 else 0.01  # Avoid zero std

        threshold = ewma_mean + (self.sigma_multiplier * ewma_std)

        return {
            "ewma_mean": ewma_mean,
            "ewma_std": ewma_std,
            "threshold": threshold,
        }

    def update(self, score: float, ewma_mean: float, ewma_std: float) -> dict:
        """
        Update EWMA statistics with new observation.

        Args:
            score: Latest drift metric score
            ewma_mean: Previous EWMA mean
            ewma_std: Previous EWMA std deviation

        Returns:
            dict with keys: 'ewma_mean', 'ewma_std', 'threshold'
        """
        # Update EWMA mean
        new_ewma_mean = (self.alpha * score) + ((1 - self.alpha) * ewma_mean)

        # Update EWMA std: use deviation from updated mean
        deviation = abs(score - new_ewma_mean)
        new_ewma_std = (self.alpha * deviation) + ((1 - self.alpha) * ewma_std)

        # Compute new adaptive threshold
        new_threshold = new_ewma_mean + (self.sigma_multiplier * new_ewma_std)

        return {
            "ewma_mean": new_ewma_mean,
            "ewma_std": new_ewma_std,
            "threshold": new_threshold,
        }

    def should_alert(
        self,
        score: float,
        threshold: float,
        allow_margin: float = 0.0,
    ) -> bool:
        """
        Determine if current score exceeds threshold.

        Args:
            score: Latest drift metric score
            threshold: EWMA adaptive threshold
            allow_margin: Grace margin before alerting (default 0 = exact threshold)

        Returns:
            True if score exceeds (threshold + margin)
        """
        return score > (threshold + allow_margin)


class ThresholdHistory:
    """Track historical threshold values for retrospective analysis."""

    def __init__(self, model_id: int, detector: str, metric_name: str):
        """
        Args:
            model_id: Which model this tracks
            detector: Detector name (e.g., 'psi', 'cusum')
            metric_name: Metric name (e.g., 'age', 'income')
        """
        self.model_id = model_id
        self.detector = detector
        self.metric_name = metric_name
        self.history: list[dict] = []

    def record(self, threshold: float, ewma_mean: float, ewma_std: float):
        """
        Record a threshold value at current timestamp.

        Args:
            threshold: Computed threshold value
            ewma_mean: EWMA mean at this time
            ewma_std: EWMA std at this time
        """
        self.history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "threshold": threshold,
                "ewma_mean": ewma_mean,
                "ewma_std": ewma_std,
            }
        )
        logger.info(
            "threshold_recorded",
            model_id=self.model_id,
            detector=self.detector,
            metric=self.metric_name,
            threshold=round(threshold, 4),
        )

    def to_json(self) -> str:
        """Serialize history to JSON."""
        return json.dumps(self.history)

    @classmethod
    def from_json(cls, model_id: int, detector: str, metric_name: str, json_str: str):
        """Deserialize history from JSON."""
        instance = cls(model_id, detector, metric_name)
        instance.history = json.loads(json_str)
        return instance
