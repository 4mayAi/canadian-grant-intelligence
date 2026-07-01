import urllib.request
import re
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

def parse_relative_time(text: str) -> datetime:
    """
    Converts YouTube relative time strings (e.g., '13 hours ago', '5 days ago', '2 weeks ago')
    into naive UTC datetimes.
    """
    now = datetime.utcnow()
    text_lower = text.lower().strip()
    
    # Matches 'X second/minute/hour/day/week/month/year ago'
    match = re.match(r'(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago', text_lower)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        
        # Translate units to seconds
        deltas = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
            "week": 604800,
            "month": 2592000,   # approx 30 days
            "year": 31536000    # approx 365 days
        }
        
        seconds_to_sub = value * deltas.get(unit, 0)
        return (now - timedelta(seconds=seconds_to_sub)).replace(microsecond=0)
        
    return now.replace(microsecond=0)

def is_french_video(title: str) -> bool:
    """
    Heuristic to filter out French versions of announcements to prevent duplicate LLM runs.
    """
    french_indicators = [
        "l'avenir", "l’avenir", "énergétique", "générale", "gouverneure", 
        "la ligne de conduite", "ligne de conduite", "notre plan", "progrès", 
        "réalisés", "général", "jusqu'ici", "jusqu’ici", "l’avenir énergétique"
    ]
    title_lower = title.lower()
    return any(indicator in title_lower for indicator in french_indicators)

def fetch_youtube_videos(
    sources: List[Dict[str, Any]],
    lookback_limit: Optional[datetime] = None,
    max_items: int = 5,
    failed_feeds: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Scrapes YouTube channel /videos tabs to extract video details.
    Maps them into standard news feed item dictionaries.
    """
    raw_results = []
    is_seeding = (lookback_limit is None)
    
    for src in sources:
        if src.get("type") != "youtube_channel":
            continue
            
        name = src["name"]
        url = src["url"]
        
        logging.info(f"Scraping YouTube Videos from {url} ({name})...")
        try:
            # Format videos URL path
            videos_url = url.rstrip("/") + "/videos"
            req = urllib.request.Request(
                videos_url, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            )
            
            html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', errors='ignore')
            
            match = re.search(r"var ytInitialData = ({.*?});</script>", html, re.DOTALL)
            if not match:
                logging.error(f"Could not locate ytInitialData on page for source {name}")
                if failed_feeds is not None:
                    failed_feeds.append(name)
                continue
                
            data = json.loads(match.group(1))
            tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
            
            # Extract videos tab contents
            videos_tab = next(
                (tab["tabRenderer"] for tab in tabs if tab.get("tabRenderer", {}).get("title") == "Videos"), 
                None
            )
            if not videos_tab:
                logging.error(f"Could not find Videos tab for source {name}")
                if failed_feeds is not None:
                    failed_feeds.append(name)
                continue
                
            contents = videos_tab["content"]["richGridRenderer"]["contents"]
            
            feed_results = []
            for item in contents:
                rich_item = item.get("richItemRenderer", {})
                content = rich_item.get("content", {})
                lockup = content.get("lockupViewModel", {})
                if not lockup:
                    continue
                    
                vid_id = lockup.get("contentId", "")
                if not vid_id:
                    continue
                video_url = f"https://www.youtube.com/watch?v={vid_id}"
                
                metadata = lockup.get("metadata", {})
                lockup_metadata = metadata.get("lockupMetadataViewModel", {})
                title = lockup_metadata.get("title", {}).get("content", "Unknown Title")
                
                # Heuristic: Filter out French duplicate videos
                if is_french_video(title):
                    logging.info(f"Filtering French duplicate video: '{title}'")
                    continue
                    
                # Extract views and publish date
                published_text = "Unknown"
                views_text = "Unknown"
                try:
                    parts = lockup_metadata.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [{}])[0].get("metadataParts", [])
                    if len(parts) > 0:
                        views_text = parts[0].get("text", {}).get("content", "Unknown")
                    if len(parts) > 1:
                        published_text = parts[1].get("text", {}).get("content", "Unknown")
                except Exception:
                    pass
                
                # Parse relative publish date string to datetime object
                pub_date = parse_relative_time(published_text)
                
                # Filter by lookback window
                if not is_seeding and lookback_limit:
                    if pub_date.tzinfo is not None:
                        pub_date = pub_date.replace(tzinfo=None)
                    if pub_date < lookback_limit:
                        continue
                        
                # Limit count per source
                if len(feed_results) >= max_items:
                    break
                    
                feed_results.append({
                    "source": name,
                    "title": title,
                    "link": video_url,
                    "date": pub_date,
                    "text_to_search": f"{title} (Duration: {published_text}, Views: {views_text})".lower()
                })
                
            raw_results.extend(feed_results)
            logging.info(f"Successfully processed {len(feed_results)} video entries from {name}.")
            
        except Exception as e:
            logging.error(f"Failed to fetch or scrape YouTube source {name}: {e}")
            if failed_feeds is not None:
                failed_feeds.append(name)
                
    return raw_results
