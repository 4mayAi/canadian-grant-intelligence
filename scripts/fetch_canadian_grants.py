import os, requests, feedparser
from datetime import datetime

FEEDS = {"CanadaBuys": "https://canadabuys.canada.ca/en/tender-opportunities/rss"}
KEYWORDS = ["grant", "stimulus", "incentive", "funding", "rfp", "tender"]

def get_insight(c):
            k = os.getenv("GEMINI_API_KEY")
            if not k: return "No Key"
                        u = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={k}"
    p = {"contents": [{"parts": [{"text": f"Analyze: {c}"}]}]}
    try:
                    r = requests.post(u, json=p, timeout=10); d = r.json()
                    return d['candidates'][0]['content']['parts'][0]['text'] if 'candidates' in d else "Error"
                except: return "Error"

def scrape():
            res = []
    for n, u in FEEDS.items():
                    f = feedparser.parse(u)
                    for e in f.entries:
                                        t = (e.title + " " + getattr(e, 'summary', '')).lower()
                                        if any(kw in t for kw in KEYWORDS):
                                                                i = get_insight(e.title)
                                                                res.append(f"## {e.title}\n- Link: {e.link}\n- AI: {i}\n\n")
                        rep = f"# Report {datetime.now().strftime('%Y-%m-%d')}\n\n" + ("".join(res) if res else "None.")
                os.makedirs("reports/grants", exist_ok=True)
    with open("reports/grants/report.md", "w") as f: f.write(rep)

if __name__ == "__main__":
            scrape()
