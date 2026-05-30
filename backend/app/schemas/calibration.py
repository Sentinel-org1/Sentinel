"""Calibration request/response schemas."""
from typing import List, Optional

from pydantic import BaseModel


# ── Existing schemas (do not remove) ──────────────────────────

class CalibrationPoint(BaseModel):
    """Single calibration point."""
    threshold: float
    fp_rate: float
    tp_rate: float


class CalibrationResponse(BaseModel):
    """Calibration response."""
    model_id: int
    points: List[CalibrationPoint]


# ── New schemas for Novel #5 — CalibrationReport ──────────────

class CalibrationPointDetailed(BaseModel):
    """One point on the ROC curve, including Youden's J statistic."""
    threshold: float
    tp_rate: float
    fp_rate: float
    youden_j: float


class CalibrationResultResponse(BaseModel):
    """Full calibration result returned from CalibrationReport.generate()."""
    detector_name: str
    optimal_threshold: float
    optimal_tp_rate: float
    optimal_fp_rate: float
    auc: float
    ewma_agreement: Optional[bool]
    points: List[CalibrationPointDetailed]