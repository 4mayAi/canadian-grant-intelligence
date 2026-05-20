import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import sys

# Ensure scripts folder is on the python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from validate_outputs import validate_outputs_func
from src.api.notifier import Notifier
from src.api.mail_sender import MailSender


class TestPipelineAndDashboard(unittest.TestCase):

    def setUp(self):
        self.mock_tenders = [
            {
                "type": "New",
                "title": "Test Grant Opportunity",
                "description": "This is a **test** opportunity",
                "link": "https://example.com/grant",
                "closing_date": "2026-06-01T00:00:00Z",
                "publication_date": "2026-05-20T00:00:00Z",
                "province": "National",
                "province_abbrev": "NAT",
                "category": "services"
            }
        ]
        self.mock_kpis = {
            "total_active": 1,
            "new_today": 1,
            "closing_this_week": 0,
            "top_category": "Services",
            "hero_hook": "Golden opportunity detected!",
            "generated_at": "2026-05-20T18:00:00Z"
        }
        self.mock_pmo = {
            "generated_at": "2026-05-20T18:00:00Z",
            "linkedin_post": "Hello linkedin!",
            "insights": [
                {
                    "source": "PMO",
                    "title": "PMO Insight Title",
                    "link": "https://example.com/pmo",
                    "date": "2026-05-20",
                    "insight": {
                        "linkedin_hook": "Hook text",
                        "strategic_value": "Value text",
                        "co_bidding_opportunity": "Co-bidding text"
                    }
                }
            ]
        }

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_validation_passes_valid_data(self, mock_file_open, mock_exists):
        """Verify that output validation succeeds with perfect inputs matching schema."""
        # Order in validate_outputs.py: kpis_file, tenders_file, pmo_file
        file_contents = [
            json.dumps(self.mock_kpis),
            json.dumps(self.mock_tenders),
            json.dumps(self.mock_pmo)
        ]
        mock_file_open.side_effect = [
            mock_open(read_data=content).return_value for content in file_contents
        ]

        try:
            validate_outputs_func("mock/path")
        except Exception as exc:
            self.fail(f"Validation unexpectedly failed: {exc}")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_validation_fails_missing_keys(self, mock_file_open, mock_exists):
        """Verify that validation flags incomplete schema records."""
        # Corrupt data by removing a required key
        corrupted_kpis = self.mock_kpis.copy()
        corrupted_kpis.pop("total_active")

        # Order: kpis_file, tenders_file, pmo_file
        file_contents = [
            json.dumps(corrupted_kpis),
            json.dumps(self.mock_tenders),
            json.dumps(self.mock_pmo)
        ]
        mock_file_open.side_effect = [
            mock_open(read_data=content).return_value for content in file_contents
        ]

        with self.assertRaises(Exception) as context:
            validate_outputs_func("mock/path")
        self.assertIn("kpis.json missing key: total_active", str(context.exception))

    @patch('src.api.notifier.requests.post')
    def test_discord_alert_success(self, mock_post):
        """Verify Discord Webhook dispatcher returns true on HTTP 204/200."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        notifier = Notifier()
        notifier.discord_url = "https://discord.com/api/webhooks/mock"
        
        result = notifier.send_discord_alert("Test alert message")
        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch('src.api.notifier.smtplib.SMTP_SSL')
    def test_email_alert_success(self, mock_smtp_ssl):
        """Verify fallback email alert logs into SMTP server and dispatches successfully."""
        mock_server = mock_smtp_ssl.return_value

        notifier = Notifier()
        notifier.alert_email = "admin@example.com"
        notifier.smtp_user = "sender@example.com"
        notifier.smtp_pass = "app_password"

        result = notifier.send_email_alert("Test Alert", "Alert message content")
        self.assertTrue(result)
        mock_server.login.assert_called_once_with("sender@example.com", "app_password")
        mock_server.sendmail.assert_called_once()

    @patch('src.api.mail_sender.azure_client.download_json')
    @patch('src.api.mail_sender.smtplib.SMTP_SSL')
    @patch('builtins.open', new_callable=mock_open, read_data="## Newsletter Title\nContent goes here")
    @patch('os.path.exists', return_value=False) # Skip attachment open by returning False for exists checks
    def test_mail_sender_dispatch(self, mock_exists, mock_file, mock_smtp_ssl, mock_download):
        """Verify MailSender downloads subscribers, converts markdown to HTML, and sends emails."""
        mock_download.return_value = ["sub1@example.com", "sub2@example.com"]
        mock_server = mock_smtp_ssl.return_value

        sender = MailSender()
        sender.smtp_user = "newsletter@example.com"
        sender.smtp_pass = "app_password"

        success = sender.send_daily_digest("mock/post.md", "mock/card.png")
        self.assertTrue(success)
        self.assertEqual(mock_server.sendmail.call_count, 2)


if __name__ == '__main__':
    unittest.main()
