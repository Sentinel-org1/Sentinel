"""backend/app/models/baseline.py — Reference baseline table."""
from datetime import datetime, timezone
from sqlalchemy import Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ReferenceBaseline(Base):
    __tablename__ = "reference_baselines"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Incremented each time the baseline is replaced
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Per-feature stats: {feature: {mean, std, min, max, p25, p50, p75, histogram_bins, histogram_counts}}
    feature_stats: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Number of rows used to compute baseline
    n_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )