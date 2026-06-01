"""
Calibration routes: GET/POST /api/models/{id}/calibration.

GET  — returns the latest stored calibration curve for the model.
POST — generates a new calibration curve by running CalibrationReportGenerator
       against baseline data + current detectors, stores the result, and
       returns the computed curve data.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.baseline import ReferenceBaseline
from app.models.calibration_curve import CalibrationCurve
from app.models.model_registry import ModelRegistry
from app.novelties.calibration_report import CalibrationReport
from app.detectors.psi import PSIDetector

logger = structlog.get_logger()

router = APIRouter()


# ── Pydantic response schemas ─────────────────────────────────
class CalibrationPointResponse(BaseModel):
    threshold: float
    tp_rate: float
    fp_rate: float
    youden_j: float


class CalibrationResponse(BaseModel):
    model_id: int
    points: list[CalibrationPointResponse]
    optimal_threshold: Optional[float] = None
    auc: Optional[float] = None
    message: Optional[str] = None


# ── Routes ─────────────────────────────────────────────────────
@router.get(
    "/{model_id}/calibration",
    response_model=CalibrationResponse,
    summary="Get calibration curve for model",
)
async def get_calibration(
    model_id: int,
    db: AsyncSession = Depends(get_db),
) -> CalibrationResponse:
    """
    Returns the latest stored calibration curve for the model.
    If no calibration has been generated, returns empty points.
    """
    # Verify model exists
    model = await db.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    # Load latest calibration curve
    curve = await db.scalar(
        select(CalibrationCurve)
        .filter(CalibrationCurve.model_id == model_id)
        .order_by(CalibrationCurve.created_at.desc())
        .limit(1)
    )

    if not curve or not curve.curve_data:
        return CalibrationResponse(
            model_id=model_id,
            points=[],
            message="No calibration curve generated yet. POST to generate one.",
        )

    data = curve.curve_data
    points = [
        CalibrationPointResponse(**pt)
        for pt in data.get("points", [])
    ]

    return CalibrationResponse(
        model_id=model_id,
        points=points,
        optimal_threshold=data.get("optimal_threshold"),
        auc=data.get("auc"),
    )


@router.post(
    "/{model_id}/calibration",
    response_model=CalibrationResponse,
    summary="Generate calibration curve",
)
async def generate_calibration(
    model_id: int,
    db: AsyncSession = Depends(get_db),
) -> CalibrationResponse:
    """
    Generates a new calibration curve by running CalibrationReportGenerator
    against the model's baseline. Stores the result and returns it.
    """
    # Verify model exists
    model = await db.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    # Load baseline
    baseline = await db.scalar(
        select(ReferenceBaseline)
        .filter(ReferenceBaseline.model_id == model_id)
        .order_by(ReferenceBaseline.created_at.desc())
        .limit(1)
    )

    if not baseline or not baseline.feature_stats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No baseline found for model {model_id}. Upload baseline first.",
        )

    # Extract a numeric feature's baseline array for calibration
    baseline_stats = baseline.feature_stats
    numeric_features = [
        f for f, s in baseline_stats.items()
        if isinstance(s, dict) and s.get("type") == "numeric"
    ]

    if not numeric_features:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No numeric features in baseline. Cannot generate calibration.",
        )

    # Use the first numeric feature's histogram to reconstruct baseline
    feat_name = numeric_features[0]
    feat_stat = baseline_stats[feat_name]
    hist = feat_stat.get("histogram", {})

    if not hist or not hist.get("counts"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No histogram data for feature '{feat_name}'.",
        )

    counts = np.array(hist["counts"], dtype=float)
    edges = np.array(hist["bin_edges"])
    midpoints = (edges[:-1] + edges[1:]) / 2
    reps = np.round(counts / counts.sum() * 500).astype(int)
    baseline_arr = np.repeat(midpoints, reps)

    if len(baseline_arr) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Baseline too small for calibration (need ≥ 50 samples).",
        )

    # Generate calibration report
    generator = CalibrationReport()
    try:
        report = generator.generate(
            baseline=baseline_arr,
            detector_class=PSIDetector,
        )
    except Exception as exc:
        logger.exception("calibration_generation_failed", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calibration generation failed: {str(exc)}",
        )

    # Serialize and store
    curve_data = {
        "points": [
            {
                "threshold": pt.threshold,
                "tp_rate": pt.tp_rate,
                "fp_rate": pt.fp_rate,
                "youden_j": pt.youden_j,
            }
            for pt in report.points
        ],
        "optimal_threshold": report.optimal_threshold,
        "auc": report.auc,
    }

    curve = CalibrationCurve(
        model_id=model_id,
        curve_data=curve_data,
    )
    db.add(curve)
    await db.commit()
    await db.refresh(curve)

    logger.info(
        "calibration_curve_generated",
        model_id=model_id,
        n_points=len(report.points),
        auc=round(report.auc, 4),
        optimal_threshold=round(report.optimal_threshold, 4),
    )

    points = [
        CalibrationPointResponse(**pt)
        for pt in curve_data["points"]
    ]

    return CalibrationResponse(
        model_id=model_id,
        points=points,
        optimal_threshold=report.optimal_threshold,
        auc=report.auc,
    )
