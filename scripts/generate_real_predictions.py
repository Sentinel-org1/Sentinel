"""
scripts/generate_real_predictions.py
-------------------------------------
Generates real predictions using the trained models in ml/models/ and the
preprocessed datasets. Simulates 7 days of predictions in 12-hour steps (14 steps total),
injects drift in the last 4 steps, and triggers drift checks and calibration.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import random
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np

# Ensure root and backend/ are on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.prediction import Prediction
from app.models.model_registry import ModelRegistry
from app.models.baseline import ReferenceBaseline
from app.models.calibration_curve import CalibrationCurve
from app.tasks.drift_check import _run_drift_check
from app.novelties.calibration_report import CalibrationReport
from app.detectors.psi import PSIDetector
from ml.models.model_loader import load_model
from scripts.data_preprocessor import (
    preprocess_model_1,
    preprocess_model_2,
    preprocess_model_3,
)

async def run_simulation():
    print("\n[START] Sentinel Real Prediction Generator & Drift Simulator\n")
    
    # 1. Load trained models
    print("  Loading trained ML models...")
    model1, _, features1, _ = load_model(1)
    model2, _, features2, _ = load_model(2)
    model3, _, features3, _ = load_model(3)
    print("  [OK] Models loaded successfully.")

    # 2. Load preprocessed datasets
    print("  Loading and preprocessing datasets...")
    X1, _ = preprocess_model_1()
    X2, _ = preprocess_model_2()
    X3, _, scaler3 = preprocess_model_3()
    print(f"  [OK] Datasets loaded. Model 1: {len(X1)} rows, Model 2: {len(X2)} rows, Model 3: {len(X3)} rows.")

    # Convert features to list of dicts for easier sampling
    rows1 = X1.to_dict(orient="records")
    rows2 = X2.to_dict(orient="records")
    rows3 = X3.to_dict(orient="records")

    # 3. Simulate 14 steps over the last 7 days
    steps = 14
    batch_size = 150
    now = datetime.now(timezone.utc)

    # Let's seed random to be deterministic
    random.seed(42)
    np.random.seed(42)

    for step in range(steps):
        is_drifted = step >= 10
        step_time = now - timedelta(hours=12 * (steps - 1 - step))
        print(f"\n[STEP] Step {step + 1}/{steps} - Timestamp: {step_time.strftime('%Y-%m-%d %H:%M:%S')} {'(DRIFTED)' if is_drifted else '(NORMAL)'}")

        async with AsyncSessionLocal() as db:
            # --- MODEL 1: Credit Risk (XGBoost) ---
            print("    Generating Model 1 predictions...")
            batch_preds1 = []
            for _ in range(batch_size):
                raw_feat = random.choice(rows1).copy()
                if is_drifted:
                    # Perturb features to induce drift
                    raw_feat['RevolvingUtilizationOfUnsecuredLines'] = min(raw_feat['RevolvingUtilizationOfUnsecuredLines'] * 1.8, 1.0)
                    raw_feat['MonthlyIncome'] = raw_feat['MonthlyIncome'] * 0.5
                    raw_feat['age'] = max(raw_feat['age'] - 15, 18)
                
                # Predict probability
                feat_df = pd.DataFrame([raw_feat])[features1]
                proba = float(model1.predict_proba(feat_df)[:, 1][0])
                confidence = max(proba, 1 - proba)

                created_at = step_time + timedelta(minutes=random.randint(-120, 120))
                batch_preds1.append(Prediction(
                    model_id=1,
                    features=raw_feat,
                    prediction=proba,
                    confidence=confidence,
                    created_at=created_at
                ))
            db.add_all(batch_preds1)

            # --- MODEL 2: Churn Predictor (XGBoost) ---
            print("    Generating Model 2 predictions...")
            batch_preds2 = []
            for _ in range(batch_size):
                raw_feat = random.choice(rows2).copy()
                if is_drifted:
                    raw_feat['tenure'] = max(raw_feat['tenure'] - 20, 1)
                    raw_feat['MonthlyCharges'] = raw_feat['MonthlyCharges'] + 30.0
                
                feat_df = pd.DataFrame([raw_feat])[features2]
                proba = float(model2.predict_proba(feat_df)[:, 1][0])
                confidence = max(proba, 1 - proba)

                created_at = step_time + timedelta(minutes=random.randint(-120, 120))
                batch_preds2.append(Prediction(
                    model_id=2,
                    features=raw_feat,
                    prediction=proba,
                    confidence=confidence,
                    created_at=created_at
                ))
            db.add_all(batch_preds2)

            # --- MODEL 3: Product Recommender (Logistic Regression) ---
            print("    Generating Model 3 predictions...")
            batch_preds3 = []
            for _ in range(batch_size):
                raw_feat = random.choice(rows3).copy()
                if is_drifted:
                    raw_feat['customer_total_spent'] = raw_feat['customer_total_spent'] * 0.2
                    raw_feat['customer_total_orders'] = max(raw_feat['customer_total_orders'] * 0.2, 1.0)
                
                feat_df = pd.DataFrame([raw_feat])[features3]
                feat_scaled = scaler3.transform(feat_df)
                proba = float(model3.predict_proba(feat_scaled)[:, 1][0])
                confidence = max(proba, 1 - proba)

                created_at = step_time + timedelta(minutes=random.randint(-120, 120))
                batch_preds3.append(Prediction(
                    model_id=3,
                    features=raw_feat,
                    prediction=proba,
                    confidence=confidence,
                    created_at=created_at
                ))
            db.add_all(batch_preds3)

            await db.commit()
            print("    [OK] Batch committed to database.")

        # Trigger drift checks for each model
        print("    Triggering drift check tasks...")
        for model_id in [1, 2, 3]:
            res = await _run_drift_check(model_id)
            print(f"      Model {model_id} drift check: {res['status']} ({res['drift_events']} events, {res['alerts_created']} alerts)")

    # 4. Generate Calibration Curves
    print("\n[CALIBRATION] Generating threshold calibration curves...")
    async with AsyncSessionLocal() as db:
        for model_id in [1, 2, 3]:
            # Load baseline
            baseline = await db.scalar(  # type: ignore
                select(ReferenceBaseline)
                .filter(ReferenceBaseline.model_id == model_id)  # type: ignore
                .order_by(ReferenceBaseline.created_at.desc())  # type: ignore
                .limit(1)
            )
            if not baseline or not baseline.feature_stats:
                continue

            # Extract first numeric feature's baseline array
            baseline_stats = baseline.feature_stats
            numeric_features = [
                f for f, s in baseline_stats.items()
                if isinstance(s, dict) and s.get("type") == "numeric"
            ]
            if not numeric_features:
                continue

            feat_name = numeric_features[0]
            feat_stat = baseline_stats[feat_name]
            hist = feat_stat.get("histogram", {})
            if not hist or not hist.get("counts"):
                continue

            counts = np.array(hist["counts"], dtype=float)
            edges = np.array(hist["bin_edges"])
            midpoints = (edges[:-1] + edges[1:]) / 2
            reps = np.round(counts / counts.sum() * 500).astype(int)
            baseline_arr = np.repeat(midpoints, reps)

            generator = CalibrationReport()
            report = generator.generate(
                baseline=baseline_arr,  # type: ignore
                detector_class=PSIDetector,
            )

            curve_data = {
                "points": [
                    {
                        "threshold": pt.threshold,
                        "tp_rate": pt.tp_rate,
                        "fp_rate": pt.fp_rate,
                        "youden_j": pt.youden_j,
                    }
                    for pt in report.points
                ],
                "optimal_threshold": report.optimal_threshold,
                "auc": report.auc,
            }

            curve = CalibrationCurve(
                model_id=model_id,
                curve_data=curve_data,
                optimal_threshold=report.optimal_threshold,
                auc=report.auc,
            )
            db.add(curve)
            print(f"    [OK] Calibration curve saved for Model {model_id} (AUC: {report.auc:.4f}, Optimal Threshold: {report.optimal_threshold:.4f})")

        await db.commit()
        print("\n[COMPLETE] Simulation and calibration complete!")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_simulation())
