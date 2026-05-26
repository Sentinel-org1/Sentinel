"""backend/app/models/alert.py — Alerts and audit log tables."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    drift_event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drift_events.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # info | warn | critical
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    # open | acknowledged | resolved
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    # True while within the 10-minute cooldown window
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_alerts_model_id_status", "model_id", "status"),
    )


class AuditLog(Base):
    """Immutable record of every alert status change."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # acknowledged | resolved
    comment: Mapped[Optional[str]] = mapped_column(Text)
    performed_by: Mapped[Optional[int]] = mapped_column(Integer)  # user_id
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )