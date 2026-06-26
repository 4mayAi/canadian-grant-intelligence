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
    if clean_code in ["unknown", "uncategorized", "uncategorised"]:
        return "Uncategorized"
    category_map = {
        'cnst srv gd': 'Construction, Services & Goods',
        'cnstsrvgd': 'Construction, Services & Goods',
        'gd': 'Goods',
        'srv': 'Services',
        'cnst': 'Construction',
        'cnst srv': 'Construction & Services',
        'cnstsrv': 'Construction & Services',
        'cnst gd': 'Construction & Goods',
        'cnstgd': 'Construction & Goods',
        'srv gd': 'Services & Goods',
        'gd srv': 'Services & Goods',
        'srvgd': 'Services & Goods',
        'gdsrv': 'Services & Goods',
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
    source_name: str = "Canada_CanadaBuys_Procurement",
    pulse_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Direct CKAN CSV crawler for CanadaBuys.
    - Queries the JSON API metadata to find CSV URLs.
    - Downloads and decodes the CSV.
    - Processes rows, filtering by keywords and publication/closing dates.
    - Returns a list of standardized dicts containing both feed fields and tender metadata.
    """
    logging.info(f"Querying CanadaBuys CKAN API: {ckan_api_url} (pulse_only={pulse_only})...")
    try:
        data = requests.get(ckan_api_url, headers=HEADERS, timeout=30).json()
    except Exception as e:
        logging.error(f"Failed to fetch CanadaBuys CKAN API: {e}")
        return []

    if not data.get("success"):
        logging.error("CKAN API returned success=False")
        return []

    resources = data.get("result", {}).get("resources", [])
    urls_to_process = []
    
    # We prioritize "new tender notices" for delta updates, and add "open tender notices" for deep seed/crawl
    for res in resources:
        name = res.get("name", "").lower()
        if "new tender notices" in name:
            urls_to_process.append(("New", res.get("url")))
        elif "open tender notices" in name and not pulse_only:
            urls_to_process.append(("Open", res.get("url")))

    if not urls_to_process:
        logging.error("No valid CSV resources found in CanadaBuys CKAN metadata.")
        return []

    tenders = []
    seen_links = set()
    
    for t_type, csv_url in urls_to_process:
        logging.info(f"Downloading {t_type} tenders CSV from: {csv_url}...")
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
                    ref_num = row.get("referenceNumber-numeroReference", "")
                    if ref_num:
                        link = f"https://canadabuys.canada.ca/tender-opportunities/tender-notice/{ref_num}"
                
                if not link or link in seen_links:
                    continue
                
                title = row.get("title-titre-eng", "").replace('*', '').replace('  ', ' ').strip()
                gsin_desc = row.get("gsinDescription-nibsDescription-eng", "").replace('*', '').replace('  ', ' ').strip()
                unspsc_desc = row.get("unspscDescription-eng", "").replace('*', '').replace('  ', ' ').strip()
                desc = f"{gsin_desc} {unspsc_desc}".strip()
                
                organization = row.get("contractingEntityName-nomEntitContractante-eng", "").replace('*', '').strip()
                solicitation_number = row.get("solicitationNumber-numeroSollicitation", "").replace('*', '').strip()
                notice_type = row.get("noticeType-avisType-eng", "").replace('*', '').strip()
                procurement_method = row.get("procurementMethod-methodeApprovisionnement-eng", "").replace('*', '').strip()
                selection_criteria = row.get("selectionCriteria-criteresSelection-eng", "").replace('*', '').strip()
                trade_agreements = row.get("tradeAgreements-accordsCommerciaux-eng", "").replace('*', '').strip()
                tender_description = row.get("tenderDescription-descriptionAppelOffres-eng", "").replace('*', '').strip()

                search_base = (title + " " + desc + " " + tender_description).lower().replace('_', ' ')
                
                matched_kw = False
                for kw in keywords:
                    kw_lower = kw.lower()
                    if len(kw) <= 4:
                        if re.search(r'\b' + re.escape(kw_lower) + r'\b', search_base):
                            matched_kw = True
                            break
                    else:
                        if kw_lower in search_base:
                            matched_kw = True
                            break
                
                if not matched_kw:
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
                    if re.search(r'\bapn\b|\badvance procurement notice\b|\bpre-solicitation\b', search_base):
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

                    structured_parts = []
                    if organization:
                        structured_parts.append(f"Organization: {organization}")
                    if solicitation_number:
                        structured_parts.append(f"Solicitation Number: {solicitation_number}")
                    if notice_type:
                        structured_parts.append(f"Notice Type: {notice_type}")
                    if procurement_method:
                        structured_parts.append(f"Procurement Method: {procurement_method}")
                    if selection_criteria:
                        structured_parts.append(f"Selection Criteria: {selection_criteria}")
                    if trade_agreements:
                        structured_parts.append(f"Trade Agreements: {trade_agreements}")
                    
                    real_desc = tender_description or desc
                    if real_desc:
                        structured_parts.append(f"Description: {real_desc}")
                    
                    text_to_search = "\n".join(structured_parts)

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
                        "description": real_desc[:500] + "..." if len(real_desc) > 500 else real_desc,
                        "type": t_type,
                        
                        # Organization and structured details
                        "organization": organization or "Unknown",
                        "solicitation_number": solicitation_number,
                        "notice_type": notice_type,
                        "procurement_method": procurement_method,
                        "selection_criteria": selection_criteria,
                        "trade_agreements": trade_agreements
                    })
                    seen_links.add(link)
                    match_count += 1
                    
                    if len(tenders) >= max_items:
                        break
            
            logging.info(f"Processed {processed_count} {t_type} CSV rows. Found {match_count} keyword-matching tenders.")
            if len(tenders) >= max_items:
                break
        except Exception as e:
            logging.error(f"Error parsing {t_type} tenders CSV: {e}")

    return tenders
