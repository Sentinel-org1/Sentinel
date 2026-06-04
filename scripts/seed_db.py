"""
scripts/seed_db.py
-------------------
Seeds the Sentinel database with:
  - 1 admin user
  - 3 real models registered with correct feature lists
  - Real baseline statistics computed from training data
  - Old state cleared to ensure a clean registry.
"""
from __future__ import annotations

from typing import Any
import asyncio
import os
import sys
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Ensure root and backend/ are on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.models.model_registry import ModelRegistry
from app.services.auth_service import auth_service
from app.services.baseline_service import baseline_service
from scripts.data_preprocessor import (
    preprocess_model_1,
    preprocess_model_2,
    preprocess_model_3,
)

async def seed(db: AsyncSession) -> None:
    print("\n[SEED] Sentinel database seeder (Real Models)\n")

    # ── Cleanup existing data ─────────────────────────────────
    print("  Cleaning up database...")
    await db.execute(text("TRUNCATE TABLE alerts, drift_events, drift_thresholds, predictions, reference_baselines, model_registry CASCADE;"))
    await db.commit()
    print("  [OK] Database cleared.")

    # ── Admin user ────────────────────────────────────────────
    print("  Creating admin user...")
    admin = await auth_service.get_user_by_email(db, "admin@sentinel.dev")  # type: ignore
    if not admin:
        admin = await auth_service.create_user(
            db,  # type: ignore
            email="admin@sentinel.dev",
            password="sentinel",
            is_superuser=True,
        )
        print(f"  [OK] Admin user created (id={admin.id})")
    else:
        print(f"  [INFO] Admin user already exists (id={admin.id})")

    # Model definition specs matching model_registry.json
    model_specs: list[dict[str, Any]] = [
        {
            "id": 1,
            "name": "credit-risk-scorer",
            "version": "1.0.0",
            "task_type": "classification",
            "config_json": {
                "threshold": 0.5,
                "framework": "xgboost",
                "ml_model_path": "ml/models/1",
            },
            "loader": preprocess_model_1,
        },
        {
            "id": 2,
            "name": "churn-predictor",
            "version": "3.0.1",
            "task_type": "classification",
            "config_json": {
                "threshold": 0.6,
                "framework": "xgboost",
                "ml_model_path": "ml/models/2",
            },
            "loader": preprocess_model_2,
        },
        {
            "id": 3,
            "name": "product-recommender",
            "version": "2.1.0",
            "task_type": "ranking",
            "config_json": {
                "threshold": 0.5,
                "framework": "sklearn",
                "ml_model_path": "ml/models/3",
            },
            "loader": preprocess_model_3,
        },
    ]

    for spec in model_specs:
        print(f"\n  [MODEL] Model: {spec['name']} v{spec['version']}")

        # ── Register model ─────────────────────────────────────
        model = ModelRegistry(
            id=spec["id"],
            name=spec["name"],
            version=spec["version"],
            task_type=spec["task_type"],
            config_json=spec["config_json"],
        )
        db.add(model)
        await db.flush()
        print(f"     [OK] Registered model (id={model.id})")

        # ── Compute baseline from training data ────────────────
        print(f"     Loading training dataset to compute baseline...")
        res = spec["loader"]()
        # For model 3, loader returns (X, y, scaler)
        if len(res) == 3:
            X, _, _ = res
        else:
            X, _ = res
            
        # Sample 1000 rows to compute baseline
        baseline_df = X.sample(n=min(len(X), 1000), random_state=42)
        baseline_data = baseline_df.to_dict(orient="records")
        
        await baseline_service.compute_and_save(db, model.id, baseline_data)  # type: ignore
        print(f"     [OK] Reference baseline saved ({len(baseline_data)} samples)")

    await db.commit()
    print("\n[COMPLETE] Seeding complete!\n")
    print("  Credentials: admin@sentinel.dev / sentinel\n")

async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        await seed(db)
    await engine.dispose()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())