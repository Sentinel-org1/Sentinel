"""
backend/app/novelties/calibration_report.py
--------------------------------------------
Novel #5 — FP-rate calibration curves.

Runs a Monte Carlo simulation over (shift_magnitude, scale_factor) combinations
to build a ROC-style curve for any BaseDetector subclass.
Finds the Youden-J optimal threshold and checks agreement with the live
EWMA adaptive threshold from the DriftThreshold table.

Pure computation — no DB access, no async, no Pydantic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

# ── Module-level constants ──────────────────────────────────────────────────
DEFAULT_SHIFT_MAGNITUDES: list[float] = [0.0, 0.05, 0.1, 0.2, 0.5]
DEFAULT_SCALE_FACTORS: list[float]    = [1.0, 1.5, 2.0, 3.0]
DEFAULT_THRESHOLDS: np.ndarray        = np.arange(0.05, 0.55, 0.05)
DEFAULT_N_RUNS: int                   = 20
DEFAULT_RANDOM_SEED: int              = 42
MIN_BASELINE_SAMPLES: int             = 50   # raise ValueError if baseline shorter
EWMA_AGREEMENT_TOLERANCE: float       = 0.05  # |ewma_threshold - youden_optimal| ≤ this


# ── Dataclasses ─────────────────────────────────────────────────────────────
@dataclass
class ScoreDistributionStats:
    """Detector scores on drifted vs clean batches for one (shift, scale) combo."""

    shift_magnitude:  float  # mean shift amount applied
    scale_factor:     float  # std multiplier applied
    drifted_mean:     float  # mean of detector scores on n_runs drifted batches
    drifted_std:      float  # std  of detector scores on n_runs drifted batches
    non_drifted_mean: float  # mean of detector scores on n_runs clean batches
    non_drifted_std:  float  # std  of detector scores on n_runs clean batches
    separation:       float  # drifted_mean - non_drifted_mean


@dataclass
class CalibrationPoint:
    """One point on the ROC curve, corresponding to one threshold value."""

    threshold: float  # score cutoff value being tested
    tp_rate:   float  # fraction of drifted batches correctly scored above threshold
    fp_rate:   float  # fraction of clean   batches incorrectly scored above threshold
    youden_j:  float  # tp_rate - fp_rate


@dataclass
class EWMAState:
    """
    Current EWMA statistics for one detector+feature combo.
    Populated from the DriftThreshold table by the caller; never fetched here.
    """

    ewma_threshold: float  # current adaptive threshold value
    ewma_mean:      float  # current EWMA mean
    ewma_std:       float  # current EWMA std deviation


@dataclass
class CalibrationResult:
    """Full output of CalibrationReport.generate()."""

    detector_name:       str                         # e.g. "PSIDetector"
    points:              list[CalibrationPoint]      # full ROC curve
    optimal_threshold:   float                       # highest Youden-J threshold
    optimal_tp_rate:     float                       # tp_rate at optimal threshold
    optimal_fp_rate:     float                       # fp_rate at optimal threshold
    auc:                 float                       # Area Under ROC Curve [0, 1]
    score_distributions: list[ScoreDistributionStats]  # one per (shift, scale) combo
    ewma_agreement:      Optional[bool]              # None if no ewma_state passed
    random_seed:         int                         # seed used (reproducibility audit)


# ── Main class ───────────────────────────────────────────────────────────────
class CalibrationReport:
    """
    Generate ROC-style calibration curves for any BaseDetector subclass.

    Usage:
        report = CalibrationReport()
        result = report.generate(baseline_array, PSIDetector)
        print(result.optimal_threshold, result.auc)
    """

    def generate(
        self,
        baseline: np.ndarray,
        detector_class: type,
        n_runs: int = DEFAULT_N_RUNS,
        shift_magnitudes: list[float] = DEFAULT_SHIFT_MAGNITUDES,
        scale_factors: list[float] = DEFAULT_SCALE_FACTORS,
        thresholds: np.ndarray = DEFAULT_THRESHOLDS,
        batch_size: Optional[int] = None,
        random_seed: int = DEFAULT_RANDOM_SEED,
        ewma_state: Optional[EWMAState] = None,
    ) -> CalibrationResult:
        """
        Run Monte Carlo simulation and return a full CalibrationResult.

        Args:
            baseline:         1D numpy array of reference feature values (≥ 50 samples)
            detector_class:   A BaseDetector subclass (not an instance — the class itself)
            n_runs:           Number of Monte Carlo runs per (shift, scale) combination
            shift_magnitudes: Mean-shift magnitudes (as multiples of baseline std) to sweep
            scale_factors:    Std-scale multipliers to sweep
            thresholds:       Score cutoff values for the ROC curve
            batch_size:       Batch size for generated samples; defaults to len(baseline)
            random_seed:      Seed for reproducibility
            ewma_state:       Optional live EWMA state to compare against optimal threshold

        Returns:
            CalibrationResult with ROC curve, optimal threshold, AUC, and distributions
        """
        # ── Step 1: Validate inputs ─────────────────────────────────────────
        if len(baseline) < MIN_BASELINE_SAMPLES:
            raise ValueError(
                f"baseline requires >= {MIN_BASELINE_SAMPLES} samples, got {len(baseline)}"
            )
        if baseline.ndim != 1:
            raise ValueError("baseline must be a 1D numpy array")

        # ── Step 2: Setup ───────────────────────────────────────────────────
        rng: np.random.Generator = np.random.default_rng(random_seed)
        effective_batch_size: int = batch_size if batch_size is not None else len(baseline)

        # Fit detector ONCE on the full baseline — all runs share this single fit
        detector = detector_class()
        detector.fit(baseline, feature_name="calibration_baseline")
        detector_name: str = detector_class.__name__

        # ── Step 3: Score across all (shift_magnitude, scale_factor) combos ─
        score_distributions: list[ScoreDistributionStats] = []
        all_drifted_scores: list[float] = []
        all_clean_scores: list[float]   = []

        for shift_magnitude in shift_magnitudes:
            for scale_factor in scale_factors:
                drifted_scores: list[float] = []
                clean_scores: list[float]   = []

                for _ in range(n_runs):
                    # Drifted batch: mean-shifted AND std-scaled
                    drifted_batch = self._generate_batch(
                        baseline, rng, effective_batch_size,
                        shift_magnitude, scale_factor,
                    )
                    drifted_scores.append(detector.score(drifted_batch))

                    # Clean batch: no shift, no scale (always 0.0 and 1.0)
                    clean_batch = self._generate_batch(
                        baseline, rng, effective_batch_size,
                        shift_magnitude=0.0, scale_factor=1.0,
                    )
                    clean_scores.append(detector.score(clean_batch))

                d_mean = float(np.mean(drifted_scores))
                d_std  = float(np.std(drifted_scores))
                c_mean = float(np.mean(clean_scores))
                c_std  = float(np.std(clean_scores))

                score_distributions.append(ScoreDistributionStats(
                    shift_magnitude=shift_magnitude,
                    scale_factor=scale_factor,
                    drifted_mean=d_mean,
                    drifted_std=d_std,
                    non_drifted_mean=c_mean,
                    non_drifted_std=c_std,
                    separation=d_mean - c_mean,
                ))

                all_drifted_scores.extend(drifted_scores)
                all_clean_scores.extend(clean_scores)

        # ── Step 4: Compute ROC curve ────────────────────────────────────────
        points: list[CalibrationPoint] = self._compute_roc_points(
            all_drifted_scores, all_clean_scores, thresholds
        )

        # ── Step 5: Find optimal threshold (highest youden_j; tie → lower fp_rate)
        optimal_point: CalibrationPoint = max(
            points, key=lambda p: (p.youden_j, -p.fp_rate)
        )

        # ── Step 6: Compute AUC ─────────────────────────────────────────────
        auc: float = self._compute_auc(points)

        # ── Step 7: EWMA agreement check ─────────────────────────────────────
        ewma_agreement: Optional[bool] = self._check_ewma_agreement(
            optimal_point.threshold, ewma_state
        )

        # ── Step 8: Return full result ────────────────────────────────────────
        return CalibrationResult(
            detector_name=detector_name,
            points=points,
            optimal_threshold=optimal_point.threshold,
            optimal_tp_rate=optimal_point.tp_rate,
            optimal_fp_rate=optimal_point.fp_rate,
            auc=auc,
            score_distributions=score_distributions,
            ewma_agreement=ewma_agreement,
            random_seed=random_seed,
        )

    # ── Private methods ──────────────────────────────────────────────────────

    def _generate_batch(
        self,
        baseline: np.ndarray,
        rng: np.random.Generator,
        batch_size: int,
        shift_magnitude: float,
        scale_factor: float,
    ) -> np.ndarray:
        """
        Sample a batch from baseline with replacement, then apply mean-shift
        and variance-scale transforms.

        Args:
            baseline:        Reference 1D array to sample from
            rng:             Seeded numpy Generator (shared across calls)
            batch_size:      Number of samples to draw
            shift_magnitude: Mean shift as a multiple of baseline std (0.0 = no shift)
            scale_factor:    Variance scale multiplier (1.0 = no scale)

        Returns:
            Transformed 1D numpy array of length batch_size
        """
        # Sample with replacement
        indices = rng.integers(0, len(baseline), size=batch_size)
        batch = baseline[indices].copy()

        # Compute baseline statistics (not batch statistics) for shift scaling
        batch_std = float(np.std(baseline))
        if batch_std == 0:
            batch_std = 1.0  # avoid degenerate case

        # Apply mean shift (shift_magnitude × baseline_std units)
        batch = batch + shift_magnitude * batch_std

        # Apply scale factor — scale AROUND the batch mean to preserve its center
        if scale_factor != 1.0:
            batch_center = np.mean(batch)
            batch = batch_center + (batch - batch_center) * scale_factor

        return batch

    def _compute_roc_points(
        self,
        drifted_scores: list[float],
        clean_scores: list[float],
        thresholds: np.ndarray,
    ) -> list[CalibrationPoint]:
        """
        Build one CalibrationPoint per threshold value.

        tp_rate: fraction of drifted-batch scores strictly above the threshold
        fp_rate: fraction of clean-batch scores strictly above the threshold

        Args:
            drifted_scores: All detector scores from drifted batches
            clean_scores:   All detector scores from clean batches
            thresholds:     Array of cutoff values to sweep

        Returns:
            list[CalibrationPoint] in the same order as thresholds
        """
        n_drifted = len(drifted_scores)
        n_clean   = len(clean_scores)
        points: list[CalibrationPoint] = []

        for t in thresholds:
            tp_rate  = sum(s > t for s in drifted_scores) / n_drifted
            fp_rate  = sum(s > t for s in clean_scores)   / n_clean
            youden_j = tp_rate - fp_rate
            points.append(CalibrationPoint(
                threshold=float(t),
                tp_rate=float(tp_rate),
                fp_rate=float(fp_rate),
                youden_j=float(youden_j),
            ))

        return points

    def _compute_auc(self, points: list[CalibrationPoint]) -> float:
        """
        Area Under the ROC Curve via the trapezoidal rule.

        Extracts fp_rates and tp_rates in the order the points appear
        (not sorted), as specified. Clamps result to [0.0, 1.0].

        Args:
            points: ROC curve points in threshold-sweep order

        Returns:
            AUC value clamped to [0.0, 1.0]
        """
        sorted_points = sorted(points, key=lambda p: p.fp_rate)

        fp_rates = [p.fp_rate for p in sorted_points]
        tp_rates = [p.tp_rate for p in sorted_points]

        auc = float(np.trapz(tp_rates, fp_rates))
        return max(0.0, min(1.0, auc))

    def _check_ewma_agreement(
        self,
        optimal_threshold: float,
        ewma_state: Optional[EWMAState],
    ) -> Optional[bool]:
        """
        Check whether the live EWMA threshold is close to the Youden-J optimal.

        Args:
            optimal_threshold: Best threshold from ROC curve analysis
            ewma_state:        Live EWMA stats from DriftThreshold table, or None

        Returns:
            None  — if ewma_state was not provided
            True  — if |ewma_threshold - optimal_threshold| ≤ EWMA_AGREEMENT_TOLERANCE
            False — otherwise
        """
        if ewma_state is None:
            return None
        return (
            abs(ewma_state.ewma_threshold - optimal_threshold)
            <= EWMA_AGREEMENT_TOLERANCE
        )