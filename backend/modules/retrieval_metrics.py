"""
Retrieval Metrics Module

Collects and exposes metrics for the retrieval system.
Supports Prometheus/Grafana integration.

Usage:
    from modules.retrieval_metrics import get_metrics, record_retrieval
    
    # Record a retrieval event
    record_retrieval(twin_id="twin-123", contexts_found=5, duration_ms=150)
    
    # Get current metrics
    metrics = get_metrics()
"""

import time
import threading
from collections import defaultdict
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class RetrievalMetrics:
    """Container for retrieval metrics."""
    
    # Counters
    total_retrievals: int = 0
    successful_retrievals: int = 0
    failed_retrievals: int = 0
    
    # Source breakdown
    owner_memory_hits: int = 0
    verified_qna_hits: int = 0
    vector_search_hits: int = 0
    
    # Timing (milliseconds)
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    
    # Context counts
    total_contexts_found: int = 0
    contexts_per_query: List[int] = field(default_factory=list)
    
    # Errors
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Namespace stats
    namespace_hits: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    def record_retrieval(
        self,
        contexts_found: int,
        duration_ms: float,
        source: str = "vector_search",
        error: Optional[str] = None,
        namespaces: Optional[List[str]] = None
    ):
        """Record a retrieval event."""
        self.total_retrievals += 1
        
        if error:
            self.failed_retrievals += 1
            self.errors_by_type[error] += 1
        else:
            self.successful_retrievals += 1
            
            # Track source
            if source == "owner_memory":
                self.owner_memory_hits += 1
            elif source == "verified_qna":
                self.verified_qna_hits += 1
            else:
                self.vector_search_hits += 1
            
            # Track timing
            self.total_duration_ms += duration_ms
            self.min_duration_ms = min(self.min_duration_ms, duration_ms)
            self.max_duration_ms = max(self.max_duration_ms, duration_ms)
            
            # Track contexts
            self.total_contexts_found += contexts_found
            self.contexts_per_query.append(contexts_found)
            
            # Keep only last 1000 measurements for memory
            if len(self.contexts_per_query) > 1000:
                self.contexts_per_query = self.contexts_per_query[-1000:]
        
        # Track namespaces
        if namespaces:
            for ns in namespaces:
                self.namespace_hits[ns] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of metrics."""
        avg_duration = (self.total_duration_ms / self.total_retrievals) if self.total_retrievals > 0 else 0
        avg_contexts = (self.total_contexts_found / self.successful_retrievals) if self.successful_retrievals > 0 else 0
        
        return {
            "total_retrievals": self.total_retrievals,
            "successful_retrievals": self.successful_retrievals,
            "failed_retrievals": self.failed_retrievals,
            "success_rate": round(self.successful_retrievals / self.total_retrievals, 4) if self.total_retrievals > 0 else 0,
            "source_breakdown": {
                "owner_memory": self.owner_memory_hits,
                "verified_qna": self.verified_qna_hits,
                "vector_search": self.vector_search_hits
            },
            "timing_ms": {
                "average": round(avg_duration, 2),
                "min": round(self.min_duration_ms, 2) if self.min_duration_ms != float('inf') else 0,
                "max": round(self.max_duration_ms, 2)
            },
            "contexts": {
                "average_per_query": round(avg_contexts, 2),
                "total_found": self.total_contexts_found
            },
            "errors": dict(self.errors_by_type),
            "top_namespaces": dict(sorted(self.namespace_hits.items(), key=lambda x: x[1], reverse=True)[:10])
        }


# Global metrics instance
_metrics = RetrievalMetrics()
_metrics_lock = threading.Lock()


def record_retrieval(
    twin_id: str,
    contexts_found: int,
    duration_ms: float,
    source: str = "vector_search",
    error: Optional[str] = None,
    namespaces: Optional[List[str]] = None
):
    """Record a retrieval event thread-safely."""
    with _metrics_lock:
        _metrics.record_retrieval(
            contexts_found=contexts_found,
            duration_ms=duration_ms,
            source=source,
            error=error,
            namespaces=namespaces
        )


def get_metrics() -> Dict[str, Any]:
    """Get current metrics summary."""
    with _metrics_lock:
        return _metrics.get_summary()


def reset_metrics():
    """Reset all metrics (useful for testing)."""
    global _metrics
    with _metrics_lock:
        _metrics = RetrievalMetrics()


# Phase timing tracker for detailed performance analysis
_phase_times: Dict[str, List[float]] = defaultdict(list)
_phase_lock = threading.Lock()


def record_phase_timing(phase: str, duration_ms: float):
    """Record timing for a specific phase."""
    with _phase_lock:
        _phase_times[phase].append(duration_ms)
        # Keep last 1000 measurements
        if len(_phase_times[phase]) > 1000:
            _phase_times[phase] = _phase_times[phase][-1000:]


def get_phase_timing_stats() -> Dict[str, Dict[str, float]]:
    """Get timing statistics for each phase."""
    with _phase_lock:
        stats = {}
        for phase, times in _phase_times.items():
            if times:
                stats[phase] = {
                    "count": len(times),
                    "avg_ms": round(sum(times) / len(times), 2),
                    "min_ms": round(min(times), 2),
                    "max_ms": round(max(times), 2),
                    "p95_ms": round(sorted(times)[int(len(times) * 0.95)], 2) if len(times) >= 20 else round(max(times), 2)
                }
        return stats


# Prometheus-compatible metrics export
def get_prometheus_metrics() -> str:
    """Export metrics in Prometheus format."""
    with _metrics_lock:
        lines = []
        
        # Total retrievals
        lines.append(f'retrieval_total{{}} {_metrics.total_retrievals}')
        lines.append(f'retrieval_successful{{}} {_metrics.successful_retrievals}')
        lines.append(f'retrieval_failed{{}} {_metrics.failed_retrievals}')
        
        # Source breakdown
        lines.append(f'retrieval_source{{source="owner_memory"}} {_metrics.owner_memory_hits}')
        lines.append(f'retrieval_source{{source="verified_qna"}} {_metrics.verified_qna_hits}')
        lines.append(f'retrieval_source{{source="vector_search"}} {_metrics.vector_search_hits}')
        
        # Timing
        if _metrics.total_retrievals > 0:
            avg = _metrics.total_duration_ms / _metrics.total_retrievals
            lines.append(f'retrieval_duration_ms{{stat="avg"}} {round(avg, 2)}')
            lines.append(f'retrieval_duration_ms{{stat="min"}} {round(_metrics.min_duration_ms, 2) if _metrics.min_duration_ms != float("inf") else 0}')
            lines.append(f'retrieval_duration_ms{{stat="max"}} {round(_metrics.max_duration_ms, 2)}')
        
        # Namespace hits
        for ns, count in _metrics.namespace_hits.items():
            lines.append(f'retrieval_namespace_hits{{namespace="{ns}"}} {count}')
        
        return '\n'.join(lines)


# Health check thresholds
HEALTH_THRESHOLDS = {
    "max_avg_latency_ms": 2000,
    "min_success_rate": 0.95,
    "max_error_rate": 0.05
}


def get_health_status() -> Dict[str, Any]:
    """Get health status based on metrics."""
    with _metrics_lock:
        if _metrics.total_retrievals == 0:
            return {"status": "unknown", "message": "No retrieval data yet"}
        
        issues = []
        
        # Check success rate
        success_rate = _metrics.successful_retrievals / _metrics.total_retrievals
        if success_rate < HEALTH_THRESHOLDS["min_success_rate"]:
            issues.append(f"Success rate {success_rate:.2%} below threshold {HEALTH_THRESHOLDS['min_success_rate']:.2%}")
        
        # Check latency
        if _metrics.total_retrievals > 0:
            avg_latency = _metrics.total_duration_ms / _metrics.total_retrievals
            if avg_latency > HEALTH_THRESHOLDS["max_avg_latency_ms"]:
                issues.append(f"Average latency {avg_latency:.0f}ms above threshold {HEALTH_THRESHOLDS['max_avg_latency_ms']}ms")
        
        if issues:
            return {
                "status": "unhealthy",
                "issues": issues,
                "metrics": _metrics.get_summary()
            }
        
        return {
            "status": "healthy",
            "metrics": _metrics.get_summary()
        }
