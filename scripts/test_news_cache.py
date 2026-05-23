import sys
import os
from datetime import datetime, timedelta
import unittest
from unittest.mock import MagicMock, patch

# Add scripts directory to sys.path to resolve src.*
scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from src.extractors.rss import fetch_rss_feeds
from src.main import fetch_and_process_news

# A mock class for Gemini insights output
class MockInsightModel:
    def __init__(self, summary="Mock summary", tags=None, linkedin_hook="Mock linkedin"):
        self.summary = summary
        self.tags = tags or ["mock"]
        self.linkedin_hook = linkedin_hook
        
    def to_dict(self):
        return {
            "summary": self.summary,
            "tags": self.tags,
            "linkedin_hook": self.linkedin_hook
        }

class TestNewsCache(unittest.TestCase):
    def setUp(self):
        # Base datetime for testing
        self.now = datetime(2026, 5, 23, 12, 0, 0)
        self.lookback_limit = self.now - timedelta(days=7)
        
        # Corrupted state with 5 items (mix of valid, garbage, and old)
        self.mock_pmo_insights = {
            "generated_at": "2026-05-22T19:57:00Z",
            "insights": [
                {
                    "source": "PMO_News",
                    "title": "PMO Active Article",
                    "link": "https://www.pm.gc.ca/en/news-releases/active-1",
                    "date": "2026-05-20T10:00:00Z",
                    "insight": {"summary": "Insight 1", "tags": ["a"], "linkedin_hook": "Hook 1"}
                },
                {
                    "source": "PMO_News",
                    "title": "PMO Garbage/Footer Article",
                    "link": "https://www.pm.gc.ca/en/news-releases/garbage-footer",
                    "date": "2026-05-20T10:00:00Z",
                    "insight": {"summary": "Garbage", "tags": ["garbage"], "linkedin_hook": "Garbage"}
                },
                {
                    "source": "PMO_News",
                    "title": "PMO Historical Article 2024",
                    "link": "https://www.pm.gc.ca/en/news-releases/historical-2024",
                    "date": "2024-05-20T10:00:00Z",
                    "insight": {"summary": "Historical", "tags": ["old"], "linkedin_hook": "Old"}
                },
                {
                    "source": "ISED_News",
                    "title": "ISED Active Article",
                    "link": "https://ised-isde.canada.ca/active-ised",
                    "date": "2026-05-21T10:00:00Z",
                    "insight": {"summary": "ISED Insight", "tags": ["ised"], "linkedin_hook": "ISED Hook"}
                },
                {
                    "source": "Finance_Canada",
                    "title": "Finance Active Article",
                    "link": "https://canada.ca/finance-active",
                    "date": "2026-05-22T10:00:00Z",
                    "insight": {"summary": "Finance Insight", "tags": ["finance"], "linkedin_hook": "Finance Hook"}
                }
            ]
        }
        
    @patch("src.main.azure_client")
    @patch("src.main.gemini_client")
    @patch("src.main.fetch_rss_feeds")
    def test_cache_hits_and_pruning(self, mock_fetch, mock_gemini, mock_azure):
        # 1. Setup mocks
        mock_azure.download_json.return_value = self.mock_pmo_insights
        
        # Mock RSS feeds returns:
        # - PMO Active Article (exists in cache)
        # - PMO Brand New Article (does not exist in cache)
        # - ISED Active Article (exists in cache)
        # Note: PMO Garbage/Footer and PMO Historical 2024 are NOT in the feed results!
        # Note: Finance Active Article is NOT in the feed results (it fell out of the feed/lookback)
        mock_fetch.return_value = [
            {
                "source": "PMO_News",
                "title": "PMO Active Article",
                "link": "https://www.pm.gc.ca/en/news-releases/active-1",
                "date": datetime(2026, 5, 20, 10, 0, 0),
                "text_to_search": "pmo active article summary"
            },
            {
                "source": "PMO_News",
                "title": "PMO Brand New Article",
                "link": "https://www.pm.gc.ca/en/news-releases/brand-new",
                "date": datetime(2026, 5, 23, 10, 0, 0),
                "text_to_search": "pmo brand new article summary"
            },
            {
                "source": "ISED_News",
                "title": "ISED Active Article",
                "link": "https://ised-isde.canada.ca/active-ised",
                "date": datetime(2026, 5, 21, 10, 0, 0),
                "text_to_search": "ised active article summary"
            }
        ]
        
        # Mock Gemini to return insight for the brand new article
        mock_gemini.get_gemini_insights_batch.return_value = [
            MockInsightModel(summary="Insight Brand New", tags=["new"], linkedin_hook="Hook New")
        ]
        
        processed_urls = set()
        
        # 2. Run logic
        result = fetch_and_process_news(self.lookback_limit, 15, processed_urls, test_mode=False)
        
        # 3. Assertions
        # Total active output should be exactly 3 articles:
        # - PMO Brand New Article (newly processed)
        # - ISED Active Article (cached)
        # - PMO Active Article (cached)
        # Garbage, Historical 2024, and Finance Active Article should be pruned.
        self.assertEqual(len(result), 3)
        
        # Check sorting order (date desc):
        # 1. Brand New (2026-05-23)
        # 2. ISED Active (2026-05-21)
        # 3. PMO Active (2026-05-20)
        self.assertEqual(result[0]["title"], "PMO Brand New Article")
        self.assertEqual(result[1]["title"], "ISED Active Article")
        self.assertEqual(result[2]["title"], "PMO Active Article")
        
        # Check cached contents are preserved
        self.assertEqual(result[1]["insight"]["summary"], "ISED Insight")
        self.assertEqual(result[2]["insight"]["summary"], "Insight 1")
        # Check new content is populated
        self.assertEqual(result[0]["insight"]["summary"], "Insight Brand New")
        
        # Verify LLM was only called once for the brand new article
        mock_gemini.get_gemini_insights_batch.assert_called_once()
        called_args = mock_gemini.get_gemini_insights_batch.call_args[0][0]
        self.assertEqual(len(called_args), 1)
        self.assertIn("Title: PMO Brand New Article", called_args[0])
        
        # Check processed_urls updated
        self.assertIn("https://www.pm.gc.ca/en/news-releases/active-1", processed_urls)
        self.assertIn("https://www.pm.gc.ca/en/news-releases/brand-new", processed_urls)
        self.assertIn("https://ised-isde.canada.ca/active-ised", processed_urls)
        # Pruned articles should not be in processed_urls
        self.assertNotIn("https://www.pm.gc.ca/en/news-releases/garbage-footer", processed_urls)
        
    @patch("src.main.azure_client")
    @patch("src.main.gemini_client")
    @patch("src.main.fetch_rss_feeds")
    def test_feed_failure_resilience(self, mock_fetch, mock_gemini, mock_azure):
        # 1. Setup mocks
        mock_azure.download_json.return_value = self.mock_pmo_insights
        
        # Mock fetch_rss_feeds to simulate:
        # - PMO feed is fetched successfully with 1 entry.
        # - ISED_News feed and Finance_Canada feed failed (returned via failed_feeds list).
        def side_effect_fetch(lookback_limit, max_items_per_feed, failed_feeds):
            failed_feeds.append("ISED_News")
            failed_feeds.append("Finance_Canada")
            return [
                {
                    "source": "PMO_News",
                    "title": "PMO Active Article",
                    "link": "https://www.pm.gc.ca/en/news-releases/active-1",
                    "date": datetime(2026, 5, 20, 10, 0, 0),
                    "text_to_search": "pmo active article summary"
                }
            ]
            
        mock_fetch.side_effect = side_effect_fetch
        
        processed_urls = set()
        
        # 2. Run logic
        result = fetch_and_process_news(self.lookback_limit, 15, processed_urls, test_mode=False)
        
        # 3. Assertions
        # - PMO_News succeeded: PMO Active Article is kept, but PMO Garbage and PMO Historical 2024 are PRUNED.
        # - ISED_News failed: ISED Active Article is RETAINED.
        # - Finance_Canada failed: Finance Active Article is RETAINED.
        # Total output should contain:
        # - PMO Active Article
        # - ISED Active Article
        # - Finance Active Article
        # Total count = 3
        self.assertEqual(len(result), 3)
        
        titles = {item["title"] for item in result}
        self.assertIn("PMO Active Article", titles)
        self.assertIn("ISED Active Article", titles)
        self.assertIn("Finance Active Article", titles)
        self.assertNotIn("PMO Garbage/Footer Article", titles)
        self.assertNotIn("PMO Historical Article 2024", titles)
        
        # No new articles should have been sent to Gemini
        mock_gemini.get_gemini_insights_batch.assert_not_called()

if __name__ == "__main__":
    unittest.main()
