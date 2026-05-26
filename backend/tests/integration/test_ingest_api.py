"""
backend/tests/integration/test_ingest_pipeline.py
---------------------------------------------------
Day 7 sprint-review integration test.

Validates the full data flow:
  ingest API → Postgres write → Redis Stream publish

Requires a running test DB and Redis. Run with:
  pytest backend/tests/integration/ -v --asyncio-mode=auto

Test DB is isolated in its own schema to avoid clobbering dev data.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.models.base import Base
from app.models.model_registry import ModelRegistry
from app.models.prediction import Prediction
from app.services.auth_service import auth_service
from app.config import settings


# ── Fixtures ───────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="module")
async def test_engine():
    """Isolated in-memory SQLite engine for integration tests."""
    # Use a separate test-specific Postgres schema for isolation
    engine = create_async_engine(
        settings.DATABASE_URL.replace("/sentinel", "/sentinel_test"),
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(test_engine):
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_model(db: AsyncSession):
    """Create a test model and return its ID."""
    model = ModelRegistry(name="test-model", version="1.0.0", task_type="classification")
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@pytest_asyncio.fixture
async def auth_token(db: AsyncSession):
    """Create an admin user and return a valid access token."""
    user = await auth_service.create_user(db, "test@sentinel.dev", "testpass", is_superuser=True)
    return auth_service.create_access_token(user.id)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ── Tests ──────────────────────────────────────────────────────
class TestPredictionIngest:
    async def test_health_check(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_ingest_requires_auth(self, client: AsyncClient, seeded_model):
        r = await client.post(
            "/api/predictions/ingest",
            json={"predictions": [{"model_id": seeded_model.id, "features": {"x": 1.0}, "prediction": 0.5}]},
        )
        assert r.status_code == 401

    async def test_ingest_100_predictions(
        self, client: AsyncClient, auth_token: str, seeded_model, db: AsyncSession
    ):
        batch = [
            {
                "model_id": seeded_model.id,
                "features": {"age": float(i), "income": float(i * 1000)},
                "prediction": 0.5 + i / 200,
                "confidence": 0.9,
            }
            for i in range(100)
        ]

        r = await client.post(
            "/api/predictions/ingest",
            json={"predictions": batch},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ingested"] == 100
        assert body["stream_published"] == 100
        assert body["duration_ms"] > 0

        # Verify rows landed in Postgres
        count_result = await db.execute(
            select(func.count()).where(Prediction.model_id == seeded_model.id)
        )
        assert count_result.scalar() == 100

    async def test_ingest_validates_max_batch(
        self, client: AsyncClient, auth_token: str, seeded_model
    ):
        """Batches over 1000 should be rejected with 422."""
        batch = [
            {"model_id": seeded_model.id, "features": {"x": 1.0}, "prediction": 0.5}
            for _ in range(1001)
        ]
        r = await client.post(
            "/api/predictions/ingest",
            json={"predictions": batch},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r.status_code == 422

    async def test_ingest_rejects_empty_features(
        self, client: AsyncClient, auth_token: str, seeded_model
    ):
        r = await client.post(
            "/api/predictions/ingest",
            json={"predictions": [{"model_id": seeded_model.id, "features": {}, "prediction": 0.5}]},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r.status_code == 422


class TestModelRegistry:
    async def test_create_and_retrieve_model(
        self, client: AsyncClient, auth_token: str
    ):
        payload = {"name": "fraud-detector", "version": "1.2.0", "task_type": "classification"}
        r = await client.post(
            "/api/models/",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r.status_code == 201
        model_id = r.json()["id"]

        r2 = await client.get(
            f"/api/models/{model_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["name"] == "fraud-detector"

    async def test_baseline_404_when_none(
        self, client: AsyncClient, auth_token: str
    ):
        """Requesting baseline before upload returns 404."""
        # Create model without baseline
        r = await client.post(
            "/api/models/",
            json={"name": "no-baseline-model", "version": "1.0.0", "task_type": "regression"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        model_id = r.json()["id"]

        r2 = await client.get(
            f"/api/models/{model_id}/baseline",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r2.status_code == 404