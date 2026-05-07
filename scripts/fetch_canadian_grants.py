import os
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

# Target Feeds
FEEDS = {
    "CanadaBuys": "https://canadabuys.canada.ca/en/tender-opportunities/rss",
    "ISED": "https://www.canada.ca/en/innovation-science-economic-development/news.rss",
    "Finance_Canada": "https://www.canada.ca/en/department-finance/news.rss",
    "PMO_News": "https://www.pm.gc.ca/en/news.rss",
    "Ontario_News": "https://news.ontario.ca/newsroom/en/rss/allnews.rss",
    "BC_News": "https://news.gov.bc.ca/feed",
    "PHAC_Updates": "https://www.canada.ca/content/dam/phac-aspc/rss/new-eng.xml",
    "Toronto_News": "https://wx.toronto.ca/inter/it/newsrel.nsf/rss.xml",
    "Vancouver_News": "https://vancouver.ca/news-calendar/rss.aspx",
    "Calgary_News": "https://newsroom.calgary.ca/rss/"
}

KEYWORDS = ["grant", "stimulus", "incentive", "funding", "RFP", "tender", "economic support", "investment"]

def get_gemini_insight(content):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Insight generation skipped: GEMINI_API_KEY not found."
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent?key={api_key}"
    
    prompt = f"""
    Analyze the following Canadian government announcement/tender and provide:
    1. A 'LinkedIn Hook': A high-impact opening line to drive traffic.
    2. Strategic Value: Why this matters for Canadian businesses.
    3. Co-Bidding Opportunity: Identify if this RFP/grant favors consortia or B2B partnerships.
    
    Content: {content[:3000]}
    """
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 429:
                wait_time = 10 * (attempt + 1)
                print(f"Rate limited (429). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            data = response.json()
            
            # Rate limit protection between successful calls
            time.sleep(4)
            
            if 'candidates' in data and data['candidates']:
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                feedback = data.get('promptFeedback', {}).get('blockReason', 'Unknown reason')
                return f"Insight generation blocked by safety filters: {feedback}"
                
        except requests.exceptions.RequestException as e:
            try:
                error_details = response.json()
                err_msg = error_details.get('error', {}).get('message', str(e))
                return f"Gemini API Error ({response.status_code}): {err_msg}"
            except:
                return f"Request error: {str(e)}"
        except Exception as e:
            return f"Insight error: {str(e)}"
    
    return "Gemini API Error: Rate limited after max retries."

def fetch_feed_data():
    reports = []
    lookback_limit = datetime.now() - timedelta(hours=48)
    
    for name, url in FEEDS.items():
        print(f"Fetching {name}...")
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            # Check date
            published = getattr(entry, 'published_parsed', None)
            if published:
                pub_date = datetime.fromtimestamp(time.mktime(published))
                if pub_date < lookback_limit:
                    continue
            
            # Check keywords
            text_to_scan = (entry.title + " " + getattr(entry, 'summary', '')).lower()
            if any(kw in text_to_scan for kw in KEYWORDS):
                print(f"Match found: {entry.title}")
                insight = get_gemini_insight(text_to_scan)
                reports.append({
                    "source": name,
                    "title": entry.title,
                    "link": entry.link,
                    "date": pub_date.strftime("%Y-%m-%d"),
                    "insight": insight
                })
    
    return reports

def generate_markdown_report(results):
    if not results:
        print("No new grants/tenders found.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"reports/grants/canadian_grants_{date_str}.md"
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    content = f"# Canadian Grant Intelligence Report - {date_str}\n\n"
    content += "Daily automated scan of federal funding and procurement opportunities.\n\n"
    
    for item in results:
        content += f"## {item['title']}\n"
        content += f"**Source:** {item['source']} | **Date:** {item['date']}\n\n"
        content += f"### Gemini Insight\n{item['insight']}\n\n"
        content += f"[Link to Opportunity]({item['link']})\n\n"
        content += "---\n\n"
        
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Report generated: {filename}")

if __name__ == "__main__":
    results = fetch_feed_data()
    generate_markdown_report(results)
