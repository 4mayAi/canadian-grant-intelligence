"""Targeted unit tests for the LLM-assisted batch event clustering deduplication logic."""
import sys
import logging

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

# Mock items
mock_items = [
    {"title": "Glencore restarts Cerrejon mine", "link": "https://mining.com/cerrejon-restart", "source": "Mining.com"},
    {"title": "Glencore lifts force majeure at Cerrejon", "link": "https://seekingalpha.com/cerrejon-force-majeure", "source": "Seeking Alpha"},
    {"title": "China mining state firm coordinator", "link": "https://miningweekly.com/china-state-mna", "source": "Mining Weekly"},
]

class MockGeminiClient:
    def __init__(self, mock_return):
        self.mock_return = mock_return
        self.calls = 0

    def filter_duplicate_articles(self, articles):
        self.calls += 1
        return self.mock_return

def run_deduplication_logic(unprocessed_items, gemini_client, processed_urls):
    """Reproduces the exact deduplication loop in main.py."""
    if len(unprocessed_items) > 1:
        unprocessed_metadata = [{"id": idx, "title": item["title"], "source": item["source"]} for idx, item in enumerate(unprocessed_items)]
        try:
            selected_ids = gemini_client.filter_duplicate_articles(unprocessed_metadata)
            
            # Safety Gate: empty list fallback
            if not selected_ids:
                selected_ids = list(range(len(unprocessed_items)))
            else:
                # Safety Gate: out-of-bounds index check
                selected_ids = [idx for idx in selected_ids if isinstance(idx, int) and 0 <= idx < len(unprocessed_items)]
                
            selected_unprocessed = [unprocessed_items[idx] for idx in selected_ids]
            
            # Record skipped duplicate URLs
            selected_links = {item["link"] for item in selected_unprocessed}
            for item in unprocessed_items:
                if item["link"] not in selected_links:
                    processed_urls.add(item["link"])
                    
            return selected_unprocessed
        except Exception as e:
            # Fallback on exception
            return unprocessed_items
    return unprocessed_items

# === TEST 1: Normal Deduplication Selection ===
print("\n" + "="*60)
print("TEST 1: Normal Deduplication Selection")
print("="*60)

client = MockGeminiClient([0, 2])  # Select Glencore Mining.com and China Mining Weekly, skip Seeking Alpha duplicate
processed_urls = set()
res = run_deduplication_logic(list(mock_items), client, processed_urls)

test("Selected correct number of items", len(res) == 2, f"Got {len(res)}")
test("Selected first item", res[0]["link"] == "https://mining.com/cerrejon-restart")
test("Selected third item", res[1]["link"] == "https://miningweekly.com/china-state-mna")
test("Skipped item added to processed registry", "https://seekingalpha.com/cerrejon-force-majeure" in processed_urls)
test("Selected items NOT in processed registry yet", "https://mining.com/cerrejon-restart" not in processed_urls)

# === TEST 2: Safety Gate - Empty Return Fallback ===
print("\n" + "="*60)
print("TEST 2: Safety Gate - Empty Return Fallback (Hallucination Guard)")
print("="*60)

client = MockGeminiClient([])  # Empty list returned by LLM
processed_urls = set()
res = run_deduplication_logic(list(mock_items), client, processed_urls)

test("Empty list falls back to retaining all items", len(res) == 3, f"Got {len(res)}")
test("No items added to processed registry", len(processed_urls) == 0, f"Registry size {len(processed_urls)}")

# === TEST 3: Safety Gate - Out of Bounds Indices ===
print("\n" + "="*60)
print("TEST 3: Safety Gate - Out-of-Bounds Indices Guard")
print("="*60)

client = MockGeminiClient([0, 2, 7, -1, "string"])  # Returns out-of-bounds indices and non-integers
processed_urls = set()
res = run_deduplication_logic(list(mock_items), client, processed_urls)

test("Invalid indices filtered out, valid retained", len(res) == 2, f"Got {len(res)}")
test("Selected valid index 0", res[0]["link"] == "https://mining.com/cerrejon-restart")
test("Selected valid index 2", res[1]["link"] == "https://miningweekly.com/china-state-mna")
test("Registry tracked skipped index 1", "https://seekingalpha.com/cerrejon-force-majeure" in processed_urls)

# === TEST 4: Single Item Bypass ===
print("\n" + "="*60)
print("TEST 4: Single Item Bypass")
print("="*60)

client = MockGeminiClient([0])
processed_urls = set()
res = run_deduplication_logic([mock_items[0]], client, processed_urls)

test("Deduplication skipped for single item", client.calls == 0, f"Calls count {client.calls}")
test("Single item preserved", len(res) == 1)

# === SUMMARY ===
print("\n" + "="*60)
print(f"RESULTS: {passed}/{passed+failed} passed, {failed} failed")
print("ALL TESTS PASSED" if failed == 0 else "SOME TESTS FAILED")
print("="*60)
if failed:
    sys.exit(1)
else:
    sys.exit(0)
