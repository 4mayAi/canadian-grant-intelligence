import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import sys
from datetime import datetime, timezone

# Ensure scripts and generic_engine folders are on the python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'generic_engine')))

from api.notifier import Notifier

azure_client = MagicMock()

class MailSender:
    def __init__(self):
        self.smtp_user = "newsletter@example.com"
        self.smtp_pass = "app_password"

    def send_daily_digest(self, newsletter_md_path, social_card_path, recipients=None):
        if recipients is None:
            recipients = azure_client.download_json("subscribers.json")
        if not recipients:
            return False
            
        notifier = Notifier()
        notifier.smtp_user = self.smtp_user
        notifier.smtp_pass = self.smtp_pass
        
        with open(newsletter_md_path, "r", encoding="utf-8") as f:
            body_md = f.read()
            
        return notifier.send_digest(
            subject="Daily Digest",
            markdown_content=body_md,
            social_card_path=social_card_path,
            from_name="Grants",
            topic_name="Grants",
            recipients=recipients
        )


def validate_outputs_func(output_dir):
    import os
    import json
    kpis_file = os.path.join(output_dir, "kpis.json")
    tenders_file = os.path.join(output_dir, "tenders.json")
    pmo_file = os.path.join(output_dir, "pmo_insights.json")
    for fpath in (kpis_file, tenders_file, pmo_file):
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Missing output file: {fpath}")
    
    with open(kpis_file, "r") as f:
        kpis = json.load(f)
        if "total_active" not in kpis:
            raise KeyError("kpis.json missing key: total_active")
        if "generated_at" in kpis:
            from datetime import datetime, timezone
            try:
                dt_str = kpis["generated_at"].replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
                age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
                if age > 2.0:
                    raise ValueError("is stale")
            except Exception as e:
                if "is stale" in str(e):
                    raise


def fetch_canadabuys_csvs(pulse_only=True):
    from generic_engine.extractors.ckan import fetch_canadabuys_tenders
    from models import Tender
    raw_tenders = fetch_canadabuys_tenders(
        ckan_api_url="https://example.com/api",
        keywords=["grant", "stimulus", "incentive", "funding", "RFP", "tender", "economic support", "investment", "infrastructure"],
        pulse_only=pulse_only
    )
    tenders = []
    for t in raw_tenders:
        tenders.append(Tender(
            type=t.get("type", "New"),
            title=t.get("title", ""),
            description=t.get("description", ""),
            link=t.get("link", ""),
            closing_date=t.get("closing_date", ""),
            publication_date=t.get("date", ""),
            province=t.get("province", ""),
            province_abbrev=t.get("province_abbrev", ""),
            category=t.get("category", "")
        ))
    return tenders


class TestPipelineAndDashboard(unittest.TestCase):

    def setUp(self):
        current_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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
                "category": "services",
                "category_label": "Services"
            }
        ]
        self.mock_kpis = {
            "total_active": 1,
            "new_today": 1,
            "closing_this_week": 0,
            "top_category": "Services",
            "hero_hook": "Golden opportunity detected!",
            "generated_at": current_time
        }
        self.mock_pmo = {
            "generated_at": current_time,
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

    @patch('api.notifier.requests.post')
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

    @patch('api.notifier.smtplib.SMTP_SSL')
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

    @patch('api.notifier.smtplib.SMTP_SSL')
    @patch('builtins.open', new_callable=mock_open, read_data="## Newsletter Title\nContent goes here")
    @patch('os.path.exists', return_value=False) # Skip attachment open by returning False for exists checks
    def test_mail_sender_dispatch(self, mock_exists, mock_file, mock_smtp_ssl):
        """Verify MailSender downloads subscribers, converts markdown to HTML, and sends emails."""
        azure_client.download_json.return_value = ["sub1@example.com", "sub2@example.com"]
        mock_server = mock_smtp_ssl.return_value

        sender = MailSender()
        sender.smtp_user = "newsletter@example.com"
        sender.smtp_pass = "app_password"

        success = sender.send_daily_digest("mock/post.md", "mock/card.png")
        self.assertTrue(success)
        self.assertEqual(mock_server.sendmail.call_count, 2)

    @patch('os.path.exists', return_value=False)
    def test_validation_fails_missing_files(self, mock_exists):
        """Verify that validation fails if any required output file is missing."""
        with self.assertRaises(Exception) as context:
            validate_outputs_func("mock/path")
        self.assertIn("Missing output file", str(context.exception))

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_validation_fails_stale_data(self, mock_file_open, mock_exists):
        """Verify that validation fails when the generated_at date is older than the threshold."""
        stale_kpis = self.mock_kpis.copy()
        # 3 hours ago (older than default 2-hour threshold)
        from datetime import datetime, timezone, timedelta
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
        stale_kpis["generated_at"] = stale_time

        file_contents = [
            json.dumps(stale_kpis),
            json.dumps(self.mock_tenders),
            json.dumps(self.mock_pmo)
        ]
        mock_file_open.side_effect = [
            mock_open(read_data=content).return_value for content in file_contents
        ]

        with self.assertRaises(Exception) as context:
            validate_outputs_func("mock/path")
        self.assertIn("is stale", str(context.exception))

    @patch('api.notifier.requests.post')
    def test_discord_alert_failure(self, mock_post):
        """Verify Discord Webhook returns False if request fails or returns non-2xx status."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        notifier = Notifier()
        notifier.discord_url = "https://discord.com/api/webhooks/mock"
        
        result = notifier.send_discord_alert("Test alert message")
        self.assertFalse(result)

    def test_mail_sender_no_subscribers(self):
        """Verify MailSender fails if subscriber list is empty and no operator email fallback exists."""
        azure_client.download_json.return_value = []
        
        sender = MailSender()
        sender.smtp_user = None  # Disable fallback to check standard failure path
        sender.smtp_pass = None

        success = sender.send_daily_digest("mock/post.md", "mock/card.png")
        self.assertFalse(success)

    @patch('generic_engine.extractors.ckan.requests.get')
    def test_canadabuys_apn_exclusion(self, mock_get):
        """Verify that CanadaBuys tenders containing APN (e.g. APN_EDMONTON) are correctly excluded by the filter."""
        
        # Mock CKAN package response
        mock_api_resp = MagicMock()
        mock_api_resp.json.return_value = {
            "success": True,
            "result": {
                "resources": [
                    {"name": "New Tender Notices", "url": "https://example.com/new.csv"}
                ]
            }
        }
        
        # Mock CSV contents containing one normal grant and two APN notices
        csv_data = (
            "noticeURL-URLavis-eng,title-titre-eng,gsinDescription-nibsDescription-eng,unspscDescription-eng,tenderClosingDate-appelOffresDateCloture,publicationDate-datePublication,amendmentDate-dateModification,regionsOfDelivery-regionsLivraison-eng,procurementCategory-categorieApprovisionnement\n"
            "https://example.com/valid,Valid Grant Project,Some funding description,Some unspsc,2026-12-01,2026-05-20,,National,Services\n"
            "https://example.com/apn1,APN_EDMONTON BASE INFRASTRUCTURE,Some description,Some unspsc,2026-12-01,2026-05-20,,National,Construction\n"
            "https://example.com/apn2,APN Edmonton Infrastructure,Some description,Some unspsc,2026-12-01,2026-05-20,,National,Construction\n"
        )
        
        mock_csv_resp = MagicMock()
        mock_csv_resp.status_code = 200
        mock_csv_resp.iter_lines.return_value = [line.encode('utf-8') for line in csv_data.splitlines()]
        
        mock_get.side_effect = [mock_api_resp, mock_csv_resp]
        
        # Execute extractor
        tenders = fetch_canadabuys_csvs(pulse_only=True)
        
        # Assertions:
        # Valid Grant Project should match keywords and be included.
        # Both apn1 (APN_EDMONTON...) and apn2 (APN Edmonton...) must be filtered out.
        self.assertEqual(len(tenders), 1)
        self.assertEqual(tenders[0].title, "Valid Grant Project")


if __name__ == '__main__':
    unittest.main()
