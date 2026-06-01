import asyncio
import logging
from datetime import datetime
from dateutil import parser as date_parser
from typing import List, Dict, Any, Optional, Set

from playwright.async_api import async_playwright, Browser

async def _scrape_single_url(
    browser: Browser, 
    url: str, 
    source_name: str, 
    semaphore: asyncio.Semaphore
) -> List[Dict[str, Any]]:
    """Scrapes a single JS-rendered page with concurrency limits."""
    results = []
    async with semaphore:
        logging.info(f"Scraping JS-rendered news from {url} using Playwright...")
        page = None
        try:
            page = await browser.new_page()
            # Set a standard viewport and user agent to bypass basic bot detections
            await page.set_viewport_size({"width": 1280, "height": 800})
            
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Allow some extra time for dynamic SPA hydration
            await page.wait_for_timeout(3000)
            
            items = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll('a'));
                const results = [];
                
                links.forEach(a => {
                    const href = a.href || '';
                    let title = a.innerText.trim();
                    
                    // Simple heuristic filter to identify article links and filter out navigation links
                    const isNewsLink = href.includes('/news') || 
                                       href.includes('news-releases') || 
                                       href.includes('/news-nouvelles/') || 
                                       href.includes('article') || 
                                       href.includes('release') ||
                                       href.includes('/blog/') ||
                                       href.includes('/update') ||
                                       href.includes('pic-updates');
                                       
                    if (isNewsLink) {
                        // Check if it's a container link with structured title inside
                        const cardNameElem = a.querySelector('.card__name, .card__title, .card-title, h1, h2, h3, h4, h5, h6, [class*="title"], [class*="name"]');
                        if (cardNameElem) {
                            title = cardNameElem.innerText.trim();
                        }
                        
                        if (title.length > 15) {
                            if (!results.some(r => r.link === href)) {
                                let dateText = '';
                                
                                // Try finding date within the link container first
                                const dateElem = a.querySelector('.card__postDate, .date, .pubdate, .published, .card-time, time, [class*="date"]');
                                if (dateElem) {
                                    dateText = dateElem.innerText.trim();
                                }
                                
                                // Sibling or parent search if not inside link
                                if (!dateText) {
                                    const parent = a.closest('div, li, tr, article, section');
                                    if (parent) {
                                        const timeElem = parent.querySelector('time');
                                        if (timeElem) {
                                            dateText = timeElem.getAttribute('datetime') || timeElem.innerText;
                                        } else {
                                            const parentDateElem = parent.querySelector('.card__postDate, .date, .pubdate, .published, .card-time, time, [class*="date"]');
                                            if (parentDateElem) dateText = parentDateElem.innerText;
                                        }
                                    }
                                }
                                results.push({title: title, link: href, dateText: dateText});
                            }
                        }
                    }
                });
                return results.slice(0, 15);
            }''')
            
            for item in items:
                # Filter out self-references to index page
                if item['link'].rstrip('/') == url.rstrip('/'):
                    continue
                    
                pub_date = None
                if item.get('dateText'):
                    try:
                        # Clean common prefix or suffix texts (e.g. "May 27, 2026 at 10 AM")
                        clean_date = item['dateText'].split('|')[0].strip()
                        dt = date_parser.parse(clean_date)
                        pub_date = dt
                    except (ValueError, TypeError, OverflowError):
                        pass
                
                if not pub_date:
                    pub_date = datetime.utcnow()
                
                results.append({
                    "title": item['title'],
                    "link": item['link'],
                    "source": source_name,
                    "date": pub_date,
                    "text_to_search": item['title'].lower()
                })
            
            logging.info(f"Playwright successfully scraped {len(results)} items for {source_name}.")
        except Exception as e:
            logging.error(f"Playwright scraping failed for {source_name} at {url}: {e}")
            raise e
        finally:
            if page:
                await page.close()
            
    return results

async def _scrape_all_concurrently(
    sources: List[Dict[str, Any]], 
    failed_names: Set[str]
) -> List[Dict[str, Any]]:
    """Manages the playwright instance and gathers all HTML scraping tasks."""
    scraped_items = []
    semaphore = asyncio.Semaphore(2)  # Throttle to max 2 concurrent pages to save CPU
    
    html_sources = [s for s in sources if s.get("type") == "html_playwright"]
    if not html_sources:
        return scraped_items
        
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            tasks = []
            for src in html_sources:
                tasks.append(_scrape_single_url(browser, src["url"], src["name"], semaphore))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for src, res in zip(html_sources, results):
                if isinstance(res, Exception):
                    logging.error(f"A Playwright task failed for {src['name']}: {res}")
                    failed_names.add(src["name"])
                else:
                    if not res:
                        logging.warning(f"Playwright scraped 0 items for {src['name']}. Marking as failed.")
                        failed_names.add(src["name"])
                    else:
                        scraped_items.extend(res)
                    
            await browser.close()
    except Exception as e:
        logging.error(f"Failed to execute Playwright extraction loop: {e}")
        for src in html_sources:
            failed_names.add(src["name"])
        
    return scraped_items

def fetch_html_news(
    sources: List[Dict[str, Any]],
    lookback_limit: Optional[datetime] = None, 
    max_items: int = 15,
    failed_feeds: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper to fetch raw JS-rendered news items.
    """
    raw_results = []
    is_seeding = (lookback_limit is None)
    
    # Run the concurrent scrape
    failed_names = set()
    scraped_items = asyncio.run(_scrape_all_concurrently(sources, failed_names))
    if failed_feeds is not None:
        failed_feeds.extend(failed_names)
        
    counts_per_source = {}
    junk_patterns = [
        "top of page", "skip to", "archived news", "all department",
        "switch to basic html", "basic html version", "contact us",
        "terms and conditions", "privacy statement"
    ]
    
    for entry in scraped_items:
        source = entry['source']
        if source not in counts_per_source:
            counts_per_source[source] = 0
            
        pub_date = entry.get('date')
        
        # Filter by lookback window
        if not is_seeding and lookback_limit and pub_date:
            if pub_date.tzinfo is not None:
                pub_date = pub_date.replace(tzinfo=None)
            if pub_date < lookback_limit:
                continue

        # Limit count per feed if in strategy seeding mode
        if is_seeding and counts_per_source[source] >= max_items:
            continue
            
        # Filter junk links
        link_lower = entry['link'].lower()
        title_lower = entry['title'].lower()
        if any(junk in title_lower for junk in junk_patterns) or any(junk in link_lower for junk in ["/terms-conditions", "/privacy", "/contact-us"]):
            continue
            
        raw_results.append(entry)
        counts_per_source[source] += 1
        
    return raw_results
