# backend/modules/few_shot_prompting.py
"""Dynamic Few-Shot Prompting System

Automatically injects high-quality examples into prompts based on query type.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FewShotExample:
    """A single few-shot example."""
    query: str
    response: str
    query_type: str
    score: float
    source_trace_id: Optional[str] = None


class FewShotExampleSelector:
    """Selects and formats few-shot examples for prompt injection."""
    
    def __init__(self, max_examples: int = 3):
        self.max_examples = max_examples
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
                logger.info("Few-shot selector initialized")
        except Exception as e:
            logger.warning(f"Langfuse not available for few-shot: {e}")
    
    def get_examples(
        self,
        query_type: str,
        n: Optional[int] = None,
        min_score: float = 0.8
    ) -> List[FewShotExample]:
        """
        Get few-shot examples for a query type.
        
        Args:
            query_type: Type of query (e.g., "stance", "factual", "smalltalk")
            n: Number of examples (default: self.max_examples)
            min_score: Minimum quality score for examples
        
        Returns:
            List of FewShotExample objects
        """
        if not self._langfuse_available:
            return self._get_fallback_examples(query_type)
        
        n = n or self.max_examples
        
        try:
            # Get high-quality dataset
            dataset = self._client.get_dataset("high_quality_responses")
            examples = []
            
            for item in dataset.items:
                metadata = item.metadata or {}
                
                # Check if matches query type
                item_query_type = metadata.get("query_type", "general")
                if item_query_type != query_type:
                    continue
                
                # Check score threshold
                score = metadata.get("overall_score", 0)
                if score < min_score:
                    continue
                
                examples.append(FewShotExample(
                    query=item.input.get("query", ""),
                    response=item.expected_output.get("response", ""),
                    query_type=item_query_type,
                    score=score,
                    source_trace_id=metadata.get("trace_id")
                ))
                
                if len(examples) >= n:
                    break
            
            # Sort by score (highest first)
            examples.sort(key=lambda x: x.score, reverse=True)
            
            logger.info(f"Selected {len(examples)} few-shot examples for {query_type}")
            return examples
            
        except Exception as e:
            logger.warning(f"Failed to fetch few-shot examples: {e}")
            return self._get_fallback_examples(query_type)
    
    def _get_fallback_examples(self, query_type: str) -> List[FewShotExample]:
        """Get fallback examples when Langfuse is not available."""
        fallbacks = {
            "stance": [
                FewShotExample(
                    query="What is my stance on remote work?",
                    response="Based on your documented opinions, you believe remote work is effective for focused tasks but value in-person collaboration for creative brainstorming and team building. You mentioned this in your Q3 2023 team memo.",
                    query_type="stance",
                    score=0.9
                )
            ],
            "factual": [
                FewShotExample(
                    query="What is our company's revenue?",
                    response="According to your annual report, the company revenue was $5.2M in 2023, up 40% from 2022.",
                    query_type="factual",
                    score=0.95
                )
            ],
            "smalltalk": [
                FewShotExample(
                    query="How are you?",
                    response="I'm doing well, thanks for asking! Ready to help you with any questions about your knowledge base.",
                    query_type="smalltalk",
                    score=0.85
                )
            ]
        }
        return fallbacks.get(query_type, [])
    
    def format_examples_for_prompt(
        self,
        examples: List[FewShotExample],
        format_style: str = "qa"  # "qa", "conversation", "structured"
    ) -> str:
        """
        Format examples for prompt injection.
        
        Args:
            examples: List of examples
            format_style: How to format ("qa", "conversation", "structured")
        
        Returns:
            Formatted string for prompt
        """
        if not examples:
            return ""
        
        if format_style == "qa":
            return self._format_qa_style(examples)
        elif format_style == "conversation":
            return self._format_conversation_style(examples)
        elif format_style == "structured":
            return self._format_structured_style(examples)
        else:
            return self._format_qa_style(examples)
    
    def _format_qa_style(self, examples: List[FewShotExample]) -> str:
        """Format as Q&A pairs."""
        parts = ["Here are some example Q&As:"]
        for i, ex in enumerate(examples, 1):
            parts.append(f"\nQ{i}: {ex.query}")
            parts.append(f"A{i}: {ex.response}")
        return "\n".join(parts)
    
    def _format_conversation_style(self, examples: List[FewShotExample]) -> str:
        """Format as conversation turns."""
        parts = ["Here are some example conversations:"]
        for ex in examples:
            parts.append(f"\nUser: {ex.query}")
            parts.append(f"Assistant: {ex.response}")
        return "\n".join(parts)
    
    def _format_structured_style(self, examples: List[FewShotExample]) -> str:
        """Format as structured examples."""
        parts = ["Examples:"]
        for ex in examples:
            parts.append(f"\n<example>")
            parts.append(f"Query: {ex.query}")
            parts.append(f"Response: {ex.response}")
            parts.append(f"</example>")
        return "\n".join(parts)
    
    def get_query_type(self, query: str, dialogue_mode: Optional[str] = None) -> str:
        """
        Determine query type from query text and dialogue mode.
        
        Args:
            query: User query
            dialogue_mode: Dialogue mode from router
        
        Returns:
            Query type string
        """
        # Use dialogue mode if available
        if dialogue_mode:
            type_mapping = {
                "SMALLTALK": "smalltalk",
                "QA_FACT": "factual",
                "QA_RELATIONSHIP": "factual",
                "STANCE_GLOBAL": "stance",
                "REPAIR": "repair",
                "TEACHING": "teaching"
            }
            return type_mapping.get(dialogue_mode, "general")
        
        # Otherwise infer from query text
        query_lower = query.lower()
        
        if any(greeting in query_lower for greeting in ["hello", "hi", "hey", "how are you"]):
            return "smalltalk"
        
        if any(stance in query_lower for stance in ["what do i think", "what is my stance", "my opinion"]):
            return "stance"
        
        if any(teaching in query_lower for teaching in ["teach me", "remember this", "correct this"]):
            return "teaching"
        
        return "general"
    
    def inject_examples_into_prompt(
        self,
        base_prompt: str,
        query: str,
        dialogue_mode: Optional[str] = None,
        format_style: str = "qa"
    ) -> str:
        """
        Inject few-shot examples into a prompt.
        
        Args:
            base_prompt: Original prompt
            query: User query (to determine query type)
            dialogue_mode: Dialogue mode (optional)
            format_style: How to format examples
        
        Returns:
            Prompt with examples injected
        """
        # Determine query type
        query_type = self.get_query_type(query, dialogue_mode)
        
        # Get examples
        examples = self.get_examples(query_type)
        
        if not examples:
            return base_prompt
        
        # Format examples
        examples_text = self.format_examples_for_prompt(examples, format_style)
        
        # Inject into prompt (before the main instructions)
        # Look for a placeholder or append at the beginning
        if "{{few_shot_examples}}" in base_prompt:
            return base_prompt.replace("{{few_shot_examples}}", examples_text)
        elif "[FEW_SHOT_EXAMPLES]" in base_prompt:
            return base_prompt.replace("[FEW_SHOT_EXAMPLES]", examples_text)
        else:
            # Append before the main content
            return f"{examples_text}\n\n{base_prompt}"
    
    def track_example_usage(
        self,
        examples: List[FewShotExample],
        trace_id: Optional[str] = None
    ):
        """Track which examples were used in a trace."""
        try:
            from langfuse.decorators import langfuse_context
            
            langfuse_context.update_current_observation(
                metadata={
                    "few_shot_examples_used": len(examples),
                    "few_shot_example_ids": [ex.source_trace_id for ex in examples if ex.source_trace_id],
                    "few_shot_query_types": list(set(ex.query_type for ex in examples))
                }
            )
        except Exception:
            pass


# Singleton instance
_selector: Optional[FewShotExampleSelector] = None


def get_few_shot_selector() -> FewShotExampleSelector:
    """Get or create the singleton selector."""
    global _selector
    if _selector is None:
        _selector = FewShotExampleSelector()
    return _selector


# Convenience functions
def get_examples(query_type: str, n: int = 3) -> List[FewShotExample]:
    """Get few-shot examples (convenience function)."""
    return get_few_shot_selector().get_examples(query_type, n)


def format_examples(examples: List[FewShotExample], style: str = "qa") -> str:
    """Format examples for prompt (convenience function)."""
    return get_few_shot_selector().format_examples_for_prompt(examples, style)


def inject_few_shot(
    base_prompt: str,
    query: str,
    dialogue_mode: Optional[str] = None
) -> str:
    """Inject few-shot examples into prompt (convenience function)."""
    return get_few_shot_selector().inject_examples_into_prompt(
        base_prompt, query, dialogue_mode
    )
