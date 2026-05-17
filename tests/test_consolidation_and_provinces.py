"""Targeted unit tests for daily PMO news insight consolidation and province abbreviation mapping."""
import sys
import json
from datetime import datetime

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name} -- {detail}")
        failed += 1

# Simulation of PROVINCE_ABBREV and normalize_province logic in fetch_canadian_grants.py
VALID_PROVINCES = {
    "Alberta", "British Columbia", "Manitoba", "New Brunswick",
    "Newfoundland and Labrador", "Nova Scotia", "Ontario", "Prince Edward Island",
    "Quebec", "Saskatchewan", "Northwest Territories", "Nunavut", "Yukon",
    "National", "NCR (Ottawa/Gatineau)", "Multiple Provinces"
}

LOCATION_TO_PROVINCE = {
    "ottawa": "Ontario", "toronto": "Ontario", "kingston": "Ontario",
    "montreal": "Quebec", "montréal": "Quebec", "vancouver": "British Columbia"
}

PROVINCE_ABBREV = {
    "National": "NAT", "NCR (Ottawa/Gatineau)": "NCR", "Ontario": "ON",
    "British Columbia": "BC", "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE", "Northwest Territories": "NT",
    "New Brunswick": "NB", "Nova Scotia": "NS", "Quebec": "QC",
    "Alberta": "AB", "Manitoba": "MB", "Saskatchewan": "SK",
    "Nunavut": "NU", "Yukon": "YT", "Multiple Provinces": "MULT"
}

def sim_normalize_province(raw_value):
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

# === TEST 1: Province Normalization and Abbreviation Mapping ===
print("\n" + "="*60)
print("TEST 1: Province Normalization and Abbreviation mapping")
print("="*60)

test_cases = [
    ("", "National", "NAT"),
    ("ONTARIO", "Ontario", "ON"),
    ("vancouver, bc", "British Columbia", "BC"),
    ("NCR (Ottawa/Gatineau)", "NCR (Ottawa/Gatineau)", "NCR"),
    ("Unknown Place", "National", "NAT"),
]

for raw, expected_prov, expected_abbrev in test_cases:
    norm = sim_normalize_province(raw)
    abbrev = PROVINCE_ABBREV.get(norm, "NAT")
    test(f"Normalize '{raw}' -> {expected_prov} ({expected_abbrev})",
         norm == expected_prov and abbrev == expected_abbrev,
         f"Got province='{norm}', abbrev='{abbrev}'")

# === TEST 2: Daily PMO News Insights Consolidation and Merge ===
print("\n" + "="*60)
print("TEST 2: Daily PMO News Insights Consolidation and Merge")
print("="*60)

# Simulate existing insights on Azure for today
today_str = datetime.now().strftime("%Y-%m-%d")
simulated_azure_raw = json.dumps({
    "generated_at": "2026-05-17T02:00:00Z",
    "report_date": today_str,
    "linkedin_post": "Existing post text",
    "insights": [
        {
            "title": "Lithium mining funding",
            "source": "PMO Releases",
            "date": today_str,
            "link": "https://www.pm.gc.ca/en/news/releases/lithium",
            "linkedin_hook": "Lithium hook",
            "strategic_value": "Lithium value",
            "co_bidding_opportunity": "Lithium bidding"
        }
    ]
})

# Simulate newly scraped reports for this run
newly_scraped = [
    {
        "source": "PMO Releases",
        "title": "New Green Transition Funds",
        "link": "https://www.pm.gc.ca/en/news/releases/green",
        "date": today_str,
        "insight": {
            "linkedin_hook": "Green hook",
            "strategic_value": "Green value",
            "co_bidding_opportunity": "Green bidding"
        }
    },
    {
        "source": "PMO Releases",
        "title": "Lithium mining funding",
        "link": "https://www.pm.gc.ca/en/news/releases/lithium",
        "date": today_str,
        "insight": {
            "linkedin_hook": "New lithium hook (should be ignored due to existing)",
            "strategic_value": "New lithium value",
            "co_bidding_opportunity": "New lithium bidding"
        }
    }
]

# Run simulation of consolidation logic
pmo_reports = []
seen_links = set()

# Restore from existing JSON
existing = json.loads(simulated_azure_raw)
if existing.get("report_date") == today_str:
    for item in existing.get("insights", []):
        pmo_reports.append({
            "source": item.get("source", ""),
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "date": item.get("date", ""),
            "insight": {
                "linkedin_hook": item.get("linkedin_hook", ""),
                "strategic_value": item.get("strategic_value", ""),
                "co_bidding_opportunity": item.get("co_bidding_opportunity", "")
            }
        })
        seen_links.add(item.get("link"))

# Merge new reports
for item in newly_scraped:
    if item["link"] not in seen_links:
        pmo_reports.append(item)
        seen_links.add(item["link"])

test("Consolidated report count is 2 (1 existing + 1 new)", len(pmo_reports) == 2, f"Got {len(pmo_reports)}")
test("Consolidated contains lithium and green, no duplicates",
     seen_links == {"https://www.pm.gc.ca/en/news/releases/lithium", "https://www.pm.gc.ca/en/news/releases/green"})
test("Existing lithium item preserved as-is without being overwritten by the new scrape",
     pmo_reports[0]["insight"]["linkedin_hook"] == "Lithium hook",
     f"Got {pmo_reports[0]['insight']['linkedin_hook']}")
test("New green item correctly added",
     pmo_reports[1]["title"] == "New Green Transition Funds")

# === SUMMARY ===
print("\n" + "="*60)
print(f"RESULTS: {passed}/{passed+failed} passed, {failed} failed")
print("ALL TESTS PASSED" if failed == 0 else "SOME TESTS FAILED")
print("="*60)
if failed:
    sys.exit(1)
