import os
import requests
import feedparser
from datetime import datetime, timedelta
import time
import csv
import io
import json

# Target Feeds
# We removed brittle provincial feeds to focus purely on high-signal federal data and executive updates.
FEEDS = {
    "PMO_News": "https://www.pm.gc.ca/en/news.rss"
}

CANADABUYS_CKAN_API = "https://open.canada.ca/data/api/action/package_show?id=6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

KEYWORDS = ["grant", "stimulus", "incentive", "funding", "RFP", "tender", "economic support", "investment"]

DASHBOARD_URL = "https://emurira.github.io/canadian-grant-intelligence/"

def get_gemini_insight(content):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Insight generation skipped: GEMINI_API_KEY not found."
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    
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


def generate_linkedin_post(results):
    """Synthesize all daily findings into one LinkedIn-ready post."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not results:
        return None

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={api_key}"

    summaries = "\n".join(
        f"- {r['title']} (Source: {r['source']}, Link: {r['link']})"
        for r in results
    )

    prompt = f"""You are a professional LinkedIn content strategist for a Canadian business intelligence brand.

Write a single LinkedIn post (MAX 250 words) that summarizes today's Canadian government funding and procurement highlights. 

Rules:
- Open with a bold, attention-grabbing hook line (use an emoji at the start)
- Highlight the 2-3 most impactful opportunities from the list below
- For each highlight, include ONE actionable sentence about who should pay attention and why
- End with a call-to-action: "Full analysis with co-bidding strategies and strategic breakdowns 👉 {DASHBOARD_URL}"
- Close with exactly 5 relevant hashtags on their own line
- Do NOT use bullet points for the main body — use short paragraphs
- Tone: Authoritative but accessible. Think Bloomberg meets LinkedIn thought leadership.
- Do NOT wrap the post in markdown code fences or add a title

Today's opportunities:
{summaries}
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 429:
                wait_time = 10 * (attempt + 1)
                print(f"LinkedIn post: Rate limited. Waiting {wait_time}s (retry {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            data = response.json()
            time.sleep(4)

            if 'candidates' in data and data['candidates']:
                return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"LinkedIn post generation error: {e}")
            return None

    return None


def fetch_canadabuys_csvs():
    """
    Queries the official Open Government CKAN API to dynamically find and parse
    the CanadaBuys 'New' and 'Open' tender notice CSVs.
    """
    print("Fetching CanadaBuys metadata...")
    try:
        data = requests.get(CANADABUYS_CKAN_API, headers=HEADERS, timeout=30).json()
    except Exception as e:
        print(f"Failed to fetch CanadaBuys API: {e}")
        return []

    if not data.get("success"):
        print("CKAN API returned success=False")
        return []

    resources = data.get("result", {}).get("resources", [])
    new_url = None
    open_url = None

    for res in resources:
        name = res.get("name", "").lower()
        if "new tender notices" in name:
            new_url = res.get("url")
        elif "open tender notices" in name:
            open_url = res.get("url")

    tenders = []
    
    # Process New Tenders
    if new_url:
        print(f"Downloading New Tenders from: {new_url}")
        try:
            resp = requests.get(new_url, headers=HEADERS, timeout=60)
            resp.encoding = 'utf-8-sig'
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                # Extract clean data from CSV fields
                title = row.get("title-titre-eng", "")
                desc = row.get("tenderDescription-descriptionAppelOffres-eng", "")
                link = row.get("noticeURL-URLavis-eng", "")
                close_date = row.get("tenderClosingDate-appelOffresDateCloture", "")
                province = row.get("regionsOfDelivery-regionsLivraison-eng", "National")
                category = row.get("procurementCategory-categorieApprovisionnement", "Uncategorized")
                
                if title and link:
                    tenders.append({
                        "type": "New",
                        "title": title[:200], # Trim excessively long titles
                        "description": desc[:500] + "..." if len(desc) > 500 else desc,
                        "link": link,
                        "closing_date": close_date,
                        "province": province,
                        "category": category
                    })
        except Exception as e:
            print(f"Error parsing new tenders CSV: {e}")

    # Process Open Tenders (Limit to top 50 recently updated to save processing)
    if open_url:
        print(f"Downloading Open Tenders from: {open_url}")
        try:
            resp = requests.get(open_url, headers=HEADERS, timeout=60)
            resp.encoding = 'utf-8-sig'
            reader = csv.DictReader(io.StringIO(resp.text))
            
            # Sort open tenders by publication date or just grab the first 50
            # Usually the CSV is sorted by date descending.
            count = 0
            for row in reader:
                if count >= 50:
                    break
                    
                title = row.get("title-titre-eng", "")
                desc = row.get("tenderDescription-descriptionAppelOffres-eng", "")
                link = row.get("noticeURL-URLavis-eng", "")
                close_date = row.get("tenderClosingDate-appelOffresDateCloture", "")
                province = row.get("regionsOfDelivery-regionsLivraison-eng", "National")
                category = row.get("procurementCategory-categorieApprovisionnement", "Uncategorized")
                
                if title and link:
                    tenders.append({
                        "type": "Open",
                        "title": title[:200],
                        "description": desc[:500] + "..." if len(desc) > 500 else desc,
                        "link": link,
                        "closing_date": close_date,
                        "province": province,
                        "category": category
                    })
                    count += 1
        except Exception as e:
            print(f"Error parsing open tenders CSV: {e}")

    # Save to JSON for the UI to consume directly
    os.makedirs("data", exist_ok=True)
    with open("data/tenders.json", "w", encoding="utf-8") as f:
        json.dump(tenders, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(tenders)} CanadaBuys tenders to data/tenders.json")
    
    return tenders

def fetch_pmo_news():
    reports = []
    lookback_limit = datetime.now() - timedelta(hours=48)
    
    for name, url in FEEDS.items():
        print(f"Fetching PMO News from {url}...")
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            published = getattr(entry, 'published_parsed', None)
            if published:
                pub_date = datetime.fromtimestamp(time.mktime(published))
                if pub_date < lookback_limit:
                    continue
            
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
    os.makedirs("reports/linkedin", exist_ok=True)
    
    content = f"# Canadian Grant Intelligence Report - {date_str}\n\n"
    content += "Daily automated scan of federal, provincial, and municipal funding opportunities.\n\n"

    # Generate and insert LinkedIn post at the top
    print("Generating LinkedIn post summary...")
    linkedin_post = generate_linkedin_post(results)
    if linkedin_post:
        content += "---\n\n"
        content += "## 📋 Today's LinkedIn Post\n\n"
        content += "> *Copy-paste ready for LinkedIn. Full analysis below.*\n\n"
        content += linkedin_post + "\n\n"
        content += "---\n\n"

        # Write standalone LinkedIn post file
        with open("reports/linkedin/latest_post.md", "w", encoding="utf-8") as lf:
            lf.write(f"# LinkedIn Post - {date_str}\n\n")
            lf.write(linkedin_post + "\n")
        print("LinkedIn post saved to reports/linkedin/latest_post.md")
    else:
        print("LinkedIn post generation skipped or failed.")

    content += "## 📊 Detailed Analysis\n\n"

    for item in results:
        content += f"### {item['title']}\n"
        content += f"**Source:** {item['source']} | **Date:** {item['date']}\n\n"
        content += f"#### Gemini Insight\n{item['insight']}\n\n"
        content += f"[Link to Opportunity]({item['link']})\n\n"
        content += "---\n\n"
        
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Report generated: {filename}")

if __name__ == "__main__":
    # Fetch data
    tenders = fetch_canadabuys_csvs()
    pmo_reports = fetch_pmo_news()
    
    # Generate the markdown report for PMO news
    generate_markdown_report(pmo_reports)
