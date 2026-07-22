import logging
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

ISED_ARCHIVE_URL = "https://ised-isde.canada.ca/site/ised/en/newsletter-gc-business-insights"
BASE_URL = "https://ised-isde.canada.ca"

def fetch_ised_business_insights(max_issues: int = 2) -> List[Dict[str, Any]]:
    """
    Crawls the ISED GC Business Insights newsletter archive and parses recent monthly editions.
    Extracts structured program opportunities, descriptions, and direct CTA application URLs
    without external HTML dependencies.
    """
    logging.info(f"Crawling ISED GC Business Insights archive from {ISED_ARCHIVE_URL}...")
    items: List[Dict[str, Any]] = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        resp = requests.get(ISED_ARCHIVE_URL, headers=headers, timeout=20)
        resp.raise_for_status()
        html_text = resp.text

        # 1. Discover Issue Links using regex matching
        issue_urls: List[str] = []
        raw_hrefs = re.findall(r'href=["\'](/site/ised/en/newsletter-gc-business-insights/gc-business-insights-[a-z0-9-]+)["\']', html_text, re.IGNORECASE)
        for href in raw_hrefs:
            full_url = urljoin(BASE_URL, href)
            if "/isde/fr/" in full_url or full_url.endswith("/newsletter-gc-business-insights"):
                continue
            if full_url not in issue_urls:
                issue_urls.append(full_url)

        logging.info(f"Discovered {len(issue_urls)} ISED Business Insights issue URLs: {issue_urls[:max_issues]}")

        # 2. Fetch and Parse Selected Issue Pages
        for issue_url in issue_urls[:max_issues]:
            try:
                logging.info(f"Parsing ISED issue: {issue_url}...")
                issue_resp = requests.get(issue_url, headers=headers, timeout=20)
                issue_resp.raise_for_status()
                page_html = issue_resp.text

                # Extract publication/modified date
                date_str = datetime.now().strftime("%Y-%m-%d")
                date_match = re.search(r'property=["\']dateModified["\'][^>]*>(\d{4}-\d{2}-\d{2})<', page_html)
                if date_match:
                    date_str = date_match.group(1)

                # Extract CTA buttons / links with title or btn class
                btn_matches = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>', page_html, re.IGNORECASE)
                for href, title in btn_matches:
                    link_url = urljoin(BASE_URL, href)
                    title_clean = re.sub(r'\s+', ' ', title).strip()
                    if not link_url or "newsletter-gc-business-insights" in link_url or len(title_clean) < 5:
                        continue

                    items.append({
                        "title": f"ISED Business Insights: {title_clean}",
                        "summary": title_clean,
                        "url": link_url,
                        "date": date_str,
                        "source_name": "ISED_GC_Business_Insights",
                        "hub": "Canada"
                    })

            except Exception as issue_err:
                logging.warning(f"Error fetching ISED issue page {issue_url}: {issue_err}")

        logging.info(f"Successfully extracted {len(items)} items from ISED Business Insights.")
        return items

    except Exception as exc:
        logging.error(f"Failed to fetch ISED Business Insights archive: {exc}")
        return []
