import os
import logging
import smtplib
from email.mime.text import MIMEText
import requests
from typing import Optional

class Notifier:
    def __init__(self, discord_url: Optional[str] = None, alert_email: Optional[str] = None):
        self.discord_url = discord_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.alert_email = alert_email or os.getenv("ALERT_EMAIL_ADDRESS")
        self.smtp_user = os.getenv("EMAIL_ADDRESS")
        self.smtp_pass = os.getenv("EMAIL_APP_PASSWORD")
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "465"))

    def send_discord_alert(self, message: str, topic_name: str = "Generic Engine") -> bool:
        """Sends an alert to the Discord webhook if configured."""
        if not self.discord_url:
            logging.debug("Discord webhook URL not configured. Skipping Discord alert.")
            return False
            
        try:
            payload = {
                "embeds": [
                    {
                        "title": f"🚨 Pipeline Alert: {topic_name}",
                        "description": message,
                        "color": 15158332, # Red
                        "timestamp": requests.utils.default_headers().get("Date")
                    }
                ]
            }
            response = requests.post(self.discord_url, json=payload, timeout=10)
            if response.status_code in [200, 204]:
                logging.info("Discord alert sent successfully.")
                return True
            else:
                logging.error(f"Discord webhook returned status code {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logging.error(f"Failed to send Discord alert: {e}")
            return False

    def send_email_alert(self, subject: str, message: str) -> bool:
        """Sends an alert email to the admin/operator email address."""
        if not self.alert_email or not self.smtp_user or not self.smtp_pass:
            logging.debug("Email alert credentials or recipient address not configured. Skipping email alert.")
            return False

        try:
            msg = MIMEText(message, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = f"Pipeline Alerts <{self.smtp_user}>"
            msg['To'] = self.alert_email

            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls()
                
            with server:
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, [self.alert_email], msg.as_string())
                
            logging.info("Email failure alert sent successfully.")
            return True
        except Exception as e:
            logging.error(f"Failed to send email alert: {e}")
            return False

    def notify_failure(self, task_name: str, error_msg: str, topic_name: str = "Generic Engine"):
        """Sends alerts via all enabled channels (Discord, Email)."""
        formatted_message = f"**Task**: {task_name}\n**Error**: {error_msg}"
        subject = f"🚨 Pipeline Failure [{topic_name}]: {task_name}"
        
        self.send_discord_alert(formatted_message, topic_name=topic_name)
        self.send_email_alert(subject, f"Pipeline Error Report:\n\nTopic: {topic_name}\nTask: {task_name}\nError: {error_msg}")
