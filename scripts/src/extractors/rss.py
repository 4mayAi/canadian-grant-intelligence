import time
import logging
import feedparser
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.config import Config

def fetch_rss_feeds(
    lookback_limit: Optional[datetime] = None, 
    max_items: int = 15,
    failed_feeds: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Fetches raw RSS feed data from standard sources (like PMO).
    Returns a list of dictionaries with basic metadata, to be processed by LLM later.
    """
    raw_results = []
    is_seeding = (lookback_limit is None)

    for name, url in Config.FEEDS.items():
        logging.info(f"Fetching RSS News from {url}...")
        try:
            feed = feedparser.parse(url)
            
            # Check for network or parse failures
            status = getattr(feed, 'status', 200)
            bozo = getattr(feed, 'bozo', 0)
            
            if status >= 400:
                logging.error(f"Feed {name} returned HTTP status {status}")
                if failed_feeds is not None:
                    failed_feeds.append(name)
                continue
                
            if not feed.entries and bozo == 1:
                logging.error(f"Feed {name} failed parser check. Bozo exception: {getattr(feed, 'bozo_exception', 'None')}")
                if failed_feeds is not None:
                    failed_feeds.append(name)
                continue
                
            feed_results = []
            for entry in feed.entries:
                pub_date = None
                try:
                    published = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
                    if published:
                        pub_date = datetime.fromtimestamp(time.mktime(published))
                except Exception as parse_err:
                    logging.warning(f"Error parsing date for entry {entry.get('link', 'unknown')}: {parse_err}")
                
                if not pub_date:
                    logging.warning(f"No valid date found for entry {entry.get('link', 'unknown')}. Falling back to UTC now.")
                    pub_date = datetime.utcnow()
                
                # Filtering by lookback window
                if not is_seeding and lookback_limit:
                    if pub_date < lookback_limit:
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
            
        except Exception as e:
            logging.error(f"Failed to fetch or parse feed {name} entirely: {e}")
            if failed_feeds is not None:
                failed_feeds.append(name)
                
    return raw_results

