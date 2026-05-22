import time
import logging
import feedparser
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.config import Config

def fetch_rss_feeds(lookback_limit: Optional[datetime] = None, max_items: int = 15) -> List[Dict[str, Any]]:
    """
    Fetches raw RSS feed data from standard sources (like PMO).
    Returns a list of dictionaries with basic metadata, to be processed by LLM later.
    """
    raw_results = []
    is_seeding = (lookback_limit is None)

    for name, url in Config.FEEDS.items():
        logging.info(f"Fetching RSS News from {url}...")
        feed = feedparser.parse(url)
        
        feed_results = []
        for entry in feed.entries:
            published = getattr(entry, 'published_parsed', None)
            pub_date = None
            
            if published:
                pub_date = datetime.fromtimestamp(time.mktime(published))
            
            # Filtering by lookback window
            if not is_seeding and lookback_limit:
                if not pub_date or pub_date < lookback_limit:
                    continue
            
            # Limit count per feed if in strategy seeding mode
            if is_seeding and len(feed_results) >= max_items:
                break
                
            # Filter PMO feed to only include News Releases (exclude readouts, advisories, etc.)
            if "pm.gc.ca" in entry.link and "/news-releases/" not in entry.link:
                continue
                
            feed_results.append({
                "source": name,
                "title": entry.title,
                "link": entry.link,
                "date": pub_date,
                "text_to_search": (entry.title + " " + getattr(entry, 'summary', '')).lower()
            })
            
        raw_results.extend(feed_results)
        
    return raw_results
