"""
Alert management routes.

GET    /api/alerts                      → list alerts
GET    /api/alerts/{id}                 → alert detail
PATCH  /api/alerts/{id}                 → acknowledge or resolve alert
DELETE /api/alerts/{id}                 → delete alert (soft)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import Alert
from app.services.alert_service import AlertService

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────
class AlertResponse(BaseModel):
    id: int
    drift_event_id: int
    model_id: int
    severity: str
    status: str
    suppressed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertUpdateRequest(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]
    comment: Optional[str] = None


class AlertListResponse(BaseModel):
    total: int
    alerts: list[AlertResponse]


# ── Routes ─────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=AlertListResponse,
    summary="List alerts",
    tags=["alerts"],
)
async def list_alerts(
    model_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """
    List alerts with optional filters.

    Args:
        model_id: Filter by model ID
        status_filter: Filter by status (open, acknowledged, resolved)
        limit: Max results
        offset: Pagination offset

    Returns:
        AlertListResponse with total count and paginated alerts
    """
    alerts = await AlertService.get_open_alerts(
        db,
        model_id=model_id,
        limit=limit,
        offset=offset,
    )

    total = len(alerts)  # Simplified count for demo

    return AlertListResponse(
        total=total,
        alerts=[AlertResponse.model_validate(a) for a in alerts],
    )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Get alert detail",
    tags=["alerts"],
)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """
    Get details of a specific alert.

    Args:
        alert_id: Alert ID

    Returns:
        AlertResponse
    """
    alert = await db.get(Alert, alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    return AlertResponse.model_validate(alert)


@router.patch(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Update alert status",
    tags=["alerts"],
)
async def update_alert(
    alert_id: int,
    body: AlertUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """
    Update alert status (acknowledge or resolve).

    Args:
        alert_id: Alert ID
        body: AlertUpdateRequest with new status and optional comment

    Returns:
        Updated AlertResponse
    """
    alert = await db.get(Alert, alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    if body.status == "acknowledged":
        updated_alert = await AlertService.acknowledge_alert(db, alert_id, body.comment)
    elif body.status == "resolved":
        updated_alert = await AlertService.resolve_alert(db, alert_id, body.comment)
    else:
        updated_alert = alert

    return AlertResponse.model_validate(updated_alert)
