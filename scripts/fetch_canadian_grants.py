import os
import requests
import feedparser
from datetime import datetime, timedelta
import time
import csv
import io
import json
import html
from azure.storage.blob import BlobServiceClient, ContentSettings

def upload_to_azure(data, blob_name):
    """Uploads data to Azure Blob Storage using connection string from environment."""
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        print("AZURE_STORAGE_CONNECTION_STRING not found. Skipping Azure upload.")
        return False
    
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_name = "data"
        
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        # Prepare data for upload
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        
        # Set content type to application/json so browser renders/fetches it correctly
        content_settings = ContentSettings(content_type='application/json')
        
        print(f"Uploading {blob_name} to Azure container '{container_name}'...")
        blob_client.upload_blob(json_data, overwrite=True, content_settings=content_settings)
        print(f"Successfully uploaded {blob_name} to Azure.")
        return True
    except Exception as e:
        print(f"Failed to upload to Azure: {e}")
        return False

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
        return {"linkedin_hook": "", "strategic_value": "Insight generation skipped: GEMINI_API_KEY not found.", "co_bidding_opportunity": ""}
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    
    prompt = f"""
    Analyze the following Canadian government announcement/tender.
    You MUST respond with a raw JSON object and nothing else. No markdown formatting, no backticks.
    
    CRITICAL: If the content is just a routine schedule, placeholder, or lacks strategic business value, you MUST set the strategic_value field EXACTLY to "No insight available". Do not write anything else in that field.
    
    The JSON object must have exactly these three keys:
    "linkedin_hook": "A high-impact opening line to drive traffic (include an emoji).",
    "strategic_value": "Why this matters for Canadian businesses, highlighting new markets or investments.",
    "co_bidding_opportunity": "Identify if this favors consortia or B2B partnerships and why."
    
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
                text = data['candidates'][0]['content']['parts'][0]['text']
                # Clean up potential markdown code fences from the LLM response
                text = text.replace("```json", "").replace("```", "").strip()
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"linkedin_hook": "", "strategic_value": f"Failed to parse LLM JSON: {text}", "co_bidding_opportunity": ""}
            else:
                feedback = data.get('promptFeedback', {}).get('blockReason', 'Unknown reason')
                return {"linkedin_hook": "", "strategic_value": f"Insight generation blocked by safety filters: {feedback}", "co_bidding_opportunity": ""}
                
        except requests.exceptions.RequestException as e:
            try:
                error_details = response.json()
                err_msg = error_details.get('error', {}).get('message', str(e))
                return {"linkedin_hook": "", "strategic_value": f"Gemini API Error ({response.status_code}): {err_msg}", "co_bidding_opportunity": ""}
            except:
                return {"linkedin_hook": "", "strategic_value": f"Request error: {str(e)}", "co_bidding_opportunity": ""}
        except Exception as e:
            return {"linkedin_hook": "", "strategic_value": f"Insight error: {str(e)}", "co_bidding_opportunity": ""}
    
    return {"linkedin_hook": "", "strategic_value": "Gemini API Error: Rate limited after max retries.", "co_bidding_opportunity": ""}


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
                desc = html.unescape(row.get("tenderDescription-descriptionAppelOffres-eng", ""))
                link = row.get("noticeURL-URLavis-eng", "")
                close_date = row.get("tenderClosingDate-appelOffresDateCloture", "")
                province = row.get("regionsOfDelivery-regionsLivraison-eng", "").strip()
                category = row.get("procurementCategory-categorieApprovisionnement", "Uncategorized")
                
                # Province fallback
                if not province:
                    prov_keywords = {
                        "Ontario": ["ontario", "toronto", "ottawa"],
                        "British Columbia": ["british columbia", "vancouver", "victoria"],
                        "Alberta": ["alberta", "calgary", "edmonton"],
                        "Quebec": ["quebec", "québec", "montreal", "montréal"],
                        "Nova Scotia": ["nova scotia", "halifax"],
                        "New Brunswick": ["new brunswick"],
                        "Manitoba": ["manitoba", "winnipeg"],
                        "Saskatchewan": ["saskatchewan", "regina", "saskatoon"],
                        "PEI": ["prince edward island", "pei"],
                        "Newfoundland": ["newfoundland", "st. john's", "st johns"],
                        "National": ["national", "canada-wide", "federal"]
                    }
                    import re
                    text_to_search = f" {title} {desc} ".lower()
                    for prov_name, keywords in prov_keywords.items():
                        if any(re.search(rf"\b{re.escape(kw)}\b", text_to_search) for kw in keywords):
                            province = prov_name
                            break
                    if not province:
                        province = "National"
                        
                # Date filtering
                is_valid_date = True
                if close_date:
                    try:
                        dt = datetime.strptime(close_date[:10], "%Y-%m-%d")
                        now = datetime.now()
                        if dt < now - timedelta(days=1):
                            is_valid_date = False
                        if dt > now + timedelta(days=730):
                            is_valid_date = False
                    except:
                        pass
                
                if title and link and is_valid_date:
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
                desc = html.unescape(row.get("tenderDescription-descriptionAppelOffres-eng", ""))
                link = row.get("noticeURL-URLavis-eng", "")
                close_date = row.get("tenderClosingDate-appelOffresDateCloture", "")
                province = row.get("regionsOfDelivery-regionsLivraison-eng", "").strip()
                category = row.get("procurementCategory-categorieApprovisionnement", "Uncategorized")
                
                # Province fallback
                if not province:
                    prov_keywords = {
                        "Ontario": ["ontario", "toronto", "ottawa"],
                        "British Columbia": ["british columbia", "vancouver", "victoria"],
                        "Alberta": ["alberta", "calgary", "edmonton"],
                        "Quebec": ["quebec", "québec", "montreal", "montréal"],
                        "Nova Scotia": ["nova scotia", "halifax"],
                        "New Brunswick": ["new brunswick"],
                        "Manitoba": ["manitoba", "winnipeg"],
                        "Saskatchewan": ["saskatchewan", "regina", "saskatoon"],
                        "PEI": ["prince edward island", "pei"],
                        "Newfoundland": ["newfoundland", "st. john's", "st johns"],
                        "National": ["national", "canada-wide", "federal"]
                    }
                    import re
                    text_to_search = f" {title} {desc} ".lower()
                    for prov_name, keywords in prov_keywords.items():
                        if any(re.search(rf"\b{re.escape(kw)}\b", text_to_search) for kw in keywords):
                            province = prov_name
                            break
                    if not province:
                        province = "National"
                        
                # Date filtering
                is_valid_date = True
                if close_date:
                    try:
                        dt = datetime.strptime(close_date[:10], "%Y-%m-%d")
                        now = datetime.now()
                        if dt < now - timedelta(days=1):
                            is_valid_date = False
                        if dt > now + timedelta(days=730):
                            is_valid_date = False
                    except:
                        pass
                
                if title and link and is_valid_date:
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

    print(f"Parsed {len(tenders)} CanadaBuys tenders.")
    
    # Surgical Automation: Upload to Azure for the live dashboard
    upload_to_azure(tenders, "tenders.json")
    
    return tenders

def fetch_pmo_news(lookback_days=2):
    reports = []
    lookback_limit = datetime.now() - timedelta(days=lookback_days)
    print(f"PMO lookback window: {lookback_days} days (since {lookback_limit.strftime('%Y-%m-%d %H:%M')})")
    
    for name, url in FEEDS.items():
        print(f"Fetching PMO News from {url}...")
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            published = getattr(entry, 'published_parsed', None)
            if published:
                pub_date = datetime.fromtimestamp(time.mktime(published))
                if pub_date < lookback_limit:
                    continue
            
            text_to_search = (entry.title + " " + getattr(entry, 'summary', '')).lower()
            if any(kw in text_to_search for kw in KEYWORDS):
                print(f"Match found: {entry.title}")
                insight = get_gemini_insight(text_to_search)
                
                # Check for API failure or lack of value to prevent empty/useless reports
                strat_value = insight.get("strategic_value", "")
                if "API Error" in strat_value or "blocked" in strat_value or "not found" in strat_value or "No insight available" in strat_value or "Failed to parse" in strat_value:
                    print(f"Skipping due to lack of insight: {strat_value}")
                    continue
                    
                reports.append({
                    "source": name,
                    "title": entry.title,
                    "link": entry.link,
                    "date": pub_date.strftime("%Y-%m-%d"),
                    "insight": insight
                })
    
    return reports

def upload_pmo_json(results, linkedin_post_text):
    """Serialize PMO insights as structured JSON and upload to Azure Blob Storage."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    insights = []
    for item in results:
        insight_obj = item.get("insight", {})
        if not isinstance(insight_obj, dict):
            insight_obj = {"strategic_value": str(insight_obj)}
        
        insights.append({
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "date": item.get("date", ""),
            "link": item.get("link", ""),
            "linkedin_hook": insight_obj.get("linkedin_hook", ""),
            "strategic_value": insight_obj.get("strategic_value", ""),
            "co_bidding_opportunity": insight_obj.get("co_bidding_opportunity", "")
        })
    
    pmo_data = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "report_date": date_str,
        "linkedin_post": linkedin_post_text or "",
        "insights": insights
    }
    
    uploaded = upload_to_azure(pmo_data, "pmo_insights.json")
    if uploaded:
        print(f"PMO insights JSON uploaded to Azure ({len(insights)} insights).")
        # Archive a date-keyed snapshot so daily runs don't destroy history
        archive_name = f"pmo_insights_{date_str}.json"
        upload_to_azure(pmo_data, archive_name)
        print(f"Archived as {archive_name}.")
    else:
        print("PMO insights JSON upload to Azure failed or skipped.")


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

        # Write standalone LinkedIn post file for email digest
        with open("reports/linkedin/latest_post.md", "w", encoding="utf-8") as lf:
            lf.write(f"# LinkedIn Post - {date_str}\n\n")
            lf.write(linkedin_post + "\n")
        print("LinkedIn post saved to reports/linkedin/latest_post.md")
    else:
        print("LinkedIn post generation skipped or failed.")

    content += "## 📊 Detailed Analysis\n\n"

    for item in results:
        content += f"## {item['title']}\n"
        content += f"**Source:** {item['source']} | **Date:** {item['date']}\n\n"
        
        insight_obj = item['insight']
        if isinstance(insight_obj, dict):
            if insight_obj.get("linkedin_hook"):
                content += f"### 1. LinkedIn Hook:\n> {insight_obj['linkedin_hook']}\n\n"
            content += f"### 2. Strategic Value for Canadian Businesses:\n{insight_obj.get('strategic_value', 'No analysis available.')}\n\n"
            if insight_obj.get("co_bidding_opportunity"):
                content += f"### 3. Co-Bidding Opportunity:\n{insight_obj['co_bidding_opportunity']}\n\n"
        else:
            # Fallback if somehow a string was returned
            content += f"### Strategic Insight\n{insight_obj}\n\n"
            
        content += f"[Link to Opportunity]({item['link']})\n\n"
        content += "---\n\n"
        
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Report generated: {filename}")

    # Upload structured JSON to Azure for the dashboard
    upload_pmo_json(results, linkedin_post)


if __name__ == "__main__":
    # Lookback override for historical backfills (default: 2 days = 48h)
    lookback_days = int(os.getenv("SCRAPE_LOOKBACK_DAYS", "2"))
    
    # Fetch data
    tenders = fetch_canadabuys_csvs()
    pmo_reports = fetch_pmo_news(lookback_days=lookback_days)
    
    # Generate the markdown report for PMO news (also uploads JSON to Azure)
    generate_markdown_report(pmo_reports)
