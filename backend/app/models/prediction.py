"""backend/app/models/prediction.py — Prediction ingestion table."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, Float, DateTime, JSON, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False
    )
    # JSONB stores the full feature vector
    features: Mapped[dict] = mapped_column(JSON, nullable=False)
    prediction: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    # Ground truth label (filled in later for concept drift)
    actual: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        # composite index covering most common query pattern
        Index("ix_predictions_model_id_created_at", "model_id", "created_at"),
    )