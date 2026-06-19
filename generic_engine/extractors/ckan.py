import codecs
import csv
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
import requests

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_category_label(code: str) -> str:
    if not code: return "Uncategorized"
    clean_code = code.replace('*', '').lower().strip()
    clean_code = " ".join(clean_code.split())
    category_map = {
        'cnst srv gd': 'Construction, Services & Goods',
        'gd': 'Goods',
        'srv': 'Services',
        'cnst': 'Construction',
        'cnst srv': 'Construction & Services',
        'cnst gd': 'Construction & Goods',
        'srv gd': 'Services & Goods',
        'gd srv': 'Services & Goods',
        'srvtgd': 'Services (Goods-Related)',
        'der': 'Defence & Security',
        'it': 'Information Technology',
        'rc srv': 'Research & Consulting Services',
        'r&d': 'Research & Development',
        'health': 'Health & Medical',
        'env': 'Environmental Services',
        'trans': 'Transportation & Logistics'
    }
    return category_map.get(clean_code, code.replace('*', '').strip())

def normalize_province(raw_value: str) -> str:
    if not raw_value: return "National"
    star_count = raw_value.count('*')
    if star_count >= 2 or len(raw_value) > 50:
        return "Multiple Provinces"
    text = raw_value.replace('\n', ' ').replace('\r', '').strip().replace('*', '').strip()
    text_lower = text.lower()
    matched_prov = None
    for valid in VALID_PROVINCES:
        if text_lower == valid.lower():
            matched_prov = valid
            break
    if matched_prov:
        return matched_prov
    if text_lower in ("canada", "federal", "canada-wide"):
        return "National"
    if "national capital" in text_lower or text_lower == "ncr":
        return "NCR (Ottawa/Gatineau)"
    for city, prov in LOCATION_TO_PROVINCE.items():
        if city in text_lower:
            return prov
    return "National"

def fetch_canadabuys_tenders(
    ckan_api_url: str,
    keywords: List[str],
    max_items: int = 15,
    lookback_days: int = 7,
    source_name: str = "Canada_CanadaBuys_Procurement"
) -> List[Dict[str, Any]]:
    """
    Direct CKAN CSV crawler for CanadaBuys.
    - Queries the JSON API metadata to find CSV URLs.
    - Downloads and decodes the CSV.
    - Processes rows, filtering by keywords and publication/closing dates.
    - Returns a list of standardized dicts containing both feed fields and tender metadata.
    """
    logging.info(f"Querying CanadaBuys CKAN API: {ckan_api_url}...")
    try:
        data = requests.get(ckan_api_url, headers=HEADERS, timeout=30).json()
    except Exception as e:
        logging.error(f"Failed to fetch CanadaBuys CKAN API: {e}")
        return []

    if not data.get("success"):
        logging.error("CKAN API returned success=False")
        return []

    resources = data.get("result", {}).get("resources", [])
    csv_url = None
    
    # We prioritize "new tender notices" for delta updates, fallback to "open tender notices"
    for res in resources:
        name = res.get("name", "").lower()
        if "new tender notices" in name:
            csv_url = res.get("url")
            break
            
    if not csv_url:
        # Fallback to Open tenders if New is not found
        for res in resources:
            name = res.get("name", "").lower()
            if "open tender notices" in name:
                csv_url = res.get("url")
                break

    if not csv_url:
        logging.error("No valid CSV resource found in CanadaBuys CKAN metadata.")
        return []

    logging.info(f"Downloading tenders CSV from: {csv_url}...")
    tenders = []
    try:
        resp = requests.get(csv_url, headers=HEADERS, stream=True, timeout=120)
        resp.raise_for_status()
        
        reader = csv.DictReader(codecs.iterdecode(resp.iter_lines(), 'utf-8-sig'))
        processed_count = 0
        match_count = 0
        
        for row in reader:
            processed_count += 1
            link = row.get("noticeURL-URLavis-eng", "")
            if not link:
                continue
            
            title = row.get("title-titre-eng", "").replace('*', '').replace('  ', ' ').strip()
            gsin_desc = row.get("gsinDescription-nibsDescription-eng", "").replace('*', '').replace('  ', ' ').strip()
            unspsc_desc = row.get("unspscDescription-eng", "").replace('*', '').replace('  ', ' ').strip()
            desc = f"{gsin_desc} {unspsc_desc}".strip()

            text_to_search = (title + " " + desc).lower().replace('_', ' ')
            if not any(kw.lower() in text_to_search for kw in keywords):
                continue

            close_date = row.get("tenderClosingDate-appelOffresDateCloture", "")
            pub_date = row.get("publicationDate-datePublication", "")
            amend_date = row.get("amendmentDate-dateModification", "")
            raw_province = row.get("regionsOfDelivery-regionsLivraison-eng", "")
            category = row.get("procurementCategory-categorieApprovisionnement", "Uncategorized").replace('*', '').strip()
            
            # Date validation (skip expired)
            is_valid_date = True
            if close_date:
                try:
                    dt = datetime.strptime(close_date[:10], "%Y-%m-%d")
                    if dt < datetime.now() - timedelta(days=1):
                        is_valid_date = False
                except ValueError:
                    pass
            
            # Exclude APNs / pre-solicitation notices
            if title and link and is_valid_date:
                if re.search(r'\bapn\b|\badvance procurement notice\b|\bpre-solicitation\b', text_to_search):
                    continue
                
                province = normalize_province(raw_province)
                province_abbrev = PROVINCE_ABBREV.get(province, "NAT")
                
                # Format dates to ISO
                formatted_pub = pub_date or amend_date
                if formatted_pub and len(formatted_pub) >= 10:
                    formatted_pub = formatted_pub[:10] + "T00:00:00Z"
                
                formatted_close = close_date
                if formatted_close and len(formatted_close) >= 10:
                    formatted_close = formatted_close[:10] + "T00:00:00Z"

                tenders.append({
                    "source": source_name,
                    "title": title[:200],
                    "link": link,
                    "date": formatted_pub or datetime.utcnow().isoformat() + "Z",
                    "text_to_search": text_to_search,
                    
                    # Tender Metadata fields
                    "closing_date": formatted_close,
                    "province": province,
                    "province_abbrev": province_abbrev,
                    "category": category,
                    "category_label": get_category_label(category),
                    "description": desc[:500] + "..." if len(desc) > 500 else desc,
                    "type": "New"  # Treat parsed daily deltas as 'New' initially
                })
                match_count += 1
                
                if len(tenders) >= max_items:
                    break
        
        logging.info(f"Processed {processed_count} CSV rows. Found {match_count} new keyword-matching tenders.")
    except Exception as e:
        logging.error(f"Error parsing CanadaBuys tenders CSV: {e}")

    return tenders
