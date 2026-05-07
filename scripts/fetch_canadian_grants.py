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
    "PMO_News": "https://www.pm.gc.ca/en/news.rss"
}

KEYWORDS = ["grant", "stimulus", "incentive", "funding", "RFP", "tender", "economic support", "investment"]

def get_gemini_insight(content):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Insight generation skipped: GEMINI_API_KEY not found."
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    
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
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code != 200:
            print(f"ERROR: Gemini API returned {response.status_code}: {response.text}")
        response.raise_for_status()
        data = response.json()
        
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0]['content']['parts'][0]['text']
        else:
            feedback = data.get('promptFeedback', {}).get('blockReason', 'Unknown reason')
            return f"Insight generation blocked by safety filters: {feedback}"
            
    except requests.exceptions.RequestException as e:
        try:
            error_details = response.json()
            err_msg = error_details.get('error', {}).get('message', str(e))
            print(f"ERROR: {err_msg}")
            return f"Gemini API Error ({response.status_code}): {err_msg}"
        except:
            print(f"ERROR: Request failed: {str(e)}")
            return f"Request error: {str(e)}"
    except Exception as e:
        print(f"ERROR: Unexpected error: {str(e)}")
        return f"Insight error: {str(e)}"

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

def generate_markdown_report(reports):
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"reports/grants/daily_grants_{today}.md"
    
    content = f"# Canadian Grant Intelligence Report - {today}\n\n"
    if not reports:
        content += "No high-impact funding or stimulus signals detected in the last 48 hours."
    else:
        for r in reports:
            content += f"## [{r['source']}] {r['title']}\n"
            content += f"- **Date:** {r['date']}\n"
            content += f"- **Link:** [View Official Announcement]({r['link']})\n\n"
            content += f"### AI Synthesis & LinkedIn Hooks\n{r['insight']}\n\n"
            content += "---\n\n"
            
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Report generated: {filename}")

if __name__ == "__main__":
    results = fetch_feed_data()
    generate_markdown_report(results)
