import os
import io
import re
import logging
import requests
from urllib.parse import urljoin
from pypdf import PdfReader
from playwright.sync_api import sync_playwright
from googlenewsdecoder import new_decoderv1

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def resolve_google_news_url(url: str) -> str:
    """Decodes Google News redirect URLs offline to original URLs."""
    if not url or "news.google.com" not in url:
        return url
    try:
        res_dec = new_decoderv1(url, interval=1)
        if res_dec.get("status"):
            decoded = res_dec["decoded_url"]
            logging.info(f"Resolved Google News URL: {url} -> {decoded}")
            return decoded
        else:
            logging.warning(f"Failed to resolve Google News URL: {res_dec.get('message')}. Using original URL.")
            return url
    except Exception as e:
        logging.error(f"Error decoding Google News URL: {e}. Using original URL.")
        return url

def is_high_value_report(url: str, title: str) -> bool:
    """Classifies whether a URL or Title represents a high-value report or publication."""
    if not url or not title:
        return False
    url_lower = url.lower()
    title_lower = title.lower()
    return (
        "/publications/" in url_lower or 
        "/report/" in url_lower or 
        "/facts-figures/" in url_lower or 
        "/events/" in url_lower or
        "iisd.org" in url_lower or
        url_lower.endswith(".pdf") or
        "report" in title_lower or
        "publications" in title_lower or
        "facts & figures" in title_lower or
        "blueprint" in title_lower or
        "standards" in title_lower
    )

def clean_extracted_text(text: str) -> str:
    """Cleans up raw text: strips duplicate spaces, preserves single and double newlines, and strips trailing spaces."""
    if not text:
        return ""
    # Split text into lines, strip each line
    lines = [line.strip() for line in text.splitlines()]
    # Remove excessive blank lines (keep at most one consecutive blank line)
    cleaned_lines = []
    for line in lines:
        if line:
            # Condense multiple spaces inside the line
            cleaned_line = re.sub(r'[ \t]+', ' ', line)
            cleaned_lines.append(cleaned_line)
        else:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
    # Strip leading/trailing empty lines
    while cleaned_lines and cleaned_lines[0] == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()
    return "\n".join(cleaned_lines)

def scrape_html_report(url: str) -> str:
    """Uses Playwright to scrape body text from an HTML report page, with smart PDF auto-download."""
    logging.info(f"Scraping HTML report page: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                # Create a context with a browser-like user agent
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Retrieve raw HTML code to search for PDF/download links
                html_content = page.content()
                
                # Try to locate the main content using semantic selectors to avoid header/footer noise
                body_text = ""
                for selector in ["article", "main", "[role='main']", ".content", ".post-content", ".entry-content"]:
                    locator = page.locator(selector)
                    if locator.count() > 0:
                        text = locator.first.inner_text()
                        if len(text.strip()) > 800:
                            body_text = text
                            logging.info(f"Targeted semantic container '{selector}' for high-fidelity HTML extraction.")
                            break
                if not body_text:
                    body_text = page.locator("body").inner_text()
            finally:
                browser.close()
            
            # Clean and preserve paragraph formatting
            cleaned_text = clean_extracted_text(body_text)
            
            # Check for a download link if text is thin (i.e. landing page template)
            if len(cleaned_text) < 3000:
                # Find download links matching "/download/" or ending in ".pdf"
                matches = re.findall(r'href=["\']([^"\']*(?:/download/[^"\']+|[^"\']+\.pdf))["\']', html_content)
                if matches:
                    download_url = urljoin(url, matches[0])
                    logging.info(f"Thin landing page text ({len(cleaned_text)} chars). Found nested download link: {download_url}. Attempting PDF extraction...")
                    pdf_text = scrape_pdf_report(download_url)
                    if pdf_text:
                        return pdf_text
            
            return cleaned_text[:5000]  # Cap at 5000 characters
    except Exception as e:
        logging.error(f"Error scraping HTML page via Playwright: {e}")
        return ""

def scrape_pdf_report(url: str) -> str:
    """Downloads a PDF and extracts text from the first 5 pages."""
    logging.info(f"Downloading and extracting PDF: {url}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Load PDF reader
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        extracted_text = []
        # Read up to the first 5 pages
        max_pages = min(5, len(reader.pages))
        for page_num in range(max_pages):
            text = reader.pages[page_num].extract_text()
            if text:
                extracted_text.append(text)
                
        full_text = "\n".join(extracted_text)
        cleaned_text = clean_extracted_text(full_text)
        return cleaned_text[:5000]  # Cap at 5000 characters
    except Exception as e:
        logging.error(f"Error extracting PDF: {e}")
        return ""
