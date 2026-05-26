"""backend/app/models/drift_event.py — Detected drift events table."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Float, DateTime, JSON, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class DriftEvent(Base):
    __tablename__ = "drift_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False
    )
    # psi | ks_test | js_divergence | cusum | page_hinkley | isolation_forest
    detector: Mapped[str] = mapped_column(String(64), nullable=False)
    # Which feature triggered the drift (None = multi-feature)
    metric_name: Mapped[Optional[str]] = mapped_column(String(255))
    score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    # data_drift | concept_drift | covariate_shift | label_drift | mixed
    drift_type: Mapped[Optional[str]] = mapped_column(String(64))
    # info | warn | critical
    severity: Mapped[str] = mapped_column(String(32), default="warn", nullable=False)
    # Top-5 Δ_SHAP feature attribution (populated async)
    shap_attribution: Mapped[Optional[dict]] = mapped_column(JSON)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_drift_events_model_id_detected_at", "model_id", "detected_at"),
    )