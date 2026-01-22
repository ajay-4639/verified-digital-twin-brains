# backend/tests/test_enhanced_ingestion.py
"""Unit tests for Phase 2: Enhanced Ingestion modules.

Tests:
- web_crawler.py: URL validation, scraping, crawling
- social_ingestion.py: RSS, Twitter, LinkedIn parsing
- auto_updater.py: Pipeline CRUD, scheduling
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))


class TestWebCrawler(unittest.TestCase):
    """Test web_crawler.py functions."""
    
    def test_validate_url_valid(self):
        """Test URL validation with valid URLs."""
        from modules.web_crawler import validate_url
        
        self.assertTrue(validate_url("https://example.com"))
        self.assertTrue(validate_url("http://example.com/page"))
        self.assertTrue(validate_url("https://sub.domain.com/path?query=1"))
    
    def test_validate_url_invalid(self):
        """Test URL validation with invalid URLs."""
        from modules.web_crawler import validate_url
        
        self.assertFalse(validate_url(""))
        self.assertFalse(validate_url("not-a-url"))
        self.assertFalse(validate_url("ftp://invalid.com"))
        self.assertFalse(validate_url("javascript:alert(1)"))
    
    def test_extract_domain(self):
        """Test domain extraction."""
        from modules.web_crawler import extract_domain
        
        self.assertEqual(extract_domain("https://example.com/page"), "example.com")
        self.assertEqual(extract_domain("https://sub.example.com"), "sub.example.com")
        self.assertEqual(extract_domain("http://localhost:8000"), "localhost:8000")
    
    @patch('modules.web_crawler.get_firecrawl_client')
    def test_scrape_single_page_no_client(self, mock_client):
        """Test scraping when Firecrawl client is unavailable."""
        import asyncio
        from modules.web_crawler import scrape_single_page
        
        mock_client.return_value = None
        
        result = asyncio.run(scrape_single_page("https://example.com"))
        
        self.assertFalse(result.get("success"))
        self.assertIn("not available", result.get("error", "").lower())
    
    @patch('modules.web_crawler.get_firecrawl_client')
    def test_scrape_single_page_success(self, mock_client):
        """Test successful single page scrape."""
        import asyncio
        from modules.web_crawler import scrape_single_page
        
        # Mock Firecrawl response
        mock_firecrawl = MagicMock()
        mock_firecrawl.scrape_url.return_value = {
            "markdown": "# Test Content\n\nThis is test content.",
            "metadata": {
                "title": "Test Page",
                "description": "A test page",
                "sourceURL": "https://example.com"
            }
        }
        mock_client.return_value = mock_firecrawl
        
        result = asyncio.run(scrape_single_page("https://example.com"))
        
        self.assertTrue(result.get("success"))
        self.assertIn("Test Content", result.get("content", ""))
        self.assertEqual(result.get("metadata", {}).get("title"), "Test Page")


class TestSocialIngestion(unittest.TestCase):
    """Test social_ingestion.py functions."""
    
    def test_rss_fetch_invalid_feed(self):
        """Test RSS fetching with invalid feed."""
        import asyncio
        from modules.social_ingestion import RSSFetcher
        
        result = asyncio.run(RSSFetcher.fetch_feed("not-a-valid-url"))
        
        # Should return error or empty entries
        if result.get("success"):
            self.assertEqual(result.get("entry_count", 0), 0)
    
    @patch('feedparser.parse')
    def test_rss_fetch_valid_feed(self, mock_parse):
        """Test RSS fetching with mocked valid feed."""
        import asyncio
        from modules.social_ingestion import RSSFetcher
        
        # Mock feedparser response
        mock_entry = MagicMock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article"
        mock_entry.published = "2024-01-01"
        mock_entry.summary = "This is a test article summary."
        # Explicitly set content to empty list so logic falls back to summary
        mock_entry.content = []
        
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]
        mock_feed.feed.get = lambda x, d=None: "Test Blog" if x == "title" else d
        
        mock_parse.return_value = mock_feed
        
        result = asyncio.run(RSSFetcher.fetch_feed("https://example.com/feed.xml"))
        
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("entry_count"), 1)
        self.assertEqual(result.get("entries")[0]["title"], "Test Article")
    
    def test_twitter_username_extraction(self):
        """Test extracting Twitter username from URL."""
        import re
        
        test_cases = [
            ("https://twitter.com/elonmusk", "elonmusk"),
            ("https://x.com/elonmusk", "elonmusk"),
            ("https://twitter.com/username/status/123", "username"),
        ]
        
        for url, expected in test_cases:
            match = re.search(r'twitter\.com/(\w+)|x\.com/(\w+)', url)
            if match:
                username = match.group(1) or match.group(2)
                self.assertEqual(username, expected)


class TestAutoUpdater(unittest.TestCase):
    """Test auto_updater.py functions."""
    
    def test_pipeline_to_dict(self):
        """Test IngestionPipeline serialization."""
        from modules.auto_updater import IngestionPipeline, SourceType
        
        pipeline = IngestionPipeline(
            twin_id="test-twin-id",
            source_url="https://example.com",
            source_type=SourceType.WEBSITE,
            schedule_hours=12
        )
        
        data = pipeline.to_dict()
        
        self.assertEqual(data["twin_id"], "test-twin-id")
        self.assertEqual(data["source_url"], "https://example.com")
        self.assertEqual(data["source_type"], "website")
        self.assertEqual(data["schedule_hours"], 12)
        self.assertIsNotNone(data["id"])
    
    def test_pipeline_from_dict(self):
        """Test IngestionPipeline deserialization."""
        from modules.auto_updater import IngestionPipeline, PipelineStatus
        
        data = {
            "id": "test-pipeline-id",
            "twin_id": "test-twin-id",
            "source_url": "https://example.com",
            "source_type": "rss",
            "schedule_hours": 6,
            "crawl_depth": 1,
            "max_pages": 5,
            "status": "active",
            "last_run_at": None,
            "next_run_at": "2024-01-01T00:00:00",
            "run_count": 3,
            "error_count": 1,
            "last_error": None,
            "metadata": {}
        }
        
        pipeline = IngestionPipeline.from_dict(data)
        
        self.assertEqual(pipeline.id, "test-pipeline-id")
        self.assertEqual(pipeline.schedule_hours, 6)
        self.assertEqual(pipeline.run_count, 3)
        self.assertEqual(pipeline.status, PipelineStatus.ACTIVE)
    
    def test_source_type_enum(self):
        """Test SourceType enum values."""
        from modules.auto_updater import SourceType
        
        self.assertEqual(SourceType.WEBSITE.value, "website")
        self.assertEqual(SourceType.RSS.value, "rss")
        self.assertEqual(SourceType.TWITTER.value, "twitter")
        self.assertEqual(SourceType.LINKEDIN.value, "linkedin")
        self.assertEqual(SourceType.YOUTUBE.value, "youtube")


class TestEnhancedIngestionRouter(unittest.TestCase):
    """Test enhanced_ingestion.py router models."""
    
    def test_request_models(self):
        """Test Pydantic request model validation."""
        from routers.enhanced_ingestion import (
            WebsiteCrawlRequest,
            RSSIngestRequest,
            TwitterIngestRequest,
            PipelineCreateRequest
        )
        
        # Valid requests should not raise
        website = WebsiteCrawlRequest(url="https://example.com")
        self.assertEqual(website.max_pages, 10)  # Default
        self.assertEqual(website.max_depth, 2)  # Default
        
        rss = RSSIngestRequest(url="https://example.com/feed.xml")
        self.assertEqual(rss.max_entries, 10)  # Default
        
        twitter = TwitterIngestRequest(username="testuser")
        self.assertEqual(twitter.tweet_count, 20)  # Default
        
        pipeline = PipelineCreateRequest(
            source_url="https://example.com",
            source_type="website"
        )
        self.assertEqual(pipeline.schedule_hours, 24)  # Default


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
