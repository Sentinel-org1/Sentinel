"""
scripts/seed_db.py
-------------------
Seeds the Sentinel database with:
  - 1 admin user
  - 3 demo models: credit-risk-scorer, product-recommender, churn-predictor
  - 10,000 synthetic predictions per model (30,000 total)
  - A reference baseline for each model
  - Injected drift starting at prediction 7,000 (for demo scenarios)

Usage:
    DATABASE_URL=postgresql+asyncpg://... python scripts/seed_db.py
    # or inside Docker:
    docker compose exec backend python /app/scripts/seed_db.py
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

# Ensure backend/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

from app.config import settings
from app.models.base import Base
from app.models.user import User
from app.models.model_registry import ModelRegistry
from app.models.prediction import Prediction
from app.models.baseline import ReferenceBaseline
from app.services.auth_service import auth_service
from app.services.baseline_service import baseline_service

PREDICTIONS_PER_MODEL = 10_000
DRIFT_START = 7_000          # Drift injected after this many predictions
BATCH_SIZE = 500             # DB insert batch size

# ── Model definitions ──────────────────────────────────────────
MODELS = [
    {
        "name": "credit-risk-scorer",
        "version": "1.0.0",
        "task_type": "classification",
        "config_json": {"threshold": 0.5, "framework": "xgboost"},
        "features": {
            "age":          ("normal", 45, 12),
            "income":       ("normal", 55000, 18000),
            "credit_score": ("normal", 680, 80),
            "loan_amount":  ("normal", 15000, 8000),
            "debt_ratio":   ("normal", 0.35, 0.12),
        },
        # Drift: income distribution shifts (covariate drift)
        "drift": {"income": ("normal", 35000, 10000)},
    },
    {
        "name": "product-recommender",
        "version": "2.1.0",
        "task_type": "ranking",
        "config_json": {"k": 10, "framework": "lightfm"},
        "features": {
            "user_age":       ("normal", 32, 8),
            "session_length": ("normal", 12, 5),
            "n_past_orders":  ("normal", 7, 4),
            "category_pref":  ("categorical", ["electronics", "clothing", "home"]),
        },
        "drift": {"session_length": ("normal", 25, 8)},
    },
    {
        "name": "churn-predictor",
        "version": "3.0.1",
        "task_type": "classification",
        "config_json": {"threshold": 0.6, "framework": "sklearn"},
        "features": {
            "tenure_months":   ("normal", 24, 12),
            "monthly_charges": ("normal", 65, 20),
            "support_calls":   ("normal", 2, 1.5),
            "plan_type":       ("categorical", ["basic", "standard", "premium"]),
            "is_international": ("boolean",),
        },
        # Concept drift: churn rate spikes in Q4
        "drift": {"monthly_charges": ("normal", 95, 25)},
    },
]


def sample_feature(spec: tuple, drifted: bool = False, drift_spec: tuple | None = None) -> Any:
    """Sample a single feature value from its distribution spec."""
    actual_spec = drift_spec if (drifted and drift_spec) else spec
    dist = actual_spec[0]

    if dist == "normal":
        _, mu, sigma = actual_spec
        val = random.gauss(mu, sigma)
        return round(val, 4)
    elif dist == "categorical":
        _, choices = actual_spec
        return random.choice(choices)
    elif dist == "boolean":
        return random.random() > 0.5
    return None


def make_prediction_row(model_def: dict, i: int) -> dict:
    """Build one synthetic prediction row."""
    is_drifted = i >= DRIFT_START
    drift_specs = model_def.get("drift", {})

    features = {}
    for fname, fspec in model_def["features"].items():
        dspec = drift_specs.get(fname)
        if dspec:
            dspec = (dspec[0],) + dspec[1:]
        features[fname] = sample_feature(fspec, drifted=is_drifted, drift_spec=dspec)

    confidence = round(random.uniform(0.5, 0.98), 4)
    prediction = round(random.random(), 4)

    # Simulate timestamp spread over last 30 days
    offset_minutes = random.randint(0, 60 * 24 * 30)
    created_at = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)

    return {
        "features": features,
        "prediction": prediction,
        "confidence": confidence,
        "created_at": created_at,
    }


async def seed(db: AsyncSession) -> None:
    print("\n🌱  Sentinel database seeder\n")

    # ── Admin user ────────────────────────────────────────────
    print("  Creating admin user...")
    admin = await auth_service.get_user_by_email(db, "admin@sentinel.dev")
    if not admin:
        admin = await auth_service.create_user(
            db,
            email="admin@sentinel.dev",
            password="sentinel",
            is_superuser=True,
        )
        print(f"  ✓ Admin user created (id={admin.id})")
    else:
        print(f"  ~ Admin user already exists (id={admin.id})")

    for model_def in MODELS:
        print(f"\n  📦  Model: {model_def['name']} v{model_def['version']}")

        # ── Register model ─────────────────────────────────────
        model = ModelRegistry(
            name=model_def["name"],
            version=model_def["version"],
            task_type=model_def["task_type"],
            config_json=model_def["config_json"],
        )
        db.add(model)
        await db.flush()   # get model.id without full commit
        print(f"     ✓ Registered (id={model.id})")

        # ── Compute baseline from first 1000 baseline rows ─────
        baseline_data = [
            {
                fname: sample_feature(fspec)
                for fname, fspec in model_def["features"].items()
            }
            for _ in range(1000)
        ]
        await baseline_service.compute_and_save(db, model.id, baseline_data)
        print(f"     ✓ Baseline computed ({len(baseline_data)} samples)")

        # ── Seed predictions in batches ────────────────────────
        total = PREDICTIONS_PER_MODEL
        inserted = 0
        for batch_start in range(0, total, BATCH_SIZE):
            batch = [
                Prediction(
                    model_id=model.id,
                    **make_prediction_row(model_def, batch_start + j),
                )
                for j in range(min(BATCH_SIZE, total - batch_start))
            ]
            db.add_all(batch)
            await db.flush()
            inserted += len(batch)
            print(f"     ✓ {inserted:,}/{total:,} predictions inserted", end="\r")

        await db.commit()
        print(f"     ✓ {inserted:,} predictions committed (drift starts at #{DRIFT_START:,})")

    print("\n✅  Seeding complete!\n")
    print("  Credentials: admin@sentinel.dev / sentinel")
    print("  Run: python scripts/smoke_test.py  to verify\n")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        await seed(db)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())