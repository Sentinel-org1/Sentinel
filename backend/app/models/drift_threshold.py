"""backend/app/models/drift_threshold.py — EWMA adaptive thresholds table."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Float, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class DriftThreshold(Base):
    __tablename__ = "drift_thresholds"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False
    )
    detector: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_name: Mapped[Optional[str]] = mapped_column(String(255))
    ewma_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    ewma_mean: Mapped[Optional[float]] = mapped_column(Float)
    ewma_std: Mapped[Optional[float]] = mapped_column(Float)
    # Last N threshold values for charting
    history: Mapped[Optional[list]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_drift_thresholds_model_detector", "model_id", "detector", "metric_name"),
    )