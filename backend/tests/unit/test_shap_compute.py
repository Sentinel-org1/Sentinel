from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.tasks.shap_compute import _compute_shap_attribution
from app.models.drift_event import DriftEvent
from app.models.model_registry import ModelRegistry
from app.models.baseline import ReferenceBaseline
from app.models.prediction import Prediction


@pytest.mark.asyncio
async def test_compute_shap_attribution_success():
    # Mock DriftEvent
    mock_event = MagicMock(spec=DriftEvent)
    mock_event.id = 123
    mock_event.model_id = 456
    mock_event.shap_attribution = None

    # Mock ModelRegistry
    mock_model = MagicMock(spec=ModelRegistry)
    mock_model.id = 456

    # Mock ReferenceBaseline
    mock_baseline = MagicMock(spec=ReferenceBaseline)
    mock_baseline.feature_stats = {
        "feature_x": {
            "type": "numeric",
            "histogram": {
                "counts": [10, 20, 30, 40, 100],
                "bin_edges": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
            }
        }
    }

    # Mock Predictions (need at least 30 predictions)
    mock_predictions = []
    for i in range(50):
        pred = MagicMock(spec=Prediction)
        pred.features = {"feature_x": float(i / 50.0)}
        pred.prediction = 0.5 + (i / 100.0)
        mock_predictions.append(pred)

    # Mock Database session
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    
    # Configure db.get behavior
    async def get_side_effect(model_class, ident):
        if model_class == DriftEvent:
            return mock_event
        if model_class == ModelRegistry:
            return mock_model
        return None
    
    mock_db.get.side_effect = get_side_effect
    
    # Configure db.scalar behavior for ReferenceBaseline query
    # and db.scalars behavior for Prediction query
    mock_db.scalar = AsyncMock(return_value=mock_baseline)
    
    mock_scalars_result = MagicMock()
    mock_scalars_result.all = MagicMock(return_value=mock_predictions)
    mock_db.scalars = AsyncMock(return_value=mock_scalars_result)

    # Mock Redis client
    mock_redis = AsyncMock()
    
    # Mock DeltaSHAP return value
    mock_shap_result = MagicMock()
    mock_shap_result.to_dict.return_value = {
        "feature_deltas": {"feature_x": 0.05},
        "top_movers": [("feature_x", 0.05)],
        "baseline_importances": {"feature_x": 0.1},
        "current_importances": {"feature_x": 0.15}
    }

    with patch("app.tasks.shap_compute.AsyncSessionLocal", return_value=mock_db), \
         patch("app.tasks.shap_compute.get_redis", return_value=mock_redis), \
         patch("app.tasks.shap_compute.DeltaSHAP") as MockDeltaSHAP:
        
        MockDeltaSHAP.return_value.compute.return_value = mock_shap_result
        
        result = await _compute_shap_attribution(drift_event_id=123)

        assert result["drift_event_id"] == 123
        assert result["model_id"] == 456
        assert "attribution" in result
        assert result["attribution"]["top_movers"] == [("feature_x", 0.05)]
        
        # Verify event attribution is updated
        assert mock_event.shap_attribution == mock_shap_result.to_dict()
        
        # Verify db.commit was called
        mock_db.commit.assert_called_once()
        
        # Verify Redis publish was called
        mock_redis.publish.assert_called_once()


@pytest.mark.asyncio
async def test_compute_shap_attribution_missing_event():
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_db.get.return_value = None

    with patch("app.tasks.shap_compute.AsyncSessionLocal", return_value=mock_db):
        result = await _compute_shap_attribution(drift_event_id=999)
        assert "error" in result
        assert result["error"] == "Event not found"
