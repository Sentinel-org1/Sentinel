"""
backend/scripts/demo_reset.py
-------------------------------
Reset and replay demo data for Sentinel's 3 showcase models.

Usage:
    python scripts/demo_reset.py

This script:
  1. Clears all predictions, drift_events, and alerts from the database.
  2. Re-seeds 3 demo models with chronological drift stories:
     - credit-risk-scorer: covariate drift starting day 15 (income shift)
     - churn-predictor: seasonal Q4 concept drift spike
     - product-recommender: gradual label drift
  3. Each model gets ~10,000 synthetic predictions with realistic timestamps.

Requires: DATABASE_URL env var or .env file in backend/
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

# Ensure we can import from the app package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.model import Model
from app.models.prediction import Prediction
from app.models.drift_event import DriftEvent
from app.models.alert import Alert


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # ── 1. Clear existing demo data ────────────────────────
        print("🧹 Clearing existing data...")
        await db.execute(delete(Alert))
        await db.execute(delete(DriftEvent))
        await db.execute(delete(Prediction))
        await db.execute(delete(Model))
        await db.commit()
        print("   ✓ All tables cleared.")

        # ── 2. Create 3 demo models ────────────────────────────
        models_config = [
            {
                "name": "credit-risk-scorer",
                "version": "2.1.0",
                "task_type": "classification",
                "description": "Credit risk binary classifier — covariate drift scenario",
                "config_json": {"framework": "xgboost", "features": 12},
            },
            {
                "name": "churn-predictor",
                "version": "1.4.2",
                "task_type": "classification",
                "description": "Customer churn predictor — seasonal concept drift scenario",
                "config_json": {"framework": "lightgbm", "features": 8},
            },
            {
                "name": "product-recommender",
                "version": "3.0.1",
                "task_type": "regression",
                "description": "Product recommendation score — gradual label drift scenario",
                "config_json": {"framework": "tensorflow", "features": 24},
            },
        ]

        created_models = []
        for mc in models_config:
            model = Model(**mc)
            db.add(model)
            await db.flush()
            created_models.append(model)
            print(f"   ✓ Created model: {model.name} (id={model.id})")

        await db.commit()

        # ── 3. Generate synthetic predictions + drift events ────
        now = datetime.now(timezone.utc)
        base_time = now - timedelta(days=30)

        for model in created_models:
            print(f"\n📊 Seeding data for {model.name}...")
            predictions = []
            drift_events = []

            for day in range(30):
                day_time = base_time + timedelta(days=day)
                n_preds = random.randint(300, 400)

                for i in range(n_preds):
                    ts = day_time + timedelta(
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59),
                        seconds=random.randint(0, 59),
                    )

                    # Generate model-specific drift patterns
                    if model.name == "credit-risk-scorer":
                        # Covariate drift: income distribution shifts after day 15
                        if day < 15:
                            pred_val = random.gauss(0.35, 0.12)
                            conf = random.uniform(0.75, 0.98)
                        else:
                            pred_val = random.gauss(0.52, 0.18)  # shifted
                            conf = random.uniform(0.55, 0.85)   # lower confidence
                        features = {
                            "income": random.gauss(55000 if day < 15 else 38000, 8000),
                            "age": random.randint(22, 65),
                            "debt_ratio": random.uniform(0.1, 0.6 if day < 15 else 0.85),
                        }
                    elif model.name == "churn-predictor":
                        # Seasonal Q4 concept drift
                        seasonal_factor = 1.0 + (0.3 if 20 <= day <= 28 else 0.0)
                        pred_val = random.gauss(0.25 * seasonal_factor, 0.1)
                        conf = random.uniform(0.7, 0.95)
                        features = {
                            "usage_days": random.randint(5, 30),
                            "support_tickets": random.randint(0, int(3 * seasonal_factor)),
                            "contract_months": random.randint(1, 24),
                        }
                    else:  # product-recommender
                        # Gradual label drift
                        drift_amount = day * 0.008
                        pred_val = random.gauss(3.5 + drift_amount, 0.5)
                        conf = None  # regression model
                        features = {
                            "user_history_len": random.randint(10, 500),
                            "category_id": random.randint(1, 50),
                            "price_range": random.uniform(5.0, 200.0),
                        }

                    predictions.append(Prediction(
                        model_id=model.id,
                        features=features,
                        prediction=round(max(0, min(1, pred_val)) if model.task_type == "classification" else pred_val, 4),
                        confidence=round(conf, 4) if conf else None,
                        created_at=ts,
                    ))

                # Generate drift events on specific days
                should_drift = False
                severity = "info"
                detector = "psi"
                score = 0.0

                if model.name == "credit-risk-scorer" and day >= 15:
                    should_drift = True
                    severity = "critical" if day >= 17 else "warn"
                    score = round(0.15 + (day - 15) * 0.05 + random.uniform(-0.02, 0.02), 4)
                    detector = "ewma" if day >= 17 else "psi"
                elif model.name == "churn-predictor" and 20 <= day <= 28:
                    should_drift = True
                    severity = "warn"
                    score = round(0.12 + random.uniform(-0.03, 0.03), 4)
                    detector = "ks_test"
                elif model.name == "product-recommender" and day >= 22:
                    should_drift = True
                    severity = "warn" if day < 27 else "critical"
                    score = round(0.10 + (day - 22) * 0.03 + random.uniform(-0.01, 0.01), 4)
                    detector = "jsd"

                if should_drift:
                    drift_events.append(DriftEvent(
                        model_id=model.id,
                        detector=detector,
                        metric_name="overall_distribution",
                        score=score,
                        threshold=0.10,
                        drift_type="covariate" if model.name == "credit-risk-scorer" else "concept",
                        severity=severity,
                        detected_at=day_time + timedelta(hours=23, minutes=30),
                    ))

            # Batch insert
            db.add_all(predictions)
            db.add_all(drift_events)
            await db.commit()

            print(f"   ✓ {len(predictions)} predictions, {len(drift_events)} drift events")

            # Create alerts for critical/warn drift events
            alert_count = 0
            for de in drift_events:
                if de.severity in ("warn", "critical"):
                    alert = Alert(
                        drift_event_id=de.id,
                        model_id=model.id,
                        severity=de.severity,
                        status="open",
                        suppressed=False,
                    )
                    db.add(alert)
                    alert_count += 1

            await db.commit()
            print(f"   ✓ {alert_count} alerts created")

    await engine.dispose()
    print("\n✅ Demo reset complete! Dashboard should now show all 3 models with drift stories.")


if __name__ == "__main__":
    asyncio.run(main())
