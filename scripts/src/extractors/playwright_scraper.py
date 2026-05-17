import asyncio
import logging
from datetime import datetime
import time
from dateutil import parser as date_parser
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, Browser

from src.config import Config

async def _scrape_single_url(browser: Browser, url: str, source_name: str, semaphore: asyncio.Semaphore) -> List[Dict[str, Any]]:
    """Scrapes a single JS-rendered page with concurrency limits."""
    results = []
    async with semaphore:
        logging.info(f"Scraping JS-rendered news from {url} using Playwright...")
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            items = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll('a'));
                const results = [];
                links.forEach(a => {
                    const href = a.href || '';
                    const title = a.innerText.trim();
                    if (title.length > 20 && (href.includes('/news') || href.includes('news-releases') || href.includes('/news-nouvelles/') || href.includes('article'))) {
                        if (!results.some(r => r.link === href)) {
                            let dateText = '';
                            const parent = a.closest('div, li, tr, article');
                            if (parent) {
                                const timeElem = parent.querySelector('time');
                                if (timeElem) {
                                    dateText = timeElem.getAttribute('datetime') || timeElem.innerText;
                                } else {
                                    const dateElem = parent.querySelector('.date, .pubdate, .published');
                                    if (dateElem) dateText = dateElem.innerText;
                                }
                            }
                            results.push({title: title, link: href, dateText: dateText});
                        }
                    }
                });
                return results.slice(0, 15);
            }''')
            
            for item in items:
                pub_date = None
                if item.get('dateText'):
                    try:
                        dt = date_parser.parse(item['dateText'])
                        pub_date = dt
                    except (ValueError, TypeError, OverflowError):
                        pass
                
                results.append({
                    "title": item['title'],
                    "link": item['link'],
                    "source": source_name,
                    "date": pub_date,
                    "text_to_search": item['title'].lower()
                })
            
            await page.close()
        except Exception as e:
            logging.error(f"Playwright scraping failed for {source_name} at {url}: {e}")
            
    return results

async def _scrape_all_concurrently() -> List[Dict[str, Any]]:
    """Manages the playwright instance and gathers all scraping tasks."""
    scraped_items = []
    # Throttle concurrency to max 3 simultaneous pages to prevent crashing
    semaphore = asyncio.Semaphore(3)
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            tasks = []
            for name, url in Config.HTML_SOURCES.items():
                tasks.append(_scrape_single_url(browser, url, name, semaphore))
                
            # Gather runs them concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in results:
                if isinstance(res, Exception):
                    logging.error(f"A scrape task failed: {res}")
                else:
                    scraped_items.extend(res)
                    
            await browser.close()
    except Exception as e:
        logging.error(f"Failed to launch Playwright browser: {e}")
        
    return scraped_items

def fetch_html_news(lookback_limit: Optional[datetime] = None, max_items: int = 15) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper to fetch raw JS-rendered news items.
    Returns a list of dictionaries with basic metadata.
    """
    raw_results = []
    is_seeding = (lookback_limit is None)
    
    # Run the concurrent scrape
    scraped_items = asyncio.run(_scrape_all_concurrently())
    
    # Filter and format results
    counts_per_source = {}
    
    junk_patterns = ["top of page", "skip to", "archived news", "all department"]
    
    for entry in scraped_items:
        source = entry['source']
        if source not in counts_per_source:
            counts_per_source[source] = 0
            
        pub_date = entry.get('date')
        
        # Filter by lookback window
        if not is_seeding and lookback_limit and pub_date:
            # We must make pub_date naive if it's aware to compare, or vice versa.
            # Assuming lookback_limit is naive local time, we convert pub_date to naive.
            if pub_date.tzinfo is not None:
                pub_date = pub_date.replace(tzinfo=None)
            if pub_date < lookback_limit:
                continue

        # Limit count per feed if in strategy seeding mode
        if is_seeding and counts_per_source[source] >= max_items:
            continue
            
        # Filter junk
        if any(junk in entry['text_to_search'] for junk in junk_patterns):
            continue
            
        raw_results.append(entry)
        counts_per_source[source] += 1
        
    return raw_results
