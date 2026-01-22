# backend/modules/reasoning_engine.py
"""Reasoning Engine: Logical deduction system for Advisor Mode.

Enables the Twin to answer "Would I...?" and "What do I think about...?" questions
by traversing the cognitive graph and synthesizing a response based on known
beliefs, values, and past decisions.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from pydantic import BaseModel

from modules.observability import supabase
from modules.graph_context import _get_all_nodes, _expand_one_hop
from modules.clients import get_openai_client

logger = logging.getLogger(__name__)

class StanceType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"

class LogicStep(BaseModel):
    """A single step in the reasoning chain."""
    step_number: int
    description: str
    nodes_involved: List[str]  # IDs of nodes used in this step
    inference_type: str  # e.g., "direct_match", "implication", "contradiction"

class DecisionTrace(BaseModel):
    """Complete trace of why a decision was made."""
    topic: str
    final_stance: StanceType
    confidence_score: float  # 0.0 to 1.0
    logic_chain: List[LogicStep]
    key_factors: List[str]  # Summarized bullet points
    
    def to_readable_trace(self) -> str:
        """Convert trace to a human-readable explanation."""
        trace = f"### Reasoning Trace for '{self.topic}'\n\n"
        trace += f"**Final Stance:** {self.final_stance.value.upper()} (Confidence: {int(self.confidence_score * 100)}%)\n\n"
        
        trace += "**Logic Chain:**\n"
        for step in self.logic_chain:
            trace += f"{step.step_number}. {step.description}\n"
        
        trace += "\n**Key Factors:**\n"
        for factor in self.key_factors:
            trace += f"- {factor}\n"
            
        return trace

class ReasoningEngine:
    """
    Engine for graph-based logical deduction (Advisor Mode).
    
    This engine enables the Twin to answer hypothetical questions ("Would I...?")
    by traversing the cognitive graph to find relevant Values, Beliefs, and Principles,
    and then using an LLM to synthesize a consistent stance.
    
    Attributes:
        twin_id (str): The UUID of the twin.
        client (AsyncOpenAI): OpenAI client for reasoning.
    """
    
    def __init__(self, twin_id: str):
        """
        Initialize the Reasoning Engine.

        Args:
            twin_id (str): The unique identifier of the Digital Twin.
        """
        self.twin_id = twin_id
        self.client = get_openai_client()

    async def predict_stance(self, topic: str, context_context: str = "") -> DecisionTrace:
        """
        Predict the twin's stance on a hypothetical topic.
        
        Args:
            topic: The topic or question (e.g., "investing in crypto")
            context_context: Optional additional context from chat
            
        Returns:
            DecisionTrace object explaining the reasoning
        """
        # 1. Search for relevant nodes (Beliefs, Values, Past Decisions)
        # We search specifically for high-level cognitive nodes
        relevant_nodes = await self._find_relevant_cognitive_nodes(topic)
        
        if not relevant_nodes:
            return DecisionTrace(
                topic=topic,
                final_stance=StanceType.UNCERTAIN,
                confidence_score=0.1,
                logic_chain=[LogicStep(
                    step_number=1,
                    description="No relevant beliefs or values found in knowledge graph.",
                    nodes_involved=[],
                    inference_type="search_failure"
                )],
                key_factors=["Lack of data"]
            )

        # 2. Build reasoning prompt
        knowledge_summary = self._format_nodes_for_reasoning(relevant_nodes)
        
        prompt = f"""
        You are a logical reasoning engine for a Digital Twin.
        Your goal is to predict the Twin's stance on: "{topic}"
        
        Based ONLY on the following known Beliefs, Values, and Rules:
        {knowledge_summary}
        
        Additional Context: {context_context}
        
        Task:
        1. Analyze compatibility of the topic with known values.
        2. Check for precedents in past decisions.
        3. Identify any contradictions.
        4. Deduce a final stance (Positive, Negative, Neutral).
        
        Return a JSON object with:
        - "stance": "positive", "negative", "neutral", or "uncertain"
        - "confidence": 0.0 to 1.0
        - "logic_chain": List of strings explaining step-by-step deduction.
        - "key_factors": List of key values/beliefs driving this decision.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", # Use smart model for reasoning
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # 3. Construct Trace
            logic_steps = []
            for i, step_desc in enumerate(result.get("logic_chain", [])):
                logic_steps.append(LogicStep(
                    step_number=i+1,
                    description=step_desc,
                    nodes_involved=[], # Specific node attribution would require more granular mapping
                    inference_type="deduction"
                ))
            
            return DecisionTrace(
                topic=topic,
                final_stance=StanceType(result.get("stance", "neutral")),
                confidence_score=result.get("confidence", 0.5),
                logic_chain=logic_steps,
                key_factors=result.get("key_factors", [])
            )
            
        except Exception as e:
            logger.error(f"Reasoning error: {e}")
            return DecisionTrace(
                topic=topic,
                final_stance=StanceType.ERROR,
                confidence_score=0.0,
                logic_chain=[],
                key_factors=[f"Error: {str(e)}"]
            )

    async def _find_relevant_cognitive_nodes(self, query: str) -> List[Dict[str, Any]]:
        """
        Find nodes specifically related to cognition (Values, Beliefs, Principles).
        Uses embedding search + filtering.
        """
        try:
            # This uses the system RPC but filters results
            # In a real expanded implementation, we would use vector search on the 'nodes' table
            # but for now we reuse the existing keyword search from graph_context
            # and filter for specific types.
            
            from modules.graph_context import _select_seeds
            
            potential_nodes = await _select_seeds(self.twin_id, query)
            
            # Expand to 1-hop to get connected values
            if potential_nodes:
                neighbor_nodes, _ = await _expand_one_hop(
                    self.twin_id, 
                    [n['id'] for n in potential_nodes]
                )
                potential_nodes.extend(neighbor_nodes)
            else:
                 # If keyword match fails, perform a broader fetch of just Values/Principles
                 # This is a fallback to "General Principles" when specific topic isn't found
                 potential_nodes = await self._get_core_values()

            # Deduplicate by ID
            seen_ids = set()
            unique_nodes = []
            for n in potential_nodes:
                if n['id'] not in seen_ids:
                    unique_nodes.append(n)
                    seen_ids.add(n['id'])
            
            # Prioritize Cognitive Types
            cognitive_types = ["value", "belief", "principle", "stance", "rule"]
            
            relevant = []
            for node in unique_nodes:
                n_type = node.get("type", "").lower()
                # We include everything but prioritize cognitive types in ranking/usage
                relevant.append(node)
                
            return relevant
            
        except Exception as e:
            logger.error(f"Error finding cognitive nodes: {e}")
            return []

    async def _get_core_values(self) -> List[Dict[str, Any]]:
        """Fetch core values/principles as fallback context."""
        try:
            res = supabase.table("nodes").select("*").eq("twin_id", self.twin_id).in_("type", ["Value", "Principle", "Belief"]).limit(10).execute()
            return res.data or []
        except Exception:
            return []

    def _format_nodes_for_reasoning(self, nodes: List[Dict[str, Any]]) -> str:
        """Format nodes into a structured context for the LLM."""
        formatted = []
        for n in nodes:
            name = n.get("name", "Unknown")
            n_type = n.get("type", "Node")
            desc = n.get("description", "")
            formatted.append(f"- [{n_type.upper()}] {name}: {desc}")
        return "\n".join(formatted)
