"""
Retrieval Router with Delphi creator-based namespaces.

This router keeps strict tenant isolation while enabling creator-scoped
namespace operations.
"""
from typing import Any, Dict, List, Optional
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from modules.auth_guard import require_tenant
from modules.embeddings_delphi import get_delphi_client
from modules.tenant_guard import (
    TenantAuditLogger,
    TenantGuard,
    require_creator_access,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/retrieval", tags=["retrieval"])
audit_logger = TenantAuditLogger()


class QueryRequest(BaseModel):
    vector: List[float]
    creator_id: str
    twin_id: Optional[str] = None
    top_k: int = 10
    filter: Optional[dict] = None


class QueryAcrossTwinsRequest(BaseModel):
    vector: List[float]
    creator_id: str
    twin_ids: List[str]
    top_k: int = 10


class QueryResponse(BaseModel):
    matches: List[dict]
    namespace: str
    total_matches: int
    latency_ms: float


class DeletionRequest(BaseModel):
    creator_id: str
    twin_id: Optional[str] = None
    gdpr_request: bool = False


class DeletionResponse(BaseModel):
    success: bool
    deleted_count: int
    namespace: str


def _match_to_dict(match: Any) -> Dict[str, Any]:
    """
    Normalize Pinecone match object to dict.
    """
    if isinstance(match, dict):
        return {
            "id": match.get("id"),
            "score": match.get("score"),
            "metadata": match.get("metadata"),
        }
    return {
        "id": getattr(match, "id", None),
        "score": getattr(match, "score", None),
        "metadata": getattr(match, "metadata", None),
    }


def _extract_matches(result: Any) -> List[Any]:
    if isinstance(result, dict):
        return result.get("matches", []) or []
    return getattr(result, "matches", []) or []


@router.post("/query", response_model=QueryResponse)
@require_creator_access(creator_id_param="creator_id")
async def query_vectors(
    request: QueryRequest,
    current_user: dict = Depends(require_tenant),
):
    """
    Query vectors with creator/twin namespace isolation enforced.
    """
    start_time = time.time()
    client = get_delphi_client()

    try:
        result = client.query(
            vector=request.vector,
            creator_id=request.creator_id,
            twin_id=request.twin_id,
            top_k=request.top_k,
            filter=request.filter,
            include_metadata=True,
        )

        guard = TenantGuard(current_user)
        raw_matches = _extract_matches(result)
        filtered_matches = guard.filter_results_by_tenant(raw_matches)
        matches = [_match_to_dict(m) for m in filtered_matches]

        latency_ms = (time.time() - start_time) * 1000
        audit_logger.log_vector_query(
            user_id=current_user.get("user_id") or current_user.get("id"),
            creator_id=request.creator_id,
            twin_id=request.twin_id,
            top_k=request.top_k,
            result_count=len(matches),
            latency_ms=latency_ms,
        )

        return QueryResponse(
            matches=matches,
            namespace=client.get_namespace(request.creator_id, request.twin_id),
            total_matches=len(matches),
            latency_ms=round(latency_ms, 2),
        )
    except Exception as e:
        logger.error(f"Delphi query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/query-across-twins")
@require_creator_access(creator_id_param="creator_id")
async def query_across_twins(
    request: QueryAcrossTwinsRequest,
    current_user: dict = Depends(require_tenant),
):
    """
    Query across multiple twin namespaces for a creator.
    """
    start_time = time.time()
    client = get_delphi_client()

    try:
        matches = client.query_across_twins(
            vector=request.vector,
            creator_id=request.creator_id,
            twin_ids=request.twin_ids,
            top_k=request.top_k,
            include_metadata=True,
        )
        guard = TenantGuard(current_user)
        filtered = guard.filter_results_by_tenant(matches)
        normalized = [_match_to_dict(m) for m in filtered]

        latency_ms = (time.time() - start_time) * 1000
        audit_logger.log_vector_query(
            user_id=current_user.get("user_id") or current_user.get("id"),
            creator_id=request.creator_id,
            twin_id=f"multiple:{len(request.twin_ids)}",
            top_k=request.top_k,
            result_count=len(normalized),
            latency_ms=latency_ms,
        )

        return {
            "matches": normalized,
            "twins_queried": len(request.twin_ids),
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        logger.error(f"Delphi multi-twin query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.delete("/delete-twin", response_model=DeletionResponse)
@require_creator_access(creator_id_param="creator_id")
async def delete_twin(
    request: DeletionRequest,
    current_user: dict = Depends(require_tenant),
):
    if not request.twin_id:
        raise HTTPException(status_code=400, detail="twin_id is required")

    client = get_delphi_client()
    try:
        stats = client.get_twin_stats(request.creator_id, request.twin_id)
        count_before = stats.get("vector_count", 0)
        success = client.delete_twin(request.creator_id, request.twin_id)
        if not success:
            raise HTTPException(status_code=500, detail="Deletion failed")

        audit_logger.log_data_deletion(
            user_id=current_user.get("user_id") or current_user.get("id"),
            creator_id=request.creator_id,
            twin_id=request.twin_id,
            vector_count=count_before,
            gdpr_request=request.gdpr_request,
        )
        return DeletionResponse(
            success=True,
            deleted_count=count_before,
            namespace=client.get_namespace(request.creator_id, request.twin_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delphi twin deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.delete("/delete-creator")
@require_creator_access(creator_id_param="creator_id")
async def delete_creator_data(
    request: DeletionRequest,
    current_user: dict = Depends(require_tenant),
):
    """
    Delete all creator namespaces (GDPR).
    """
    client = get_delphi_client()
    try:
        twins = client.list_creator_twins(request.creator_id)
        vector_count = sum(int(t.get("vector_count", 0)) for t in twins)
        success = client.delete_creator_data(request.creator_id)
        verified = client.verify_gdpr_deletion(request.creator_id)

        if not success or not verified:
            raise HTTPException(status_code=500, detail="Creator deletion verification failed")

        audit_logger.log_data_deletion(
            user_id=current_user.get("user_id") or current_user.get("id"),
            creator_id=request.creator_id,
            twin_id=None,
            vector_count=vector_count,
            gdpr_request=True,
        )
        return {
            "success": True,
            "creator_id": request.creator_id,
            "namespaces_deleted": len(twins),
            "vectors_deleted": vector_count,
            "gdpr_verified": verified,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delphi creator deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/twins/{creator_id}")
async def list_creator_twins(
    creator_id: str,
    current_user: dict = Depends(require_tenant),
):
    guard = TenantGuard(current_user)
    try:
        guard.validate_creator_access(creator_id)
        client = get_delphi_client()
        twins = client.list_creator_twins(creator_id)
        return {
            "creator_id": creator_id,
            "twins": twins,
            "count": len(twins),
        }
    except Exception as e:
        logger.error(f"List creator twins failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list twins: {str(e)}")


@router.get("/stats/{creator_id}")
async def get_creator_stats(
    creator_id: str,
    current_user: dict = Depends(require_tenant),
):
    guard = TenantGuard(current_user)
    try:
        guard.validate_creator_access(creator_id)
        client = get_delphi_client()
        twins = client.list_creator_twins(creator_id)
        total_vectors = sum(int(t.get("vector_count", 0)) for t in twins)
        return {
            "creator_id": creator_id,
            "total_twins": len(twins),
            "total_vectors": total_vectors,
            "namespaces": [t["namespace"] for t in twins],
        }
    except Exception as e:
        logger.error(f"Get creator stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/health")
async def delphi_health():
    """
    Basic health check for creator namespace retrieval service.
    """
    try:
        client = get_delphi_client()
        stats = client.index.describe_index_stats()
        return {
            "status": "healthy",
            "index": client.index_name,
            "total_vectors": stats.total_vector_count,
            "namespaces": len(stats.namespaces),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
