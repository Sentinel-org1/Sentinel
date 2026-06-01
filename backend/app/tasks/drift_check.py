"""
Drift check Celery task orchestration.

Executed when:
  1. Prediction batch reaches DRIFT_BATCH_SIZE
  2. 60 seconds elapsed since last check
  3. Manual trigger via POST /api/drift/{model_id}/check

Flow:
  1. Fetch recent predictions from Postgres
  2. Load baseline from Postgres
  3. Run all detectors (PSI, KS, JS-Div, CUSUM, Page-Hinkley, IForest)
  4. Update EWMA adaptive thresholds
  5. Apply STL alert suppression (Novel #4) — seasonal noise → skip alert
  6. Create alerts (with 10-min cooldown dedup)
  7. Classify drift type
  8. Enqueue async SHAP attribution
  9. Publish drift events to Redis pub/sub
  10. Store results in DB
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import numpy as np
import structlog
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.detectors.cusum import CUSUMDetector
from app.detectors.isolation_forest import IForestDetector
from app.detectors.js_divergence import JSDetector
from app.detectors.ks_test import KSDetector
from app.detectors.page_hinkley import PageHinkleyDetector
from app.detectors.psi import PSIDetector
from app.models.baseline import ReferenceBaseline
from app.models.drift_event import DriftEvent
from app.models.drift_threshold import DriftThreshold
from app.models.model_registry import ModelRegistry
from app.models.prediction import Prediction
from app.novelties.drift_classifier import DriftClassifier, DriftSignals
from app.novelties.ewma_thresholds import EWMAThresholds
from app.novelties.stl_decomposition import STLAlertSuppressor
from app.redis_client import get_redis
from app.services.alert_service import AlertService
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reconstruct_baseline_array(feat_stat: dict, n_target: int = 500) -> np.ndarray | None:
    """Reconstruct a synthetic baseline array from stored histogram data.

    Used by all detectors that need a reference distribution. Returns None
    if the histogram data is missing or empty.
    """
    hist = feat_stat.get("histogram", {})
    if not hist or not hist.get("counts"):
        return None

    counts = np.array(hist["counts"], dtype=float)
    edges = np.array(hist["bin_edges"])
    if counts.sum() == 0:
        return None

    midpoints = (edges[:-1] + edges[1:]) / 2
    reps = np.round(counts / counts.sum() * n_target).astype(int)
    baseline_arr = np.repeat(midpoints, reps)

    if len(baseline_arr) < 50:
        return None

    return baseline_arr


def _get_baseline_prediction_mean(baseline_stats: dict) -> float:
    """Extract the stored baseline prediction mean.

    Looks for a '__prediction__' meta key first (stored by baseline service),
    then falls back to computing from the histogram of any 'prediction'
    feature stat, and finally defaults to 0.5.
    """
    # Check for explicit prediction metadata
    pred_meta = baseline_stats.get("__prediction__", {})
    if pred_meta.get("mean") is not None:
        return float(pred_meta["mean"])

    # Check for a 'prediction' feature with stored stats
    pred_stat = baseline_stats.get("prediction", {})
    if pred_stat.get("mean") is not None:
        return float(pred_stat["mean"])

    # Fallback: reconstruct from histogram if available
    baseline_arr = _reconstruct_baseline_array(pred_stat, n_target=500)
    if baseline_arr is not None and len(baseline_arr) > 0:
        return float(np.mean(baseline_arr))

    # Final fallback — 0.5 for binary classification models
    logger.warning("baseline_prediction_mean_fallback", value=0.5)
    return 0.5


# ── STL alert suppression ────────────────────────────────────────────────────

_stl_suppressor = STLAlertSuppressor(
    period=7,
    seasonal_window=7,
    trend_threshold_ratio=0.8,
)


def _extract_score_history(threshold_record: DriftThreshold) -> list[float]:
    """Extract the score time series from a DriftThreshold's history JSON."""
    raw = threshold_record.history
    if not raw:
        return []

    try:
        history = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []

    return [
        float(entry["score"])
        for entry in history
        if isinstance(entry, dict) and "score" in entry
    ]


# ── Async core — runs inside asyncio.run() from the sync Celery task ──────────
async def _run_drift_check(model_id: int) -> dict:
    result: dict = {
        "model_id": model_id,
        "status": "pending",
        "detectors_run": [],
        "drift_events": 0,
        "alerts_created": 0,
        "alerts_suppressed": 0,
        "error": None,
    }

    async with AsyncSessionLocal() as db:
        # ── 1. Load model & baseline ──────────────────────────
        model = await db.get(ModelRegistry, model_id)
        if not model:
            result.update(status="error", error=f"Model {model_id} not found")
            return result

        baseline = await db.scalar(
            select(ReferenceBaseline)
            .filter(ReferenceBaseline.model_id == model_id)
            .order_by(ReferenceBaseline.created_at.desc())
            .limit(1)
        )
        if not baseline or not baseline.feature_stats:
            result.update(status="error", error=f"No baseline for model {model_id}")
            return result

        baseline_stats: dict = baseline.feature_stats

        # ── 2. Fetch recent predictions ───────────────────────
        recent_preds = list(reversed(
            (await db.scalars(
                select(Prediction)
                .filter(Prediction.model_id == model_id)
                .order_by(Prediction.created_at.desc())
                .limit(500)
            )).all()
        ))

        if len(recent_preds) < 50:
            result.update(
                status="insufficient_data",
                error=f"Only {len(recent_preds)} predictions (need ≥50)",
            )
            return result

        logger.info("drift_check_predictions_loaded", model_id=model_id, count=len(recent_preds))

        # ── 3. Build feature arrays ───────────────────────────
        feature_names = [
            f for f, s in baseline_stats.items()
            if isinstance(s, dict) and s.get("type") == "numeric"
        ]
        feature_data: dict[str, list[float]] = {f: [] for f in feature_names}

        for pred in recent_preds:
            for feat in feature_names:
                if feat in pred.features:
                    try:
                        feature_data[feat].append(float(pred.features[feat]))
                    except (TypeError, ValueError):
                        pass

        # Prediction score array for sequential detectors
        pred_scores = np.array([p.prediction for p in recent_preds], dtype=float)

        # Baseline prediction mean (used by sequential detectors)
        baseline_pred_mean = _get_baseline_prediction_mean(baseline_stats)

        # ── 4. Run detectors ──────────────────────────────────
        detectors_run: list[str] = []
        drift_scores: dict[str, list[tuple[str, float]]] = {}

        ewma_mgr = EWMAThresholds(
            alpha=settings.EWMA_LAMBDA,
            sigma_multiplier=settings.EWMA_SIGMA_MULTIPLIER,
        )

        for feat_name, current_values in feature_data.items():
            if len(current_values) < 50:
                continue

            current_arr = np.array(current_values)
            feat_stat = baseline_stats.get(feat_name, {})

            baseline_arr = _reconstruct_baseline_array(feat_stat, n_target=500)
            if baseline_arr is None:
                continue

            # PSI
            try:
                det = PSIDetector(n_bins=10)
                det.fit(baseline_arr, feature_name=feat_name)
                score = det.score(current_arr)
                drift_scores.setdefault("psi", []).append((feat_name, score))
                if score > 0.25:
                    detectors_run.append("psi")
            except Exception as exc:
                logger.warning("psi_failed", feature=feat_name, error=str(exc))

            # KS test
            try:
                det = KSDetector(min_samples=50)
                det.fit(baseline_arr, feature_name=feat_name)
                score = det.score(current_arr)
                drift_scores.setdefault("ks_test", []).append((feat_name, score))
                if score > 0.2:
                    detectors_run.append("ks_test")
            except Exception as exc:
                logger.warning("ks_failed", feature=feat_name, error=str(exc))

        # CUSUM on prediction scores — use real baseline prediction mean
        try:
            baseline_pred_arr = _reconstruct_baseline_array(
                baseline_stats.get("prediction", {}), n_target=500
            )
            if baseline_pred_arr is None:
                # Fallback: generate synthetic baseline from stored mean/std
                baseline_pred_std = baseline_stats.get("prediction", {}).get("std", 0.1)
                baseline_pred_arr = np.random.default_rng(42).normal(
                    baseline_pred_mean, max(baseline_pred_std, 0.01), 500
                )

            det = CUSUMDetector()
            det.fit(baseline_pred_arr, feature_name="prediction")
            score = det.score(pred_scores)
            drift_scores.setdefault("cusum", []).append(("prediction", score))
            if det.threshold and score > det.threshold:
                detectors_run.append("cusum")
        except Exception as exc:
            logger.warning("cusum_failed", error=str(exc))

        # Page-Hinkley on prediction scores — reuse baseline array
        try:
            det = PageHinkleyDetector()
            det.fit(baseline_pred_arr, feature_name="prediction")
            score = det.score(pred_scores)
            drift_scores.setdefault("page_hinkley", []).append(("prediction", score))
            if det.threshold and score > det.threshold:
                detectors_run.append("page_hinkley")
        except Exception as exc:
            logger.warning("page_hinkley_failed", error=str(exc))

        # Isolation Forest (multivariate) — use real baseline features
        try:
            if feature_names:
                # Build current feature matrix
                valid_features = [
                    f for f in feature_names
                    if len(feature_data[f]) == len(feature_data[feature_names[0]])
                ]
                if valid_features:
                    matrix = np.column_stack([
                        np.array(feature_data[f]) for f in valid_features
                    ])

                    if matrix.shape[0] >= 50:
                        # Reconstruct baseline matrix from stored histograms
                        baseline_cols = []
                        for f in valid_features:
                            b_arr = _reconstruct_baseline_array(
                                baseline_stats.get(f, {}), n_target=500
                            )
                            if b_arr is not None:
                                baseline_cols.append(b_arr[:500])

                        if len(baseline_cols) == len(valid_features):
                            # Ensure all columns have the same length
                            min_len = min(len(c) for c in baseline_cols)
                            baseline_matrix = np.column_stack([
                                c[:min_len] for c in baseline_cols
                            ])

                            det = IForestDetector(contamination=0.05)
                            det.fit(baseline_matrix)
                            score = det.score(matrix)
                            drift_scores.setdefault("isolation_forest", []).append(
                                ("multivariate", score)
                            )
                            if score < -0.2:
                                detectors_run.append("isolation_forest")
        except Exception as exc:
            logger.warning("iforest_failed", error=str(exc))

        # ── 5. Update EWMA thresholds ─────────────────────────
        for detector_name, feature_scores in drift_scores.items():
            for feat_name, score in feature_scores:
                threshold_record = await db.scalar(
                    select(DriftThreshold).filter(
                        DriftThreshold.model_id == model_id,
                        DriftThreshold.detector == detector_name,
                        DriftThreshold.metric_name == feat_name,
                    ).limit(1)
                )
                if threshold_record is None:
                    init = ewma_mgr.initialize_ewma([score])
                    threshold_record = DriftThreshold(
                        model_id=model_id,
                        detector=detector_name,
                        metric_name=feat_name,
                        ewma_threshold=float(init["threshold"]),
                        ewma_mean=float(init["ewma_mean"]),
                        ewma_std=float(init["ewma_std"]),
                        history=json.dumps([{**init, "score": score}]),
                    )
                    db.add(threshold_record)
                else:
                    upd = ewma_mgr.update(score, threshold_record.ewma_mean or 0.0, threshold_record.ewma_std or 0.01)
                    threshold_record.ewma_threshold = float(upd["threshold"])
                    threshold_record.ewma_mean = float(upd["ewma_mean"])
                    threshold_record.ewma_std = float(upd["ewma_std"])
                    history = json.loads(threshold_record.history or "[]")
                    history.append({**upd, "score": score, "timestamp": datetime.now(timezone.utc).isoformat()})
                    threshold_record.history = json.dumps(history[-100:])

                    # ── STL decomposition on score history ──
                    score_series = _extract_score_history(threshold_record)
                    if len(score_series) >= _stl_suppressor.min_observations:
                        stl_result = _stl_suppressor.decompose(np.array(score_series))
                        if stl_result is not None:
                            threshold_record.stl_decomposition = stl_result.to_dict()

                    db.add(threshold_record)

        await db.flush()

        # ── 6. Create drift events & alerts ───────────────────
        alerts_created = 0
        alerts_suppressed = 0
        drift_event_count = 0

        # ── Build DriftSignals for drift type classification ──
        psi_score_dict: dict[str, float] = {
            feat: score
            for feat, score in drift_scores.get("psi", [])
        }

        prediction_shift = float(abs(np.mean(pred_scores) - baseline_pred_mean))

        # error_rate_delta: actuals pipeline not yet wired — always 0.0 for now.
        error_rate_delta = 0.0

        feature_count_drifted = sum(
            1 for _, score in drift_scores.get("psi", [])
            if score > 0.25
        )

        # has_actuals: actuals pipeline not yet wired — always False for now.
        has_actuals = False

        sequential_detector_fired = (
            "cusum" in detectors_run or "page_hinkley" in detectors_run
        )

        signals = DriftSignals(
            psi_scores=psi_score_dict,
            prediction_shift=prediction_shift,
            error_rate_delta=error_rate_delta,
            feature_count_drifted=feature_count_drifted,
            has_actuals=has_actuals,
            sequential_detector_fired=sequential_detector_fired,
        )

        classification = DriftClassifier().classify(signals)

        logger.info(
            "drift_type_classified",
            model_id=model_id,
            drift_type=classification.drift_type,
            confidence=round(classification.confidence, 3),
            recommended_action=classification.recommended_action,
            signals_used=classification.signals_used,
        )

        for detector_name in set(detectors_run):
            for feat_name, score in drift_scores.get(detector_name, []):
                severity = "critical" if score > 0.5 else "warn"
                drift_event = DriftEvent(
                    model_id=model_id,
                    detector=detector_name,
                    metric_name=feat_name,
                    score=float(score),
                    threshold=0.25,
                    drift_type=classification.drift_type,
                    severity=severity,
                )
                db.add(drift_event)
                await db.flush()
                drift_event_count += 1

                # ── STL alert suppression check ──
                threshold_record = await db.scalar(
                    select(DriftThreshold).filter(
                        DriftThreshold.model_id == model_id,
                        DriftThreshold.detector == detector_name,
                        DriftThreshold.metric_name == feat_name,
                    ).limit(1)
                )

                should_suppress = False
                if threshold_record is not None:
                    score_series = _extract_score_history(threshold_record)
                    ewma_thresh = threshold_record.ewma_threshold or 0.25
                    should_suppress = _stl_suppressor.should_suppress_alert(
                        np.array(score_series) if score_series else np.array([score]),
                        raw_score=score,
                        threshold=ewma_thresh,
                    )

                if should_suppress:
                    alerts_suppressed += 1
                    logger.info(
                        "alert_suppressed_by_stl",
                        model_id=model_id,
                        detector=detector_name,
                        feature=feat_name,
                        score=round(score, 6),
                    )
                else:
                    alert = await AlertService.create_alert(db, drift_event.id, model_id, severity)
                    if alert:
                        alerts_created += 1

                # ── Enqueue async SHAP attribution ──
                from app.tasks.shap_compute import compute_shap
                compute_shap.apply_async(
                    args=[drift_event.id],
                    queue="shap",
                )

        await db.commit()

        # ── 7. Publish to Redis pub/sub ───────────────────────
        if detectors_run:
            redis = await get_redis()
            for detector_name in set(detectors_run):
                await redis.publish(
                    f"sentinel:drift:{model_id}:{detector_name}",
                    json.dumps({
                        "model_id": model_id,
                        "detector": detector_name,
                        "drift_type": classification.drift_type,
                        "drift_confidence": round(classification.confidence, 3),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }),
                )

        result.update(
            status="success",
            detectors_run=list(set(detectors_run)),
            drift_events=drift_event_count,
            alerts_created=alerts_created,
            alerts_suppressed=alerts_suppressed,
        )
        logger.info("drift_check_complete", **result)
        return result


# ── Celery task wrapper — must be sync; asyncio.run() bridges to async core ───
@celery_app.task(name="drift_check", bind=True, max_retries=3, acks_late=True)
def check_drift(self, model_id: int) -> dict:
    """Synchronous Celery task entry point. Bridges to async _run_drift_check."""
    try:
        return asyncio.run(_run_drift_check(model_id))
    except Exception as exc:
        logger.exception("drift_check_failed", model_id=model_id, error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)