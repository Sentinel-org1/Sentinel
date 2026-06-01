"""
Async SHAP computation Celery task.

Loads a drift event, computes Δ_SHAP feature attribution, and stores the
result back into DriftEvent.shap_attribution (JSONB).

This runs on the dedicated ``shap`` Celery queue to avoid blocking drift
detection. Target execution time: < 5 seconds.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import numpy as np
import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.baseline import ReferenceBaseline
from app.models.drift_event import DriftEvent
from app.models.model_registry import ModelRegistry
from app.models.prediction import Prediction
from app.novelties.shap_attribution import DeltaSHAP
from app.redis_client import get_redis
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


async def _compute_shap_attribution(drift_event_id: int) -> dict:
    """Core async logic for SHAP computation."""
    async with AsyncSessionLocal() as db:
        # ── 1. Load drift event ───────────────────────────────
        event = await db.get(DriftEvent, drift_event_id)
        if not event:
            logger.warning("shap_event_not_found", event_id=drift_event_id)
            return {"drift_event_id": drift_event_id, "error": "Event not found"}

        model_id = event.model_id

        # ── 2. Load model & baseline ──────────────────────────
        model = await db.get(ModelRegistry, model_id)
        if not model:
            logger.warning("shap_model_not_found", model_id=model_id)
            return {"drift_event_id": drift_event_id, "error": "Model not found"}

        baseline = await db.scalar(
            select(ReferenceBaseline)
            .filter(ReferenceBaseline.model_id == model_id)
            .order_by(ReferenceBaseline.created_at.desc())
            .limit(1)
        )
        if not baseline or not baseline.feature_stats:
            logger.warning("shap_no_baseline", model_id=model_id)
            return {"drift_event_id": drift_event_id, "error": "No baseline"}

        baseline_stats: dict = baseline.feature_stats

        # ── 3. Build feature arrays ───────────────────────────
        # Identify numeric features
        feature_names = [
            f for f, s in baseline_stats.items()
            if isinstance(s, dict) and s.get("type") == "numeric"
        ]

        if not feature_names:
            logger.warning("shap_no_numeric_features", model_id=model_id)
            return {"drift_event_id": drift_event_id, "error": "No numeric features"}

        # Load recent predictions (current window)
        recent_preds = list(reversed(
            (await db.scalars(
                select(Prediction)
                .filter(Prediction.model_id == model_id)
                .order_by(Prediction.created_at.desc())
                .limit(200)
            )).all()
        ))

        if len(recent_preds) < 30:
            logger.warning("shap_insufficient_predictions", count=len(recent_preds))
            return {"drift_event_id": drift_event_id, "error": "Insufficient predictions"}

        # Build current feature matrix
        current_rows: list[list[float]] = []
        for pred in recent_preds:
            row = []
            valid = True
            for feat in feature_names:
                if feat in pred.features:
                    try:
                        row.append(float(pred.features[feat]))
                    except (TypeError, ValueError):
                        valid = False
                        break
                else:
                    valid = False
                    break
            if valid:
                current_rows.append(row)

        if len(current_rows) < 30:
            logger.warning("shap_insufficient_valid_rows", count=len(current_rows))
            return {"drift_event_id": drift_event_id, "error": "Insufficient valid rows"}

        current_data = np.array(current_rows)

        # Reconstruct baseline feature matrix from stored histograms
        baseline_cols: list[np.ndarray] = []
        for feat in feature_names:
            stat = baseline_stats.get(feat, {})
            hist = stat.get("histogram", {})
            if not hist or not hist.get("counts"):
                logger.warning("shap_missing_histogram", feature=feat)
                return {"drift_event_id": drift_event_id, "error": f"Missing histogram for {feat}"}

            counts = np.array(hist["counts"], dtype=float)
            edges = np.array(hist["bin_edges"])
            if counts.sum() == 0:
                return {"drift_event_id": drift_event_id, "error": f"Empty histogram for {feat}"}

            midpoints = (edges[:-1] + edges[1:]) / 2
            reps = np.round(counts / counts.sum() * 200).astype(int)
            baseline_cols.append(np.repeat(midpoints, reps))

        # Ensure all columns have the same length
        min_len = min(len(c) for c in baseline_cols) if baseline_cols else 0
        if min_len < 30:
            return {"drift_event_id": drift_event_id, "error": "Baseline too small for SHAP"}

        baseline_data = np.column_stack([c[:min_len] for c in baseline_cols])

        # ── 4. Train a simple model for SHAP ──────────────────
        # Use a lightweight model to compute SHAP values.
        # We train on the combined data to understand feature contributions.
        from sklearn.ensemble import GradientBoostingClassifier

        # Label: 0 = baseline, 1 = current (drift detection framing)
        X = np.vstack([baseline_data, current_data])
        y = np.concatenate([
            np.zeros(baseline_data.shape[0]),
            np.ones(current_data.shape[0]),
        ])

        clf = GradientBoostingClassifier(
            n_estimators=50,
            max_depth=3,
            random_state=42,
            subsample=0.8,
        )
        clf.fit(X, y)

        # ── 5. Compute Δ_SHAP ────────────────────────────────
        delta_shap = DeltaSHAP(max_samples=100, background_samples=50)
        try:
            shap_result = delta_shap.compute(
                model=clf,
                baseline_data=baseline_data,
                current_data=current_data,
                feature_names=feature_names,
            )
        except Exception as exc:
            logger.warning("shap_compute_failed", error=str(exc))
            return {"drift_event_id": drift_event_id, "error": str(exc)}

        attribution = shap_result.to_dict()

        # ── 6. Store attribution in drift event ───────────────
        event.shap_attribution = attribution
        db.add(event)
        await db.commit()

        logger.info(
            "shap_attribution_computed",
            event_id=drift_event_id,
            model_id=model_id,
            top_movers=attribution.get("top_movers", [])[:3],
        )

        # ── 7. Publish to Redis for WebSocket relay ───────────
        try:
            redis = await get_redis()
            await redis.publish(
                f"sentinel:drift:{model_id}:shap",
                json.dumps({
                    "type": "shap_attribution",
                    "drift_event_id": drift_event_id,
                    "model_id": model_id,
                    "top_movers": attribution.get("top_movers", [])[:5],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }),
            )
        except Exception as exc:
            logger.warning("shap_redis_publish_failed", error=str(exc))

        return {
            "drift_event_id": drift_event_id,
            "model_id": model_id,
            "attribution": attribution,
        }


@celery_app.task(
    name="compute_shap",
    bind=True,
    max_retries=2,
    acks_late=True,
    soft_time_limit=30,
    time_limit=60,
)
def compute_shap(self, drift_event_id: int) -> dict:
    """Synchronous Celery task. Bridges to async _compute_shap_attribution."""
    try:
        return asyncio.run(_compute_shap_attribution(drift_event_id))
    except Exception as exc:
        logger.exception(
            "shap_computation_failed",
            drift_event_id=drift_event_id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
