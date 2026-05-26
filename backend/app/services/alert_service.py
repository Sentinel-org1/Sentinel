"""
Alert service with deduplication and cooldown logic.

Suppresses duplicate alerts for the same model+metric within cooldown window.
Implements status tracking (open, acknowledged, resolved).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.drift_event import DriftEvent
from app.config import settings

logger = structlog.get_logger()


class AlertService:
    """Service for creating, deduplicating, and managing drift alerts."""

    COOLDOWN_SECONDS = settings.ALERT_COOLDOWN_SECONDS  # 600 seconds (10 minutes)
    SEVERITY_LEVELS = {"info": 0, "warn": 1, "critical": 2}

    @staticmethod
    async def should_alert(
        db: AsyncSession,
        model_id: int,
        detector: str,
        metric_name: Optional[str],
    ) -> bool:
        """
        Check if we should create an alert (not within cooldown window).

        Args:
            db: Database session
            model_id: Model ID
            detector: Detector name
            metric_name: Metric name (can be None)

        Returns:
            True if cooldown has expired or no recent alert exists
        """
        # Find the most recent alert for this model+detector+metric
        recent_alert = await db.scalar(
            select(Alert)
            .join(DriftEvent, Alert.drift_event_id == DriftEvent.id)
            .filter(
                and_(
                    Alert.model_id == model_id,
                    DriftEvent.detector == detector,
                    DriftEvent.metric_name == metric_name,
                    Alert.status != "resolved",  # Exclude resolved alerts
                )
            )
            .order_by(desc(Alert.created_at))
            .limit(1)
        )

        if recent_alert is None:
            return True  # No recent alert, should alert

        # Check if cooldown has expired
        now = datetime.now(timezone.utc)
        elapsed = (now - recent_alert.created_at).total_seconds()

        if elapsed > AlertService.COOLDOWN_SECONDS:
            logger.info(
                "alert_cooldown_expired",
                model_id=model_id,
                elapsed_sec=int(elapsed),
                cooldown_sec=AlertService.COOLDOWN_SECONDS,
            )
            return True

        logger.debug(
            "alert_suppressed_cooldown",
            model_id=model_id,
            detector=detector,
            metric=metric_name,
            remaining_sec=int(AlertService.COOLDOWN_SECONDS - elapsed),
        )
        return False

    @staticmethod
    async def create_alert(
        db: AsyncSession,
        drift_event_id: int,
        model_id: int,
        severity: str,
    ) -> Optional[Alert]:
        """
        Create an alert for a drift event with deduplication.

        Args:
            db: Database session
            drift_event_id: DriftEvent ID
            model_id: Model ID
            severity: Alert severity (info, warn, critical)

        Returns:
            Created Alert object, or None if suppressed by cooldown
        """
        # Fetch drift event for detector/metric info
        drift_event = await db.get(DriftEvent, drift_event_id)
        if not drift_event:
            logger.error("drift_event_not_found", drift_event_id=drift_event_id)
            return None

        # Check deduplication
        can_alert = await AlertService.should_alert(
            db,
            model_id,
            drift_event.detector,
            drift_event.metric_name,
        )

        if not can_alert:
            logger.info(
                "alert_creation_skipped",
                drift_event_id=drift_event_id,
                reason="cooldown_active",
            )
            return None

        # Create alert
        alert = Alert(
            drift_event_id=drift_event_id,
            model_id=model_id,
            severity=severity,
            status="open",
            suppressed=False,
        )

        db.add(alert)
        await db.commit()
        await db.refresh(alert)

        logger.info(
            "alert_created",
            alert_id=alert.id,
            model_id=model_id,
            severity=severity,
            drift_event_id=drift_event_id,
        )

        return alert

    @staticmethod
    async def acknowledge_alert(
        db: AsyncSession,
        alert_id: int,
        comment: Optional[str] = None,
    ) -> Optional[Alert]:
        """
        Mark an alert as acknowledged.

        Args:
            db: Database session
            alert_id: Alert ID
            comment: Optional acknowledgment comment

        Returns:
            Updated Alert object
        """
        alert = await db.get(Alert, alert_id)
        if not alert:
            logger.error("alert_not_found", alert_id=alert_id)
            return None

        alert.status = "acknowledged"
        alert.updated_at = datetime.now(timezone.utc)

        db.add(alert)
        await db.commit()
        await db.refresh(alert)

        logger.info("alert_acknowledged", alert_id=alert_id, comment=comment)
        return alert

    @staticmethod
    async def resolve_alert(
        db: AsyncSession,
        alert_id: int,
        resolution: Optional[str] = None,
    ) -> Optional[Alert]:
        """
        Mark an alert as resolved.

        Args:
            db: Database session
            alert_id: Alert ID
            resolution: Optional resolution description

        Returns:
            Updated Alert object
        """
        alert = await db.get(Alert, alert_id)
        if not alert:
            logger.error("alert_not_found", alert_id=alert_id)
            return None

        alert.status = "resolved"
        alert.updated_at = datetime.now(timezone.utc)

        db.add(alert)
        await db.commit()
        await db.refresh(alert)

        logger.info("alert_resolved", alert_id=alert_id, resolution=resolution)
        return alert

    @staticmethod
    async def get_open_alerts(
        db: AsyncSession,
        model_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        """
        Fetch open/acknowledged alerts, optionally filtered by model.

        Args:
            db: Database session
            model_id: Optional model ID filter
            limit: Max results
            offset: Pagination offset

        Returns:
            List of Alert objects
        """
        query = select(Alert).filter(Alert.status.in_(["open", "acknowledged"]))

        if model_id:
            query = query.filter(Alert.model_id == model_id)

        query = query.order_by(desc(Alert.created_at)).limit(limit).offset(offset)

        return (await db.scalars(query)).all()
