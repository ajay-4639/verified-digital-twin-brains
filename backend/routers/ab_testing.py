"""
A/B Testing API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
import logging

from modules.auth_guard import require_admin
from modules.ab_testing import (
    ABTestingFramework,
    ABTestVariant,
    get_ab_testing_framework
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/ab-tests", tags=["ab-testing"])


@router.get("", response_model=List[Dict[str, Any]])
async def list_ab_tests(
    user=Depends(require_admin)
):
    """List all A/B tests."""
    framework = get_ab_testing_framework()
    return framework.list_tests()


@router.post("")
async def create_ab_test(
    name: str,
    description: str,
    variants: List[Dict[str, Any]],
    success_metric: str = "overall_quality",
    min_sample_size: int = 100,
    user=Depends(require_admin)
):
    """
    Create a new A/B test.
    
    Variants format:
    [
        {"name": "control", "config": {"prompt": "..."}, "traffic_percentage": 0.5},
        {"name": "variant_b", "config": {"prompt": "..."}, "traffic_percentage": 0.5}
    ]
    """
    try:
        framework = get_ab_testing_framework()
        
        # Parse variants
        variant_objects = [
            ABTestVariant(
                name=v["name"],
                config=v["config"],
                traffic_percentage=v["traffic_percentage"]
            )
            for v in variants
        ]
        
        test_id = framework.create_test(
            name=name,
            description=description,
            variants=variant_objects,
            success_metric=success_metric,
            min_sample_size=min_sample_size
        )
        
        return {
            "test_id": test_id,
            "status": "created",
            "message": f"A/B test '{name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to create A/B test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{test_id}")
async def get_ab_test(
    test_id: str,
    user=Depends(require_admin)
):
    """Get A/B test details and results."""
    framework = get_ab_testing_framework()
    results = framework.get_test_results(test_id)
    
    if not results:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return results


@router.post("/{test_id}/stop")
async def stop_ab_test(
    test_id: str,
    user=Depends(require_admin)
):
    """Stop an A/B test and declare winner."""
    framework = get_ab_testing_framework()
    
    # Check if test exists
    test = framework.get_test_results(test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Stop test
    framework.stop_test(test_id)
    
    # Get final results
    final_results = framework.get_test_results(test_id)
    
    return {
        "test_id": test_id,
        "status": "stopped",
        "winner": final_results.get("winner"),
        "final_results": final_results
    }


@router.get("/{test_id}/assign")
async def get_variant_assignment(
    test_id: str,
    user_id: str,
    user=Depends(require_admin)
):
    """
    Get variant assignment for a user.
    This is used by the frontend to determine which variant to show.
    """
    framework = get_ab_testing_framework()
    variant = framework.get_variant_for_request(test_id, user_id)
    
    if not variant:
        raise HTTPException(status_code=404, detail="Test not found or not running")
    
    return {
        "test_id": test_id,
        "user_id": user_id,
        "variant": variant
    }
