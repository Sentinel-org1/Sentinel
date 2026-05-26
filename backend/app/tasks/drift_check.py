"""
Drift check Celery task orchestration.

Executed when:
  1. Prediction batch reaches DRIFT_BATCH_SIZE
  2. 60 seconds elapsed since last check
  3. Manual trigger

Flow:
  1. Fetch recent predictions from Redis Streams
  2. Load baseline from Postgres
  3. Run all detectors (PSI, KS, JS-Div, CUSUM, Page-Hinkley, IForest)
  4. Update EWMA adaptive thresholds
  5. Create alerts (with dedup)
  6. Publish drift events to Redis pub/sub
  7. Store results in DB
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.detectors.cusum import CUSUMDetector
from app.detectors.isolation_forest import IForestDetector
from app.detectors.js_divergence import JSDetector
from app.detectors.ks_test import KSDetector
from app.detectors.page_hinkley import PageHinkleyDetector
from app.detectors.psi import PSIDetector
from app.models.drift_event import DriftEvent
from app.models.drift_threshold import DriftThreshold
from app.models.model_registry import ModelRegistry
from app.models.prediction import Prediction
from app.models.baseline import ReferenceBaseline
from app.novelties.ewma_thresholds import EWMAThresholds
from app.redis_client import get_redis
from app.services.alert_service import AlertService
from app.tasks.celery_app import celery_app
from ml.models.model_loader import load_model

logger = structlog.get_logger()


@celery_app.task(name="drift_check", bind=True, max_retries=3)
async def check_drift(self, model_id: int) -> dict:
    """
    Execute full drift detection pipeline for a model.

    Args:
        model_id: Model ID to check

    Returns:
        dict with detection results and any drift events
    """
    result = {
        "model_id": model_id,
        "status": "pending",
        "detectors_run": [],
        "drift_events": [],
        "alerts_created": 0,
        "error": None,
    }

    try:
        logger.info("drift_check_started", model_id=model_id)

        async with AsyncSessionLocal() as db:
            # ── 1. Fetch model and baseline ──────────────────────────
            model = await db.get(ModelRegistry, model_id)
            if not model:
                result["error"] = f"Model {model_id} not found"
                return result

            baseline = await db.scalar(
                select(ReferenceBaseline)
                .filter(ReferenceBaseline.model_id == model_id)
                .order_by(ReferenceBaseline.created_at.desc())
                .limit(1)
            )

            if not baseline or not baseline.feature_stats:
                result["error"] = f"No baseline found for model {model_id}"
                return result

            baseline_stats = baseline.feature_stats

            # ── 2. Fetch recent predictions ──────────────────────────
            recent_preds = (
                await db.scalars(
                    select(Prediction)
                    .filter(Prediction.model_id == model_id)
                    .order_by(Prediction.created_at.desc())
                    .limit(500)
                )
            ).all()

            if len(recent_preds) < 50:
                result["status"] = "insufficient_data"
                result["error"] = f"Only {len(recent_preds)} recent predictions (need ≥50)"
                return result

            # Reverse for chronological order
            recent_preds = list(reversed(recent_preds))

            logger.info(
                "predictions_loaded",
                model_id=model_id,
                count=len(recent_preds),
            )

            # ── 3. Extract feature columns ───────────────────────────
            feature_names = list(baseline_stats.keys())
            feature_data = {feat: [] for feat in feature_names}

            for pred in recent_preds:
                for feat in feature_names:
                    if feat in pred.features:
                        feature_data[feat].append(float(pred.features[feat]))

            # ── 4. Run detectors per feature ─────────────────────────
            detectors_run = []
            drift_scores = {}  # detector -> list of per-feature scores

            # Numerical detectors: PSI, KS, CUSUM, Page-Hinkley
            for feat_name, current_values in feature_data.items():
                if len(current_values) < 50:
                    continue

                current_array = np.array(current_values)
                baseline_array = np.array(baseline_stats[feat_name].get("values", []))

                if len(baseline_array) < 50:
                    continue

                # ── PSI Detector ──────────────────────────────────
                try:
                    psi_detector = PSIDetector(n_bins=10)
                    psi_detector.fit(baseline_array, feature_name=feat_name)
                    psi_score = psi_detector.score(current_array)

                    if "psi" not in drift_scores:
                        drift_scores["psi"] = []
                    drift_scores["psi"].append((feat_name, psi_score))

                    if psi_score > 0.25:  # Threshold for significant drift
                        logger.info(
                            "drift_detected_psi",
                            model_id=model_id,
                            feature=feat_name,
                            score=round(psi_score, 4),
                        )
                        detectors_run.append("psi")

                except Exception as e:
                    logger.warning("psi_detector_failed", error=str(e), feature=feat_name)

                # ── KS Test Detector ──────────────────────────────
                try:
                    ks_detector = KSDetector(min_samples=50)
                    ks_detector.fit(baseline_array, feature_name=feat_name)
                    ks_score = ks_detector.score(current_array)

                    if "ks" not in drift_scores:
                        drift_scores["ks"] = []
                    drift_scores["ks"].append((feat_name, ks_score))

                    if ks_score > 0.2:  # KS threshold
                        logger.info(
                            "drift_detected_ks",
                            model_id=model_id,
                            feature=feat_name,
                            score=round(ks_score, 4),
                        )
                        detectors_run.append("ks")

                except Exception as e:
                    logger.warning("ks_detector_failed", error=str(e), feature=feat_name)

                # ── CUSUM Detector ───────────────────────────────
                try:
                    cusum_detector = CUSUMDetector()
                    cusum_detector.fit(baseline_array, feature_name=feat_name)
                    cusum_score = cusum_detector.score(current_array)

                    if "cusum" not in drift_scores:
                        drift_scores["cusum"] = []
                    drift_scores["cusum"].append((feat_name, cusum_score))

                    if cusum_detector.threshold and cusum_score > cusum_detector.threshold:
                        logger.info(
                            "drift_detected_cusum",
                            model_id=model_id,
                            feature=feat_name,
                            score=round(cusum_score, 4),
                        )
                        detectors_run.append("cusum")

                except Exception as e:
                    logger.warning("cusum_detector_failed", error=str(e), feature=feat_name)

                # ── Page-Hinkley Detector ────────────────────────
                try:
                    ph_detector = PageHinkleyDetector()
                    ph_detector.fit(baseline_array, feature_name=feat_name)
                    ph_score = ph_detector.score(current_array)

                    if "page_hinkley" not in drift_scores:
                        drift_scores["page_hinkley"] = []
                    drift_scores["page_hinkley"].append((feat_name, ph_score))

                    if ph_detector.threshold and ph_score > ph_detector.threshold:
                        logger.info(
                            "drift_detected_page_hinkley",
                            model_id=model_id,
                            feature=feat_name,
                            score=round(ph_score, 4),
                        )
                        detectors_run.append("page_hinkley")

                except Exception as e:
                    logger.warning("page_hinkley_detector_failed", error=str(e), feature=feat_name)

            # ── Categorical Detectors: JS Divergence ─────────────────
            for feat_name, current_values in feature_data.items():
                if len(current_values) < 50:
                    continue

                try:
                    current_array = np.array(current_values)
                    baseline_array = np.array(baseline_stats[feat_name].get("values", []))

                    if len(baseline_array) < 50:
                        continue

                    js_detector = JSDetector(min_samples=50)
                    js_detector.fit(baseline_array, feature_name=feat_name)
                    js_score = js_detector.score(current_array)

                    if "js_divergence" not in drift_scores:
                        drift_scores["js_divergence"] = []
                    drift_scores["js_divergence"].append((feat_name, js_score))

                    if js_score > 0.15:  # JS threshold
                        logger.info(
                            "drift_detected_js",
                            model_id=model_id,
                            feature=feat_name,
                            score=round(js_score, 4),
                        )
                        detectors_run.append("js_divergence")

                except Exception as e:
                    logger.warning("js_detector_failed", error=str(e), feature=feat_name)

            # ── 5. NOVEL #1: Update EWMA Adaptive Thresholds ──────────
            ewma_mgr = EWMAThresholds(
                alpha=settings.EWMA_LAMBDA,
                sigma_multiplier=settings.EWMA_SIGMA_MULTIPLIER,
            )

            for detector_name, feature_scores in drift_scores.items():
                for feat_name, score in feature_scores:
                    # Fetch or create threshold record
                    threshold_record = await db.scalar(
                        select(DriftThreshold)
                        .filter(
                            DriftThreshold.model_id == model_id,
                            DriftThreshold.detector == detector_name,
                            DriftThreshold.metric_name == feat_name,
                        )
                        .limit(1)
                    )

                    if threshold_record is None:
                        # Initialize new threshold
                        init_result = ewma_mgr.initialize_ewma([score])
                        threshold_record = DriftThreshold(
                            model_id=model_id,
                            detector=detector_name,
                            metric_name=feat_name,
                            ewma_threshold=float(init_result["threshold"]),
                            ewma_mean=float(init_result["ewma_mean"]),
                            ewma_std=float(init_result["ewma_std"]),
                            history=json.dumps([init_result]),
                        )
                        db.add(threshold_record)
                    else:
                        # Update existing threshold
                        update_result = ewma_mgr.update(
                            score,
                            threshold_record.ewma_mean or 0.0,
                            threshold_record.ewma_std or 0.01,
                        )
                        threshold_record.ewma_threshold = float(update_result["threshold"])
                        threshold_record.ewma_mean = float(update_result["ewma_mean"])
                        threshold_record.ewma_std = float(update_result["ewma_std"])

                        # Append to history
                        history = json.loads(threshold_record.history or "[]")
                        history.append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "score": score,
                            "threshold": float(update_result["threshold"]),
                            "ewma_mean": float(update_result["ewma_mean"]),
                            "ewma_std": float(update_result["ewma_std"]),
                        })
                        threshold_record.history = json.dumps(history[-100:])  # Keep last 100

                        db.add(threshold_record)

            await db.commit()

            # ── 6. Create Drift Events & Alerts ──────────────────────
            alerts_created = 0

            for detector_name in set(detectors_run):
                if detector_name in drift_scores:
                    feature_scores = drift_scores[detector_name]
                    for feat_name, score in feature_scores:
                        # Determine severity
                        severity = "warn"
                        if detector_name == "psi" and score > 0.5:
                            severity = "critical"
                        elif detector_name == "ks" and score > 0.5:
                            severity = "critical"

                        # Create drift event
                        drift_event = DriftEvent(
                            model_id=model_id,
                            detector=detector_name,
                            metric_name=feat_name,
                            score=float(score),
                            threshold=0.25,  # Default threshold (overridden by EWMA)
                            drift_type="covariate",  # Will be classified in NOVEL #2
                            severity=severity,
                        )
                        db.add(drift_event)
                        await db.flush()

                        # Create alert with dedup
                        alert = await AlertService.create_alert(
                            db,
                            drift_event.id,
                            model_id,
                            severity,
                        )
                        if alert:
                            alerts_created += 1

            await db.commit()

            # ── 7. Publish to Redis pub/sub ──────────────────────────
            redis = await get_redis()
            for detector_name in set(detectors_run):
                channel = f"sentinel:drift:{model_id}:{detector_name}"
                await redis.publish(
                    channel,
                    json.dumps({
                        "model_id": model_id,
                        "detector": detector_name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "detectors_triggered": list(set(detectors_run)),
                    }),
                )

            result["status"] = "success"
            result["detectors_run"] = list(set(detectors_run))
            result["alerts_created"] = alerts_created
            result["drift_events"] = len(set(detectors_run))

            logger.info(
                "drift_check_completed",
                model_id=model_id,
                detectors=list(set(detectors_run)),
                alerts=alerts_created,
            )

            return result

    except Exception as exc:
        logger.exception("drift_check_failed", model_id=model_id, error=str(exc))
        result["status"] = "error"
        result["error"] = str(exc)

        # Retry with exponential backoff
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            logger.error("drift_check_max_retries", model_id=model_id)
            result["status"] = "max_retries_exceeded"

        return result
