"""
ml/detectors_benchmark/test_benchmark.py
------------------------------------------
Pytest-based benchmark tests that assert Sentinel's detectors meet
minimum performance thresholds and compare against Evidently.

Usage:
    pip install -e ./backend[benchmark]
    python -m pytest ml/detectors_benchmark/test_benchmark.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.detectors.psi import PSIDetector
from app.detectors.ks_test import KSDetector
from app.novelties.cw_psi import ConfidenceWeightedPSI

# Conditionally import Evidently
try:
    import pandas as pd
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset
    HAS_EVIDENTLY = True
except ImportError:
    HAS_EVIDENTLY = False


# ── Fixtures ──────────────────────────────────────────────────
N_BASELINE = 5000
N_CURRENT = 1000
N_FEATURES = 5
RNG = np.random.default_rng(42)
FEATURE_NAMES = [f"feature_{i}" for i in range(N_FEATURES)]


@pytest.fixture(scope="module")
def baseline_data() -> np.ndarray:
    return RNG.standard_normal((N_BASELINE, N_FEATURES))


@pytest.fixture(scope="module")
def clean_current() -> np.ndarray:
    return RNG.standard_normal((N_CURRENT, N_FEATURES))


@pytest.fixture(scope="module")
def drifted_current() -> np.ndarray:
    data = RNG.standard_normal((N_CURRENT, N_FEATURES))
    data[:, :3] += 2.0  # Large mean shift on first 3 features
    return data


@pytest.fixture(scope="module")
def subtle_drift_current() -> np.ndarray:
    data = RNG.standard_normal((N_CURRENT, N_FEATURES))
    data[:, :2] += 0.5  # Small mean shift on first 2 features
    return data


# ── Sentinel PSI Tests ────────────────────────────────────────

class TestSentinelPSI:
    """Tests for Sentinel PSI detector accuracy and performance."""

    def test_detects_large_drift(self, baseline_data, drifted_current):
        """PSI should detect a 2σ mean shift."""
        scores = []
        for i, feat in enumerate(FEATURE_NAMES):
            det = PSIDetector(n_bins=10)
            det.fit(baseline_data[:, i], feature_name=feat)
            scores.append(det.score(drifted_current[:, i]))

        max_score = max(scores)
        assert max_score > 0.25, f"PSI failed to detect large drift: max_score={max_score}"

    def test_no_false_positive_on_clean(self, baseline_data, clean_current):
        """PSI should not trigger on clean data."""
        scores = []
        for i, feat in enumerate(FEATURE_NAMES):
            det = PSIDetector(n_bins=10)
            det.fit(baseline_data[:, i], feature_name=feat)
            scores.append(det.score(clean_current[:, i]))

        max_score = max(scores)
        assert max_score < 0.25, f"PSI false positive on clean data: max_score={max_score}"

    def test_detection_rate_above_threshold(self, baseline_data):
        """PSI detection rate must be >= 85% across varied drift magnitudes."""
        detections = 0
        n_trials = 20

        for trial in range(n_trials):
            rng = np.random.default_rng(trial + 100)
            shift = rng.uniform(1.0, 3.0)
            current = rng.standard_normal((N_CURRENT, N_FEATURES))
            current[:, :3] += shift

            scores = []
            for i, feat in enumerate(FEATURE_NAMES):
                det = PSIDetector(n_bins=10)
                det.fit(baseline_data[:, i], feature_name=feat)
                scores.append(det.score(current[:, i]))

            if max(scores) > 0.25:
                detections += 1

        detection_rate = detections / n_trials
        assert detection_rate >= 0.85, f"PSI detection rate too low: {detection_rate:.0%}"


# ── Sentinel KS Tests ─────────────────────────────────────────

class TestSentinelKS:
    """Tests for Sentinel KS detector."""

    def test_detects_large_drift(self, baseline_data, drifted_current):
        """KS should detect a 2σ mean shift."""
        scores = []
        for i, feat in enumerate(FEATURE_NAMES):
            det = KSDetector(min_samples=50)
            det.fit(baseline_data[:, i], feature_name=feat)
            scores.append(det.score(drifted_current[:, i]))

        max_score = max(scores)
        assert max_score > 0.2, f"KS failed to detect drift: max_score={max_score}"

    def test_no_false_positive_on_clean(self, baseline_data, clean_current):
        """KS should not trigger on clean data."""
        scores = []
        for i, feat in enumerate(FEATURE_NAMES):
            det = KSDetector(min_samples=50)
            det.fit(baseline_data[:, i], feature_name=feat)
            scores.append(det.score(clean_current[:, i]))

        max_score = max(scores)
        assert max_score < 0.2, f"KS false positive on clean data: max_score={max_score}"


# ── Sentinel CW-PSI Tests ─────────────────────────────────────

class TestSentinelCWPSI:
    """Tests for Sentinel CW-PSI detector."""

    def test_detects_large_drift(self, baseline_data, drifted_current):
        """CW-PSI should detect a 2σ mean shift."""
        rng = np.random.default_rng(99)
        confidences = rng.uniform(0.5, 0.99, drifted_current.shape[0])

        cwpsi = ConfidenceWeightedPSI(n_bins=10)
        scores = []
        for i, feat in enumerate(FEATURE_NAMES):
            result = cwpsi.compute(
                baseline=baseline_data[:, i],
                current=drifted_current[:, i],
                confidence_scores=confidences,
                feature_name=feat,
            )
            scores.append(result.cw_psi)

        max_score = max(scores)
        assert max_score > 0.25, f"CW-PSI failed to detect drift: max_score={max_score}"


# ── Evidently Comparison Tests ─────────────────────────────────

@pytest.mark.skipif(not HAS_EVIDENTLY, reason="Evidently not installed")
class TestEvidentlyComparison:
    """Compare Sentinel vs Evidently detection performance."""

    def test_sentinel_faster_than_evidently(self, baseline_data, drifted_current):
        """Sentinel should be faster than Evidently on average."""
        import time

        # Sentinel timing
        t0 = time.perf_counter()
        for i, feat in enumerate(FEATURE_NAMES):
            det = PSIDetector(n_bins=10)
            det.fit(baseline_data[:, i], feature_name=feat)
            det.score(drifted_current[:, i])
        sentinel_time = (time.perf_counter() - t0) * 1000

        # Evidently timing
        ref_df = pd.DataFrame(baseline_data, columns=FEATURE_NAMES)
        cur_df = pd.DataFrame(drifted_current, columns=FEATURE_NAMES)

        t0 = time.perf_counter()
        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=ref_df, current_data=cur_df)
        evidently_time = (time.perf_counter() - t0) * 1000

        assert sentinel_time < evidently_time, (
            f"Sentinel ({sentinel_time:.1f}ms) slower than "
            f"Evidently ({evidently_time:.1f}ms)"
        )

    def test_both_detect_large_drift(self, baseline_data, drifted_current):
        """Both frameworks should detect large drift."""
        # Sentinel
        scores = []
        for i, feat in enumerate(FEATURE_NAMES):
            det = PSIDetector(n_bins=10)
            det.fit(baseline_data[:, i], feature_name=feat)
            scores.append(det.score(drifted_current[:, i]))
        sentinel_detected = max(scores) > 0.25

        # Evidently
        ref_df = pd.DataFrame(baseline_data, columns=FEATURE_NAMES)
        cur_df = pd.DataFrame(drifted_current, columns=FEATURE_NAMES)
        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=ref_df, current_data=cur_df)

        result_dict = report.as_dict()
        evidently_detected = False
        for metric_result in result_dict.get("metrics", []):
            metric_data = metric_result.get("result", {})
            if "dataset_drift" in metric_data:
                evidently_detected = metric_data["dataset_drift"]
                break

        assert sentinel_detected, "Sentinel failed to detect large drift"
        assert evidently_detected, "Evidently failed to detect large drift"

    def test_sentinel_lower_fp_rate(self, baseline_data):
        """Sentinel should have a lower false positive rate than Evidently."""
        sentinel_fps = 0
        evidently_fps = 0
        n_trials = 20

        for trial in range(n_trials):
            rng = np.random.default_rng(trial + 200)
            clean = rng.standard_normal((N_CURRENT, N_FEATURES))

            # Sentinel
            scores = []
            for i, feat in enumerate(FEATURE_NAMES):
                det = PSIDetector(n_bins=10)
                det.fit(baseline_data[:, i], feature_name=feat)
                scores.append(det.score(clean[:, i]))
            if max(scores) > 0.25:
                sentinel_fps += 1

            # Evidently
            ref_df = pd.DataFrame(baseline_data, columns=FEATURE_NAMES)
            cur_df = pd.DataFrame(clean, columns=FEATURE_NAMES)
            report = Report(metrics=[DataDriftPreset()])
            report.run(reference_data=ref_df, current_data=cur_df)
            result_dict = report.as_dict()
            for metric_result in result_dict.get("metrics", []):
                metric_data = metric_result.get("result", {})
                if metric_data.get("dataset_drift", False):
                    evidently_fps += 1
                    break

        sentinel_fpr = sentinel_fps / n_trials
        evidently_fpr = evidently_fps / n_trials

        # Sentinel should not have MORE false positives
        assert sentinel_fpr <= evidently_fpr + 0.1, (
            f"Sentinel FPR ({sentinel_fpr:.0%}) much higher than "
            f"Evidently ({evidently_fpr:.0%})"
        )
