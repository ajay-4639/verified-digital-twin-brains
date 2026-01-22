# backend/tests/test_media_ingestion.py
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

class TestMediaIngestion(unittest.TestCase):
    
    def setUp(self):
        # Patch sys.modules to mock dependencies
        self.modules_patcher = patch.dict(sys.modules, {
            "modules.observability": MagicMock(),
            "modules.ingestion": MagicMock(),
            "modules.auth_guard": MagicMock(),  # Mock auth guard here safely
        })
        self.modules_patcher.start()
        
        # Mock specific attributes
        sys.modules["modules.observability"].supabase = MagicMock()
        sys.modules["modules.ingestion"].process_and_index_text = AsyncMock(return_value=5)
        
        # Import module under test (inside setup to use mocked modules)
        if "modules.media_ingestion" in sys.modules:
            del sys.modules["modules.media_ingestion"]
        from modules.media_ingestion import MediaIngester
        self.MediaIngester = MediaIngester

    def tearDown(self):
        self.modules_patcher.stop()

    @patch('modules.media_ingestion.yt_dlp.YoutubeDL')
    async def test_ingest_youtube_success(self, mock_ytdl):
        """Test full youtube ingestion flow with mocks."""
        # Setup mocks
        mock_ytdl.return_value.__enter__.return_value.extract_info.return_value = {}
        mock_ytdl.return_value.__enter__.return_value.prepare_filename.return_value = "video.webm"
        
        # We need to rely on the class imported in setUp
        MediaIngester = self.MediaIngester
        
        # Patch methods on the class
        with patch.object(MediaIngester, '_download_audio', return_value="fake.mp3"), \
             patch.object(MediaIngester, '_transcribe_audio', return_value="Raw transcript"), \
             patch.object(MediaIngester, '_diarize_and_process', return_value="Diarized content"):
            
            ingester = MediaIngester("twin-123")
            result = await ingester.ingest_youtube_video("http://youtube.com/watch?v=123")
            
            self.assertTrue(result["success"])
            self.assertEqual(result["chunks"], 5)

    @patch('modules.media_ingestion.get_openai_client')
    async def test_diarization_logic(self, mock_client):
        """Test that diarization calls the LLM correctly."""
        MediaIngester = self.MediaIngester
        ingester = MediaIngester("twin-123")
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Diarized text"
        mock_client.return_value.chat.completions.create.return_value = mock_response
        
        result = await ingester._diarize_and_process("Full raw text")
        
        self.assertEqual(result, "Diarized text")


if __name__ == "__main__":
    unittest.main(verbosity=2)
