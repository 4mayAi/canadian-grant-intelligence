
import os
import sys
# Add scripts dir to path
sys.path.append(os.path.abspath("scripts"))
from fetch_canadian_grants import fetch_canadabuys_csvs

def test_canadabuys():
    print("Testing CanadaBuys fetch...")
    tenders = fetch_canadabuys_csvs()
    print(f"Found {len(tenders)} tenders.")
    if tenders:
        print("Sample tender:")
        print(tenders[0])
        
    # Check for specific interesting tenders
    new_tenders = [t for t in tenders if t.get('status') == 'New']
    print(f"New tenders: {len(new_tenders)}")
    
    # Check for keyword matches
    KEYWORDS = ["grant", "stimulus", "incentive", "funding", "RFP", "tender", "economic support", "investment", "infrastructure"]
    matches = []
    for t in tenders:
        title = t.get('title', '').lower()
        if any(k in title for k in KEYWORDS):
            matches.append(t)
    
    print(f"Keyword matches: {len(matches)}")
    for m in matches[:3]:
        print(f"- {m['title']} ({m['status']})")

if __name__ == "__main__":
    test_canadabuys()
