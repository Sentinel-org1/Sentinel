from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app.routers.calibration import get_calibration, generate_calibration
from app.models.model_registry import ModelRegistry
from app.models.calibration_curve import CalibrationCurve
from app.models.baseline import ReferenceBaseline


@pytest.mark.asyncio
async def test_get_calibration_success():
    # Mock ModelRegistry
    mock_model = MagicMock(spec=ModelRegistry)
    
    # Mock CalibrationCurve
    mock_curve = MagicMock(spec=CalibrationCurve)
    mock_curve.model_id = 123
    mock_curve.curve_data = {
        "points": [
            {"threshold": 0.1, "tp_rate": 0.9, "fp_rate": 0.1, "youden_j": 0.8},
            {"threshold": 0.2, "tp_rate": 0.85, "fp_rate": 0.05, "youden_j": 0.8},
        ],
        "optimal_threshold": 0.2,
        "auc": 0.92,
    }

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_model
    mock_db.scalar.return_value = mock_curve

    response = await get_calibration(model_id=123, db=mock_db)

    assert response.model_id == 123
    assert len(response.points) == 2
    assert response.optimal_threshold == 0.2
    assert response.auc == 0.92
    
    mock_db.get.assert_called_once_with(ModelRegistry, 123)


@pytest.mark.asyncio
async def test_get_calibration_model_not_found():
    mock_db = AsyncMock()
    mock_db.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_calibration(model_id=999, db=mock_db)
    
    assert exc_info.value.status_code == 404
    assert "Model 999 not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_calibration_empty_curve():
    mock_model = MagicMock(spec=ModelRegistry)
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_model
    mock_db.scalar.return_value = None  # No calibration curve stored yet

    response = await get_calibration(model_id=123, db=mock_db)

    assert response.model_id == 123
    assert len(response.points) == 0
    assert response.message == "No calibration curve generated yet. POST to generate one."


@pytest.mark.asyncio
async def test_generate_calibration_success():
    # Mock model
    mock_model = MagicMock(spec=ModelRegistry)
    
    # Mock ReferenceBaseline with numeric feature histograms
    mock_baseline = MagicMock(spec=ReferenceBaseline)
    mock_baseline.feature_stats = {
        "feature_a": {
            "type": "numeric",
            "histogram": {
                "counts": [10, 20, 30, 40, 100],
                "bin_edges": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
            }
        }
    }

    mock_db = AsyncMock()
    
    # db.get returns model, db.scalar returns baseline
    mock_db.get.return_value = mock_model
    mock_db.scalar.return_value = mock_baseline

    # Mock CalibrationReport generator
    mock_report = MagicMock()
    mock_point = MagicMock()
    mock_point.threshold = 0.25
    mock_point.tp_rate = 0.8
    mock_point.fp_rate = 0.1
    mock_point.youden_j = 0.7
    
    mock_report.points = [mock_point]
    mock_report.optimal_threshold = 0.25
    mock_report.auc = 0.85

    with patch("app.routers.calibration.CalibrationReport") as MockReport:
        MockReport.return_value.generate.return_value = mock_report
        
        response = await generate_calibration(model_id=123, db=mock_db)
        
        assert response.model_id == 123
        assert len(response.points) == 1
        assert response.optimal_threshold == 0.25
        assert response.auc == 0.85
        
        # Verify database adds the calibration curve and commits
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
