import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import List
from src.api.azure_client import azure_client

class MailSender:
    def __init__(self):
        self.smtp_user = os.getenv("EMAIL_ADDRESS")
        self.smtp_pass = os.getenv("EMAIL_APP_PASSWORD")
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "465"))

    def get_subscribers(self) -> List[str]:
        """Downloads the subscriber list from subscribers.json in Azure Blob Storage."""
        try:
            subscribers = azure_client.download_json("subscribers.json")
            if isinstance(subscribers, list) and len(subscribers) > 0:
                logging.info(f"Loaded {len(subscribers)} subscribers from Azure Blob.")
                return [s.strip() for s in subscribers if isinstance(s, str) and "@" in s]
        except Exception as e:
            logging.error(f"Failed to fetch subscribers from Azure: {e}")
        
        # Fallback to sender's own email to ensure someone receives the run digest
        if self.smtp_user:
            logging.warning(f"No subscribers found in Azure. Falling back to operator email: {self.smtp_user}")
            return [self.smtp_user]
        return []

    def _convert_markdown_to_html(self, md_content: str) -> str:
        """Converts basic markdown from latest_post.md to HTML.
        Supports:
        - Headers (#, ##, ###, ####)
        - Bold text
        - Bullet lists (- and *)
        - Horizontal rules (---)
        - Images
        - Links
        - Newlines to line breaks
        """
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
                # 1. Images: ![alt](url)
                img_pattern = r'!\[([^\]]*)\]\(([^)]*)\)'
                bullet_content = re.sub(img_pattern, r'<img src="\2" alt="\1" style="max-width: 100%; border-radius: 8px; margin: 10px 0; border: 1px solid #ffd700;" />', bullet_content)

                # 2. Inline links: [text](url)
                link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
                bullet_content = re.sub(link_pattern, r'<a href="\2" style="color: #ffd700; text-decoration: none; font-weight: bold;">\1</a>', bullet_content)

                # 3. Bold: **text**
                bold_pattern = r'\*\*([^*]+)\*\*'
                bullet_content = re.sub(bold_pattern, r'<strong>\1</strong>', bullet_content)
                
                html_lines.append(f"<li style='margin-bottom: 6px;'>{bullet_content}</li>")
                continue

            # If not a bullet, check if we need to close ul
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False

            import re
            # 1. Images: ![alt](url)
            img_pattern = r'!\[([^\]]*)\]\(([^)]*)\)'
            line_str = re.sub(img_pattern, r'<img src="\2" alt="\1" style="max-width: 100%; border-radius: 8px; margin: 10px 0; border: 1px solid #ffd700;" />', line_str)

            # 2. Inline links: [text](url)
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            line_str = re.sub(link_pattern, r'<a href="\2" style="color: #ffd700; text-decoration: none; font-weight: bold;">\1</a>', line_str)

            # 3. Bold: **text**
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
                <p style="color: #a0a0a0; font-size: 12px; margin: 5px 0 0 0;">Delivering Golden Opportunities Daily</p>
            </div>
            <div style="padding: 10px 0;">
                {body_html}
            </div>
            <div style="text-align: center; padding-top: 20px; border-top: 1px solid #1a1f26; font-size: 11px; color: #707070; margin-top: 30px;">
                <p>You are receiving this because you subscribed to mayAi Canadian Grant Intelligence.</p>
                <p>Powered by mayAi &middot; Azure Cloud Operations</p>
            </div>
        </body>
        </html>
        """

    def send_daily_digest(self, markdown_path: str, social_card_path: str) -> bool:
        """Reads latest post content, compiles HTML, and sends it to all subscribers."""
        if not self.smtp_user or not self.smtp_pass:
            logging.error("SMTP credentials not configured. Skipping email digest distribution.")
            return False

        subscribers = self.get_subscribers()
        if not subscribers:
            logging.error("No recipients available for email distribution. Aborting.")
            return False

        # Read Markdown Content
        try:
            with open(markdown_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
        except Exception as e:
            logging.error(f"Failed to read newsletter markdown file: {e}")
            return False

        # Convert to HTML and Plain Text fallback
        html_body = self._convert_markdown_to_html(md_content)
        plain_body = md_content

        # Extract title from markdown content (find first line starting with #)
        subject_title = ""
        for line in md_content.split("\n"):
            line_str = line.strip()
            if line_str.startswith("# "):
                subject_title = line_str[2:].strip()
                # Clean up any potential markdown formatting in header
                subject_title = subject_title.replace("**", "").replace("*", "").replace("`", "").strip()
                break

        # Get current date for subject line
        from datetime import datetime
        today_str = datetime.now().strftime("%b %d, %Y")
        
        if subject_title:
            subject = f"{today_str} — 🇨🇦 Grant Intelligence — {subject_title}"
        else:
            subject = f"{today_str} — 🇨🇦 Grant Intelligence"

        success = True
        try:
            # Connect to SMTP
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
                server.starttls()

            with server:
                server.login(self.smtp_user, self.smtp_pass)

                for recipient in subscribers:
                    try:
                        # Build Multipart Message for each recipient (prevents email leaking/header overload)
                        msg = MIMEMultipart('alternative')
                        msg['Subject'] = subject
                        msg['From'] = f"Canadian Grant Intelligence <{self.smtp_user}>"
                        msg['To'] = recipient

                        # Attach parts
                        part1 = MIMEText(plain_body, 'plain', 'utf-8')
                        part2 = MIMEText(html_body, 'html', 'utf-8')
                        msg.attach(part1)
                        msg.attach(part2)

                        # Attach Social Card image if exists
                        if social_card_path and os.path.exists(social_card_path):
                            try:
                                with open(social_card_path, 'rb') as f:
                                    img_data = f.read()
                                img = MIMEImage(img_data, name=os.path.basename(social_card_path))
                                # Optional content-ID for inline images
                                img.add_header('Content-ID', '<social_card_img>')
                                img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(social_card_path))
                                msg.attach(img)
                            except Exception as img_err:
                                logging.error(f"Failed to attach social card image: {img_err}")

                        server.sendmail(self.smtp_user, [recipient], msg.as_string())
                        logging.info(f"Digest email sent successfully to {recipient}")
                    except Exception as rcpt_err:
                        logging.error(f"Failed to send digest to {recipient}: {rcpt_err}")
                        success = False
        except Exception as conn_err:
            logging.error(f"SMTP Connection or Login failed: {conn_err}")
            success = False

        return success

mail_sender = MailSender()
