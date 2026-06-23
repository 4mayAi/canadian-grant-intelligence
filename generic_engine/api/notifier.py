import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import requests
from typing import Optional, List

class Notifier:
    def __init__(self, discord_url: Optional[str] = None, alert_email: Optional[str] = None):
        self.discord_url = discord_url or os.getenv("DISCORD_WEBHOOK_URL")
        if self.discord_url and (self.discord_url.startswith("${") or self.discord_url.strip() == ""):
            self.discord_url = None

        self.smtp_user = os.getenv("EMAIL_ADDRESS")
        self.smtp_pass = os.getenv("EMAIL_APP_PASSWORD")
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "465"))

        if alert_email and (alert_email.startswith("${") or alert_email.strip() == ""):
            alert_email = None
        self.alert_email = alert_email or os.getenv("ALERT_EMAIL_ADDRESS") or self.smtp_user

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

    def _convert_markdown_to_html(self, md_content: str, topic_name: str = "Canadian Innovation Clusters Intelligence") -> str:
        """Converts basic markdown from digest to HTML."""
        lines = md_content.split("\n")
        html_lines = []
        in_p = False
        in_ul = False

        for line in lines:
            line_str = line.strip()
            if not line_str:
                if in_p:
                    html_lines.append("</p>")
                    in_p = False
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                continue

            # Horizontal Rule
            if line_str == "---":
                if in_p:
                    html_lines.append("</p>")
                    in_p = False
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                html_lines.append("<hr style='border: 0; border-top: 1px solid #1a1f26; margin: 20px 0;'/>")
                continue

            # Headers
            if line_str.startswith("# "):
                if in_p:
                    html_lines.append("</p>")
                    in_p = False
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                header_text = line_str[2:]
                html_lines.append(f"<h1 style='color: #ffd700; font-family: sans-serif; border-bottom: 1px solid #1a1f26; padding-bottom: 5px; margin-top: 20px;'>{header_text}</h1>")
                continue
            elif line_str.startswith("## "):
                if in_p:
                    html_lines.append("</p>")
                    in_p = False
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                header_text = line_str[3:]
                html_lines.append(f"<h2 style='color: #ffd700; font-family: sans-serif; border-bottom: 1px solid #1a1f26; padding-bottom: 5px; margin-top: 20px;'>{header_text}</h2>")
                continue
            elif line_str.startswith("### "):
                if in_p:
                    html_lines.append("</p>")
                    in_p = False
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                header_text = line_str[4:]
                html_lines.append(f"<h3 style='color: #ffd700; font-family: sans-serif; margin-top: 20px; margin-bottom: 10px; font-size: 16px;'>{header_text}</h3>")
                continue
            elif line_str.startswith("#### "):
                if in_p:
                    html_lines.append("</p>")
                    in_p = False
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                header_text = line_str[5:]
                html_lines.append(f"<h4 style='color: #ffd700; font-family: sans-serif; margin-top: 15px; margin-bottom: 8px; font-size: 14px;'>{header_text}</h4>")
                continue

            # Bullets: starting with - or *
            if line_str.startswith("- ") or line_str.startswith("* "):
                if in_p:
                    html_lines.append("</p>")
                    in_p = False
                if not in_ul:
                    html_lines.append("<ul style='font-family: sans-serif; color: #e0e0e0; line-height: 1.6; font-size: 14px; margin-left: 20px; padding-left: 0;'>")
                    in_ul = True
                bullet_content = line_str[2:]
                
                # Apply inline styles
                import re
                # Inline images: ![alt](url)
                img_pattern = r'!\[([^\]]*)\]\(([^)]*)\)'
                bullet_content = re.sub(img_pattern, r'<img src="\2" alt="\1" style="max-width: 100%; border-radius: 8px; margin: 10px 0; border: 1px solid #ffd700;" />', bullet_content)

                # Inline links: [text](url)
                link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
                bullet_content = re.sub(link_pattern, r'<a href="\2" style="color: #ffd700; text-decoration: none; font-weight: bold;">\1</a>', bullet_content)

                # Bold: **text**
                bold_pattern = r'\*\*([^*]+)\*\*'
                bullet_content = re.sub(bold_pattern, r'<strong>\1</strong>', bullet_content)
                
                html_lines.append(f"<li style='margin-bottom: 6px;'>{bullet_content}</li>")
                continue

            # If not a bullet, check if we need to close ul
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False

            import re
            # Inline images: ![alt](url)
            img_pattern = r'!\[([^\]]*)\]\(([^)]*)\)'
            line_str = re.sub(img_pattern, r'<img src="\2" alt="\1" style="max-width: 100%; border-radius: 8px; margin: 10px 0; border: 1px solid #ffd700;" />', line_str)

            # Inline links: [text](url)
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            line_str = re.sub(link_pattern, r'<a href="\2" style="color: #ffd700; text-decoration: none; font-weight: bold;">\1</a>', line_str)

            # Bold: **text**
            bold_pattern = r'\*\*([^*]+)\*\*'
            line_str = re.sub(bold_pattern, r'<strong>\1</strong>', line_str)

            if not in_p:
                html_lines.append("<p style='font-family: sans-serif; color: #e0e0e0; line-height: 1.6; font-size: 14px;'>")
                in_p = True
            
            html_lines.append(line_str + "<br/>")

        if in_p:
            html_lines.append("</p>")
        if in_ul:
            html_lines.append("</ul>")

        body_html = "\n".join(html_lines)
        return f"""
        <html>
        <body style="background-color: #05070a; color: #e0e0e0; padding: 20px; font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #1a1f26; border-radius: 12px;">
            <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #1a1f26;">
                <h1 style="color: #ffd700; margin: 0; font-family: sans-serif; font-size: 28px;">may<span style="color: #ffffff;">Ai</span></h1>
                <p style="color: #a0a0a0; font-size: 12px; margin: 5px 0 0 0;">{topic_name}</p>
            </div>
            <div style="padding: 10px 0;">
                {body_html}
            </div>
            <div style="text-align: center; padding-top: 20px; border-top: 1px solid #1a1f26; font-size: 11px; color: #707070; margin-top: 30px;">
                <p>You are receiving this because you subscribed to the mayAi {topic_name} digest.</p>
                <p>Powered by mayAi &middot; Azure Cloud Operations</p>
            </div>
        </body>
        </html>
        """

    def send_digest(
        self, 
        subject: str, 
        markdown_content: str, 
        social_card_path: Optional[str] = None,
        from_name: str = "Canadian Innovation Clusters",
        topic_name: str = "Canadian Innovation Clusters Intelligence",
        recipients: Optional[List[str]] = None
    ) -> bool:
        """Sends a beautiful HTML newsletter digest to the configured recipients."""
        if not self.smtp_user or not self.smtp_pass:
            logging.debug("Email credentials not configured. Skipping digest mail.")
            return False

        # Determine target recipients list
        target_recipients = []
        if recipients:
            target_recipients = [r.strip() for r in recipients if r and "@" in r]
        
        if not target_recipients and self.alert_email:
            target_recipients = [r.strip() for r in self.alert_email.split(",") if r.strip() and "@" in r]

        if not target_recipients:
            # Fall back to operator email
            target_recipients = [self.smtp_user]

        try:
            # Convert markdown to HTML
            html_body = self._convert_markdown_to_html(markdown_content, topic_name)
            
            # Connect to SMTP
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
                server.starttls()

            with server:
                server.login(self.smtp_user, self.smtp_pass)
                for recipient in target_recipients:
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = subject
                    msg['From'] = f"{from_name} <{self.smtp_user}>"
                    msg['To'] = recipient

                    # Attach parts
                    part1 = MIMEText(markdown_content, 'plain', 'utf-8')
                    part2 = MIMEText(html_body, 'html', 'utf-8')
                    msg.attach(part1)
                    msg.attach(part2)

                    # Attach social card if present
                    if social_card_path and os.path.exists(social_card_path):
                        try:
                            with open(social_card_path, 'rb') as f:
                                img = MIMEImage(f.read(), name=os.path.basename(social_card_path))
                            img.add_header('Content-ID', '<social_card_img>')
                            img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(social_card_path))
                            msg.attach(img)
                        except Exception as img_err:
                            logging.error(f"Failed to attach social card: {img_err}")

                    server.sendmail(self.smtp_user, [recipient], msg.as_string())
                    logging.info(f"Digest email sent successfully to {recipient}")

            return True
        except Exception as e:
            logging.error(f"Failed to send digest email: {e}")
            return False
