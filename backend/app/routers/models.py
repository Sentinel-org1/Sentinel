"""
backend/app/routers/models.py
-------------------------------
Model registry CRUD + baseline management.

Routes:
  GET    /api/models               → list models
  POST   /api/models               → register a model
  GET    /api/models/{id}          → model detail
  PATCH  /api/models/{id}          → update status/config
  DELETE /api/models/{id}          → soft-delete (status=archived)
  POST   /api/models/{id}/baseline → upload baseline dataset and compute stats
  GET    /api/models/{id}/baseline → retrieve latest baseline stats
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.model_registry import ModelRegistry
from app.services.baseline_service import baseline_service

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────
class ModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(..., min_length=1, max_length=64)
    task_type: Literal["classification", "regression", "ranking"] = "classification"
    config_json: Optional[dict] = None


class ModelUpdate(BaseModel):
    status: Optional[Literal["active", "archived", "deprecated"]] = None
    config_json: Optional[dict] = None


class ModelResponse(BaseModel):
    id: int
    name: str
    version: str
    task_type: Optional[str]
    status: str
    config_json: Optional[dict]

    model_config = {"from_attributes": True}


class BaselineResponse(BaseModel):
    id: int
    model_id: int
    version: int
    n_samples: int
    feature_stats: dict
    created_at: str

    model_config = {"from_attributes": True}


# ── Helpers ────────────────────────────────────────────────────
async def _get_model_or_404(db: AsyncSession, model_id: int) -> ModelRegistry:
    result = await db.execute(
        select(ModelRegistry).where(ModelRegistry.id == model_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return model


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    """Parse a CSV upload into a list of dicts, auto-casting numerics."""
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        parsed = {}
        for k, v in row.items():
            try:
                parsed[k] = float(v) if "." in v else int(v)
            except (ValueError, TypeError):
                parsed[k] = v
        rows.append(parsed)
    return rows


# ── Routes ─────────────────────────────────────────────────────
@router.get("/", response_model=list[ModelResponse], summary="List all models")
async def list_models(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> list[ModelResponse]:
    q = select(ModelRegistry)
    if status_filter:
        q = q.where(ModelRegistry.status == status_filter)
    result = await db.execute(q.order_by(ModelRegistry.created_at.desc()))
    return [ModelResponse.model_validate(m) for m in result.scalars().all()]


@router.post(
    "/",
    response_model=ModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new model",
)
async def create_model(
    body: ModelCreate,
    db: AsyncSession = Depends(get_db),
) -> ModelResponse:
    model = ModelRegistry(
        name=body.name,
        version=body.version,
        task_type=body.task_type,
        config_json=body.config_json,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return ModelResponse.model_validate(model)


@router.get("/{model_id}", response_model=ModelResponse, summary="Get model by ID")
async def get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
) -> ModelResponse:
    model = await _get_model_or_404(db, model_id)
    return ModelResponse.model_validate(model)


@router.patch("/{model_id}", response_model=ModelResponse, summary="Update model")
async def update_model(
    model_id: int,
    body: ModelUpdate,
    db: AsyncSession = Depends(get_db),
) -> ModelResponse:
    model = await _get_model_or_404(db, model_id)
    if body.status is not None:
        model.status = body.status
    if body.config_json is not None:
        model.config_json = body.config_json
    await db.commit()
    await db.refresh(model)
    return ModelResponse.model_validate(model)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive model")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)) -> None:
    model = await _get_model_or_404(db, model_id)
    model.status = "archived"
    await db.commit()


# ── Baseline endpoints ─────────────────────────────────────────
@router.post(
    "/{model_id}/baseline",
    response_model=BaselineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload training dataset CSV and compute baseline statistics",
)
async def upload_baseline(
    model_id: int,
    file: UploadFile = File(..., description="Training data CSV (rows = samples, cols = features)"),
    db: AsyncSession = Depends(get_db),
) -> BaselineResponse:
    """
    Accepts a CSV of training samples. Computes per-feature statistics
    (mean, std, percentiles, histogram) and stores as a versioned baseline.
    Each upload creates a new version — the previous one is retained for audit.
    """
    await _get_model_or_404(db, model_id)

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only .csv files are accepted",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty file")

    try:
        data = _parse_csv(content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV parse error: {exc}",
        )

    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CSV has no data rows")

    baseline = await baseline_service.compute_and_save(db, model_id, data)
    return BaselineResponse(
        id=baseline.id,
        model_id=baseline.model_id,
        version=baseline.version,
        n_samples=baseline.n_samples,
        feature_stats=baseline.feature_stats,
        created_at=baseline.created_at.isoformat(),
    )


@router.get(
    "/{model_id}/baseline",
    response_model=BaselineResponse,
    summary="Retrieve latest baseline statistics",
)
async def get_baseline(
    model_id: int,
    db: AsyncSession = Depends(get_db),
) -> BaselineResponse:
    await _get_model_or_404(db, model_id)
    baseline = await baseline_service.get_latest(db, model_id)
    if not baseline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No baseline found. Upload a training dataset first.",
        )
    return BaselineResponse(
        id=baseline.id,
        model_id=baseline.model_id,
        version=baseline.version,
        n_samples=baseline.n_samples,
        feature_stats=baseline.feature_stats,
        created_at=baseline.created_at.isoformat(),
    )