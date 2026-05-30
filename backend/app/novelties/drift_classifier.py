"""
backend/app/novelties/drift_classifier.py
------------------------------------------
Drift Type Classifier — Rule-based engine for categorising ML model drift.

Takes aggregated signals from all detectors (PSI, KS, CUSUM, Page-Hinkley,
etc.) that ran in drift_check.py and outputs a structured DriftClassification:
  - Primary drift type and confidence
  - Human-readable recommended action for the on-call engineer
  - Optional secondary type when evidence is split (mixed)
  - Explainability list of which signals drove the result

Design principle: every rule is scored independently; no early-exit if/elif
chains. This is what makes mixed detection possible — two types can score
nearly equally when their evidence overlaps.

Drift Types
-----------
covariate_shift     Input feature distribution changed; model relationship intact.
concept_drift       Feature-target relationship changed; model has degraded.
label_drift         Target distribution shifted (e.g. class imbalance changed).
upstream_data_issue Many features drifted simultaneously → data pipeline problem.
mixed               Top-2 types score within MIXED_CONFIDENCE_THRESHOLD.
unknown             All scores ≤ 0.15 — insufficient signal to classify.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Module-level Threshold Constants ──────────────────────────────────────────
PSI_HIGH_THRESHOLD = 0.25              # PSI ≥ this → high feature drift
PSI_MEDIUM_THRESHOLD = 0.10            # PSI in [0.10, 0.25) → medium feature drift
PREDICTION_SHIFT_HIGH = 0.10           # |mean_current - mean_baseline| ≥ this → high shift
PREDICTION_SHIFT_MEDIUM = 0.05         # |mean_current - mean_baseline| in [0.05, 0.10) → medium
ERROR_RATE_DELTA_SIGNIFICANT = 0.02    # error_rate_current - error_rate_baseline ≥ this → rising
FEATURE_COUNT_UPSTREAM_THRESHOLD = 3   # ≥ 3 features simultaneously drifted → pipeline issue
MIXED_CONFIDENCE_THRESHOLD = 0.20      # top-2 scores within this margin → declare mixed


# ── Input Dataclass ────────────────────────────────────────────────────────────
@dataclass
class DriftSignals:
    """
    Aggregated signals from all detectors for a single drift-check run.
    Populated in drift_check.py and passed into DriftClassifier.classify().

    Attributes
    ----------
    psi_scores:
        Feature name → PSI score for every feature that was evaluated.
        Empty dict if PSI did not run.
    prediction_shift:
        |mean(current_predictions) - mean(baseline_predictions)|.
        Captures overall output-space movement.
    error_rate_delta:
        current_error_rate - baseline_error_rate.
        Pass 0.0 when ground-truth labels are not yet available.
    feature_count_drifted:
        Count of features whose PSI score ≥ PSI_HIGH_THRESHOLD (0.25).
    has_actuals:
        True when ground-truth labels are available for this model/window.
    sequential_detector_fired:
        True if CUSUM or Page-Hinkley triggered during this drift-check run.
    """
    psi_scores: dict[str, float]
    prediction_shift: float
    error_rate_delta: float
    feature_count_drifted: int
    has_actuals: bool
    sequential_detector_fired: bool


# ── Output Dataclass ───────────────────────────────────────────────────────────
@dataclass
class DriftClassification:
    """
    Structured result from DriftClassifier.classify().

    Attributes
    ----------
    drift_type:
        Primary classification. One of: covariate_shift, concept_drift,
        label_drift, upstream_data_issue, mixed, unknown.
    confidence:
        Confidence in the primary classification. Range [0.0, 1.0].
    recommended_action:
        Human-readable string telling the engineer exactly what to do next.
    secondary_type:
        Second-best classification when drift_type == "mixed". None otherwise.
    secondary_confidence:
        Confidence for the secondary type. None when not mixed.
    signals_used:
        Names of signals that contributed additive score components to the
        winning rule(s). Used for explainability and audit logging.
        Examples: "high_psi_feature:age", "prediction_shift_high",
                  "sequential_detector_fired", "feature_count_drifted:4".
    """
    drift_type: str
    confidence: float
    recommended_action: str
    secondary_type: Optional[str] = None
    secondary_confidence: Optional[float] = None
    signals_used: list[str] = field(default_factory=list)


# ── Classifier ─────────────────────────────────────────────────────────────────
class DriftClassifier:
    """
    Rule-based drift type classifier.

    All four drift types are scored independently against the incoming
    DriftSignals. The top scorer wins — or a mixed result is returned when
    the top-2 scores fall within MIXED_CONFIDENCE_THRESHOLD of each other
    and both exceed 0.2.

    Usage
    -----
    >>> classifier = DriftClassifier()
    >>> result = classifier.classify(signals)
    >>> print(result.drift_type, result.confidence)
    """

    def classify(self, signals: DriftSignals) -> DriftClassification:
        """
        Classify the type of drift from aggregated detector signals.

        All four scoring rules always run — no early exit. This ensures
        mixed detection works correctly when two rules score similarly.

        Parameters
        ----------
        signals : DriftSignals
            Signals populated from the current drift-check run.

        Returns
        -------
        DriftClassification
            Drift type, confidence score, recommended action, and
            explainability metadata.
        """
        # Score all four drift types independently — every rule always runs
        cov_score,  cov_signals  = self._score_covariate_shift(signals)
        con_score,  con_signals  = self._score_concept_drift(signals)
        lab_score,  lab_signals  = self._score_label_drift(signals)
        ups_score,  ups_signals  = self._score_upstream_data_issue(signals)

        scored: list[tuple[str, float, list[str]]] = [
            ("covariate_shift",     cov_score,  cov_signals),
            ("concept_drift",       con_score,  con_signals),
            ("label_drift",         lab_score,  lab_signals),
            ("upstream_data_issue", ups_score,  ups_signals),
        ]

        # ── Unknown fallback: all rules have negligible signal ─────────────────
        if all(s <= 0.15 for _, s, _ in scored):
            return DriftClassification(
                drift_type="unknown",
                confidence=0.0,
                recommended_action=(
                    "Insufficient signal to classify drift. Run manual inspection."
                ),
                signals_used=[],
            )

        # ── Sort descending, take the top-2 ───────────────────────────────────
        scored.sort(key=lambda x: x[1], reverse=True)
        top_type,    top_score,    top_signals    = scored[0]
        second_type, second_score, second_signals = scored[1]

        # ── Mixed detection: top-2 are close and both meaningful ──────────────
        if (
            top_score - second_score <= MIXED_CONFIDENCE_THRESHOLD
            and second_score > 0.2
        ):
            # Deduplicate signals while preserving insertion order
            combined_signals = list(dict.fromkeys(top_signals + second_signals))
            return DriftClassification(
                drift_type="mixed",
                confidence=round(top_score, 4),
                recommended_action=self._recommended_action(
                    "mixed", primary=top_type, secondary=second_type
                ),
                secondary_type=second_type,
                secondary_confidence=round(second_score, 4),
                signals_used=combined_signals,
            )

        # ── Clear winner ───────────────────────────────────────────────────────
        return DriftClassification(
            drift_type=top_type,
            confidence=round(top_score, 4),
            recommended_action=self._recommended_action(top_type),
            secondary_type=None,
            secondary_confidence=None,
            signals_used=top_signals,
        )

    # ── Private Scoring Methods ────────────────────────────────────────────────

    def _score_covariate_shift(
        self, signals: DriftSignals
    ) -> tuple[float, list[str]]:
        """
        Score evidence for covariate shift.

        Covariate shift: the input feature distribution P(X) has changed,
        but the conditional relationship P(Y|X) remains valid. The model
        is technically correct but is now operating outside its training
        distribution.

        Typical signal: high PSI on a small number of features while the
        prediction output remains relatively stable.

        Note: Requires PSI data — returns (0.0, []) without it, since
        covariate shift cannot be assessed when no feature distributions
        were evaluated.
        """
        # Guard: without PSI data there is no basis to claim covariate shift
        if not signals.psi_scores:
            return 0.0, []

        score: float = 0.5   # Base — covariate shift is the default suspicion when PSI fires
        used: list[str] = []

        # +0.3 — any single feature has high PSI (primary covariate signal)
        high_psi_features = [
            feat for feat, psi in signals.psi_scores.items()
            if psi >= PSI_HIGH_THRESHOLD
        ]
        if high_psi_features:
            score += 0.3
            for feat in high_psi_features:
                used.append(f"high_psi_feature:{feat}")

        # +0.2 — very low prediction shift confirms features drifted but model output is stable
        if signals.prediction_shift < PREDICTION_SHIFT_MEDIUM:
            score += 0.2
            used.append("prediction_shift_low")

        # -0.2 — high prediction shift contradicts pure covariate shift
        if signals.prediction_shift >= PREDICTION_SHIFT_HIGH:
            score -= 0.2

        # -0.2 — too many features drifted simultaneously → looks like upstream issue
        if signals.feature_count_drifted >= FEATURE_COUNT_UPSTREAM_THRESHOLD:
            score -= 0.2

        return max(0.0, min(1.0, score)), used

    def _score_concept_drift(
        self, signals: DriftSignals
    ) -> tuple[float, list[str]]:
        """
        Score evidence for concept drift.

        Concept drift: the statistical relationship P(Y|X) has changed —
        the patterns the model learned no longer reflect reality. The model
        is actively making wrong predictions even for familiar inputs.

        Typical signals: rising prediction shift, increasing error rate
        (when actuals available), and sequential detector firing on the
        prediction stream.
        """
        score: float = 0.0
        used: list[str] = []

        # +0.4 — mean prediction output shifted significantly
        if signals.prediction_shift >= PREDICTION_SHIFT_HIGH:
            score += 0.4
            used.append("prediction_shift_high")

        # +0.3 — we have ground truth and the error rate is rising
        if signals.has_actuals and signals.error_rate_delta >= ERROR_RATE_DELTA_SIGNIFICANT:
            score += 0.3
            used.append("error_rate_rising")

        # +0.3 — CUSUM or Page-Hinkley detected a regime change in the prediction stream
        if signals.sequential_detector_fired:
            score += 0.3
            used.append("sequential_detector_fired")

        # +0.1 — medium PSI on any feature supports gradual concept shift
        #         (slight feature movement alongside model degradation)
        medium_psi_features = [
            feat for feat, psi in signals.psi_scores.items()
            if PSI_MEDIUM_THRESHOLD <= psi < PSI_HIGH_THRESHOLD
        ]
        if medium_psi_features:
            score += 0.1
            used.append(f"medium_psi_feature:{medium_psi_features[0]}")

        # -0.2 — PSI is high on 3+ features simultaneously → upstream issue, not concept drift
        high_psi_count = sum(
            1 for psi in signals.psi_scores.values()
            if psi >= PSI_HIGH_THRESHOLD
        )
        if high_psi_count >= FEATURE_COUNT_UPSTREAM_THRESHOLD:
            score -= 0.2

        return max(0.0, min(1.0, score)), used

    def _score_label_drift(
        self, signals: DriftSignals
    ) -> tuple[float, list[str]]:
        """
        Score evidence for label drift.

        Label drift: the marginal target distribution P(Y) has shifted —
        e.g. class imbalance changed over time. The model and features are
        intact, but the prior has moved, causing systematic output shifts
        without corresponding feature-space changes.

        Validity gate: only meaningful when ground-truth labels are available
        OR when prediction shift is high while all feature PSIs are clean
        (output shifted without any feature-space change — the hallmark of
        pure label drift).
        """
        score: float = 0.0
        used: list[str] = []

        # Pre-compute: are ALL feature PSI scores below the medium threshold?
        all_psi_clean = bool(signals.psi_scores) and all(
            psi < PSI_MEDIUM_THRESHOLD for psi in signals.psi_scores.values()
        )

        # Validity gate — label drift assessment requires one of:
        #   1. Ground-truth labels available for direct measurement, OR
        #   2. Prediction shift is high while all feature PSIs are clean
        #      (output moved without any feature-space explanation)
        prediction_high_and_clean = (
            signals.prediction_shift >= PREDICTION_SHIFT_HIGH and all_psi_clean
        )
        if not signals.has_actuals and not prediction_high_and_clean:
            return 0.0, []

        # +0.5 — prediction output shifted significantly (proxy for label shift)
        if signals.prediction_shift >= PREDICTION_SHIFT_HIGH:
            score += 0.5
            used.append("prediction_shift_high")

        # +0.3 — all feature distributions are clean; only the output shifted
        if all_psi_clean:
            score += 0.3
            used.append("all_features_psi_clean")

        # -0.3 — rising error rate points to concept drift, not label drift
        if signals.error_rate_delta >= ERROR_RATE_DELTA_SIGNIFICANT:
            score -= 0.3

        # -0.2 — sequential detector firing points to a regime change (concept drift)
        if signals.sequential_detector_fired:
            score -= 0.2

        return max(0.0, min(1.0, score)), used

    def _score_upstream_data_issue(
        self, signals: DriftSignals
    ) -> tuple[float, list[str]]:
        """
        Score evidence for an upstream data pipeline issue.

        Upstream data issue: many features drifted simultaneously, which is
        unlikely from natural population shift. This pattern strongly suggests
        a broken ETL job, schema change, missing join, or feature-store
        corruption that corrupted multiple columns at once.

        Key differentiator from covariate shift: the scale (3+ features at
        once vs. 1–2 features from natural population movement).
        """
        score: float = 0.0
        used: list[str] = []

        # +0.6 — 3+ features drifted simultaneously (primary upstream signal)
        if signals.feature_count_drifted >= FEATURE_COUNT_UPSTREAM_THRESHOLD:
            score += 0.6
            used.append(f"feature_count_drifted:{signals.feature_count_drifted}")

        # +0.3 — 5+ features drifted (even stronger signal — almost certainly a pipeline bug)
        if signals.feature_count_drifted >= 5:
            score += 0.3
            used.append("feature_count_drifted_severe")

        # +0.1 — prediction output also shifted (cascade effect of corrupted upstream data)
        if signals.prediction_shift >= PREDICTION_SHIFT_MEDIUM:
            score += 0.1
            used.append("prediction_shift_medium")

        return max(0.0, min(1.0, score)), used

    # ── Recommended Action Lookup ──────────────────────────────────────────────

    @staticmethod
    def _recommended_action(
        drift_type: str,
        primary: Optional[str] = None,
        secondary: Optional[str] = None,
    ) -> str:
        """
        Return a human-readable recommended action for the on-call engineer.

        For the mixed case, primary and secondary identify the two competing
        drift types so the combined guidance can be assembled.
        """
        _actions: dict[str, str] = {
            "covariate_shift": (
                "Input feature distributions have shifted. "
                "Inspect recent data pipelines for population shifts or schema changes. "
                "Consider retraining with recent data if the shift is sustained "
                "over multiple drift windows."
            ),
            "concept_drift": (
                "The model's predictive relationship has degraded. "
                "Validate performance with recent labeled data, review error metrics, "
                "and schedule a retraining run against the updated distribution."
            ),
            "label_drift": (
                "Target class distribution has shifted (e.g. class imbalance changed). "
                "Review upstream labeling processes and business context for the change. "
                "Adjust decision thresholds or retrain if the imbalance shift is permanent."
            ),
            "upstream_data_issue": (
                "Multiple features drifted simultaneously — this is likely a data pipeline "
                "problem, not natural population shift. Immediately check the feature store, "
                "ETL jobs, and ingestion logs for schema changes, missing joins, or broken "
                "transformations before considering retraining."
            ),
            "unknown": (
                "Insufficient signal to classify drift. Run manual inspection."
            ),
        }

        if drift_type == "mixed":
            p_label = primary or "unknown"
            s_label = secondary or "unknown"
            p_action = _actions.get(p_label, "")
            s_action = _actions.get(s_label, "")
            return (
                f"Mixed drift detected: evidence for both '{p_label}' and '{s_label}'. "
                f"Investigate both in parallel. "
                f"[{p_label.replace('_', ' ').title()}]: {p_action} "
                f"[{s_label.replace('_', ' ').title()}]: {s_action}"
            )

        return _actions.get(
            drift_type, "Unknown drift type. Perform manual inspection."
        )
