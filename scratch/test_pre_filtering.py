import sys
import os
import re
from typing import List
import json

# Ensure the repository root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def matches_keywords(text: str, keywords: List[str]) -> bool:
    """Performs case-insensitive word-boundary matching for short acronyms and substring matching for longer terms."""
    if not text:
        return False
    text_lower = text.lower().replace('_', ' ')
    for kw in keywords:
        kw_lower = kw.lower()
        if len(kw) <= 4:
            if re.search(r'\b' + re.escape(kw_lower) + r'\b', text_lower):
                return True
        else:
            if kw_lower in text_lower:
                return True
    return False

def main():
    # Load keywords
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../configs/amr_simulation.json"))
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    keywords = config.get("keywords", [])
    
    print(f"Loaded {len(keywords)} keywords from {config_path}")
    
    # Test cases based on actual configs/amr_simulation.json keywords
    test_cases = [
        {
            "text": "In silico drug discovery for antimicrobial resistance using machine learning",
            "expected": True,
            "description": "antimicrobial resistance, drug discovery, in silico"
        },
        {
            "text": "A new computational biology model for bacterial simulation",
            "expected": True,
            "description": "bacterial simulation, computational biology"
        },
        {
            "text": "Pathogen modeling of drug-resistant pathogens in hospitals",
            "expected": True,
            "description": "pathogen modeling"
        },
        {
            "text": "Antiviral activity of anisomycin against chikungunya virus",
            "expected": False,
            "description": "unrelated virus without simulation keywords"
        },
        {
            "text": "Canada is evaluating the InnoVet-AMR 2.0 program",
            "expected": True,
            "description": "AMR acronym matching"
        },
        {
            "text": "This is a new funding call from CIHR",
            "expected": True,
            "description": "CIHR acronym matching"
        },
        {
            "text": "Our research is supported by a grant from NRCAN",
            "expected": False,
            "description": "NRCAN should not match short acronym NRC"
        }
    ]
    
    failed = 0
    print("\nRunning test cases:")
    for idx, case in enumerate(test_cases):
        res = matches_keywords(case["text"], keywords)
        status = "PASS" if res == case["expected"] else "FAIL"
        if res != case["expected"]:
            failed += 1
        print(f"  {idx+1}. [{status}] '{case['text'][:50]}...' -> Got {res}, Expected {case['expected']} ({case['description']})")
        
    if failed == 0:
        print("\nAll pre-filtering tests PASSED!")
        sys.exit(0)
    else:
        print(f"\n{failed} test cases FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
