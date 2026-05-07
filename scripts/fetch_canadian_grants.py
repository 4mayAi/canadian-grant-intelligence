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

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    prompt = f"""
        Analyze the following Canadian government announcement and provide:
            1. A concise summary (1-2 sentences).
                2. A 'LinkedIn Hook' - a compelling insight for Canadian business owners or investors.
                    3. Credibility Score (1-10) based on source reliability.

                            Content: {content[:4000]}
                                """

    payload = {
                "contents": [{
                                "parts": [{"text": prompt}]
                }]
    }

    try:
                response = requests.post(url, json=payload, timeout=30)
                data = response.json()
                if 'candidates' in data and len(data['candidates']) > 0:
                                return data['candidates'][0]['content']['parts'][0]['text']
    else:
            return f"Insight error: Unexpected API response format. Response: {data}"
    except Exception as e:
        return f"Insight error: {e}"

def scrape():
        print(f"Starting scrape at {datetime.now()}")
        all_items = []

    for name, url in FEEDS.items():
                print(f"Fetching {name}...")
                feed = feedparser.parse(url)
                for entry in feed.entries:
                                published = getattr(entry, 'published_parsed', None)
                                if published:
                                                    pub_date = datetime(*published[:6])
                                                    if datetime.now() - pub_date > timedelta(days=1):
                                                                            continue

                                                text_to_search = (entry.title + " " + getattr(entry, 'summary', '')).lower()
                                if any(kw.lower() in text_to_search for kw in KEYWORDS):
                                                    insight = get_gemini_insight(entry.title + " " + getattr(entry, 'summary', ''))
                                                    all_items.append({
                                                        "source": name,
                                                        "title": entry.title,
                                                        "link": entry.link,
                                                        "date": pub_date.strftime("%Y-%m-%d") if published else "N/A",
                                                        "insight": insight
                                                    })

                        if not all_items:
                                    report_content = f"# Canadian Grant Intelligence Report - {datetime.now().strftime('%Y-%m-%d')}\n\nNo new grants or relevant announcements found in the last 24 hours."
else:
        report_content = f"# Canadian Grant Intelligence Report - {datetime.now().strftime('%Y-%m-%d')}\n\n"
        for item in all_items:
                        report_content += f"## [{item['source']}] {item['title']}\n"
                        report_content += f"- **Date**: {item['date']}\n"
                        report_content += f"- **Link**: [View Official Announcement]({item['link']})\n"
                        report_content += f"- **AI Synthesis & LinkedIn Hooks**:\n{item['insight']}\n\n"
                        report_content += "---\n\n"

    os.makedirs("reports/grants", exist_ok=True)
    filename = f"reports/grants/daily_grants_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, "w", encoding="utf-8") as f:
                f.write(report_content)
    print(f"Report generated: {filename}")

if __name__ == '__main__':
        scrape()
