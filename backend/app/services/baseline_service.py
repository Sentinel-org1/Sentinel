"""
backend/app/services/baseline_service.py
-----------------------------------------
Computes and persists reference baseline statistics for a model's
feature set. Used by all drift detectors as the reference distribution.

Supported feature types:
  - Numeric  → mean, std, min, max, percentiles (p5–p95), histogram
  - Categorical → value_counts, n_unique, top_k frequencies
  - Boolean  → treated as categorical (True/False counts)
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.baseline import ReferenceBaseline

N_HISTOGRAM_BINS = 20
TOP_K_CATEGORIES = 20


class BaselineService:

    # ── Public API ─────────────────────────────────────────────
    async def compute_and_save(
        self,
        db: AsyncSession,
        model_id: int,
        data: list[dict[str, Any]],
    ) -> ReferenceBaseline:
        """
        Accepts a list of feature dicts (one per training sample),
        computes per-feature statistics, and persists as a new baseline version.
        """
        if not data:
            raise ValueError("data must not be empty")

        feature_stats = self._compute_stats(data)
        version = await self._next_version(db, model_id)

        baseline = ReferenceBaseline(
            model_id=model_id,
            version=version,
            feature_stats=feature_stats,
            n_samples=len(data),
        )
        db.add(baseline)
        await db.commit()
        await db.refresh(baseline)
        return baseline

    async def get_latest(
        self, db: AsyncSession, model_id: int
    ) -> ReferenceBaseline | None:
        result = await db.execute(
            select(ReferenceBaseline)
            .where(ReferenceBaseline.model_id == model_id)
            .order_by(ReferenceBaseline.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── Statistics computation ─────────────────────────────────
    def _compute_stats(self, data: list[dict]) -> dict[str, dict]:
        """Return {feature_name: stats_dict} for all features."""
        if not data:
            return {}

        # Pivot rows → columns
        feature_names = list(data[0].keys())
        columns: dict[str, list] = {f: [] for f in feature_names}
        for row in data:
            for f in feature_names:
                columns[f].append(row.get(f))

        stats: dict[str, dict] = {}
        for feature, values in columns.items():
            clean = [v for v in values if v is not None]
            if not clean:
                stats[feature] = {"type": "unknown", "n_missing": len(values)}
                continue

            # Type inference
            if all(isinstance(v, bool) for v in clean):
                stats[feature] = self._categorical_stats(
                    [str(v) for v in clean], n_total=len(values)
                )
                stats[feature]["type"] = "boolean"
            elif all(isinstance(v, (int, float)) for v in clean):
                stats[feature] = self._numeric_stats(clean, n_total=len(values))
            else:
                stats[feature] = self._categorical_stats(
                    [str(v) for v in clean], n_total=len(values)
                )

        return stats

    def _numeric_stats(self, values: list[float], n_total: int) -> dict:
        arr = np.array(values, dtype=float)
        counts, bin_edges = np.histogram(arr, bins=N_HISTOGRAM_BINS)
        percentiles = np.percentile(arr, [5, 10, 25, 50, 75, 90, 95])

        return {
            "type": "numeric",
            "count": len(arr),
            "n_missing": n_total - len(arr),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "p5":  float(percentiles[0]),
            "p10": float(percentiles[1]),
            "p25": float(percentiles[2]),
            "p50": float(percentiles[3]),
            "p75": float(percentiles[4]),
            "p90": float(percentiles[5]),
            "p95": float(percentiles[6]),
            "histogram": {
                "counts": counts.tolist(),
                "bin_edges": bin_edges.tolist(),
            },
        }

    def _categorical_stats(self, values: list[str], n_total: int) -> dict:
        from collections import Counter
        counts = Counter(values)
        n = len(values)
        top_k = dict(counts.most_common(TOP_K_CATEGORIES))
        frequencies = {k: v / n for k, v in top_k.items()}

        return {
            "type": "categorical",
            "count": n,
            "n_missing": n_total - n,
            "n_unique": len(counts),
            "top_k_counts": top_k,
            "top_k_frequencies": frequencies,
        }

    # ── Helpers ────────────────────────────────────────────────
    async def _next_version(self, db: AsyncSession, model_id: int) -> int:
        baseline = await self.get_latest(db, model_id)
        return (baseline.version + 1) if baseline else 1


baseline_service = BaselineService()