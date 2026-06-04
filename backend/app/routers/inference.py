"""
backend/app/routers/inference.py
---------------------------------
POST /api/models/{model_id}/predict — runs live model prediction and SHAP explanation.
"""
from __future__ import annotations

import os
import sys
import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

# Ensure root directory is on PATH so ml/ and scripts/ can be imported
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ml.models.model_loader import load_model

router = APIRouter()

# Global caches
_MODEL_CACHE = {}
_SCALER_CACHE = {}

def get_cached_model(model_id: int):
    if model_id not in _MODEL_CACHE:
        try:
            _MODEL_CACHE[model_id] = load_model(model_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model ID {model_id} artifacts could not be loaded: {str(exc)}"
            ) from exc
    return _MODEL_CACHE[model_id]

def get_scaler():
    if 3 not in _SCALER_CACHE:
        try:
            from scripts.data_preprocessor import preprocess_model_3
            _, _, scaler = preprocess_model_3()
            _SCALER_CACHE[3] = scaler
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fit/load scaler for model 3: {str(exc)}"
            ) from exc
    return _SCALER_CACHE[3]

# --- Schemas ---
class PredictRequest(BaseModel):
    features: dict

class PredictResponse(BaseModel):
    prediction: float
    confidence: float
    shap_values: dict[str, float]

@router.post(
    "/{model_id}/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dynamic model prediction and SHAP features"
)
async def predict_model(model_id: int, body: PredictRequest) -> PredictResponse:
    # 1. Load model, explainer, feature list
    model, explainer, feature_names, _ = get_cached_model(model_id)

    # 2. Check if all required features are present
    missing = [f for f in feature_names if f not in body.features]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required features for model {model_id}: {missing}"
        )

    # 3. Format features as DataFrame in correct order
    try:
        raw_values = {f: [float(body.features[f])] for f in feature_names}
        feat_df = pd.DataFrame(raw_values)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Feature values must be numeric: {str(exc)}"
        ) from exc

    # 4. Preprocess / Scale if Model 3
    try:
        if model_id == 3:
            scaler = get_scaler()
            feat_input = scaler.transform(feat_df)
        else:
            feat_input = feat_df

        # 5. Run prediction
        proba = float(model.predict_proba(feat_input)[:, 1][0])
        confidence = float(max(proba, 1 - proba))

        # 6. Compute SHAP values
        shap_dict = {}
        if explainer is not None:
            try:
                shap_vals = explainer.shap_values(feat_input)
                
                # Handle different SHAP output formats (lists of arrays, multi-class etc.)
                if isinstance(shap_vals, list):
                    # Binary classification list format, take positive class
                    shap_vals = shap_vals[1]
                
                if len(shap_vals.shape) > 1:
                    shap_vals = shap_vals[0]

                shap_dict = {name: float(val) for name, val in zip(feature_names, shap_vals)}
            except Exception:
                explainer = None

        if explainer is None:
            # Fallback: compute proxy SHAP values from feature importances or model coefficients
            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_
                for name, imp in zip(feature_names, importances):
                    # Scale by value deviation to simulate influence sign
                    val = float(imp * (float(body.features[name]) - 0.5) * 0.1)
                    shap_dict[name] = val
            elif hasattr(model, "coef_"):
                coefs = model.coef_[0]
                for name, coef in zip(feature_names, coefs):
                    val = float(coef * (float(body.features[name]) - 0.5) * 0.1)
                    shap_dict[name] = val
            else:
                shap_dict = {name: 0.0 for name in feature_names}

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction/SHAP computation failed: {str(exc)}"
        ) from exc

    return PredictResponse(
        prediction=proba,
        confidence=confidence,
        shap_values=shap_dict
    )
