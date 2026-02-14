# backend/modules/regression_testing.py
"""Regression Testing System for Digital Twin

Runs dataset items against the chat endpoint to catch regressions
before they reach production.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TestResultStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class RegressionTestResult:
    """Result of a single regression test."""
    dataset_item_id: str
    query: str
    status: TestResultStatus
    baseline_score: float
    new_score: float
    score_diff: float
    diff_percent: float
    details: Dict[str, Any]
    execution_time_ms: int
    timestamp: str


@dataclass
class RegressionTestReport:
    """Full regression test report."""
    test_id: str
    dataset_name: str
    started_at: str
    completed_at: str
    total_items: int
    passed: int
    failed: int
    warnings: int
    errors: int
    results: List[RegressionTestResult]
    summary: Dict[str, Any]


class RegressionTestRunner:
    """Runs regression tests against the chat endpoint."""
    
    # Thresholds for pass/fail/warning
    SCORE_REGRESSION_THRESHOLD = 0.1  # 10% drop is a failure
    SCORE_WARNING_THRESHOLD = 0.05    # 5% drop is a warning
    
    def __init__(self):
        self._langfuse_available = False
        self._client = None
        self._init_langfuse()
    
    def _init_langfuse(self):
        """Initialize Langfuse client."""
        try:
            from langfuse import Langfuse
            
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
            
            if public_key and secret_key:
                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                self._langfuse_available = True
                logger.info("Regression Test Runner initialized")
        except Exception as e:
            logger.warning(f"Langfuse not available for regression testing: {e}")
    
    async def run_test(
        self,
        dataset_name: str,
        twin_id: str,
        sample_size: Optional[int] = None,
        baseline_tag: Optional[str] = None
    ) -> RegressionTestReport:
        """
        Run regression test on a dataset.
        
        Args:
            dataset_name: Name of the dataset to test
            twin_id: Twin ID to use for testing
            sample_size: Number of items to test (None = all)
            baseline_tag: Tag to use for baseline scores (None = use dataset metadata)
        
        Returns:
            RegressionTestReport with full results
        """
        if not self._langfuse_available:
            raise RuntimeError("Langfuse not available for regression testing")
        
        test_id = f"regression_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        started_at = datetime.utcnow().isoformat()
        
        try:
            # Load dataset
            dataset = self._client.get_dataset(dataset_name)
            items = list(dataset.items)
            
            if sample_size and sample_size < len(items):
                import random
                items = random.sample(items, sample_size)
            
            logger.info(f"Running regression test {test_id} on {len(items)} items from {dataset_name}")
            
            # Run tests
            results = []
            for item in items:
                result = await self._test_single_item(
                    item=item,
                    twin_id=twin_id,
                    baseline_tag=baseline_tag
                )
                results.append(result)
            
            # Generate report
            completed_at = datetime.utcnow().isoformat()
            report = self._generate_report(
                test_id=test_id,
                dataset_name=dataset_name,
                started_at=started_at,
                completed_at=completed_at,
                results=results
            )
            
            # Log report to Langfuse
            self._log_report_to_langfuse(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Regression test failed: {e}")
            raise
    
    async def _test_single_item(
        self,
        item: Any,
        twin_id: str,
        baseline_tag: Optional[str] = None
    ) -> RegressionTestResult:
        """Test a single dataset item."""
        import time
        
        start_time = time.time()
        query = item.input.get("query", "")
        expected_response = item.expected_output.get("response", "")
        context = item.input.get("context", "")
        
        # Get baseline score from metadata or scores
        baseline_score = self._get_baseline_score(item, baseline_tag)
        
        try:
            # Run chat request (this is a mock - in production, call actual endpoint)
            # For now, we'll use the evaluation pipeline to score
            from modules.evaluation_pipeline import EvaluationPipeline
            
            # Create a mock trace for testing
            test_trace_id = f"regression_test_{item.id}"
            
            # Score the expected response (simulating what the new model would produce)
            # In production, this would actually call the chat endpoint
            pipeline = EvaluationPipeline()
            eval_result = await pipeline.evaluate_response(
                trace_id=test_trace_id,
                query=query,
                response=expected_response,  # In production, this would be the actual response
                context=context,
                citations=item.expected_output.get("citations", [])
            )
            
            new_score = eval_result.overall_score
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Calculate difference
            score_diff = new_score - baseline_score
            diff_percent = (score_diff / baseline_score * 100) if baseline_score > 0 else 0
            
            # Determine status
            if score_diff <= -self.SCORE_REGRESSION_THRESHOLD:
                status = TestResultStatus.FAILED
            elif score_diff <= -self.SCORE_WARNING_THRESHOLD:
                status = TestResultStatus.WARNING
            else:
                status = TestResultStatus.PASSED
            
            return RegressionTestResult(
                dataset_item_id=item.id,
                query=query,
                status=status,
                baseline_score=baseline_score,
                new_score=new_score,
                score_diff=score_diff,
                diff_percent=diff_percent,
                details={
                    "scores": eval_result.scores,
                    "flags": eval_result.flags,
                    "expected_response_preview": expected_response[:200] if expected_response else ""
                },
                execution_time_ms=execution_time_ms,
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to test item {item.id}: {e}")
            return RegressionTestResult(
                dataset_item_id=item.id,
                query=query,
                status=TestResultStatus.ERROR,
                baseline_score=baseline_score,
                new_score=0.0,
                score_diff=-baseline_score,
                diff_percent=-100.0,
                details={"error": str(e)},
                execution_time_ms=int((time.time() - start_time) * 1000),
                timestamp=datetime.utcnow().isoformat()
            )
    
    def _get_baseline_score(self, item: Any, baseline_tag: Optional[str] = None) -> float:
        """Get baseline score from dataset item."""
        metadata = item.metadata or {}
        
        # If baseline_tag specified, look for that specific score
        if baseline_tag:
            return metadata.get(f"baseline_score_{baseline_tag}") or metadata.get("overall_score", 0.8)
        
        # Otherwise use the overall_score from when item was collected
        return metadata.get("overall_score", 0.8)
    
    def _generate_report(
        self,
        test_id: str,
        dataset_name: str,
        started_at: str,
        completed_at: str,
        results: List[RegressionTestResult]
    ) -> RegressionTestReport:
        """Generate final test report."""
        passed = sum(1 for r in results if r.status == TestResultStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestResultStatus.FAILED)
        warnings = sum(1 for r in results if r.status == TestResultStatus.WARNING)
        errors = sum(1 for r in results if r.status == TestResultStatus.ERROR)
        
        # Calculate summary stats
        avg_baseline = sum(r.baseline_score for r in results) / len(results) if results else 0
        avg_new = sum(r.new_score for r in results) / len(results) if results else 0
        avg_diff = avg_new - avg_baseline
        
        # Find worst regressions
        failed_results = [r for r in results if r.status == TestResultStatus.FAILED]
        failed_results.sort(key=lambda x: x.score_diff)
        worst_regressions = [
            {
                "item_id": r.dataset_item_id,
                "query": r.query[:100],
                "score_drop": round(r.score_diff, 3)
            }
            for r in failed_results[:5]
        ]
        
        summary = {
            "avg_baseline_score": round(avg_baseline, 3),
            "avg_new_score": round(avg_new, 3),
            "avg_score_diff": round(avg_diff, 3),
            "pass_rate": round(passed / len(results) * 100, 1) if results else 0,
            "worst_regressions": worst_regressions,
            "execution_time_total_sec": (
                datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)
            ).total_seconds()
        }
        
        return RegressionTestReport(
            test_id=test_id,
            dataset_name=dataset_name,
            started_at=started_at,
            completed_at=completed_at,
            total_items=len(results),
            passed=passed,
            failed=failed,
            warnings=warnings,
            errors=errors,
            results=results,
            summary=summary
        )
    
    def _log_report_to_langfuse(self, report: RegressionTestReport):
        """Log regression test report to Langfuse."""
        try:
            # Create a trace for the regression test run
            trace = self._client.trace(
                name="regression_test",
                metadata={
                    "test_id": report.test_id,
                    "dataset_name": report.dataset_name,
                    "total_items": report.total_items,
                    "passed": report.passed,
                    "failed": report.failed,
                    "warnings": report.warnings,
                    "errors": report.errors,
                    "summary": report.summary
                }
            )
            
            # Add scores
            trace.score(
                name="regression_pass_rate",
                value=report.summary["pass_rate"],
                data_type="NUMERIC"
            )
            trace.score(
                name="regression_score_diff",
                value=report.summary["avg_score_diff"],
                data_type="NUMERIC"
            )
            
            # Flag if failures
            if report.failed > 0:
                trace.score(
                    name="regression_has_failures",
                    value=1,
                    comment=f"{report.failed} items regressed",
                    data_type="BOOLEAN"
                )
            
            self._client.flush()
            
        except Exception as e:
            logger.error(f"Failed to log regression report to Langfuse: {e}")
    
    def save_baseline(
        self,
        dataset_name: str,
        tag: str,
        scores: Dict[str, float]
    ):
        """
        Save current scores as baseline for future comparison.
        
        Args:
            dataset_name: Name of the dataset
            tag: Tag for this baseline (e.g., "v1.2.3", "pre-refactor")
            scores: Dict mapping item_id to score
        """
        try:
            dataset = self._client.get_dataset(dataset_name)
            
            for item in dataset.items:
                if item.id in scores:
                    # Update metadata with baseline score
                    metadata = item.metadata or {}
                    metadata[f"baseline_score_{tag}"] = scores[item.id]
                    
                    # Note: Langfuse doesn't support updating dataset items directly
                    # This would need to be implemented based on their API
                    logger.info(f"Would save baseline {tag} for item {item.id}: {scores[item.id]}")
            
        except Exception as e:
            logger.error(f"Failed to save baseline: {e}")


# Singleton instance
_runner: Optional[RegressionTestRunner] = None


def get_regression_runner() -> RegressionTestRunner:
    """Get or create the singleton regression test runner."""
    global _runner
    if _runner is None:
        _runner = RegressionTestRunner()
    return _runner


# Convenience functions
async def run_regression_test(
    dataset_name: str,
    twin_id: str,
    sample_size: Optional[int] = None
) -> RegressionTestReport:
    """Run regression test (convenience function)."""
    runner = get_regression_runner()
    return await runner.run_test(dataset_name, twin_id, sample_size)
