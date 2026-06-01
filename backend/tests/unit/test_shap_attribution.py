"""
backend/tests/unit/test_shap_attribution.py
---------------------------------------------
Unit tests for DeltaSHAP feature attribution (Δ_SHAP novelty).
Pure computation tests — no DB, no async, no HTTP.

Uses sklearn DecisionTreeClassifier as a lightweight, deterministic model
that SHAP's TreeExplainer can handle efficiently.
"""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.novelties.shap_attribution import DeltaSHAP, DeltaSHAPResult


# ── Shared fixtures ────────────────────────────────────────────
RNG = np.random.default_rng(42)


@pytest.fixture
def simple_classifier():
    """Train a small DecisionTreeClassifier on synthetic 3-feature data."""
    X = RNG.normal(0, 1, (200, 3))
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    model = DecisionTreeClassifier(max_depth=4, random_state=42)
    model.fit(X, y)
    return model


@pytest.fixture
def simple_regressor():
    """Train a small DecisionTreeRegressor on synthetic 3-feature data."""
    X = RNG.normal(0, 1, (200, 3))
    y = X[:, 0] * 2 + X[:, 1] + RNG.normal(0, 0.1, 200)
    model = DecisionTreeRegressor(max_depth=4, random_state=42)
    model.fit(X, y)
    return model


@pytest.fixture
def baseline_data():
    """Baseline data: 100 samples × 3 features, standard normal."""
    return RNG.normal(0, 1, (100, 3))


@pytest.fixture
def current_data():
    """Current data: same distribution as baseline (no drift)."""
    return RNG.normal(0, 1, (100, 3))


@pytest.fixture
def shifted_current_data():
    """Current data with feature_0 shifted by +3 (strong drift on one feature)."""
    data = RNG.normal(0, 1, (100, 3))
    data[:, 0] += 3.0  # Shift feature 0
    return data


# ── Test 1 — Basic compute returns correct structure ───────────
class TestBasicCompute:
    def test_returns_delta_shap_result(
        self, simple_classifier, baseline_data, current_data
    ):
        """compute() should return a DeltaSHAPResult with all fields."""
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20, random_seed=42)
        result = delta_shap.compute(
            model=simple_classifier,
            baseline_data=baseline_data,
            current_data=current_data,
            feature_names=["f0", "f1", "f2"],
        )

        assert isinstance(result, DeltaSHAPResult)
        assert len(result.feature_deltas) == 3
        assert len(result.top_movers) == 3
        assert len(result.baseline_importances) == 3
        assert len(result.current_importances) == 3


# ── Test 2 — Feature deltas keys match input names ─────────────
class TestFeatureNames:
    def test_deltas_keys_match_feature_names(
        self, simple_classifier, baseline_data, current_data
    ):
        """feature_deltas keys must match the provided feature_names."""
        names = ["age", "income", "tenure"]
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=simple_classifier,
            baseline_data=baseline_data,
            current_data=current_data,
            feature_names=names,
        )

        assert set(result.feature_deltas.keys()) == set(names)
        assert set(result.baseline_importances.keys()) == set(names)
        assert set(result.current_importances.keys()) == set(names)

    def test_auto_generated_feature_names(
        self, simple_classifier, baseline_data, current_data
    ):
        """Without feature_names, should auto-generate feature_0, etc."""
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=simple_classifier,
            baseline_data=baseline_data,
            current_data=current_data,
        )

        assert "feature_0" in result.feature_deltas
        assert "feature_1" in result.feature_deltas
        assert "feature_2" in result.feature_deltas


# ── Test 3 — top_movers sorted by absolute delta ──────────────
class TestTopMovers:
    def test_top_movers_sorted_descending(
        self, simple_classifier, baseline_data, shifted_current_data
    ):
        """top_movers must be sorted by |delta| descending."""
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=simple_classifier,
            baseline_data=baseline_data,
            current_data=shifted_current_data,
            feature_names=["f0", "f1", "f2"],
        )

        abs_deltas = [abs(d) for _, d in result.top_movers]
        assert abs_deltas == sorted(abs_deltas, reverse=True)


# ── Test 4 — Identical data produces near-zero deltas ──────────
class TestIdenticalData:
    def test_same_distribution_near_zero_deltas(self, simple_classifier):
        """When baseline == current, deltas should be near zero."""
        data = RNG.normal(0, 1, (100, 3))
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20, random_seed=42)
        result = delta_shap.compute(
            model=simple_classifier,
            baseline_data=data,
            current_data=data,  # Same data
            feature_names=["f0", "f1", "f2"],
        )

        for delta in result.feature_deltas.values():
            assert abs(delta) < 0.1, f"Delta {delta} too large for identical data"


# ── Test 5 — Shifted feature produces the largest delta ────────
class TestShiftedFeature:
    def test_shifted_feature_is_top_mover(
        self, simple_classifier, baseline_data, shifted_current_data
    ):
        """The feature with a +3 shift should appear as the top mover."""
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=simple_classifier,
            baseline_data=baseline_data,
            current_data=shifted_current_data,
            feature_names=["f0", "f1", "f2"],
        )

        top_feature, _ = result.top_movers[0]
        assert top_feature == "f0", (
            f"Expected f0 (shifted) as top mover, got {top_feature}"
        )


# ── Test 6 — to_dict serialisation ─────────────────────────────
class TestSerialisation:
    def test_to_dict_is_json_safe(
        self, simple_classifier, baseline_data, current_data
    ):
        """to_dict() must produce a dict with JSON-safe values."""
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=simple_classifier,
            baseline_data=baseline_data,
            current_data=current_data,
            feature_names=["f0", "f1", "f2"],
        )
        d = result.to_dict()

        assert set(d.keys()) == {
            "feature_deltas", "top_movers",
            "baseline_importances", "current_importances",
        }

        # All values should be serialisable
        for v in d["feature_deltas"].values():
            assert isinstance(v, float)
        for name, v in d["top_movers"]:
            assert isinstance(name, str)
            assert isinstance(v, float)


# ── Test 7 — Single feature ───────────────────────────────────
class TestSingleFeature:
    def test_single_feature_works(self):
        """Model with a single feature should produce valid results."""
        X = RNG.normal(0, 1, (200, 1))
        y = (X[:, 0] > 0).astype(int)
        model = DecisionTreeClassifier(max_depth=2, random_state=42)
        model.fit(X, y)

        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=model,
            baseline_data=X[:100],
            current_data=X[100:],
            feature_names=["only_feature"],
        )

        assert len(result.feature_deltas) == 1
        assert "only_feature" in result.feature_deltas


# ── Test 8 — Regressor (predict only, no predict_proba) ───────
class TestRegressorModel:
    def test_regressor_uses_predict(
        self, simple_regressor, baseline_data, current_data
    ):
        """A regressor without predict_proba should use predict."""
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=simple_regressor,
            baseline_data=baseline_data,
            current_data=current_data,
            feature_names=["f0", "f1", "f2"],
        )

        assert isinstance(result, DeltaSHAPResult)
        assert len(result.feature_deltas) == 3


# ── Test 9 — Shape validation ─────────────────────────────────
class TestShapeValidation:
    def test_feature_count_mismatch_raises(self, simple_classifier):
        """Mismatched feature counts should raise ValueError."""
        baseline = RNG.normal(0, 1, (50, 3))
        current = RNG.normal(0, 1, (50, 2))

        delta_shap = DeltaSHAP()
        with pytest.raises(ValueError, match="Feature count mismatch"):
            delta_shap.compute(
                model=simple_classifier,
                baseline_data=baseline,
                current_data=current,
            )

    def test_feature_names_length_mismatch_raises(self, simple_classifier):
        """Wrong number of feature_names should raise ValueError."""
        data = RNG.normal(0, 1, (50, 3))

        delta_shap = DeltaSHAP()
        with pytest.raises(ValueError, match="feature_names length"):
            delta_shap.compute(
                model=simple_classifier,
                baseline_data=data,
                current_data=data,
                feature_names=["only_two", "features"],
            )

    def test_1d_input_is_reshaped(self, simple_classifier):
        """1-D arrays should be auto-reshaped to 2-D."""
        X = RNG.normal(0, 1, (200, 1))
        y = (X[:, 0] > 0).astype(int)
        model = DecisionTreeClassifier(max_depth=2, random_state=42)
        model.fit(X, y)

        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=model,
            baseline_data=X[:100].ravel(),  # 1-D
            current_data=X[100:].ravel(),   # 1-D
        )

        assert isinstance(result, DeltaSHAPResult)
        assert len(result.feature_deltas) == 1


# ── Test 10 — Importances are non-negative ─────────────────────
class TestImportancesNonNegative:
    def test_all_importances_non_negative(
        self, simple_classifier, baseline_data, current_data
    ):
        """Mean |SHAP| importances must be ≥ 0."""
        delta_shap = DeltaSHAP(max_samples=50, background_samples=20)
        result = delta_shap.compute(
            model=simple_classifier,
            baseline_data=baseline_data,
            current_data=current_data,
        )

        for v in result.baseline_importances.values():
            assert v >= 0.0
        for v in result.current_importances.values():
            assert v >= 0.0
