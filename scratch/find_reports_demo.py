import urllib.parse
import xml.etree.ElementTree as ET
import requests
import re
import sys

def is_high_value_report(url: str, title: str) -> bool:
    url_lower = url.lower()
    title_lower = title.lower()
    return (
        "/publications/" in url_lower or 
        "/report/" in url_lower or 
        "/facts-figures/" in url_lower or 
        "/events/" in url_lower or
        "iisd.org" in url_lower or
        url_lower.endswith(".pdf") or
        "report" in title_lower or
        "publications" in title_lower or
        "facts & figures" in title_lower or
        "blueprint" in title_lower or
        "standards" in title_lower or
        "annual review" in title_lower or
        "sustainability" in title_lower
    )

def search_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall('.//item'):
            title = item.find('title').text
            link = item.find('link').text
            items.append({"title": title, "link": link})
        return items
    except Exception as e:
        print(f"Error querying RSS: {e}", file=sys.stderr)
        return []

def run_demo():
    hubs = {
        "Canada": {
            "query": '"Mining Association of Canada" AND ("report" OR "publication" OR "facts" OR "figures")',
            "org": "Mining Association of Canada (MAC)"
        },
        "Australia": {
            "query": '"Minerals Council of Australia" AND ("report" OR "publication" OR "economic" OR "contribution")',
            "org": "Minerals Council of Australia (MCA)"
        },
        "China": {
            "query": '("China Mining Association" OR "Zijin Mining") AND ("annual report" OR "sustainability" OR "ESG")',
            "org": "Zijin Mining / China Mining Association"
        },
        "Switzerland": {
            "query": '("Glencore" OR "Trafigura" OR "SUISSENEGOCE") AND ("annual report" OR "sustainability" OR "payments to governments")',
            "org": "SUISSENEGOCE / Trading Houses"
        },
        "United Kingdom": {
            "query": '("London Metal Exchange" OR "International Council on Mining and Metals" OR "ICMM") AND ("report" OR "blueprint" OR "standards")',
            "org": "LME / ICMM (London HQ)"
        }
    }
    
    print("| Hub | Target Organization | Identified Report/Publication Title | Resolved Link Preview |")
    print("| :--- | :--- | :--- | :--- |")
    
    for hub_name, details in hubs.items():
        results = search_rss(details["query"])
        reports_found = 0
        
        # Filter and show top 2-3 reports per hub
        for item in results:
            title = item["title"]
            link = item["link"]
            
            # Clean Google News titles (usually ends with " - Publisher")
            clean_title = re.sub(r'\s+-\s+[^(-]+$', '', title).strip()
            
            if is_high_value_report(link, clean_title):
                # We show the link or a preview of it
                # For safety, we truncate title if too long
                short_title = clean_title if len(clean_title) <= 85 else clean_title[:82] + "..."
                print(f"| **{hub_name}** | {details['org']} | {short_title} | [View Source/Google News Link]({link}) |")
                reports_found += 1
                if reports_found >= 3:
                    break
        
        if reports_found == 0:
            print(f"| **{hub_name}** | {details['org']} | *No active report publications in recent news feeds* | N/A |")

if __name__ == "__main__":
    run_demo()
