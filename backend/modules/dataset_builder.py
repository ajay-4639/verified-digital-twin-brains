# backend/modules/dataset_builder.py
"""Dataset Builder for Langfuse

Collects high-quality and low-quality examples for:
- Regression testing
- Few-shot prompting
- Fine-tuning data preparation
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DatasetItem:
    """A single dataset item."""
    input: Dict[str, Any]
    expected_output: Dict[str, Any]
    metadata: Dict[str, Any]
    source_trace_id: Optional[str] = None


class DatasetBuilder:
    """Builds datasets in Langfuse for testing and few-shot examples."""
    
    # Quality thresholds
    HIGH_QUALITY_THRESHOLD = 0.8
    LOW_QUALITY_THRESHOLD = 0.5
    
    def __init__(self):
        self._client = None
        self._langfuse_available = False
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
                logger.info("Dataset Builder initialized successfully")
            else:
                logger.warning("Langfuse credentials not found, dataset collection disabled")
        except ImportError:
            logger.warning("Langfuse SDK not installed, dataset collection disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse client: {e}")
    
    def collect_response(
        self,
        trace_id: str,
        query: str,
        response: str,
        context: str,
        citations: List[str],
        scores: Dict[str, Any],
        overall_score: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Auto-collect response to appropriate dataset based on quality.
        
        Args:
            trace_id: Langfuse trace ID
            query: User query
            response: Generated response
            context: Retrieved context
            citations: List of citations
            scores: Individual judge scores
            overall_score: Overall quality score
            metadata: Additional metadata
        """
        if not self._langfuse_available:
            return
        
        try:
            if overall_score >= self.HIGH_QUALITY_THRESHOLD:
                self._add_to_high_quality_dataset(
                    trace_id=trace_id,
                    query=query,
                    response=response,
                    context=context,
                    citations=citations,
                    scores=scores,
                    overall_score=overall_score,
                    metadata=metadata
                )
            elif overall_score <= self.LOW_QUALITY_THRESHOLD:
                self._add_to_improvement_dataset(
                    trace_id=trace_id,
                    query=query,
                    response=response,
                    context=context,
                    citations=citations,
                    scores=scores,
                    overall_score=overall_score,
                    metadata=metadata
                )
        except Exception as e:
            logger.error(f"Failed to collect response to dataset: {e}")
    
    def _add_to_high_quality_dataset(
        self,
        trace_id: str,
        query: str,
        response: str,
        context: str,
        citations: List[str],
        scores: Dict[str, Any],
        overall_score: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a high-quality response to the dataset."""
        try:
            dataset_name = "high_quality_responses"
            
            # Create dataset if it doesn't exist
            try:
                self._client.create_dataset(name=dataset_name)
            except Exception:
                pass  # Dataset may already exist
            
            # Create dataset item
            self._client.create_dataset_item(
                dataset_name=dataset_name,
                input={
                    "query": query,
                    "context": context[:2000],  # Truncate for storage
                },
                expected_output={
                    "response": response,
                    "citations": citations,
                },
                metadata={
                    "trace_id": trace_id,
                    "overall_score": overall_score,
                    "faithfulness_score": scores.get("faithfulness", {}).get("score"),
                    "citation_score": scores.get("citation_alignment", {}).get("score"),
                    "completeness_score": scores.get("completeness", {}).get("score"),
                    "collected_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            logger.info(f"Added high-quality response to dataset (trace: {trace_id})")
        except Exception as e:
            logger.error(f"Failed to add to high-quality dataset: {e}")
    
    def _add_to_improvement_dataset(
        self,
        trace_id: str,
        query: str,
        response: str,
        context: str,
        citations: List[str],
        scores: Dict[str, Any],
        overall_score: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a low-quality response to the improvement dataset."""
        try:
            dataset_name = "needs_improvement"
            
            # Create dataset if it doesn't exist
            try:
                self._client.create_dataset(name=dataset_name)
            except Exception:
                pass  # Dataset may already exist
            
            # Determine failure reasons
            failure_reasons = []
            if scores.get("faithfulness", {}).get("score", 1.0) < self.LOW_QUALITY_THRESHOLD:
                failure_reasons.append("low_faithfulness")
            if scores.get("citation_alignment", {}).get("score", 1.0) < self.LOW_QUALITY_THRESHOLD:
                failure_reasons.append("low_citation_alignment")
            if scores.get("completeness", {}).get("score", 1.0) < self.LOW_QUALITY_THRESHOLD:
                failure_reasons.append("low_completeness")
            
            # Create dataset item
            self._client.create_dataset_item(
                dataset_name=dataset_name,
                input={
                    "query": query,
                    "context": context[:2000],
                },
                expected_output={
                    "response": response,  # This is the bad response
                    "citations": citations,
                },
                metadata={
                    "trace_id": trace_id,
                    "overall_score": overall_score,
                    "failure_reasons": failure_reasons,
                    "faithfulness_score": scores.get("faithfulness", {}).get("score"),
                    "citation_score": scores.get("citation_alignment", {}).get("score"),
                    "completeness_score": scores.get("completeness", {}).get("score"),
                    "collected_at": datetime.utcnow().isoformat(),
                    **(metadata or {})
                }
            )
            logger.info(f"Added low-quality response to improvement dataset (trace: {trace_id})")
        except Exception as e:
            logger.error(f"Failed to add to improvement dataset: {e}")
    
    def get_few_shot_examples(
        self, 
        query_type: str, 
        n: int = 3
    ) -> List[DatasetItem]:
        """
        Fetch examples for few-shot prompting.
        
        Args:
            query_type: Type of query (e.g., "stance", "factual", "smalltalk")
            n: Number of examples to fetch
        
        Returns:
            List of DatasetItem objects
        """
        if not self._langfuse_available:
            return []
        
        try:
            dataset = self._client.get_dataset("high_quality_responses")
            items = []
            
            for item in dataset.items:
                item_metadata = item.metadata or {}
                if item_metadata.get("query_type") == query_type:
                    items.append(DatasetItem(
                        input=item.input,
                        expected_output=item.expected_output,
                        metadata=item_metadata,
                        source_trace_id=item_metadata.get("trace_id")
                    ))
                if len(items) >= n:
                    break
            
            return items
        except Exception as e:
            logger.error(f"Failed to fetch few-shot examples: {e}")
            return []
    
    def add_manual_example(
        self,
        dataset_name: str,
        query: str,
        context: str,
        expected_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Manually add an example to a dataset.
        
        Args:
            dataset_name: Name of the dataset
            query: User query
            context: Retrieved context
            expected_response: Expected/good response
            metadata: Additional metadata
        """
        if not self._langfuse_available:
            return
        
        try:
            # Create dataset if it doesn't exist
            try:
                self._client.create_dataset(name=dataset_name)
            except Exception:
                pass
            
            self._client.create_dataset_item(
                dataset_name=dataset_name,
                input={
                    "query": query,
                    "context": context,
                },
                expected_output={
                    "response": expected_response,
                },
                metadata={
                    "collected_at": datetime.utcnow().isoformat(),
                    "source": "manual",
                    **(metadata or {})
                }
            )
            logger.info(f"Added manual example to dataset {dataset_name}")
        except Exception as e:
            logger.error(f"Failed to add manual example: {e}")
    
    def export_dataset_for_training(
        self, 
        dataset_name: str,
        output_path: str
    ):
        """
        Export a dataset to JSONL format for model training.
        
        Args:
            dataset_name: Name of the dataset to export
            output_path: Path to save the JSONL file
        """
        if not self._langfuse_available:
            return
        
        try:
            import json
            
            dataset = self._client.get_dataset(dataset_name)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for item in dataset.items:
                    record = {
                        "input": item.input,
                        "output": item.expected_output,
                        "metadata": item.metadata,
                    }
                    f.write(json.dumps(record) + '\n')
            
            logger.info(f"Exported {len(dataset.items)} items to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export dataset: {e}")


# Singleton instance
_builder: Optional[DatasetBuilder] = None


def get_dataset_builder() -> DatasetBuilder:
    """Get or create the singleton dataset builder."""
    global _builder
    if _builder is None:
        _builder = DatasetBuilder()
    return _builder


# Convenience functions
def collect_response(
    trace_id: str,
    query: str,
    response: str,
    context: str,
    citations: List[str],
    scores: Dict[str, Any],
    overall_score: float,
    metadata: Optional[Dict[str, Any]] = None
):
    """Auto-collect response based on quality (convenience function)."""
    get_dataset_builder().collect_response(
        trace_id=trace_id,
        query=query,
        response=response,
        context=context,
        citations=citations,
        scores=scores,
        overall_score=overall_score,
        metadata=metadata
    )


def get_few_shot_examples(query_type: str, n: int = 3) -> List[DatasetItem]:
    """Fetch few-shot examples (convenience function)."""
    return get_dataset_builder().get_few_shot_examples(query_type, n)


def add_manual_example(
    dataset_name: str,
    query: str,
    context: str,
    expected_response: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Manually add an example (convenience function)."""
    get_dataset_builder().add_manual_example(
        dataset_name=dataset_name,
        query=query,
        context=context,
        expected_response=expected_response,
        metadata=metadata
    )
