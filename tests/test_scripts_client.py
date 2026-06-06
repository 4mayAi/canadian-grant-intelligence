import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure scripts folder is on the python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from src.api.gemini_client import GeminiClient

class TestScriptsClient(unittest.TestCase):

    @patch('time.sleep')
    @patch('requests.post')
    def test_cascading_retries_and_zero_delay_pivoting(self, mock_post, mock_sleep):
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
        
        client = GeminiClient()
        client.api_key = "mock-key"
        # Override models to make testing simple
        client.fallback_models = ["model-1", "model-2"]
        
        payload = {"contents": [{"parts": [{"text": "hello"}]}]}
        res = client._retry_request(payload)
        
        self.assertIsNotNone(res)
        self.assertEqual(mock_post.call_count, 2)
        self.assertIn("model-1", mock_post.call_args_list[0][0][0])
        self.assertIn("model-2", mock_post.call_args_list[1][0][0])
        
        self.assertEqual(client.stats["requests_rate_limited"], 1)
        self.assertEqual(client.stats["model_fallbacks"], 1)
        self.assertEqual(client.stats["requests_success"], 1)
        self.assertEqual(len(client.blacklisted_models), 0)

    @patch('time.sleep')
    @patch('requests.post')
    def test_daily_quota_exhaustion_blacklisting(self, mock_post, mock_sleep):
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
        
        client = GeminiClient()
        client.api_key = "mock-key"
        client.fallback_models = ["model-1", "model-2"]
        
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
        from src.api.gemini_client import clean_json_text
        import json
        raw_json_with_newlines = '{\n  "key": "line1\nline2",\n  "tab": "val1\tval2"\n}'
        cleaned = clean_json_text(raw_json_with_newlines)
        self.assertIn("line1\\nline2", cleaned)
        self.assertIn("val1\\tval2", cleaned)
        parsed = json.loads(cleaned)
        self.assertEqual(parsed["key"], "line1\nline2")
        self.assertEqual(parsed["tab"], "val1\tval2")

if __name__ == "__main__":
    unittest.main()
