"""
backend/tests/unit/test_stl_decomposition.py
----------------------------------------------
Unit tests for STLAlertSuppressor (Novel #4).
Pure computation tests — no DB, no async, no HTTP.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.novelties.stl_decomposition import (
    STLAlertSuppressor,
    STLResult,
    DEFAULT_PERIOD,
    DEFAULT_SEASONAL_WINDOW,
    DEFAULT_TREND_THRESHOLD_RATIO,
    MIN_OBSERVATIONS_FACTOR,
)

# ── Shared fixtures ────────────────────────────────────────────
RNG = np.random.default_rng(42)


def _make_seasonal_series(
    n: int = 50,
    period: int = 7,
    trend_slope: float = 0.0,
    seasonal_amplitude: float = 0.3,
    noise_std: float = 0.01,
) -> np.ndarray:
    """Build a synthetic drift-score time-series with known components.

    Returns a 1-D array of length n with:
      - Linear trend:  trend_slope × t
      - Seasonal: seasonal_amplitude × sin(2π × t / period)
      - Noise:  Gaussian(0, noise_std)
    """
    t = np.arange(n, dtype=np.float64)
    trend = trend_slope * t
    seasonal = seasonal_amplitude * np.sin(2 * np.pi * t / period)
    noise = RNG.normal(0, noise_std, n)
    return trend + seasonal + noise + 0.1  # +0.1 baseline offset


# ── Test 1 — Decompose a pure trend signal ─────────────────────
class TestDecomposeTrend:
    def test_pure_trend_seasonal_near_zero(self):
        """A linear trend with no seasonality should have seasonal ≈ 0."""
        suppressor = STLAlertSuppressor(period=7)
        series = _make_seasonal_series(
            n=50, period=7, trend_slope=0.02,
            seasonal_amplitude=0.0, noise_std=0.001,
        )
        result = suppressor.decompose(series)

        assert result is not None
        assert isinstance(result, STLResult)
        # Seasonal component should be negligible
        assert np.max(np.abs(result.seasonal)) < 0.05
        # Trend should follow the input (increasing)
        assert result.trend[-1] > result.trend[0]

    def test_decompose_returns_correct_shapes(self):
        """All output arrays must match the input series length."""
        n = 30
        suppressor = STLAlertSuppressor(period=7)
        series = _make_seasonal_series(n=n)
        result = suppressor.decompose(series)

        assert result is not None
        assert len(result.trend) == n
        assert len(result.seasonal) == n
        assert len(result.residual) == n
        assert result.period == 7


# ── Test 2 — Decompose seasonal + noise ────────────────────────
class TestDecomposeSeasonality:
    def test_seasonal_component_captures_periodicity(self):
        """Seasonal component should have appreciable amplitude for a
        signal with strong seasonality."""
        suppressor = STLAlertSuppressor(period=7)
        series = _make_seasonal_series(
            n=50, period=7, trend_slope=0.0,
            seasonal_amplitude=0.5, noise_std=0.01,
        )
        result = suppressor.decompose(series)

        assert result is not None
        # Seasonal range should be substantial (at least half of amplitude)
        seasonal_range = float(np.max(result.seasonal) - np.min(result.seasonal))
        assert seasonal_range > 0.3


# ── Test 3 — should_suppress_alert: seasonal-dominated ─────────
class TestSuppressSeasonalAlert:
    def test_seasonal_spike_is_suppressed(self):
        """When raw score is high due to seasonal peak but trend is low,
        the alert should be suppressed."""
        suppressor = STLAlertSuppressor(period=7, trend_threshold_ratio=0.8)

        # Build a series with strong seasonality but flat trend
        series = _make_seasonal_series(
            n=50, period=7, trend_slope=0.0,
            seasonal_amplitude=0.4, noise_std=0.01,
        )

        # Raw score = peak of seasonal → ~0.5
        raw_score = float(np.max(series))
        threshold = 0.3  # threshold well below seasonal peak

        result = suppressor.should_suppress_alert(series, raw_score, threshold)
        assert result is True, "Seasonal-dominated spike should be suppressed"


# ── Test 4 — should_suppress_alert: trend-dominated ────────────
class TestDoNotSuppressTrend:
    def test_genuine_trend_not_suppressed(self):
        """When the trend itself exceeds the threshold, the alert must NOT
        be suppressed."""
        suppressor = STLAlertSuppressor(period=7, trend_threshold_ratio=0.8)

        # Strong upward trend, minimal seasonality
        series = _make_seasonal_series(
            n=50, period=7, trend_slope=0.05,
            seasonal_amplitude=0.01, noise_std=0.001,
        )

        raw_score = float(series[-1])  # Latest value (should be high)
        threshold = 0.3  # Trend at end should be well above this

        result = suppressor.should_suppress_alert(series, raw_score, threshold)
        assert result is False, "Genuine trend alert should NOT be suppressed"


# ── Test 5 — extract_trend_score strips seasonal ───────────────
class TestExtractTrendScore:
    def test_trend_score_strips_seasonal(self):
        """extract_trend_score should return a de-seasonalised value that
        is less volatile than the raw latest score."""
        suppressor = STLAlertSuppressor(period=7)

        series = _make_seasonal_series(
            n=50, period=7, trend_slope=0.01,
            seasonal_amplitude=0.4, noise_std=0.01,
        )

        trend_score = suppressor.extract_trend_score(series)
        assert isinstance(trend_score, float)
        # Trend score should be less extreme than raw max
        assert trend_score < float(np.max(series))


# ── Test 6 — Short series fallback ─────────────────────────────
class TestShortSeriesFallback:
    def test_decompose_returns_none_for_short_series(self):
        """Series shorter than 2 × period should return None."""
        suppressor = STLAlertSuppressor(period=7)
        short_series = np.array([0.1, 0.2, 0.3, 0.15, 0.25])  # only 5 points

        result = suppressor.decompose(short_series)
        assert result is None

    def test_extract_trend_score_fallback(self):
        """extract_trend_score should return raw latest value if series
        is too short."""
        suppressor = STLAlertSuppressor(period=7)
        short_series = np.array([0.1, 0.2, 0.3])

        trend_score = suppressor.extract_trend_score(short_series)
        assert trend_score == pytest.approx(0.3, abs=1e-10)

    def test_should_suppress_returns_false_for_short_series(self):
        """Cannot suppress without decomposition — err on side of alerting."""
        suppressor = STLAlertSuppressor(period=7)
        short_series = np.array([0.1, 0.5, 0.3])

        result = suppressor.should_suppress_alert(short_series, 0.5, 0.3)
        assert result is False

    def test_extract_trend_score_empty_series(self):
        """Empty series returns 0.0."""
        suppressor = STLAlertSuppressor(period=7)
        result = suppressor.extract_trend_score(np.array([]))
        assert result == 0.0


# ── Test 7 — Edge case: constant series ────────────────────────
class TestConstantSeries:
    def test_constant_series_decomposes(self):
        """A constant series should decompose with trend ≈ constant,
        seasonal ≈ 0, residual ≈ 0."""
        suppressor = STLAlertSuppressor(period=7)
        series = np.full(30, 0.15)

        result = suppressor.decompose(series)
        assert result is not None
        assert np.allclose(result.seasonal, 0.0, atol=0.01)
        assert np.allclose(result.trend, 0.15, atol=0.01)


# ── Test 8 — Configurable period ───────────────────────────────
class TestConfigurablePeriod:
    def test_custom_period(self):
        """Custom period=12 should work with a 12-cycle seasonal signal."""
        suppressor = STLAlertSuppressor(period=12)
        series = _make_seasonal_series(
            n=50, period=12, trend_slope=0.0,
            seasonal_amplitude=0.3, noise_std=0.01,
        )

        result = suppressor.decompose(series)
        assert result is not None
        assert result.period == 12

    def test_invalid_period_raises(self):
        """period < 2 should raise ValueError."""
        with pytest.raises(ValueError, match="period must be"):
            STLAlertSuppressor(period=1)

    def test_invalid_seasonal_window_raises(self):
        """Even seasonal_window should raise ValueError."""
        with pytest.raises(ValueError, match="seasonal_window must be odd"):
            STLAlertSuppressor(seasonal_window=8)

    def test_small_seasonal_window_raises(self):
        """seasonal_window < 7 should raise ValueError."""
        with pytest.raises(ValueError, match="seasonal_window must be"):
            STLAlertSuppressor(seasonal_window=5)


# ── Test 9 — score below threshold ────────────────────────────
class TestScoreBelowThreshold:
    def test_no_suppression_when_score_below_threshold(self):
        """If raw_score <= threshold, should_suppress_alert returns False."""
        suppressor = STLAlertSuppressor(period=7)
        series = _make_seasonal_series(n=30)

        result = suppressor.should_suppress_alert(series, 0.1, 0.5)
        assert result is False


# ── Test 10 — to_dict serialisation ────────────────────────────
class TestSerialisation:
    def test_stl_result_to_dict(self):
        """to_dict() produces a JSON-safe dict."""
        suppressor = STLAlertSuppressor(period=7)
        series = _make_seasonal_series(n=30)
        result = suppressor.decompose(series)

        assert result is not None
        d = result.to_dict()

        assert set(d.keys()) == {"trend", "seasonal", "residual", "period"}
        assert isinstance(d["trend"], list)
        assert isinstance(d["seasonal"], list)
        assert isinstance(d["residual"], list)
        assert d["period"] == 7


# ── Test 11 — repr ─────────────────────────────────────────────
class TestRepr:
    def test_repr(self):
        suppressor = STLAlertSuppressor(period=7, seasonal_window=9, trend_threshold_ratio=0.75)
        r = repr(suppressor)
        assert "period=7" in r
        assert "seasonal_window=9" in r
        assert "trend_threshold_ratio=0.75" in r
