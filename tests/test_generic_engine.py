import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json
from datetime import datetime

# Ensure generic_engine folder is on the python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'generic_engine')))

from api.gemini_client import GeminiClient
from models import GeminiInsight
import main

class TestGenericEngine(unittest.TestCase):

    def setUp(self):
        self.gemini_client = GeminiClient(
            primary_model="gemini-1.5-pro",
            fallback_models=["gemini-1.5-flash"],
            system_instruction="system instruction"
        )

    @patch('api.gemini_client.GeminiClient._retry_request')
    def test_batch_insight_prompt_contains_factual_constraint(self, mock_retry):
        # Verify that get_gemini_insights_batch prompt contains the strict instructions
        mock_retry.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps([
                            {
                                "linkedin_hook": "Hook 1",
                                "strategic_value": "Value 1",
                                "co_bidding_opportunity": "Co-bid 1"
                            }
                        ])
                    }]
                }
            }]
        }
        self.gemini_client.get_gemini_insights_batch(["Test article body text"])
        
        # Check that the prompt contains the expected text
        mock_retry.assert_called_once()
        payload = mock_retry.call_args[0][0]
        prompt_text = payload["contents"][0]["parts"][0]["text"]
        
        self.assertIn("Based ONLY on facts stated in the source text, identify consortium or partnership opportunities", prompt_text)
        self.assertIn("Do NOT invent technologies, programs, or partner types not mentioned in the input", prompt_text)

    @patch('api.gemini_client.GeminiClient._retry_request')
    def test_batch_insight_prompt_contains_current_date(self, mock_retry):
        mock_retry.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps([
                            {
                                "linkedin_hook": "Hook 1",
                                "strategic_value": "Value 1",
                                "co_bidding_opportunity": "Co-bid 1"
                            }
                        ])
                    }]
                }
            }]
        }
        self.gemini_client.get_gemini_insights_batch(["Test article body text"], current_date="June 18, 2026")
        
        mock_retry.assert_called_once()
        payload = mock_retry.call_args[0][0]
        prompt_text = payload["contents"][0]["parts"][0]["text"]
        
        self.assertIn("Today's Date: June 18, 2026", prompt_text)

    @patch('api.gemini_client.GeminiClient._retry_request')
    def test_generate_linkedin_post_accepts_date_and_factual_rigor(self, mock_retry):
        # Mock successful JSON response
        mock_retry.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "suggested_title": "Suggested Title",
                            "article_content": "Suggested Content"
                        })
                    }]
                }
            }]
        }
        
        current_date_str = "June 05, 2026"
        res = self.gemini_client.generate_linkedin_post("Highlights summaries text", current_date=current_date_str)
        
        self.assertIsNotNone(res)
        self.assertEqual(res["suggested_title"], "Suggested Title")
        self.assertEqual(res["article_content"], "Suggested Content")
        
        # Check that prompt has date and factual rules
        mock_retry.assert_called_once()
        payload = mock_retry.call_args[0][0]
        prompt_text = payload["contents"][0]["parts"][0]["text"]
        
        self.assertIn("Today's Date: June 05, 2026", prompt_text)
        self.assertIn("Factual Rigor", prompt_text)
        self.assertIn("Only reference names, figures, and timeframes explicitly mentioned in the context below", prompt_text)
        self.assertIn("Do not fabricate hashtags for organizations not mentioned", prompt_text)
        self.assertIn("https://4mayAi.github.io/canadian-grant-intelligence/clusters/", prompt_text)

    @patch('main.load_and_validate_config')
    @patch('main.AzureClient')
    @patch('main.fetch_and_process_news')
    @patch('main.generate_dashboard_kpis')
    @patch('main.validate_dynamic_outputs')
    @patch('main.Notifier')
    @patch('main.os.path.exists', return_value=False)
    @patch('main.open', new_callable=mock_open)
    def test_run_engine_pipeline_enriched_summaries(self, mock_file, mock_exists, mock_notifier_cls, 
                                                    mock_validate, mock_kpis, mock_fetch, mock_azure_cls, mock_load_config):
        # Setup mock configuration
        mock_config = MagicMock()
        mock_config.topic_id = "innovation-clusters"
        mock_config.display_name = "Innovation Clusters"
        mock_config.dashboard_url = "https://example.com/dashboard"
        mock_config.storage.azure_container = "test-container"
        mock_config.storage.insights_file = "insights.json"
        mock_config.storage.kpis_file = "kpis.json"
        mock_config.storage.processed_urls_file = "processed.json"
        mock_config.llm_settings.model_primary = "gemini-1.5-pro"
        mock_config.llm_settings.model_fallbacks = ["gemini-1.5-flash"]
        mock_config.llm_settings.system_instruction = "System prompt"
        mock_config.distribution.discord_webhook = None
        mock_config.skill_version = "1.0.0"
        mock_config.schema_version = "1.0.0"
        mock_load_config.return_value = mock_config

        # Mock AzureClient instance
        mock_azure = mock_azure_cls.return_value
        mock_azure.download_json.return_value = {}

        # Setup mock processed insights
        mock_insights = [
            {
                "source": "OSC_News",
                "title": "Supercluster Announces Funding",
                "link": "https://example.com/news1",
                "date": "2026-06-05T00:00:00Z",
                "insight": {
                    "linkedin_hook": "Scroll stopper emoji",
                    "strategic_value": "- Points 1\n- Points 2",
                    "co_bidding_opportunity": "Partnership text"
                }
            }
        ]
        mock_fetch.return_value = mock_insights
        mock_kpis.return_value = {"hero_hook": "Hook"}

        # Patch GeminiClient generate_linkedin_post to verify input
        with patch('main.GeminiClient') as mock_gemini_cls:
            mock_gemini = mock_gemini_cls.return_value
            mock_gemini.get_stats.return_value = {}
            mock_gemini.get_hero_hook.return_value = "Mock Hero Hook"
            mock_gemini.generate_linkedin_post.return_value = {
                "suggested_title": "Test Title",
                "article_content": "Test post content"
            }
            
            # Execute pipeline (dry_run=True)
            main.run_engine_pipeline(config_path="mock_config.json", dry_run=True)

            # Assert generate_linkedin_post was called with enriched summaries_str containing strategic_value
            mock_gemini.generate_linkedin_post.assert_called_once()
            called_args, called_kwargs = mock_gemini.generate_linkedin_post.call_args
            
            summaries_arg = called_args[0]
            self.assertIn("Supercluster Announces Funding", summaries_arg)
            self.assertIn("Scroll stopper emoji", summaries_arg)
            self.assertIn("- Points 1", summaries_arg)
            self.assertIn("- Points 2", summaries_arg)
            
            self.assertIn("current_date", called_kwargs)
            self.assertEqual(called_kwargs["current_date"], datetime.utcnow().strftime("%B %d, %Y"))

    @patch('time.sleep')
    @patch('requests.post')
    def test_cascading_retries_and_zero_delay_pivoting(self, mock_post, mock_sleep):
        # Set up responses:
        # First call: primary_model "gemini-1.5-pro" gets 429 RPM rate limit.
        # Second call: fallback_model "gemini-1.5-flash" gets 200 Success.
        mock_resp_rate_limit = MagicMock()
        mock_resp_rate_limit.status_code = 429
        mock_resp_rate_limit.text = '{"error": {"message": "Resource has been exhausted (e.g. queries per minute)."}}'
        
        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_resp_success.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"result": "success"}'}]
                }
            }]
        }
        
        mock_post.side_effect = [mock_resp_rate_limit, mock_resp_success]
        
        client = GeminiClient(
            primary_model="model-1",
            fallback_models=["model-2"],
            system_instruction="system instruction"
        )
        client.api_key = "mock-key"
        
        payload = {"contents": [{"parts": [{"text": "hello"}]}]}
        res = client._retry_request(payload)
        
        self.assertIsNotNone(res)
        self.assertEqual(mock_post.call_count, 2)
        args_first = mock_post.call_args_list[0][0][0]
        args_second = mock_post.call_args_list[1][0][0]
        self.assertIn("model-1", args_first)
        self.assertIn("model-2", args_second)
        
        self.assertEqual(client.stats["requests_rate_limited"], 1)
        self.assertEqual(client.stats["model_fallbacks"], 1)
        self.assertEqual(client.stats["requests_success"], 1)
        self.assertEqual(len(client.blacklisted_models), 0)

    @patch('time.sleep')
    @patch('requests.post')
    def test_daily_quota_exhaustion_blacklisting(self, mock_post, mock_sleep):
        # First call: model-1 returns 429 daily quota exhausted.
        # Second call: model-2 returns 200 success.
        # Third call: model-1 is bypassed, only model-2 is tried.
        mock_resp_daily_limit = MagicMock()
        mock_resp_daily_limit.status_code = 429
        mock_resp_daily_limit.text = '{"error": {"message": "GenerateContent request limit exceeded"}}'
        
        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_resp_success.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"result": "success"}'}]
                }
            }]
        }
        
        mock_post.side_effect = [mock_resp_daily_limit, mock_resp_success, mock_resp_success]
        
        client = GeminiClient(
            primary_model="model-1",
            fallback_models=["model-2"],
            system_instruction="system instruction"
        )
        client.api_key = "mock-key"
        
        payload = {"contents": [{"parts": [{"text": "hello"}]}]}
        res1 = client._retry_request(payload)
        
        self.assertIsNotNone(res1)
        self.assertEqual(mock_post.call_count, 2)
        self.assertIn("model-1", mock_post.call_args_list[0][0][0])
        self.assertIn("model-2", mock_post.call_args_list[1][0][0])
        self.assertIn("model-1", client.blacklisted_models)
        
        res2 = client._retry_request(payload)
        self.assertIsNotNone(res2)
        self.assertEqual(mock_post.call_count, 3)
        self.assertIn("model-2", mock_post.call_args_list[2][0][0])

    def test_clean_json_text_literal_newlines_and_tabs(self):
        from api.gemini_client import clean_json_text
        raw_json_with_newlines = '{\n  "key": "line1\nline2",\n  "tab": "val1\tval2"\n}'
        cleaned = clean_json_text(raw_json_with_newlines)
        self.assertIn("line1\\nline2", cleaned)
        self.assertIn("val1\\tval2", cleaned)
        parsed = json.loads(cleaned)
        self.assertEqual(parsed["key"], "line1\nline2")
        self.assertEqual(parsed["tab"], "val1\tval2")

if __name__ == "__main__":
    unittest.main()
