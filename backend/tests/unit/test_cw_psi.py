from __future__ import annotations

"""
Tests for Confidence-Weighted PSI (CW-PSI) novelty detector.

Run from the backend directory:
    python -m pytest tests/test_cw_psi.py -v

Or standalone (no pytest needed):
    python tests/test_cw_psi.py
"""

import sys
import os
import types

# ---------------------------------------------------------------------------
# Bootstrap: ensure `app` package is importable & stub out structlog
# so tests run without the full dependency stack installed.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Minimal structlog stub
_fake_structlog = types.ModuleType("structlog")


class _FakeLogger:
    def info(self, *a: object, **kw: object) -> None: pass
    def warning(self, *a: object, **kw: object) -> None: pass
    def error(self, *a: object, **kw: object) -> None: pass
    def debug(self, *a: object, **kw: object) -> None: pass


setattr(_fake_structlog, "get_logger", lambda: _FakeLogger())  # noqa: B010
sys.modules.setdefault("structlog", _fake_structlog)

import numpy as np
from app.novelties.cw_psi import ConfidenceWeightedPSI, CWPSIResult

# Reproducible randomness
rng = np.random.default_rng(42)


# ===================================================================
# Helpers
# ===================================================================
_passed = 0
_failed = 0

def _report(name: str, ok: bool, detail: str = ""):
    global _passed, _failed
    icon = "[PASS]" if ok else "[FAIL]"
    msg = f"  {icon} {name}"
    if detail:
        msg += f"  --  {detail}"
    print(msg)
    if ok:
        _passed += 1
    else:
        _failed += 1


# ===================================================================
# Test data factories
# ===================================================================
def _baseline(n=500, mean=50, std=10):
    return rng.normal(mean, std, n)

def _confidences(n=500, lo=0.6, hi=1.0):
    return rng.uniform(lo, hi, n)

def _shifted(n=200, mean=55, std=14):
    """Current window with moderate distribution shift."""
    return rng.normal(mean, std, n)


# ===================================================================
# Tests
# ===================================================================

def test_fit_and_score_basic():
    """Fit with confidence, score with confidence -- happy path."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    bl = _baseline()
    bl_conf = _confidences(n=500)

    det.fit(bl, bl_conf, feature_name="age")
    _report("fit() succeeds", det.is_fitted)
    _report("n_bins set", det.n_bins >= 1, f"n_bins={det.n_bins}")

    cur = _shifted()
    cur_conf = _confidences(n=200, lo=0.7, hi=1.0)
    result = det.score(cur, cur_conf)

    _report("returns CWPSIResult", isinstance(result, CWPSIResult))
    _report("PSI >= 0", result.psi >= 0, f"PSI={result.psi:.6f}")
    _report("CW-PSI >= 0", result.cw_psi >= 0, f"CW-PSI={result.cw_psi:.6f}")
    _report("not fallback mode", not result.is_fallback)
    _report("per_bin arrays match n_bins",
            len(result.per_bin_psi) == det.n_bins and
            len(result.per_bin_cw_psi) == det.n_bins)
    _report("current_weights length", len(result.current_weights) == det.n_bins)



def test_compare_both_metrics():
    """score() always returns BOTH standard PSI and CW-PSI."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    det.fit(_baseline(), _confidences(500), feature_name="income")
    result = det.score(_shifted(), _confidences(200, lo=0.8, hi=1.0))

    _report("has .psi attribute", hasattr(result, "psi"))
    _report("has .cw_psi attribute", hasattr(result, "cw_psi"))
    _report("PSI and CW-PSI are different (weighted)",
            result.psi != result.cw_psi,
            f"PSI={result.psi:.6f}  CW-PSI={result.cw_psi:.6f}  delta={result.cw_psi - result.psi:+.6f}")


def test_fallback_no_confidence_in_score():
    """When score() gets no confidence data, CW-PSI == PSI (fallback)."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    det.fit(_baseline(), _confidences(500), feature_name="age")

    result = det.score(_shifted(), current_confidences=None)
    _report("is_fallback=True", result.is_fallback)
    _report("CW-PSI equals PSI in fallback",
            abs(result.psi - result.cw_psi) < 1e-12,
            f"PSI={result.psi:.6f}  CW-PSI={result.cw_psi:.6f}")
    _report("weights are all 1.0",
            np.allclose(result.current_weights, 1.0))


def test_fallback_no_confidence_anywhere():
    """Neither fit() nor score() receive confidence data."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    det.fit(_baseline(), feature_name="no_conf_feature")
    result = det.score(_shifted())

    _report("is_fallback=True", result.is_fallback)
    _report("CW-PSI equals PSI",
            abs(result.psi - result.cw_psi) < 1e-12)


def test_insufficient_samples_score():
    """score() with too few samples returns zeroed result gracefully."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=50)
    det.fit(_baseline(), _confidences(500))

    tiny = rng.normal(50, 10, 5)  # way below min_samples
    result = det.score(tiny)

    _report("PSI = 0 on tiny window", result.psi == 0.0)
    _report("CW-PSI = 0 on tiny window", result.cw_psi == 0.0)
    _report("is_fallback=True on tiny window", result.is_fallback)


def test_insufficient_samples_fit():
    """fit() with too few samples raises ValueError."""
    det = ConfidenceWeightedPSI(min_samples=100)
    ok = False
    try:
        det.fit(rng.normal(0, 1, 10))
    except ValueError:
        ok = True
    _report("fit() raises ValueError on small baseline", ok)


def test_score_before_fit():
    """score() before fit() raises RuntimeError."""
    det = ConfidenceWeightedPSI()
    ok = False
    try:
        det.score(rng.normal(0, 1, 100))
    except RuntimeError:
        ok = True
    _report("score() before fit() raises RuntimeError", ok)


def test_mismatched_confidence_lengths():
    """Mismatched array lengths raise ValueError."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    det.fit(_baseline(), _confidences(500))

    # fit mismatch
    ok_fit = False
    try:
        det2 = ConfidenceWeightedPSI(min_samples=30)
        det2.fit(_baseline(200), _confidences(100))  # 200 vs 100
    except ValueError:
        ok_fit = True
    _report("fit() rejects mismatched lengths", ok_fit)

    # score mismatch
    ok_score = False
    try:
        det.score(_shifted(200), _confidences(50))  # 200 vs 50
    except ValueError:
        ok_score = True
    _report("score() rejects mismatched lengths", ok_score)


def test_to_dict_serialisation():
    """to_dict() produces a JSON-safe dict with all expected keys."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    det.fit(_baseline(), _confidences(500))
    result = det.score(_shifted(), _confidences(200))
    d = result.to_dict()

    expected_keys = {"psi", "cw_psi", "per_bin_psi", "per_bin_cw_psi",
                     "current_weights", "n_bins", "is_fallback"}
    _report("to_dict() has all keys", set(d.keys()) == expected_keys,
            f"keys={sorted(d.keys())}")
    _report("per_bin_psi is a list", isinstance(d["per_bin_psi"], list))
    _report("values are JSON-safe (no numpy)",
            all(isinstance(v, (int, float, bool, list)) for v in d.values()))


def test_no_drift_low_psi():
    """Identical distributions should yield very low PSI and CW-PSI."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    bl = _baseline(1000)
    det.fit(bl, _confidences(1000))
    # Score on data from the SAME distribution
    same = rng.normal(50, 10, 500)
    result = det.score(same, _confidences(500))
    _report("no-drift PSI < 0.1", result.psi < 0.1, f"PSI={result.psi:.6f}")
    _report("no-drift CW-PSI < 0.1", result.cw_psi < 0.1, f"CW-PSI={result.cw_psi:.6f}")


def test_heavy_drift_high_psi():
    """Very different distributions should yield high PSI."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    bl = _baseline(1000, mean=50, std=5)
    det.fit(bl, _confidences(1000))
    # Score on heavily shifted data
    drifted = rng.normal(80, 20, 500)
    result = det.score(drifted, _confidences(500, lo=0.9, hi=1.0))
    _report("heavy-drift PSI > 0.25", result.psi > 0.25, f"PSI={result.psi:.6f}")
    _report("heavy-drift CW-PSI > 0.25", result.cw_psi > 0.25, f"CW-PSI={result.cw_psi:.6f}")


def test_confidence_weighting_effect():
    """High-confidence drift yields CW-PSI closer to PSI than low-confidence drift.

    Since w_i in [0,1], CW-PSI <= PSI always.  But when drift happens in
    high-confidence regions, CW-PSI stays close to PSI (preserving the alarm).
    When drift happens in low-confidence regions, CW-PSI drops well below PSI
    (suppressing the alarm — the model "knows" it's uncertain there).
    """
    bl = rng.normal(50, 10, 1000)
    bl_conf = np.full(1000, 0.5)

    cur = rng.normal(65, 10, 500)

    # Case A: high confidence in the drifted window
    det_hi = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    det_hi.fit(bl.copy(), bl_conf.copy())
    result_hi = det_hi.score(cur.copy(), np.full(500, 0.95))

    # Case B: low confidence in the drifted window
    det_lo = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    det_lo.fit(bl.copy(), bl_conf.copy())
    result_lo = det_lo.score(cur.copy(), np.full(500, 0.20))

    # Both should have the same standard PSI (same data)
    _report("same standard PSI for both",
            abs(result_hi.psi - result_lo.psi) < 1e-6,
            f"hi_PSI={result_hi.psi:.6f}  lo_PSI={result_lo.psi:.6f}")

    # CW-PSI should be higher for the high-confidence case
    _report("high-conf CW-PSI > low-conf CW-PSI",
            result_hi.cw_psi > result_lo.cw_psi,
            f"hi_CW={result_hi.cw_psi:.6f}  lo_CW={result_lo.cw_psi:.6f}")

    # CW-PSI <= PSI always (since weights in [0,1])
    _report("CW-PSI <= PSI (mathematical invariant)",
            result_hi.cw_psi <= result_hi.psi + 1e-12)


def test_repr():
    """__repr__ works before and after fitting."""
    det = ConfidenceWeightedPSI(n_bins=8)
    r1 = repr(det)
    _report("repr before fit contains 'unfitted'", "unfitted" in r1, r1)
    det.fit(_baseline(), feature_name="x")
    r2 = repr(det)
    _report("repr after fit contains 'fitted'", "fitted" in r2, r2)


def test_low_cardinality_feature():
    """Features with very few distinct values should dedup bin edges gracefully."""
    det = ConfidenceWeightedPSI(n_bins=10, min_samples=30)
    # Only 3 distinct values
    bl = rng.choice([1.0, 2.0, 3.0], size=300)
    det.fit(bl, _confidences(300))
    _report("low-cardinality deduped bins", det.n_bins < 10,
            f"n_bins={det.n_bins} (requested 10)")
    result = det.score(rng.choice([1.0, 2.0, 3.0], size=100), _confidences(100))
    _report("score succeeds on low-cardinality", result.psi >= 0)


# ===================================================================
# Runner
# ===================================================================

def main():
    print("=" * 64)
    print("  CW-PSI Test Suite")
    print("=" * 64)

    sections = [
        ("Core fit/score",              test_fit_and_score_basic),
        ("Compare: both PSI + CW-PSI",  test_compare_both_metrics),
        ("Fallback: no conf in score",  test_fallback_no_confidence_in_score),
        ("Fallback: no conf anywhere",  test_fallback_no_confidence_anywhere),
        ("Edge: insufficient score",    test_insufficient_samples_score),
        ("Edge: insufficient fit",      test_insufficient_samples_fit),
        ("Edge: score before fit",      test_score_before_fit),
        ("Edge: mismatched lengths",    test_mismatched_confidence_lengths),
        ("Serialisation: to_dict()",    test_to_dict_serialisation),
        ("Drift: no shift = low PSI",   test_no_drift_low_psi),
        ("Drift: heavy shift = high",   test_heavy_drift_high_psi),
        ("Drift: confidence effect",    test_confidence_weighting_effect),
        ("Low-cardinality feature",     test_low_cardinality_feature),
        ("repr()",                      test_repr),
    ]

    for title, fn in sections:
        print(f"\n--- {title} ---")
        fn()

    print("\n" + "=" * 64)
    print(f"  RESULTS:  {_passed} passed,  {_failed} failed")
    print("=" * 64)

    if _failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
