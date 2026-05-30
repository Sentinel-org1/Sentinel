"""
backend/tests/unit/test_calibration_report.py
----------------------------------------------
Unit tests for CalibrationReport (Novel #5).
Pure computation tests — no DB, no async, no HTTP.

Spec: Calibration_report_plan, Section 9.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.detectors.psi import PSIDetector
from app.novelties.calibration_report import (
    CalibrationReport,
    CalibrationResult,
    EWMAState,
    DEFAULT_THRESHOLDS,
    DEFAULT_RANDOM_SEED,
)

# ── Shared fixtures ────────────────────────────────────────────
# Baseline specified in the plan: np.random.default_rng(0).normal(0, 1, 500)
BASELINE = np.random.default_rng(0).normal(0, 1, 500)
REPORT = CalibrationReport()


# ── Test 1 — result has correct structure ──────────────────────
class TestResultStructure:
    def test_result_has_correct_structure(self):
        """CalibrationResult fields are present and within valid ranges."""
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
        )

        assert isinstance(result, CalibrationResult)
        assert len(result.points) == len(DEFAULT_THRESHOLDS)
        assert 0.0 <= result.auc <= 1.0
        assert result.optimal_threshold in DEFAULT_THRESHOLDS
        assert result.random_seed == DEFAULT_RANDOM_SEED


# ── Test 2 — reproducibility ───────────────────────────────────
class TestReproducibility:
    def test_same_seed_produces_identical_results(self):
        """Calling generate() twice with the same seed must return identical outputs."""
        result_a = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
            random_seed=DEFAULT_RANDOM_SEED,
        )
        result_b = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
            random_seed=DEFAULT_RANDOM_SEED,
        )

        assert result_a.optimal_threshold == result_b.optimal_threshold
        assert result_a.auc == result_b.auc


# ── Test 3 — large shift produces high AUC ─────────────────────
class TestDetectionPower:
    def test_large_shift_produces_high_auc(self):
        """A large mean shift must be clearly separable — AUC > 0.7."""
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
            shift_magnitudes=[0.0, 1.0, 2.0],
            scale_factors=[1.0],
        )

        assert result.auc > 0.7

    # ── Test 4 — zero shift baseline FP rate ───────────────────
    def test_zero_shift_separation_is_near_zero(self):
        """No shift means drifted and clean batches score nearly identically."""
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
        )

        # Find the entry where no shift and no scale change was applied
        zero_shift_entry = next(
            s for s in result.score_distributions
            if s.shift_magnitude == 0.0 and s.scale_factor == 1.0
        )

        assert abs(zero_shift_entry.separation) < 0.3

    # ── Test 5 — scale-only shift is detectable ─────────────────
    def test_scale_only_shift_is_detectable(self):
        """A 3× variance change must produce a higher score than no change."""
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
            shift_magnitudes=[0.0],
            scale_factors=[1.0, 3.0],
        )

        scale_entry = next(
            s for s in result.score_distributions
            if s.scale_factor == 3.0
        )

        assert scale_entry.separation > 0.0


# ── Tests 6, 7, 8 — EWMA agreement ────────────────────────────
class TestEWMAagreement:
    def _get_optimal_threshold(self) -> float:
        """Run generate() with default params and return the optimal threshold."""
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
        )
        return result.optimal_threshold

    def test_ewma_agreement_true_when_within_tolerance(self):
        """EWMA threshold that is 0.01 away from optimal must agree (tolerance = 0.05)."""
        optimal = self._get_optimal_threshold()

        ewma_state = EWMAState(
            ewma_threshold=optimal + 0.01,
            ewma_mean=0.1,
            ewma_std=0.02,
        )
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
            ewma_state=ewma_state,
        )

        assert result.ewma_agreement is True

    def test_ewma_agreement_false_when_outside_tolerance(self):
        """EWMA threshold that is 0.20 away from optimal must disagree (tolerance = 0.05)."""
        optimal = self._get_optimal_threshold()

        ewma_state = EWMAState(
            ewma_threshold=optimal + 0.20,
            ewma_mean=0.1,
            ewma_std=0.02,
        )
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
            ewma_state=ewma_state,
        )

        assert result.ewma_agreement is False

    def test_ewma_agreement_is_none_when_no_state_passed(self):
        """Omitting ewma_state must leave ewma_agreement as None."""
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
        )

        assert result.ewma_agreement is None


# ── Tests 9, 10 — edge cases ───────────────────────────────────
class TestEdgeCases:
    def test_custom_batch_size_completes_without_error(self):
        """batch_size=100 with n_runs=5 must complete and return a CalibrationResult."""
        result = REPORT.generate(
            baseline=BASELINE,
            detector_class=PSIDetector,
            batch_size=100,
            n_runs=5,
        )

        assert isinstance(result, CalibrationResult)

    def test_short_baseline_raises_value_error(self):
        """A baseline shorter than MIN_BASELINE_SAMPLES must raise ValueError."""
        short_baseline = np.array([1.0, 2.0, 3.0])  # only 3 samples

        with pytest.raises(ValueError, match="requires >="):
            REPORT.generate(
                baseline=short_baseline,
                detector_class=PSIDetector,
            )