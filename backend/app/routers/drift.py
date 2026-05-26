"""
Drift detection routes.

GET  /api/drift?model_id={id}&days=7          → list drift events
GET  /api/drift/{event_id}                    → drift event detail
GET  /api/drift/{event_id}/attribution        → SHAP attribution
POST /api/drift/{model_id}/check              → trigger manual drift check
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.drift_event import DriftEvent
from app.tasks.drift_check import check_drift

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────
class DriftEventResponse(BaseModel):
    id: int
    model_id: int
    detector: str
    metric_name: Optional[str]
    score: float
    threshold: float
    drift_type: Optional[str]
    severity: str
    shap_attribution: Optional[dict]
    detected_at: datetime

    class Config:
        from_attributes = True


class DriftListResponse(BaseModel):
    total: int
    events: list[DriftEventResponse]


# ── Routes ─────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=DriftListResponse,
    summary="List drift events",
    tags=["drift"],
)
async def list_drift_events(
    model_id: Optional[int] = Query(None),
    detector: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> DriftListResponse:
    """
    List drift events with optional filters.

    Args:
        model_id: Filter by model ID
        detector: Filter by detector name (psi, ks, cusum, etc.)
        days: Only events from last N days
        limit: Max results
        offset: Pagination offset

    Returns:
        DriftListResponse with total count and paginated events
    """
    # Build query
    query = select(DriftEvent)

    if model_id:
        query = query.filter(DriftEvent.model_id == model_id)

    if detector:
        query = query.filter(DriftEvent.detector == detector)

    # Filter by date range
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    query = query.filter(DriftEvent.detected_at >= cutoff_date)

    # Count total
    total = await db.scalar(
        select(func.count(DriftEvent.id)).select_from(DriftEvent)
    )

    # Paginate and order
    query = query.order_by(desc(DriftEvent.detected_at)).limit(limit).offset(offset)

    events = (await db.scalars(query)).all()

    return DriftListResponse(
        total=total,
        events=[DriftEventResponse.model_validate(e) for e in events],
    )


@router.get(
    "/{event_id}",
    response_model=DriftEventResponse,
    summary="Get drift event detail",
    tags=["drift"],
)
async def get_drift_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> DriftEventResponse:
    """
    Get details of a specific drift event.

    Args:
        event_id: Drift event ID

    Returns:
        DriftEventResponse
    """
    event = await db.get(DriftEvent, event_id)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drift event {event_id} not found",
        )

    return DriftEventResponse.model_validate(event)


@router.get(
    "/{event_id}/attribution",
    summary="Get SHAP attribution for drift event",
    tags=["drift"],
)
async def get_drift_attribution(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get SHAP feature attribution for drift event.

    Args:
        event_id: Drift event ID

    Returns:
        dict with top features and their SHAP values
    """
    event = await db.get(DriftEvent, event_id)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drift event {event_id} not found",
        )

    if not event.shap_attribution:
        return {
            "event_id": event_id,
            "attribution": [],
            "message": "No SHAP attribution available (computed async)",
        }

    return {
        "event_id": event_id,
        "attribution": event.shap_attribution,
        "metric": event.metric_name,
        "detector": event.detector,
    }


@router.post(
    "/{model_id}/check",
    summary="Manually trigger drift check",
    tags=["drift"],
)
async def trigger_drift_check(
    model_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Manually trigger drift detection for a model.

    Args:
        model_id: Model ID

    Returns:
        dict with task ID and status
    """
    # Verify model exists
    from app.models.model_registry import ModelRegistry

    model = await db.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    # Enqueue drift check task
    task = check_drift.apply_async(
        kwargs={"model_id": model_id},
        queue="drift",
    )

    return {
        "task_id": task.id,
        "model_id": model_id,
        "status": "enqueued",
        "message": "Drift check task enqueued. Poll /tasks/{task_id} for status.",
    }
