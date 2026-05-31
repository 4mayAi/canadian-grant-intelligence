import time
import logging
import feedparser
from datetime import datetime
from typing import List, Dict, Any, Optional

def fetch_rss_feeds(
    sources: List[Dict[str, Any]],
    lookback_limit: Optional[datetime] = None, 
    max_items: int = 15,
    failed_feeds: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Generic RSS feed crawler.
    - Loops over sources where type == "rss"
    - Each source fetch is wrapped in try-except boundaries.
    """
    raw_results = []
    is_seeding = (lookback_limit is None)

    for src in sources:
        if src.get("type") != "rss":
            continue

        name = src["name"]
        url = src["url"]

        logging.info(f"Fetching RSS News from {url} ({name})...")
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
                
                # Filter by lookback window (convert pub_date to naive local if lookback_limit is naive)
                if not is_seeding and lookback_limit:
                    if pub_date.tzinfo is not None:
                        pub_date = pub_date.replace(tzinfo=None)
                    if pub_date < lookback_limit:
                        continue
                
                # Limit count per feed if in strategy seeding mode
                if is_seeding and len(feed_results) >= max_items:
                    break
                    
                # Standard PMO feed filter logic preserved as fallback
                if "pm.gc.ca" in entry.link and "/news-releases/" not in entry.link:
                    continue
                    
                summary_text = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                feed_results.append({
                    "source": name,
                    "title": entry.title,
                    "link": entry.link,
                    "date": pub_date,
                    "text_to_search": (entry.title + " " + summary_text).lower()
                })
                
            raw_results.extend(feed_results)
            logging.info(f"Successfully processed {len(feed_results)} entries from {name}.")
            
        except Exception as e:
            logging.error(f"Failed to fetch or parse feed {name} entirely: {e}")
            if failed_feeds is not None:
                failed_feeds.append(name)
                
    return raw_results
