import os
from typing import Dict, List, Set

class Config:
    # --- API Endpoints ---
    CANADABUYS_CKAN_API: str = "https://open.canada.ca/data/api/action/package_show?id=6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2"
    
    # --- Sources ---
    FEEDS: Dict[str, str] = {
        "PMO_News": "https://www.pm.gc.ca/en/news.rss"
    }

    HTML_SOURCES: Dict[str, str] = {
        "ISED_News": "https://ised-isde.canada.ca/site/ised/en/news",
        "Global_Affairs": "https://www.international.gc.ca/news-nouvelles/news-nouvelles.aspx?lang=eng",
        "Finance_Canada": "https://www.canada.ca/en/department-finance/news.html"
    }

    # --- HTTP Settings ---
    HEADERS: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # --- Strategic Filtering Keywords ---
    KEYWORDS: List[str] = [
        "grant", "stimulus", "incentive", "funding", "RFP", "tender", 
        "economic support", "investment", "artificial intelligence", "cloud",
        "digital transformation", "cybersecurity", "clean tech", "renewable",
        "indigenous", "sme", "small business", "innovation", "research",
        "infrastructure", "defense", "defence", "security", "quantum"
    ]

    HIGH_VALUE_KEYWORDS: List[str] = [
        "rfp", "investment", "infrastructure", "innovation", "technology",
        "construction", "consulting", "defence", "security", "health",
        "environmental", "energy", "digital", "cloud", "services"
    ]

    # --- Provinces & Mappings ---
    VALID_PROVINCES: Set[str] = {
        "Alberta", "British Columbia", "Manitoba", "New Brunswick",
        "Newfoundland and Labrador", "Nova Scotia", "Ontario", "Prince Edward Island",
        "Quebec", "Saskatchewan", "Northwest Territories", "Nunavut", "Yukon",
        "National", "NCR (Ottawa/Gatineau)", "Multiple Provinces"
    }

    LOCATION_TO_PROVINCE: Dict[str, str] = {
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

    PROVINCE_ABBREV: Dict[str, str] = {
        "National": "NAT", "NCR (Ottawa/Gatineau)": "NCR", "Ontario": "ON",
        "British Columbia": "BC", "Newfoundland and Labrador": "NL",
        "Prince Edward Island": "PE", "Northwest Territories": "NT",
        "New Brunswick": "NB", "Nova Scotia": "NS", "Quebec": "QC",
        "Alberta": "AB", "Manitoba": "MB", "Saskatchewan": "SK",
        "Nunavut": "NU", "Yukon": "YT", "Multiple Provinces": "MULT"
    }

    # --- App Configuration ---
    DASHBOARD_URL: str = "https://4mayAi.github.io/canadian-grant-intelligence/"
    AZURE_CONTAINER_NAME: str = "data"
    
    # --- Local Outputs ---
    OUTPUT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports", "grants")
    TENDERS_FILE: str = os.path.join(OUTPUT_DIR, "tenders.json")
    PMO_FILE: str = os.path.join(OUTPUT_DIR, "pmo_insights.json")
    KPI_FILE: str = os.path.join(OUTPUT_DIR, "kpis.json")

    RUN_TYPE: str = os.getenv("RUN_TYPE", "DEEP_DIVE").lower()
    SCRAPE_LOOKBACK_DAYS: int = int(os.getenv("SCRAPE_LOOKBACK_DAYS", "2"))

    @classmethod
    def is_pulse_mode(cls) -> bool:
        return cls.RUN_TYPE == "pulse"
