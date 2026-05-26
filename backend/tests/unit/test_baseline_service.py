"""
backend/tests/unit/test_baseline_service.py
---------------------------------------------
Tests for BaselineService._compute_stats — the core statistics engine.
No DB needed; we test the pure computation layer directly.
"""
from __future__ import annotations

import math
import pytest

from app.services.baseline_service import BaselineService

svc = BaselineService()


# ── Helpers ────────────────────────────────────────────────────
def compute(data):
    return svc._compute_stats(data)


# ── Numeric feature tests ──────────────────────────────────────
class TestNumericStats:
    def test_basic_statistics(self):
        data = [{"age": float(i)} for i in range(1, 101)]
        stats = compute(data)["age"]
        assert stats["type"] == "numeric"
        assert stats["count"] == 100
        assert stats["n_missing"] == 0
        assert math.isclose(stats["mean"], 50.5, rel_tol=1e-6)
        assert stats["min"] == 1.0
        assert stats["max"] == 100.0

    def test_percentiles_monotone(self):
        import random
        data = [{"x": random.gauss(0, 1)} for _ in range(500)]
        stats = compute(data)["x"]
        assert stats["p5"] <= stats["p10"] <= stats["p25"] <= stats["p50"]
        assert stats["p50"] <= stats["p75"] <= stats["p90"] <= stats["p95"]

    def test_histogram_bins_and_counts(self):
        data = [{"income": float(i * 1000)} for i in range(20)]
        stats = compute(data)["income"]
        hist = stats["histogram"]
        assert len(hist["bin_edges"]) == 21  # N_HISTOGRAM_BINS + 1
        assert sum(hist["counts"]) == 20
        assert all(c >= 0 for c in hist["counts"])

    def test_single_value(self):
        """Degenerate: all values identical — std = 0."""
        data = [{"x": 5.0} for _ in range(10)]
        stats = compute(data)["x"]
        assert stats["std"] == 0.0
        assert stats["min"] == stats["max"] == 5.0

    def test_missing_values_counted(self):
        data = [{"x": 1.0}, {"x": None}, {"x": 3.0}, {"x": None}]
        stats = compute(data)["x"]
        assert stats["count"] == 2
        assert stats["n_missing"] == 2


# ── Categorical feature tests ──────────────────────────────────
class TestCategoricalStats:
    def test_type_detection(self):
        data = [{"country": "IN"}, {"country": "US"}, {"country": "IN"}]
        stats = compute(data)["country"]
        assert stats["type"] == "categorical"

    def test_frequency_sums_to_one(self):
        data = [{"color": c} for c in ["red"] * 5 + ["blue"] * 3 + ["green"] * 2]
        stats = compute(data)["color"]
        total_freq = sum(stats["top_k_frequencies"].values())
        assert math.isclose(total_freq, 1.0, rel_tol=1e-9)

    def test_n_unique(self):
        data = [{"label": str(i % 5)} for i in range(20)]
        stats = compute(data)["label"]
        assert stats["n_unique"] == 5

    def test_top_k_limited_to_20(self):
        """Verify we cap at TOP_K_CATEGORIES even with many distinct values."""
        data = [{"code": str(i)} for i in range(100)]
        stats = compute(data)["code"]
        assert len(stats["top_k_counts"]) <= 20


# ── Boolean feature tests ──────────────────────────────────────
class TestBooleanStats:
    def test_detected_as_boolean(self):
        data = [{"active": True}, {"active": False}, {"active": True}]
        stats = compute(data)["active"]
        assert stats["type"] == "boolean"

    def test_counts_correct(self):
        data = [{"flag": True} for _ in range(7)] + [{"flag": False} for _ in range(3)]
        stats = compute(data)["flag"]
        assert stats["top_k_counts"]["True"] == 7
        assert stats["top_k_counts"]["False"] == 3


# ── Multi-feature tests ────────────────────────────────────────
class TestMultiFeature:
    def test_multiple_features_returned(self):
        data = [
            {"age": 25.0, "country": "IN", "active": True},
            {"age": 30.0, "country": "US", "active": False},
        ]
        stats = compute(data)
        assert set(stats.keys()) == {"age", "country", "active"}

    def test_empty_data_returns_empty_dict(self):
        assert compute([]) == {}

    def test_all_null_feature(self):
        data = [{"x": None}, {"x": None}]
        stats = compute(data)["x"]
        assert stats["type"] == "unknown"
        assert stats["n_missing"] == 2


# ── Version increment test (needs DB — skip in unit suite) ─────
# See integration/test_baseline_api.py for DB-backed version tests