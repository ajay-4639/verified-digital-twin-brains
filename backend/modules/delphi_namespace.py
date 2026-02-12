"""
Namespace resolution helpers for Delphi-style creator namespaces.

Primary format:
    creator_{creator_id}_twin_{twin_id}

Legacy format:
    {twin_id}

These helpers keep reads backward compatible during migration while allowing
new writes to creator-based namespaces.
"""
import os
from functools import lru_cache
from typing import List, Optional

from modules.observability import supabase


def build_creator_namespace(creator_id: str, twin_id: str) -> str:
    """Build Delphi-style namespace for a creator/twin pair."""
    return f"creator_{creator_id}_twin_{twin_id}"


def _normalize_creator_id(raw_creator_id: Optional[str], tenant_id: Optional[str]) -> Optional[str]:
    """
    Normalize creator identity.

    Falls back to a deterministic tenant-derived creator id for backward
    compatibility while DB migrations are rolling out.
    """
    if raw_creator_id:
        return str(raw_creator_id)
    if tenant_id:
        return f"tenant_{tenant_id}"
    return None


@lru_cache(maxsize=4096)
def resolve_creator_id_for_twin(twin_id: str) -> Optional[str]:
    """
    Resolve creator_id for a twin from Supabase.

    If `twins.creator_id` isn't present yet, this gracefully falls back to a
    deterministic tenant-derived creator id.
    """
    try:
        # Preferred path: creator_id exists.
        res = (
            supabase.table("twins")
            .select("creator_id,tenant_id")
            .eq("id", twin_id)
            .limit(1)
            .execute()
        )
        row = res.data[0] if res.data else None
        if not row:
            return None
        return _normalize_creator_id(row.get("creator_id"), row.get("tenant_id"))
    except Exception as e:
        # Backward compatibility path for DBs without creator_id column.
        if "creator_id" in str(e) and "does not exist" in str(e):
            try:
                res = (
                    supabase.table("twins")
                    .select("tenant_id")
                    .eq("id", twin_id)
                    .limit(1)
                    .execute()
                )
                row = res.data[0] if res.data else None
                if not row:
                    return None
                return _normalize_creator_id(None, row.get("tenant_id"))
            except Exception:
                return None
        return None


def get_primary_namespace_for_twin(twin_id: str, creator_id: Optional[str] = None) -> str:
    """
    Resolve the primary namespace for read/write operations.

    Returns creator namespace when resolvable; otherwise legacy twin namespace.
    """
    resolved_creator = creator_id or resolve_creator_id_for_twin(twin_id)
    if resolved_creator:
        return build_creator_namespace(resolved_creator, twin_id)
    return twin_id


def get_namespace_candidates_for_twin(
    twin_id: str,
    creator_id: Optional[str] = None,
    include_legacy: Optional[bool] = None,
) -> List[str]:
    """
    Return namespace candidates for dual-read migration compatibility.
    """
    if include_legacy is None:
        include_legacy = os.getenv("DELPHI_DUAL_READ", "true").lower() == "true"

    primary = get_primary_namespace_for_twin(twin_id=twin_id, creator_id=creator_id)
    namespaces = [primary]

    if include_legacy and primary != twin_id:
        namespaces.append(twin_id)

    # Preserve order and uniqueness.
    out: List[str] = []
    for ns in namespaces:
        if ns not in out:
            out.append(ns)
    return out


def clear_creator_namespace_cache() -> None:
    """Clear namespace resolution cache (useful for tests or migrations)."""
    resolve_creator_id_for_twin.cache_clear()
