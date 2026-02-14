"""
Cost Tracking API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import logging

from modules.auth_guard import require_admin
from modules.cost_tracking import get_cost_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/costs", tags=["cost-tracking"])


@router.get("/summary")
async def get_cost_summary(
    hours: Optional[int] = 24,
    user=Depends(require_admin)
):
    """Get cost summary for a time period."""
    try:
        tracker = get_cost_tracker()
        summary = await tracker.get_cost_summary(hours)
        
        if "error" in summary:
            raise HTTPException(status_code=500, detail=summary["error"])
        
        # Add optimization suggestions
        suggestions = tracker.get_optimization_suggestions(summary)
        summary["optimization_suggestions"] = suggestions
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get cost summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_model_costs(
    user=Depends(require_admin)
):
    """Get cost information for available models."""
    from modules.cost_tracking import TOKEN_COSTS
    
    return {
        "models": [
            {
                "name": name,
                "input_cost_per_1k": costs["input"],
                "output_cost_per_1k": costs["output"],
            }
            for name, costs in TOKEN_COSTS.items()
        ]
    }


@router.post("/track")
async def track_cost(
    trace_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    user=Depends(require_admin)
):
    """Manually track cost for a request."""
    try:
        tracker = get_cost_tracker()
        usage = tracker.track_usage(trace_id, model, input_tokens, output_tokens)
        
        return {
            "trace_id": trace_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(usage.cost_usd, 6),
        }
        
    except Exception as e:
        logger.error(f"Failed to track cost: {e}")
        raise HTTPException(status_code=500, detail=str(e))
