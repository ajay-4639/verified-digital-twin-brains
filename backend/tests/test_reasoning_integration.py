# backend/tests/test_reasoning_integration.py
"""Integration tests for Phase 3 API endpoints.

Tests:
- POST /chat/{twin_id} (Reasoning routing)
- POST /reason/predict/{twin_id} (Direct API)
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

# Mock heavily - similar to previous integration tests
sys.modules["modules.observability"] = MagicMock()
sys.modules["modules.observability"].supabase = MagicMock()
sys.modules["modules.auth_guard"] = MagicMock()
sys.modules["modules.auth_guard"].get_current_user = lambda: {"user_id": "test-user", "tenant_id": "test-tenant"}
sys.modules["modules.auth_guard"].verify_twin_ownership = lambda twin_id, user: True

# Mock heavy deps
sys.modules["modules.ingestion"] = MagicMock()
sys.modules["modules.ingestion"].process_and_index_text = AsyncMock(return_value=5)

# Ensure AsyncMock is available before imports that might use it
from unittest.mock import AsyncMock

from main import app
from modules.reasoning_engine import DecisionTrace, StanceType, LogicStep

client = TestClient(app)

class TestReasoningIntegration(unittest.TestCase):
    
    @patch('modules.reasoning_engine.ReasoningEngine.predict_stance')
    def test_direct_prediction_endpoint(self, mock_predict):
        """Test POST /reason/predict/{twin_id}"""
        # Mock result
        mock_trace = DecisionTrace(
            topic="test",
            final_stance=StanceType.POSITIVE,
            confidence_score=0.95,
            logic_chain=[],
            key_factors=["Factor A"]
        )
        mock_predict.return_value = mock_trace
        
        response = client.post(
            "/reason/predict/twin-123",
            json={"topic": "Should I invest in AI?"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["final_stance"], "positive")
        self.assertEqual(data["confidence_score"], 0.95)
        
    @patch('modules.reasoning_engine.ReasoningEngine.predict_stance')
    @patch('modules.graph_context.get_graph_stats') # Patch the source since it's imported locally
    def test_chat_routing_to_reasoning(self, mock_stats, mock_predict):
        """Test that chat routes specific queries to reasoning engine."""
        mock_stats.return_value = {"has_graph": True, "node_count": 10}
        
        mock_trace = DecisionTrace(
            topic="test",
            final_stance=StanceType.NEGATIVE,
            confidence_score=0.8,
            logic_chain=[LogicStep(step_number=1, description="Reasoning...", nodes_involved=[], inference_type="deduction")],
            key_factors=["Risk"]
        )
        mock_predict.return_value = mock_trace
        
        # Test query that should trigger reasoning
        response = client.post(
            "/chat/twin-123",
            json={"query": "What is my stance on risk?", "conversation_id": "conv-123"}
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Parse SSE stream
        blocks = []
        for line in response.text.strip().split('\n'):
            if line:
                try:
                    blocks.append(json.loads(line))
                except:
                    pass
        
        # Verify metadata contains decision trace
        metadata = next((b for b in blocks if b.get("type") == "metadata"), None)
        self.assertIsNotNone(metadata)
        self.assertIn("decision_trace", metadata)
        self.assertEqual(metadata["decision_trace"]["final_stance"], "negative")

if __name__ == "__main__":
    unittest.main(verbosity=2)
