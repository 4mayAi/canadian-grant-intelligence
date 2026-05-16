"""Targeted verification tests for date integrity and hook selection fixes."""
import time
import sys
from datetime import datetime, timedelta
from dateutil import parser as date_parser

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

# === TEST 1: dateutil.parser.parse with gov date formats ===
print("\n" + "="*60)
print("TEST 1: Date parsing with government date formats")
print("="*60)

for date_str, label in [
    ("2025-05-15", "ISO"), ("May 15, 2025", "English long"),
    ("2025-05-15T14:30:00Z", "ISO+time"), ("15 May 2025", "Day-first"),
    ("Thu, 15 May 2025 14:30:00 GMT", "RFC 2822"),
]:
    try:
        dt = date_parser.parse(date_str)
        s = dt.timetuple()
        test(f"Parse '{date_str}' ({label})",
             s.tm_year == 2025 and s.tm_mon == 5 and s.tm_mday == 15, f"Got {dt}")
    except Exception as e:
        test(f"Parse '{date_str}' ({label})", False, str(e))

for bad in ["not a date", ""]:
    caught = False
    try:
        date_parser.parse(bad)
    except (ValueError, TypeError, OverflowError):
        caught = True
    except Exception as e:
        caught = isinstance(e, ValueError)
    test(f"Reject invalid '{bad}'", caught, "No exception raised")

# === TEST 2: Playwright consumer loop date handling ===
print("\n" + "="*60)
print("TEST 2: Playwright consumer loop date handling")
print("="*60)

def sim_playwright(scraped_items, is_seeding, lookback_limit):
    """Reproduces logic from fetch_pmo_news lines 813-865."""
    reports = []
    for entry in scraped_items:
        pub_date = None
        if entry.get('published_parsed'):
            try:
                pub_date = datetime.fromtimestamp(time.mktime(entry['published_parsed']))
            except (ValueError, TypeError, OverflowError):
                pass
        display_date = pub_date or datetime.now()
        if not is_seeding and lookback_limit and pub_date:
            if pub_date < lookback_limit:
                continue
        reports.append({"date": display_date.strftime("%Y-%m-%d"), **entry})
    return reports

today = datetime.now().strftime("%Y-%m-%d")
lookback = datetime.now() - timedelta(days=7)
item_base = {"title": "Test", "link": "https://test.gc.ca", "source": "PMO"}

# 2a: With valid date
r = sim_playwright([{**item_base, "published_parsed": datetime(2025, 5, 15).timetuple()}], False, None)
test("Extracted date used", r[0]['date'] == "2025-05-15", f"Got {r[0]['date']}")

# 2b: None date falls back to today
r = sim_playwright([{**item_base, "published_parsed": None}], False, None)
test("None date -> today", r[0]['date'] == today, f"Got {r[0]['date']}")

# 2c: Old dated item filtered by lookback
r = sim_playwright([{**item_base, "published_parsed": datetime(2025, 1, 1).timetuple()}], False, lookback)
test("Old item filtered", len(r) == 0, f"Got {len(r)} results")

# 2d: Undated item passes lookback (can't prove it's old)
r = sim_playwright([{**item_base, "published_parsed": None}], False, lookback)
test("Undated item passes lookback", len(r) == 1, f"Got {len(r)} results")

# 2e: Corrupt struct handled
try:
    r = sim_playwright([{**item_base, "published_parsed": "garbage"}], False, None)
    test("Corrupt struct -> no crash, fallback to today", r[0]['date'] == today)
except Exception as e:
    test("Corrupt struct -> no crash", False, str(e))

# === TEST 3: RSS consumer loop ===
print("\n" + "="*60)
print("TEST 3: RSS feed date handling")
print("="*60)

def sim_rss(entries, is_seeding, lookback_limit):
    """Reproduces logic from fetch_pmo_news lines 746-802."""
    reports = []
    for entry in entries:
        published = entry.get('published_parsed')
        pub_date = None
        if published:
            pub_date = datetime.fromtimestamp(time.mktime(published))
        if not is_seeding and lookback_limit:
            if not pub_date or pub_date < lookback_limit:
                continue
        display_date = pub_date or datetime.now()
        reports.append({"date": display_date.strftime("%Y-%m-%d"), **entry})
    return reports

rss_base = {"title": "Budget 2025", "link": "https://news.gc.ca/1", "source": "PMO"}

# 3a: With date
r = sim_rss([{**rss_base, "published_parsed": datetime(2025, 5, 14).timetuple()}], True, None)
test("RSS with date uses it", r[0]['date'] == "2025-05-14", f"Got {r[0]['date']}")

# 3b: No date in seeding -> today
r = sim_rss([{**rss_base, "published_parsed": None}], True, None)
test("RSS no date seeding -> today", r[0]['date'] == today, f"Got {r[0]['date']}")

# 3c: No date in reporting with lookback -> FILTERED
r = sim_rss([{**rss_base, "published_parsed": None}], False, lookback)
test("RSS no date reporting -> filtered", len(r) == 0, f"Got {len(r)}")

# 3d: No NoneType crash (the original bug)
try:
    r = sim_rss([{**rss_base, "published_parsed": None}], True, None)
    test("No NoneType crash on dateless entry", True)
except AttributeError as e:
    test("No NoneType crash on dateless entry", False, f"AttributeError: {e}")

# === TEST 4: Social card hook selection ===
print("\n" + "="*60)
print("TEST 4: Social card hook selection logic")
print("="*60)

def sim_hook(hero_hook, headline_tenders, pmo_reports, n=10):
    """Reproduces logic from lines 1048-1061."""
    if hero_hook and "mayAi" not in hero_hook:
        return hero_hook, "Strategic Intelligence Summary"
    elif headline_tenders:
        return f"{n} Active Opportunities -- {headline_tenders[0].split(' -- ')[0]}", "Federal Procurement Intelligence"
    elif pmo_reports:
        item = pmo_reports[0]
        hook = item['insight'].get('linkedin_hook', 'mayAi | Executive Intelligence')
        raw = item['insight'].get('strategic_value', 'Executive Insight').split('\n')[0].lstrip('- ').strip()
        cat = raw[:40] if len(raw) > 10 else "Executive Intelligence Report"
        return hook, cat
    else:
        return "mayAi | Golden Opportunities", "Canadian Grant Intelligence"

h, c = sim_hook("Canada invests $2B in green infra", ["IT -- T123"], [])
test("Hero hook takes priority", h == "Canada invests $2B in green infra")
test("Category = Strategic", c == "Strategic Intelligence Summary")

h, c = sim_hook("mayAi | Golden", ["IT Consulting -- Jun 30"], [])
test("mayAi hook skipped, tenders used", "Active Opportunities" in h)

h, c = sim_hook(None, [], [{"insight": {"linkedin_hook": "Budget shift", "strategic_value": "Federal infra strategy"}}])
test("PMO fallback", h == "Budget shift")

h, c = sim_hook(None, [], [])
test("Ultimate fallback", h == "mayAi | Golden Opportunities" and c == "Canadian Grant Intelligence")

h, c = sim_hook("", ["Defence -- Jul 1"], [])
test("Empty string hook skipped", "Active Opportunities" in h)

# === SUMMARY ===
print("\n" + "="*60)
print(f"RESULTS: {passed}/{passed+failed} passed, {failed} failed")
print("ALL TESTS PASSED" if failed == 0 else "SOME TESTS FAILED")
print("="*60)
if failed:
    sys.exit(1)
