"""
NOVEL #4: STL Decomposition + Alert Suppression

Decomposes a time-series of drift scores into trend, seasonal, and residual
components using Seasonal and Trend decomposition using Loess (STL).

Seasonal-dominated alerts are suppressed — only genuine degradation trends
trigger notifications to the on-call engineer.

Flow:
    1. Collect a rolling window of recent drift scores (≥ 2 × period points).
    2. Decompose with statsmodels STL.
    3. Compare the trend component at the latest time-step against the raw score.
    4. If the raw score exceeds the threshold but the trend component does NOT,
       the alert is seasonal noise → suppress.
    5. extract_trend_score() returns a de-seasonalised score suitable for EWMA
       threshold comparison.

Parameters:
    period           : Expected seasonal cycle length (default 7 for daily data
                       with weekly seasonality).
    seasonal_window  : STL seasonal smoother window (must be odd, ≥ 7).
    trend_threshold_ratio : Fraction of the raw threshold below which the
                       trend component is considered "not alarming" (default 0.8).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import structlog
from statsmodels.tsa.seasonal import STL

logger = structlog.get_logger()

# ── Module-level constants ──────────────────────────────────────────────────
DEFAULT_PERIOD: int = 7
DEFAULT_SEASONAL_WINDOW: int = 7   # Must be odd, ≥ 7
DEFAULT_TREND_THRESHOLD_RATIO: float = 0.8
MIN_OBSERVATIONS_FACTOR: int = 2   # Need at least period × this many points


# ── Result Dataclass ────────────────────────────────────────────────────────
@dataclass
class STLResult:
    """Decomposition output from STLAlertSuppressor.decompose().

    Attributes
    ----------
    trend : np.ndarray
        Trend component of the input series.
    seasonal : np.ndarray
        Seasonal component.
    residual : np.ndarray
        Residual component (series - trend - seasonal).
    period : int
        Seasonal period used for the decomposition.
    """
    trend: np.ndarray
    seasonal: np.ndarray
    residual: np.ndarray
    period: int

    def to_dict(self) -> dict:
        """Serialise to a plain dict safe for JSON / DB storage."""
        return {
            "trend": self.trend.tolist(),
            "seasonal": self.seasonal.tolist(),
            "residual": self.residual.tolist(),
            "period": self.period,
        }


# ── Core Class ──────────────────────────────────────────────────────────────
class STLAlertSuppressor:
    """STL-based alert suppression for drift score time series.

    Lifecycle
    ---------
    1. Instantiate with desired period and tuning knobs.
    2. Call ``decompose(series)`` to get trend/seasonal/residual arrays.
    3. Call ``should_suppress_alert(series, raw_score, threshold)`` to decide
       whether a triggered alert is seasonal noise.
    4. Call ``extract_trend_score(series)`` to get the de-seasonalised trend
       value at the most recent time-step.

    Note: This class is stateless — each call receives the full time series.
    State management (accumulating drift scores over time) is handled by the
    drift-check orchestrator that stores scores in DriftThreshold.history.
    """

    def __init__(
        self,
        period: int = DEFAULT_PERIOD,
        seasonal_window: int = DEFAULT_SEASONAL_WINDOW,
        trend_threshold_ratio: float = DEFAULT_TREND_THRESHOLD_RATIO,
    ) -> None:
        """
        Args:
            period: Expected seasonal cycle length in observations.
                    E.g. 7 for daily scores with weekly seasonality,
                    24 for hourly scores with daily seasonality.
            seasonal_window: STL seasonal smoother width (must be odd, ≥ 7).
            trend_threshold_ratio: Fraction of the raw threshold below which
                    the trend is considered "not alarming".  Default 0.8 means
                    if the trend at the latest point is < 80% of the threshold,
                    the alert is suppressed.
        """
        if period < 2:
            raise ValueError(f"period must be ≥ 2, got {period}")
        if seasonal_window < 7:
            raise ValueError(f"seasonal_window must be ≥ 7, got {seasonal_window}")
        if seasonal_window % 2 == 0:
            raise ValueError(f"seasonal_window must be odd, got {seasonal_window}")

        self.period = period
        self.seasonal_window = seasonal_window
        self.trend_threshold_ratio = trend_threshold_ratio

    @property
    def min_observations(self) -> int:
        """Minimum number of observations needed for a valid decomposition."""
        return self.period * MIN_OBSERVATIONS_FACTOR

    # ------------------------------------------------------------------
    # DECOMPOSE
    # ------------------------------------------------------------------
    def decompose(self, series: np.ndarray) -> Optional[STLResult]:
        """Decompose a 1-D drift-score series into trend + seasonal + residual.

        Args:
            series: 1-D array of drift scores ordered chronologically.

        Returns:
            STLResult if the series is long enough for decomposition,
            None otherwise.
        """
        series = np.asarray(series, dtype=np.float64).ravel()

        if len(series) < self.min_observations:
            logger.warning(
                "stl_series_too_short",
                got=len(series),
                need=self.min_observations,
            )
            return None

        stl = STL(
            series,
            period=self.period,
            seasonal=self.seasonal_window,
            robust=True,
        )
        result = stl.fit()

        decomposition = STLResult(
            trend=np.array(result.trend),
            seasonal=np.array(result.seasonal),
            residual=np.array(result.resid),
            period=self.period,
        )

        logger.info(
            "stl_decomposed",
            n_points=len(series),
            period=self.period,
            trend_latest=round(float(decomposition.trend[-1]), 6),
            seasonal_latest=round(float(decomposition.seasonal[-1]), 6),
        )

        return decomposition

    # ------------------------------------------------------------------
    # SHOULD SUPPRESS ALERT
    # ------------------------------------------------------------------
    def should_suppress_alert(
        self,
        series: np.ndarray,
        raw_score: float,
        threshold: float,
    ) -> bool:
        """Decide whether an alert triggered by raw_score > threshold is
        seasonal noise that should be suppressed.

        Logic:
            1. If the series is too short for STL, we cannot suppress → False.
            2. Decompose the series.
            3. If the trend at the latest time-step is below
               (threshold × trend_threshold_ratio), the alert is seasonal
               noise → suppress (True).
            4. Otherwise the trend itself is alarming → do NOT suppress (False).

        Args:
            series: Recent drift score history (1-D, chronological).
            raw_score: The latest drift score that triggered the alert.
            threshold: The threshold that raw_score exceeded.

        Returns:
            True  → suppress the alert (seasonal noise).
            False → do NOT suppress (genuine trend or insufficient data).
        """
        if raw_score <= threshold:
            # Score doesn't actually exceed threshold — nothing to suppress
            return False

        decomposition = self.decompose(series)
        if decomposition is None:
            # Not enough data for STL — err on the side of alerting
            return False

        trend_latest = float(decomposition.trend[-1])
        trend_limit = threshold * self.trend_threshold_ratio

        should_suppress = trend_latest < trend_limit

        logger.info(
            "stl_alert_suppression_check",
            raw_score=round(raw_score, 6),
            threshold=round(threshold, 6),
            trend_latest=round(trend_latest, 6),
            trend_limit=round(trend_limit, 6),
            suppressed=should_suppress,
        )

        return should_suppress

    # ------------------------------------------------------------------
    # EXTRACT TREND SCORE
    # ------------------------------------------------------------------
    def extract_trend_score(self, series: np.ndarray) -> float:
        """Return the de-seasonalised trend score at the latest time-step.

        If the series is too short for STL, returns the raw latest value
        unchanged (graceful fallback).

        Args:
            series: Recent drift score history (1-D, chronological).

        Returns:
            Trend component value at the most recent time-step, or the raw
            latest value if decomposition is not possible.
        """
        series = np.asarray(series, dtype=np.float64).ravel()

        if len(series) == 0:
            return 0.0

        decomposition = self.decompose(series)
        if decomposition is None:
            # Fallback: return raw latest value
            return float(series[-1])

        return float(decomposition.trend[-1])

    # ------------------------------------------------------------------
    # CONVENIENCE
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"STLAlertSuppressor(period={self.period}, "
            f"seasonal_window={self.seasonal_window}, "
            f"trend_threshold_ratio={self.trend_threshold_ratio})"
        )


# Alias for backwards compatibility with the original test files/stubs
STLDecomposition = STLAlertSuppressor

