"""
Δ_SHAP: Feature Attribution for Drift Explanation

Tracks the change in SHAP feature importance between a baseline window and
the current (live) window.  Answers the question: "which features caused
the model's behaviour to change?"

Flow:
    1. Compute SHAP values on a sample of the baseline data.
    2. Compute SHAP values on a sample of the current data.
    3. Take the mean(|SHAP|) per feature for each window → importance vector.
    4. Delta = current_importance - baseline_importance per feature.
    5. Rank features by |delta| descending → ``top_movers``.

Explainer selection:
    - If the model has a ``.predict_proba`` method, we use it as the model
      function for SHAP (classification models).
    - Otherwise we fall back to ``.predict`` (regression models).
    - ``shap.Explainer`` auto-selects the appropriate algorithm
      (Tree, Linear, Kernel) based on the model type.

Performance:
    - Baseline and current data are subsampled to ``max_samples`` (default 100)
      to keep SHAP computation tractable.
    - A ``background_samples`` subset (default 50) is used as the SHAP
      background dataset for KernelExplainer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union

import numpy as np
import shap
import structlog

logger = structlog.get_logger()

# ── Module-level constants ──────────────────────────────────────────────────
DEFAULT_MAX_SAMPLES: int = 100       # Max rows to explain per window
DEFAULT_BACKGROUND_SAMPLES: int = 50 # Background dataset size for Explainer


# ── Result Dataclass ────────────────────────────────────────────────────────
@dataclass
class DeltaSHAPResult:
    """Output of DeltaSHAP.compute().

    Attributes
    ----------
    feature_deltas : dict[str, float]
        Feature name → (current_importance - baseline_importance).
        Positive means the feature became MORE important; negative means LESS.
    top_movers : list[tuple[str, float]]
        Features sorted by |delta| descending.  Each entry is
        (feature_name, delta_value).
    baseline_importances : dict[str, float]
        Mean |SHAP| per feature on the baseline window.
    current_importances : dict[str, float]
        Mean |SHAP| per feature on the current window.
    """
    feature_deltas: dict[str, float] = field(default_factory=dict)
    top_movers: list[tuple[str, float]] = field(default_factory=list)
    baseline_importances: dict[str, float] = field(default_factory=dict)
    current_importances: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to a plain dict safe for JSON / DB storage."""
        return {
            "feature_deltas": {k: round(v, 8) for k, v in self.feature_deltas.items()},
            "top_movers": [(k, round(v, 8)) for k, v in self.top_movers],
            "baseline_importances": {
                k: round(v, 8) for k, v in self.baseline_importances.items()
            },
            "current_importances": {
                k: round(v, 8) for k, v in self.current_importances.items()
            },
        }


# ── Core Class ──────────────────────────────────────────────────────────────
class DeltaSHAP:
    """SHAP-based feature attribution for drift explanation.

    Usage
    -----
    >>> delta_shap = DeltaSHAP()
    >>> result = delta_shap.compute(model, baseline_data, current_data)
    >>> print(result.top_movers[:3])   # top-3 features that changed most
    """

    def __init__(
        self,
        max_samples: int = DEFAULT_MAX_SAMPLES,
        background_samples: int = DEFAULT_BACKGROUND_SAMPLES,
        random_seed: int = 42,
    ) -> None:
        """
        Args:
            max_samples: Maximum rows to SHAP-explain per window.
            background_samples: Number of background samples for the Explainer.
            random_seed: Seed for reproducible subsampling.
        """
        self.max_samples = max_samples
        self.background_samples = background_samples
        self.random_seed = random_seed

    def compute(
        self,
        model: Any,
        baseline_data: np.ndarray,
        current_data: np.ndarray,
        feature_names: Optional[list[str]] = None,
    ) -> DeltaSHAPResult:
        """Compute Δ_SHAP between baseline and current data windows.

        Args:
            model:
                A fitted model object.  Must support ``.predict()`` or
                ``.predict_proba()``.
            baseline_data:
                2-D array of shape (n_baseline, n_features) from the
                reference window.
            current_data:
                2-D array of shape (n_current, n_features) from the
                live/current window.
            feature_names:
                Optional list of feature names.  If None, features are
                named ``feature_0``, ``feature_1``, etc.

        Returns:
            DeltaSHAPResult with per-feature deltas and top movers.

        Raises:
            ValueError: If baseline or current data have incompatible shapes.
        """
        baseline_data = np.asarray(baseline_data, dtype=np.float64)
        current_data = np.asarray(current_data, dtype=np.float64)

        # ── Validate shapes ──────────────────────────────────────────────
        if baseline_data.ndim == 1:
            baseline_data = baseline_data.reshape(-1, 1)
        if current_data.ndim == 1:
            current_data = current_data.reshape(-1, 1)

        if baseline_data.shape[1] != current_data.shape[1]:
            raise ValueError(
                f"Feature count mismatch: baseline has {baseline_data.shape[1]} "
                f"features, current has {current_data.shape[1]}"
            )

        n_features = baseline_data.shape[1]

        # ── Assign feature names ─────────────────────────────────────────
        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(n_features)]
        elif len(feature_names) != n_features:
            raise ValueError(
                f"feature_names length ({len(feature_names)}) does not match "
                f"number of features ({n_features})"
            )

        # ── Subsample for performance ────────────────────────────────────
        rng = np.random.default_rng(self.random_seed)

        baseline_sample = self._subsample(baseline_data, self.max_samples, rng)
        current_sample = self._subsample(current_data, self.max_samples, rng)
        background = self._subsample(baseline_data, self.background_samples, rng)

        # ── Select prediction function ───────────────────────────────────
        predict_fn = self._get_predict_function(model)

        # ── Create SHAP explainer ────────────────────────────────────────
        try:
            explainer = shap.Explainer(predict_fn, background)
        except Exception:
            # Fallback: KernelExplainer for models SHAP can't auto-detect
            logger.info("delta_shap_kernel_fallback", model_type=type(model).__name__)
            explainer = shap.KernelExplainer(predict_fn, background)

        # ── Compute SHAP values ──────────────────────────────────────────
        baseline_shap_values = explainer(baseline_sample)
        current_shap_values = explainer(current_sample)

        # ── Extract SHAP value arrays ────────────────────────────────────
        baseline_vals = self._extract_shap_array(baseline_shap_values)
        current_vals = self._extract_shap_array(current_shap_values)

        # ── Compute mean |SHAP| per feature ──────────────────────────────
        baseline_importance = np.mean(np.abs(baseline_vals), axis=0)
        current_importance = np.mean(np.abs(current_vals), axis=0)

        # ── Build result ─────────────────────────────────────────────────
        feature_deltas: dict[str, float] = {}
        baseline_importances: dict[str, float] = {}
        current_importances: dict[str, float] = {}

        for i, name in enumerate(feature_names):
            bl_imp = float(baseline_importance[i])
            cur_imp = float(current_importance[i])
            feature_deltas[name] = cur_imp - bl_imp
            baseline_importances[name] = bl_imp
            current_importances[name] = cur_imp

        # Sort by |delta| descending
        top_movers = sorted(
            feature_deltas.items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )

        logger.info(
            "delta_shap_computed",
            n_features=n_features,
            n_baseline=baseline_sample.shape[0],
            n_current=current_sample.shape[0],
            top_mover=top_movers[0][0] if top_movers else "none",
            top_delta=round(top_movers[0][1], 6) if top_movers else 0.0,
        )

        return DeltaSHAPResult(
            feature_deltas=feature_deltas,
            top_movers=top_movers,
            baseline_importances=baseline_importances,
            current_importances=current_importances,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _get_predict_function(model: Any):
        """Select the best prediction function from the model.

        Prefers predict_proba for classification models (gives per-class
        SHAP values), falls back to predict for regression.
        """
        if hasattr(model, "predict_proba"):
            return model.predict_proba
        return model.predict

    @staticmethod
    def _subsample(
        data: np.ndarray,
        max_n: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Return data subsampled to at most max_n rows."""
        if data.shape[0] <= max_n:
            return data.copy()
        indices = rng.choice(data.shape[0], size=max_n, replace=False)
        return data[indices]

    @staticmethod
    def _extract_shap_array(shap_values) -> np.ndarray:
        """Extract a 2-D (n_samples, n_features) array from SHAP output.

        SHAP returns different shapes depending on the model type:
        - Regression / binary TreeExplainer: (n_samples, n_features)
        - Multi-class: (n_samples, n_features, n_classes)
        - shap.Explanation object with .values attribute

        For multi-class, we take the mean absolute across classes.
        """
        vals = shap_values.values if hasattr(shap_values, "values") else np.asarray(shap_values)
        vals = np.asarray(vals, dtype=np.float64)

        if vals.ndim == 3:
            # Multi-class: average absolute SHAP across classes
            vals = np.mean(np.abs(vals), axis=2)

        return vals
