import os
import requests
import feedparser
from datetime import datetime, timedelta
import time
import csv
import io
import json
import html
import asyncio
from playwright.async_api import async_playwright
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
        if isinstance(data, (dict, list)):
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            json_data = data
            
        # Set content type to application/json so browser renders/fetches it correctly
        content_settings = ContentSettings(content_type='application/json')
        
        print(f"Uploading {blob_name} to Azure container '{container_name}'...")
        blob_client.upload_blob(json_data, overwrite=True, content_settings=content_settings)
        print(f"Successfully uploaded {blob_name} to Azure.")
        return True
    except Exception as e:
        print(f"Failed to upload to Azure: {e}")
        return False

def download_blob(blob_name):
    """Downloads a blob from Azure Storage and returns its content."""
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        return None
    
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_name = "data"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        if not blob_client.exists():
            return None
            
        download_stream = blob_client.download_blob()
        return download_stream.readall().decode('utf-8')
    except Exception as e:
        print(f"Failed to download {blob_name} from Azure: {e}")
        return None

def upload_file_to_azure(file_path, blob_name, content_type='image/png'):
    """Uploads a binary file to Azure Blob Storage."""
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string or not os.path.exists(file_path):
        return False
    
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_name = "data"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        content_settings = ContentSettings(content_type=content_type)
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)
        print(f"Successfully uploaded file {blob_name} to Azure.")
        return True
    except Exception as e:
        print(f"Failed to upload file to Azure: {e}")
        return False

# Target Feeds
# We removed brittle provincial feeds to focus purely on high-signal federal data and executive updates.
# PMO maintains a stable RSS, but other departments require Playwright scraping due to JS-rendering and stale RSS feeds.
FEEDS = {
    "PMO_News": "https://www.pm.gc.ca/en/news.rss"
}

HTML_SOURCES = {
    "ISED_News": "https://ised-isde.canada.ca/site/ised/en/news",
    "Global_Affairs": "https://www.international.gc.ca/news-nouvelles/news-nouvelles.aspx?lang=eng",
    "Finance_Canada": "https://www.canada.ca/en/department-finance/news.html"
}

CANADABUYS_CKAN_API = "https://open.canada.ca/data/api/action/package_show?id=6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# High-Signal keywords for procurement/grant intelligence
KEYWORDS = [
    "grant", "stimulus", "incentive", "funding", "RFP", "tender", 
    "economic support", "investment", "artificial intelligence", "cloud",
    "digital transformation", "cybersecurity", "clean tech", "renewable",
    "indigenous", "sme", "small business", "innovation", "research",
    "infrastructure", "defense", "defence", "security", "quantum"
]

DASHBOARD_URL = "https://4mayAi.github.io/canadian-grant-intelligence/"

def get_strategic_priorities(news_results):
    """
    Analyzes latest PMO/department news to extract active federal strategic priorities.
    Returns a list of keywords/phrases to augment the CanadaBuys filter.
    """
    if not news_results:
        return []
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return []
        
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    
    news_titles = "\n".join([f"- {n['title']}" for n in news_results[:10]])
    
    prompt = f"""
    Analyze the following Canadian government news headlines.
    Extract exactly 10 high-signal, specific strategic priorities, project names, or policy anchors mentioned.
    
    Format: Return a raw JSON array of strings. No markdown.
    
    Headlines:
    {news_titles}
    """
    
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        response.raise_for_status()
        data = response.json()
        if 'candidates' in data and data['candidates']:
            text = data['candidates'][0]['content']['parts'][0]['text']
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
    except Exception as e:
        print(f"Strategic priority extraction failed: {e}")
    return []

def get_gemini_insight(content, strategic_context=None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"linkedin_hook": "", "strategic_value": "Insight generation skipped: GEMINI_API_KEY not found.", "co_bidding_opportunity": ""}
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    
    context_str = ""
    if strategic_context:
        context_str = f"\nCURRENT STRATEGIC PRIORITIES:\n- " + "\n- ".join(strategic_context)
    
    prompt = f"""
    You are a Senior Strategic Advisor for B2B Sales Executives and Bid Managers in Canada.
    Analyze the following Canadian government announcement/tender in the context of the current federal strategy.{context_str}
    
    You MUST respond with a raw JSON object and nothing else. Do not wrap the JSON in markdown code blocks.
    
    CRITICAL: If the content is just a routine schedule, placeholder, or lacks strategic business value, you MUST set the strategic_value field EXACTLY to "No insight available". Do not write anything else in that field.
    
    The JSON object must have exactly these three keys. For "strategic_value" and "co_bidding_opportunity", use markdown formatting (like bullet points) inside the JSON string to provide structured, consultative depth:
    "linkedin_hook": "A 'Stop-the-scroll' high-impact opening line to drive traffic (include an emoji).",
    "strategic_value": "Consultative analysis of why this matters. Use 3-5 markdown bullet points detailing sector impact, technical anchors, and economic signals. Connect it directly to the PM's strategy if relevant.",
    "co_bidding_opportunity": "Identify the technical or operational gap that requires a consortium. Provide actionable intelligence on why B2B partnerships are favored here (use bullet points if needed)."
    
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
            
            if response.status_code in (429, 503):
                wait_time = 30 * (attempt + 1)
                print(f"Rate limited ({response.status_code}). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
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


def get_hero_hook(tenders, news_results):
    """Generate a single high-impact 'Hero Hook' for the dashboard header."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "mayAi | Delivering Golden Opportunities Daily"

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={api_key}"

    # Provide context for the hook
    tender_context = "\n".join([f"- {t['title']} ({t.get('category', 'Uncategorized')})" for t in tenders[:5]])
    news_context = "\n".join([f"- {n['title']}" for n in (news_results or [])[:3]])

    prompt = f"""You are a high-level executive intelligence advisor.
Generate a single, powerful, one-sentence "Hero Hook" (MAX 20 words) that summarizes the most important theme in today's Canadian government procurement and policy updates.

Use a professional but catchy tone (Bloomberg style). Include one relevant emoji.
The hook will be the main headline on an executive dashboard.

Context:
Tenders:
{tender_context}

News:
{news_context}
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0]['content']['parts'][0]['text'].strip().strip('"')
    except Exception as e:
        print(f"Hero hook generation failed: {e}")
    
    return "mayAi | Delivering Golden Opportunities Daily"


def calculate_kpis(tenders):
    """Pre-calculate high-level KPIs for the dashboard."""
    now = datetime.now()
    new_today = len([t for t in tenders if t.get('type') == 'New'])
    
    closing_week = 0
    categories = {}
    
    for t in tenders:
        # Closing this week
        if t.get('closing_date'):
            try:
                dt = datetime.strptime(t['closing_date'][:10], "%Y-%m-%d")
                if 0 <= (dt - now).days <= 7:
                    closing_week += 1
            except:
                pass
        
        # Category tally
        cat = t.get('category', 'Uncategorized').replace('*', '').strip()
        categories[cat] = categories.get(cat, 0) + 1
    
    # Find top category
    top_cat_name = "Mixed Sectors"
    if categories:
        sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        top_cat = sorted_cats[0]
        percentage = int((top_cat[1] / len(tenders)) * 100)
        top_cat_name = f"{top_cat[0]} ({percentage}%)"

    return {
        "total_active": len(tenders),
        "new_today": new_today,
        "closing_this_week": closing_week,
        "top_category": top_cat_name,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")
    }


def generate_linkedin_post(results, tender_summaries=None):
    """Synthesize all daily findings into one LinkedIn-ready post.
    
    Args:
        results: PMO/department insight reports
        tender_summaries: List of headline tender summary strings from CanadaBuys
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or (not results and not tender_summaries):
        return None

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={api_key}"

    summaries = "\n".join(
        f"- {r['title']} (Source: {r['source']}, Link: {r['link']})"
        for r in (results or [])
    )

    # Build tender context section for the prompt
    tender_context = ""
    if tender_summaries:
        tender_lines = "\n".join(f"- {s}" for s in tender_summaries)
        tender_context = f"""\n\nToday's Active Federal Tenders (from CanadaBuys):
{tender_lines}

IMPORTANT: Mention at least one specific active tender by name in the post body to drive procurement professionals to the dashboard."""

    prompt = f"""You are a professional LinkedIn content strategist for a Canadian business intelligence brand called mayAi.

Write a single LinkedIn post (MAX 250 words) that summarizes today's Canadian government funding and procurement highlights. 

Rules:
- Open with a bold, attention-grabbing hook line (use an emoji at the start)
- Bridge political/policy context with actionable procurement opportunities
- Highlight the 2-3 most impactful items from BOTH the news AND the active tenders below
- For each highlight, include ONE actionable sentence about who should pay attention and why
- End with a call-to-action: "Full dashboard with filters and strategic analysis 👉 {DASHBOARD_URL}"
- Close with exactly 5 relevant hashtags on their own line
- Do NOT use bullet points for the main body — use short paragraphs
- Tone: Authoritative but accessible. Think Bloomberg meets LinkedIn thought leadership.
- Do NOT wrap the post in markdown code fences or add a title

Today's policy & news highlights:
{summaries}
{tender_context}
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


def fetch_canadabuys_csvs(pulse_only=False, dynamic_keywords=None):
    """
    Queries the official Open Government CKAN API to dynamically find and parse
    the CanadaBuys 'New' and 'Open' tender notice CSVs.
    
    Args:
        pulse_only (bool): If True, only fetch the 'New' tenders (smaller payload).
                           If False, fetch both, including the full 17k+ 'Open' set.
        dynamic_keywords (list): Optional list of themes extracted from recent PMO news.
    """
    effective_keywords = KEYWORDS + (dynamic_keywords or [])
    print(f"Fetching CanadaBuys metadata (Mode: {'PULSE' if pulse_only else 'DEEP DIVE'})...")
    if dynamic_keywords:
        print(f"Applying {len(dynamic_keywords)} dynamic strategic filters: {', '.join(dynamic_keywords[:5])}...")
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

    def clean_label(text):
        """Clean category labels and other generic text fields."""
        if not text: return ""
        text = text.replace('\n', ' ').replace('\r', '').strip()
        text = text.lstrip('*').strip()
        return text

    # --- Canonical Province/Territory Whitelist ---
    VALID_PROVINCES = {
        "Alberta", "British Columbia", "Manitoba", "New Brunswick",
        "Newfoundland and Labrador", "Nova Scotia", "Ontario", "Prince Edward Island",
        "Quebec", "Saskatchewan", "Northwest Territories", "Nunavut", "Yukon",
        "National", "NCR (Ottawa/Gatineau)", "Multiple Provinces"
    }

    # City / Base / Region → Province mapping
    LOCATION_TO_PROVINCE = {
        "ottawa": "Ontario", "toronto": "Ontario", "kingston": "Ontario",
        "london": "Ontario", "hamilton": "Ontario", "thunder bay": "Ontario",
        "north bay": "Ontario", "petawawa": "Ontario", "trenton": "Ontario",
        "borden": "Ontario", "meaford": "Ontario", "barrie": "Ontario",
        "kitchener": "Ontario", "waterloo": "Ontario", "sudbury": "Ontario",
        "windsor": "Ontario", "brampton": "Ontario", "mississauga": "Ontario",
        "montreal": "Quebec", "montréal": "Quebec", "quebec city": "Quebec",
        "gatineau": "Quebec", "vancouver": "British Columbia", "victoria": "British Columbia",
        "edmonton": "Alberta", "calgary": "Alberta", "halifax": "Nova Scotia",
        "winnipeg": "Manitoba", "regina": "Saskatchewan", "saskatoon": "Saskatchewan",
        "st. john's": "Newfoundland and Labrador", "st johns": "Newfoundland and Labrador",
        "whitehorse": "Yukon", "yellowknife": "Northwest Territories", "iqaluit": "Nunavut"
    }

    PROVINCE_ABBREV = {
        "National": "NAT", "NCR (Ottawa/Gatineau)": "NCR", "Ontario": "ON",
        "British Columbia": "BC", "Newfoundland and Labrador": "NL",
        "Prince Edward Island": "PE", "Northwest Territories": "NT",
        "New Brunswick": "NB", "Nova Scotia": "NS", "Quebec": "QC",
        "Alberta": "AB", "Manitoba": "MB", "Saskatchewan": "SK",
        "Nunavut": "NU", "Yukon": "YT", "Multiple Provinces": "MULT"
    }

    def normalize_province(raw_value):
        if not raw_value: return "National"
        text = raw_value.replace('\n', ' ').replace('\r', '').strip().replace('*', '').strip()
        text_lower = text.lower()
        
        for valid in VALID_PROVINCES:
            if text_lower == valid.lower(): return valid
        
        if text_lower in ("canada", "federal", "canada-wide"): return "National"
        if "national capital" in text_lower or text_lower == "ncr": return "NCR (Ottawa/Gatineau)"
        
        for city, prov in LOCATION_TO_PROVINCE.items():
            if city in text_lower: return prov
            
        return "National"

    tenders = []
    import re
    
    # Differential Tracking: Load seen tenders from Azure to prevent redundant processing
    print("Loading historical tender data for differential tracking...")
    historical_raw = download_blob("tenders.json")
    seen_links = set()
    existing_tenders = []
    if historical_raw:
        try:
            existing_tenders = json.loads(historical_raw)
            seen_links = {t['link'] for t in existing_tenders}
            print(f"Loaded {len(seen_links)} existing tenders from Azure.")
        except:
            print("Failed to parse historical tenders. starting fresh.")

    # Process Tenders (New/Open)
    urls_to_process = []
    if new_url:
        urls_to_process.append(("New", new_url))
    if open_url and not pulse_only:
        urls_to_process.append(("Open", open_url))

    for t_type, url in urls_to_process:
        print(f"Downloading {t_type} Tenders from: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=120)
            resp.encoding = 'utf-8-sig'
            reader = csv.DictReader(io.StringIO(resp.text))
            
            processed_count = 0
            match_count = 0
            
            for row in reader:
                processed_count += 1
                link = row.get("noticeURL-URLavis-eng", "")
                
                # Surgical Efficiency: Skip if already seen
                if link in seen_links:
                    continue
                    
                title = row.get("title-titre-eng", "")
                desc = html.unescape(row.get("tenderDescription-descriptionAppelOffres-eng", ""))
                
                # SURGICAL FILTERING: Only proceed if high-signal keywords match
                text_to_search = (title + " " + desc).lower()
                if not any(kw.lower() in text_to_search for kw in effective_keywords):
                    continue

                close_date = row.get("tenderClosingDate-appelOffresDateCloture", "")
                pub_date = row.get("publicationDate-datePublication", "")
                amend_date = row.get("amendmentDate-dateModification", "")
                province = normalize_province(row.get("regionsOfDelivery-regionsLivraison-eng", ""))
                category = clean_label(row.get("procurementCategory-categorieApprovisionnement", "Uncategorized"))
                
                # Date filtering (skip expired)
                is_valid_date = True
                if close_date:
                    try:
                        dt = datetime.strptime(close_date[:10], "%Y-%m-%d")
                        if dt < datetime.now() - timedelta(days=1):
                            is_valid_date = False
                    except:
                        pass
                
                if title and link and is_valid_date:
                    if re.search(r'\bapn\b|\badvance procurement notice\b|\bpre-solicitation\b', text_to_search):
                        continue
                    
                    tenders.append({
                        "type": t_type,
                        "title": title[:200],
                        "description": desc[:500] + "..." if len(desc) > 500 else desc,
                        "link": link,
                        "closing_date": close_date,
                        "publication_date": pub_date or amend_date,
                        "province": province,
                        "province_abbrev": PROVINCE_ABBREV.get(province, "NAT"),
                        "category": category
                    })
                    seen_links.add(link)
                    match_count += 1
            
            print(f"Processed {processed_count} {t_type} rows. Found {match_count} high-signal matches.")
        except Exception as e:
            print(f"Error parsing {t_type} tenders CSV: {e}")

    # Merge new matches with existing database
    all_tenders = existing_tenders + tenders
    
    # Final date-based cleanup (remove expired items from the persistent list)
    now = datetime.now()
    active_tenders = []
    for t in all_tenders:
        try:
            if t.get('closing_date'):
                dt = datetime.strptime(t['closing_date'][:10], "%Y-%m-%d")
                if dt >= now - timedelta(days=1):
                    active_tenders.append(t)
            else:
                active_tenders.append(t) # Keep if no date
        except:
            active_tenders.append(t)

    print(f"Total active tenders in database: {len(active_tenders)} (Merged {len(tenders)} new).")
    
    # Upload updated master list to Azure
    upload_to_azure(active_tenders, "tenders.json")
    
    return active_tenders


def select_headline_tenders(tenders, max_count=3):
    """Select the most LinkedIn-worthy tenders for the daily post.
    
    Priority: New tenders first, then by closing date urgency,
    filtered to high-value keywords.
    """
    if not tenders:
        return []
    
    high_value_keywords = [
        "rfp", "investment", "infrastructure", "innovation", "technology",
        "construction", "consulting", "defence", "security", "health",
        "environmental", "energy", "digital", "cloud", "services"
    ]
    
    scored = []
    for t in tenders:
        score = 0
        title_lower = t['title'].lower()
        desc_lower = (t.get('description', '') or '').lower()
        
        # New tenders get priority (published today)
        if t.get('type') == 'New':
            score += 10
        
        # Keyword relevance
        for kw in high_value_keywords:
            if kw in title_lower or kw in desc_lower:
                score += 1
        
        # Actionable closing window (14-60 days)
        if t.get('closing_date'):
            try:
                close_dt = datetime.strptime(t['closing_date'][:10], "%Y-%m-%d")
                days_left = (close_dt - datetime.now()).days
                if 14 <= days_left <= 60:
                    score += 5
                elif 0 <= days_left < 14:
                    score += 3  # Urgent but may be too late for some
            except:
                pass
        
        scored.append((score, t))
    
    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    
    summaries = []
    for _, t in scored[:max_count]:
        close_info = ""
        if t.get('closing_date'):
            try:
                close_dt = datetime.strptime(t['closing_date'][:10], "%Y-%m-%d")
                close_info = f", closing {close_dt.strftime('%b %d')}"
            except:
                pass
        cat = t.get('category', '').replace('*', '').strip()
        summaries.append(f"{t['title']}{close_info} — {cat}")
    
    return summaries

async def scrape_department_news_playwright(url, source_name):
    """Uses Playwright to extract news links from JS-rendered department pages."""
    print(f"Scraping JS-rendered news from {url} using Playwright...")
    results = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Universal extraction heuristic for government news portals
            items = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll('a'));
                const results = [];
                links.forEach(a => {
                    const href = a.href || '';
                    const title = a.innerText.trim();
                    if (title.length > 20 && (href.includes('/news') || href.includes('news-releases') || href.includes('/news-nouvelles/') || href.includes('article'))) {
                        if (!results.some(r => r.link === href)) {
                            results.push({title: title, link: href});
                        }
                    }
                });
                return results.slice(0, 15);
            }''')
            
            for item in items:
                results.append({
                    "title": item['title'],
                    "link": item['link'],
                    "source": source_name,
                    "published_parsed": time.gmtime()
                })
            
            await browser.close()
    except Exception as e:
        print(f"Playwright scraping failed for {source_name}: {e}")
    return results

def fetch_pmo_news(lookback_days=2, strategic_priorities=None, max_items=15):
    reports = []
    lookback_limit = None
    is_seeding = (lookback_days is None)
    
    if not is_seeding:
        lookback_limit = datetime.now() - timedelta(days=lookback_days)
        print(f"PMO lookback window: {lookback_days} days (since {lookback_limit.strftime('%Y-%m-%d %H:%M')})")
    else:
        print(f"PMO strategy seeding: Collecting last {max_items} headlines (no Gemini calls).")
    
    # 1. Process standard stable RSS Feeds (e.g. PMO)
    for name, url in FEEDS.items():
        print(f"Fetching PMO News from {url}...")
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            published = getattr(entry, 'published_parsed', None)
            pub_date = datetime.now()
            if published and lookback_limit:
                pub_date = datetime.fromtimestamp(time.mktime(published))
                if pub_date < lookback_limit:
                    continue
            
            # Limit count per feed if we are in strategy seeding mode
            if is_seeding and len([r for r in reports if r['source'] == name]) >= max_items:
                break
            
            text_to_search = (entry.title + " " + getattr(entry, 'summary', '')).lower()
            
            if is_seeding:
                # SEEDING MODE: Just collect headlines — NO Gemini calls
                print(f"Seed collected: {entry.title}")
                reports.append({
                    "source": name,
                    "title": entry.title,
                    "link": entry.link,
                    "date": pub_date.strftime("%Y-%m-%d"),
                    "insight": {}  # Empty — seeding doesn't need insights
                })
            elif any(kw.lower() in text_to_search for kw in KEYWORDS):
                # REPORTING MODE: Keyword filter + full Gemini insight generation
                print(f"Match found: {entry.title}")
                insight = get_gemini_insight(text_to_search, strategic_context=strategic_priorities)
                
                # Check for API failure or lack of value
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

    # 2. Process JS-rendered pages via Playwright
    scraped_items = []
    for name, url in HTML_SOURCES.items():
        try:
            items = asyncio.run(scrape_department_news_playwright(url, name))
            scraped_items.extend(items)
        except Exception as e:
            print(f"Error executing asyncio loop for {name}: {e}")

    for entry in scraped_items:
        # Date logic for Playwright (default to now if unknown)
        pub_date = datetime.now()
        if lookback_limit:
            # We don't have a precise date from Playwright usually, so we assume today
            # But if it's already in the past relative to the limit, we'd skip (not applicable for today)
            pass

        # Limit count per source if in strategy seeding mode
        if is_seeding and len([r for r in reports if r['source'] == entry['source']]) >= max_items:
            continue

        text_to_search = entry['title'].lower()
        
        # Filter out navigation junk from Playwright scrapes
        junk_patterns = ["top of page", "skip to", "archived news", "all department"]
        if any(junk in text_to_search for junk in junk_patterns):
            continue
        
        if is_seeding:
            # SEEDING MODE: Just collect headlines — NO Gemini calls
            print(f"Seed collected via Playwright: {entry['title']}")
            reports.append({
                "source": entry['source'],
                "title": entry['title'],
                "link": entry['link'],
                "date": datetime.now().strftime("%Y-%m-%d"),
                "insight": {}
            })
        elif any(kw.lower() in text_to_search for kw in KEYWORDS):
            # REPORTING MODE: Keyword filter + full Gemini insight generation
            print(f"Match found via Playwright: {entry['title']}")
            insight = get_gemini_insight(text_to_search, strategic_context=strategic_priorities)
            strat_value = insight.get("strategic_value", "")
            if "API Error" in strat_value or "blocked" in strat_value or "not found" in strat_value or "No insight available" in strat_value or "Failed to parse" in strat_value:
                print(f"Skipping due to lack of insight: {strat_value}")
                continue
                
            reports.append({
                "source": entry['source'],
                "title": entry['title'],
                "link": entry['link'],
                "date": datetime.now().strftime("%Y-%m-%d"),
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


def generate_markdown_report(results, headline_tenders=None):
    if not results and not headline_tenders:
        print("No new data found to report.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"reports/grants/canadian_grants_{date_str}.md"
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    os.makedirs("reports/linkedin", exist_ok=True)
    
    content = f"# mayAi | Canadian Grant Intelligence Report - {date_str}\n\n"
    content += "Daily automated scan of federal, provincial, and municipal 'Golden Opportunity' funding.\n\n"

    # Generate and insert LinkedIn post at the top
    print("Generating LinkedIn post summary...")
    linkedin_post = generate_linkedin_post(results, tender_summaries=headline_tenders)
    if linkedin_post:
        content += "---\n\n"
        content += "## 📋 Today's LinkedIn Post\n\n"
        content += "> *Copy-paste ready for LinkedIn. Full analysis below.*\n\n"
        content += linkedin_post + "\n\n"
        content += "---\n\n"

        with open("reports/linkedin/latest_post.md", "w", encoding="utf-8") as lf:
            lf.write(f"# LinkedIn Post - {date_str}\n\n")
            lf.write(linkedin_post + "\n")
        print("LinkedIn post saved to reports/linkedin/latest_post.md")

    if headline_tenders:
        content += "## 🎯 Headline Procurement Opportunities\n\n"
        content += "These high-value tenders represent strategic entry points for Canadian businesses:\n\n"
        for ht in headline_tenders:
            content += f"- {ht}\n"
        content += "\n---\n\n"

    content += "## 📊 Detailed Strategic Analysis\n\n"
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
            content += f"### Strategic Insight\n{insight_obj}\n\n"
            
        content += f"[Link to Opportunity]({item['link']})\n\n"
        content += "---\n\n"
        
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Report generated: {filename}")

    upload_pmo_json(results, linkedin_post)
    return linkedin_post


if __name__ == "__main__":
    # 1. Environment-driven run mode (PULSE or DEEP_DIVE)
    run_type = os.getenv("RUN_TYPE", "DEEP_DIVE").upper()
    pulse_only = (run_type == "PULSE")
    lookback_days = int(os.getenv("SCRAPE_LOOKBACK_DAYS", "2"))
    
    # 2. STRATEGY FIRST: Fetch PMO/department news to identify current priorities
    pmo_reports = []
    dynamic_priorities = []
    if not pulse_only:
        print("Strategy Phase: Extracting federal priorities from latest news...")
        # SEEDING: Fetch last 15 releases regardless of date to ensure filter is always primed
        raw_news = fetch_pmo_news(lookback_days=None, max_items=15)
        dynamic_priorities = get_strategic_priorities(raw_news)
        
        # Cooldown: Let Gemini rate limiter reset before reporting phase
        if dynamic_priorities:
            print(f"Extracted {len(dynamic_priorities)} strategic priorities. Cooling down 15s before reporting phase...")
            time.sleep(15)
        
        # REPORTING: Fetch news within actual lookback window for dashboard display
        pmo_reports = fetch_pmo_news(lookback_days=lookback_days, strategic_priorities=dynamic_priorities)
    else:
        print("Pulse mode: Skipping strategic context extraction.")

    # 3. Fetch CanadaBuys tenders using augmented keyword list
    tenders = fetch_canadabuys_csvs(pulse_only=pulse_only, dynamic_keywords=dynamic_priorities)
    
    # 4. Select headline tenders for LinkedIn synthesis
    headline_tenders = select_headline_tenders(tenders, max_count=3)
    if headline_tenders:
        print(f"Selected {len(headline_tenders)} headline tenders for LinkedIn.")
    
    # 5. Calculate Dashboard KPIs and Hero Hook
    print("Calculating Dashboard Intelligence...")
    kpis = calculate_kpis(tenders)
    hero_hook = get_hero_hook(tenders, pmo_reports)
    kpis["hero_hook"] = hero_hook
    
    # Upload KPIs to Azure
    upload_to_azure(kpis, "kpis.json")
    print(f"Dashboard KPIs uploaded: {kpis['total_active']} active tenders.")

    # 7. Generate reports (only if we have new data or in deep dive)
    linkedin_post = ""
    if not pulse_only or tenders:
        linkedin_post = generate_markdown_report(pmo_reports, headline_tenders=headline_tenders)
    
    # 8. Social Media Card: Prefer tender-focused hook over PMO-based hook
    if not pulse_only:
        try:
            import subprocess
            
            # Prefer a tender-based hook for the social card
            if headline_tenders:
                top_hook = f"🇨🇦 {len(tenders)} active federal tenders — {headline_tenders[0].split(' — ')[0]}"
                clean_category = "Federal Procurement Intelligence"
            elif pmo_reports:
                top_item = pmo_reports[0]
                top_hook = top_item['insight'].get('linkedin_hook', 'mayAi | Golden Opportunities')
                raw_category = top_item['insight'].get('strategic_value', 'Executive Insight').split('\n')[0].lstrip('- ').strip()
                clean_category = raw_category[:40] if len(raw_category) > 5 else "Executive Intelligence Report"
            else:
                top_hook = "mayAi | Golden Opportunities"
                clean_category = "Canadian Grant Intelligence"

            print(f"Generating Social Media Card for: {top_hook}")
            subprocess.run([
                "python", "scripts/generate_social_card.py", 
                top_hook, 
                clean_category, 
                "reports/linkedin/social_card.png"
            ], check=True)
            
            # Upload to Azure
            upload_file_to_azure("reports/linkedin/social_card.png", "latest_social_card.png")
            
            # Archive with timestamp
            date_str = datetime.now().strftime("%Y-%m-%d")
            upload_file_to_azure("reports/linkedin/social_card.png", f"social_card_{date_str}.png")
            
        except Exception as e:
            print(f"Social card automation skipped or failed: {e}")

    print("Daily intelligence cycle complete.")
