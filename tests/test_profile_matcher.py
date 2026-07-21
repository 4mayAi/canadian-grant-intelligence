import os
import sys
import unittest
from unittest.mock import MagicMock

# Resolve project root dynamically
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from generic_engine.api.profile_matcher import ProfileMatcher

class TestProfileMatcher(unittest.TestCase):
    def setUp(self):
        self.mock_azure = MagicMock()
        self.mock_gemini = MagicMock()
        self.mock_notifier = MagicMock()
        self.matcher = ProfileMatcher(
            azure_client=self.mock_azure,
            gemini_client=self.mock_gemini,
            notifier=self.mock_notifier
        )

        self.mock_profile = {
            "subscriber_id": "mayai_test",
            "name": "Mayai Test",
            "email": "rutlimeadows@gmail.com",
            "keywords": ["database", "spreadsheet", "analytics"],
            "capabilities": "Development of database-spreadsheet hybrids.",
            "target_organizations": ["Shared Services Canada"]
        }

    def test_local_keyword_pre_filtering(self):
        matching_tender = {
            "title": "Cloud based spreadsheet database hybrid",
            "description": "Purchase of software for CRA",
            "organization": "Shared Services Canada"
        }
        non_matching_tender = {
            "title": "Janitorial Services for Agassiz",
            "description": "Cleaning services for building",
            "organization": "Agriculture Canada"
        }

        self.assertTrue(self.matcher._tender_matches_keywords(matching_tender, self.mock_profile["keywords"]))
        self.assertFalse(self.matcher._tender_matches_keywords(non_matching_tender, self.mock_profile["keywords"]))

    def test_short_acronym_word_boundary_filtering(self):
        # Short keyword <= 4 chars like 'rfp' or 'sme'
        tender_with_acronym = {
            "title": "RFP for cloud services",
            "description": "Notice",
            "organization": "SSC"
        }
        tender_with_embedded = {
            "title": "Performance analysis",  # 'sme' is inside performance, should NOT match if kw is 'sme'
            "description": "Notice",
            "organization": "SSC"
        }

        self.assertTrue(self.matcher._tender_matches_keywords(tender_with_acronym, ["RFP"]))
        self.assertFalse(self.matcher._tender_matches_keywords(tender_with_embedded, ["sme"]))

    def test_process_tenders_high_fit_dispatches_email(self):
        matching_tender = {
            "title": "Cloud based spreadsheet database hybrid",
            "solicitation_number": "BPM026194",
            "organization": "Shared Services Canada",
            "link": "https://canadabuys.canada.ca/en/tender-opportunities?search_api_fulltext=BPM026194",
            "closing_date": "2026-07-29T00:00:00Z",
            "description": "Database hybrid requirement"
        }

        self.mock_gemini.evaluate_subscriber_fit.return_value = {
            "fit_score": 92,
            "fit_reasoning": "Direct match for spreadsheet hybrid capabilities.",
            "custom_pitch": "Dear Procurement Officer,\n\nParagraph 1...\nParagraph 2...\nParagraph 3...\nParagraph 4..."
        }

        results = self.matcher.process_tenders(
            tenders=[matching_tender],
            profiles=[self.mock_profile],
            dry_run=False
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["fit_score"], 92)
        self.mock_notifier.send_digest.assert_called_once()
        self.assertEqual(self.mock_azure.upload_json.call_count, 2)

    def test_process_tenders_dry_run_suppresses_email_and_azure_audit(self):
        matching_tender = {
            "title": "Cloud based spreadsheet database hybrid",
            "solicitation_number": "BPM026194",
            "organization": "Shared Services Canada",
            "description": "Database hybrid requirement"
        }

        self.mock_gemini.evaluate_subscriber_fit.return_value = {
            "fit_score": 95,
            "fit_reasoning": "Direct match.",
            "custom_pitch": "Pitch text"
        }

        results = self.matcher.process_tenders(
            tenders=[matching_tender],
            profiles=[self.mock_profile],
            dry_run=True  # DRY RUN
        )

        self.assertEqual(len(results), 1)
        self.mock_notifier.send_digest.assert_not_called()
        self.mock_azure.upload_json.assert_not_called()

    def test_process_tenders_sent_alerts_deduplication(self):
        """Verify that already-alerted tenders are skipped and do not trigger LLM calls or duplicate emails."""
        matching_tender = {
            "title": "Cloud based spreadsheet database hybrid",
            "solicitation_number": "BPM026194",
            "organization": "Shared Services Canada",
            "link": "https://canadabuys.canada.ca/en/tender-opportunities?search_api_fulltext=BPM026194",
            "description": "Database hybrid requirement"
        }

        # Mock sent_lead_alerts.json returning BPM026194 as already sent to mayai_test
        self.mock_azure.download_json.return_value = {
            "mayai_test": {
                "BPM026194": "2026-07-21T00:00:00Z"
            }
        }

        results = self.matcher.process_tenders(
            tenders=[matching_tender],
            profiles=[self.mock_profile],
            dry_run=False
        )

        # Gemini fit evaluation and notifier should NOT be called at all
        self.assertEqual(len(results), 0)
        self.mock_gemini.evaluate_subscriber_fit.assert_not_called()
        self.mock_notifier.send_digest.assert_not_called()

if __name__ == "__main__":
    unittest.main()
