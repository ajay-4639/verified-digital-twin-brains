# backend/tests/test_media_integration.py
"""Integration tests for Phase 5 Media endpoints.

Tests:
- POST /ingest/youtube/{twin_id}
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

# Mock ingestion
sys.modules["modules.ingestion"] = MagicMock()
sys.modules["modules.ingestion"].process_and_index_text = AsyncMock(return_value=10)

from main import app
from modules.auth_guard import get_current_user

client = TestClient(app)

class TestMediaIntegration(unittest.TestCase):
    
    def setUp(self):
        # Override Auth Dependency
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user", "tenant_id": "test-tenant"}
    
    def tearDown(self):
        app.dependency_overrides = {}

    @patch('routers.enhanced_ingestion.verify_twin_ownership')
    @patch('modules.media_ingestion.MediaIngester.ingest_youtube_video', new_callable=AsyncMock)
    def test_youtube_endpoint(self, mock_ingest, mock_auth):
        """Test POST /ingest/youtube/{twin_id}"""
        # Mock auth to always succeed
        mock_auth.return_value = True
        mock_ingest.return_value = {
            "success": True,
            "source_id": "src-123",
            "chunks": 10
        }
        
        response = client.post(
            "/ingest/youtube/twin-123",
            json={"url": "http://youtube.com/watch?v=realvideo"}
        )
        
        if response.status_code != 200:
            print(f"FAIL BODY: {response.text}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)
        self.assertEqual(response.json()["chunks"], 10)
        
        # Verify call
        mock_ingest.assert_called_with("http://youtube.com/watch?v=realvideo")

if __name__ == "__main__":
    unittest.main(verbosity=2)
