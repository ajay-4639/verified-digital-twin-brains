# backend/routers/reasoning.py
"""Reasoning API: Endpoints for Advisor Mode.

Provides direct access to the Reasoning Engine for testing and external integrations.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from modules.auth_guard import get_current_user, verify_twin_ownership
from modules.reasoning_engine import ReasoningEngine, DecisionTrace

router = APIRouter(tags=["reasoning"])

class PredictionRequest(BaseModel):
    topic: str
    context: Optional[str] = ""

@router.post("/reason/predict/{twin_id}")
async def predict_stance_endpoint(
    twin_id: str,
    request: PredictionRequest,
    user=Depends(get_current_user)
):
    """
    Predict the Twin's stance on a topic using the Reasoning Engine.
    Returns the decision trace explaining the logic.
    """
    verify_twin_ownership(twin_id, user)
    
    try:
        engine = ReasoningEngine(twin_id)
        trace = await engine.predict_stance(request.topic, request.context)
        return trace.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
