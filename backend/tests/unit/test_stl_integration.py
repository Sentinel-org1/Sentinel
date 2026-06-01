from __future__ import annotations

import json
from unittest.mock import MagicMock
import numpy as np
import pytest

from app.tasks.drift_check import _extract_score_history, _stl_suppressor
from app.models.drift_threshold import DriftThreshold


def test_extract_score_history_empty():
    threshold = DriftThreshold()
    threshold.history = None
    assert _extract_score_history(threshold) == []


def test_extract_score_history_valid():
    threshold = DriftThreshold()
    history_data = [
        {"score": 0.1, "threshold": 0.2},
        {"score": 0.15, "threshold": 0.2},
        {"score": 0.22, "threshold": 0.2},
    ]
    threshold.history = json.dumps(history_data)
    assert _extract_score_history(threshold) == [0.1, 0.15, 0.22]


def test_stl_suppression_seasonal_noise():
    # Construct a series dominated by seasonal periodic variation
    # With a period of 7, we construct 14 steps of sine wave (perfectly periodic)
    x = np.linspace(0, 4 * np.pi, 15)
    seasonal_series = 0.5 * np.sin(x) + 0.1  # Periodic seasonal noise
    
    # Raw score is high, threshold is 0.2
    raw_score = 0.6
    threshold = 0.2
    
    # should_suppress_alert should return True for purely seasonal variation
    should_suppress = _stl_suppressor.should_suppress_alert(
        series=seasonal_series,
        raw_score=raw_score,
        threshold=threshold,
    )
    assert should_suppress is True


def test_stl_no_suppression_genuine_trend():
    # Construct a series with a clear upward trend
    # Period is 7, length is 15. The trend grows rapidly.
    x = np.linspace(0, 15, 15)
    trend_series = 0.1 * x + 0.1  # Linear growth trend
    
    raw_score = 1.6
    threshold = 0.5
    
    # should_suppress_alert should return False because it's a trend, not seasonality
    should_suppress = _stl_suppressor.should_suppress_alert(
        series=trend_series,
        raw_score=raw_score,
        threshold=threshold,
    )
    assert should_suppress is False
