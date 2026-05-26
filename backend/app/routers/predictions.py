"""
backend/app/routers/predictions.py
------------------------------------
POST /api/predictions/ingest — bulk ingest with Redis Streams pub.

Flow:
  1. Validate batch (Pydantic v2, max 1000 records)
  2. Bulk-insert to Postgres via ORM
  3. Publish each record to Redis Stream  sentinel:predictions:{model_id}
  4. Celery task enqueued if batch_size ≥ 500 OR 60 s elapsed (handled by consumer)
  5. Return ingestion summary
"""
from __future__ import annotations

import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import Prediction
from app.redis_client import get_redis

logger = structlog.get_logger()
router = APIRouter()

_STREAM_KEY = "sentinel:predictions:{model_id}"
_BATCH_DRIFT_TRIGGER = 500   # Enqueue drift check after this many new rows
_STREAM_MAXLEN = 100_000      # Cap stream length per model


# ── Schemas ────────────────────────────────────────────────────
class PredictionItem(BaseModel):
    model_config = {"strict": True}

    model_id: int = Field(..., gt=0)
    features: dict = Field(..., min_length=1)
    prediction: float
    confidence: float | None = Field(None, ge=0.0, le=1.0)

    @field_validator("features")
    @classmethod
    def features_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("features dict must not be empty")
        return v


class IngestRequest(BaseModel):
    predictions: list[PredictionItem] = Field(..., min_length=1, max_length=1000)


class IngestResponse(BaseModel):
    ingested: int
    duration_ms: float
    stream_published: int


# ── Dependency: current user_id from request state (set by AuthMiddleware) ──
def current_user_id(request: Request) -> int:
    return getattr(request.state, "user_id", 0)


# ── Route ──────────────────────────────────────────────────────
@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk ingest model predictions",
)
async def ingest_predictions(
    body: IngestRequest,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> IngestResponse:
    t0 = time.perf_counter()

    # ── 1. Bulk-insert to Postgres ─────────────────────────────
    rows = [
        Prediction(
            model_id=item.model_id,
            features=item.features,
            prediction=item.prediction,
            confidence=item.confidence,
        )
        for item in body.predictions
    ]
    db.add_all(rows)
    await db.commit()

    # ── 2. Publish to Redis Streams ────────────────────────────
    redis = await get_redis()
    published = 0

    # Group by model_id for efficient stream publishing
    from collections import defaultdict
    by_model: dict[int, list[PredictionItem]] = defaultdict(list)
    for item in body.predictions:
        by_model[item.model_id].append(item)

    async with redis.pipeline() as pipe:
        for model_id, items in by_model.items():
            stream_key = _STREAM_KEY.format(model_id=model_id)
            for item in items:
                await pipe.xadd(
                    stream_key,
                    {
                        "model_id": str(item.model_id),
                        "prediction": str(item.prediction),
                        "confidence": str(item.confidence or ""),
                        # Send a compact feature repr; full payload is in Postgres
                        "n_features": str(len(item.features)),
                    },
                    maxlen=_STREAM_MAXLEN,
                    approximate=True,
                )
                published += 1
        await pipe.execute()

    # ── 3. Check if we should trigger a drift check ────────────
    for model_id, items in by_model.items():
        stream_key = _STREAM_KEY.format(model_id=model_id)
        stream_len = await redis.xlen(stream_key)
        if stream_len >= _BATCH_DRIFT_TRIGGER:
            from app.tasks.drift_check import check_drift
            check_drift.apply_async(
                kwargs={"model_id": model_id},
                queue="drift",
                countdown=0,
            )
            logger.info("drift_check_enqueued", model_id=model_id, stream_len=stream_len)

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "predictions_ingested",
        count=len(rows),
        models=list(by_model.keys()),
        duration_ms=round(duration_ms, 2),
        user_id=user_id,
    )

    return IngestResponse(
        ingested=len(rows),
        duration_ms=round(duration_ms, 2),
        stream_published=published,
    )


@router.get(
    "/",
    summary="List recent predictions for a model",
)
async def list_predictions(
    model_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Prediction)
        .where(Prediction.model_id == model_id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
    )
    predictions = result.scalars().all()
    return [
        {
            "id": p.id,
            "model_id": p.model_id,
            "prediction": p.prediction,
            "confidence": p.confidence,
            "created_at": p.created_at.isoformat(),
        }
        for p in predictions
    ]