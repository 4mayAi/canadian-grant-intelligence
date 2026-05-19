import codecs
import csv
import re
import logging
from datetime import datetime, timedelta
from typing import List, Set, Optional
import requests

from src.config import Config
from src.models import Tender

def normalize_province(raw_value: str) -> str:
    if not raw_value: return "National"
    text = raw_value.replace('\n', ' ').replace('\r', '').strip().replace('*', '').strip()
    text_lower = text.lower()
    
    for valid in Config.VALID_PROVINCES:
        if text_lower == valid.lower(): return valid
    
    if text_lower in ("canada", "federal", "canada-wide"): return "National"
    if "national capital" in text_lower or text_lower == "ncr": return "NCR (Ottawa/Gatineau)"
    
    for city, prov in Config.LOCATION_TO_PROVINCE.items():
        if city in text_lower: return prov
        
    return "National"

def fetch_canadabuys_csvs(pulse_only: bool = False, dynamic_keywords: Optional[List[str]] = None, seen_links: Optional[Set[str]] = None) -> List[Tender]:
    if seen_links is None:
        seen_links = set()
        
    effective_keywords = Config.KEYWORDS + (dynamic_keywords or [])
    logging.info(f"Fetching CanadaBuys metadata (Mode: {'PULSE' if pulse_only else 'DEEP DIVE'})...")
    
    try:
        data = requests.get(Config.CANADABUYS_CKAN_API, headers=Config.HEADERS, timeout=30).json()
    except Exception as e:
        logging.error(f"Failed to fetch CanadaBuys API: {e}")
        return []

    if not data.get("success"):
        logging.error("CKAN API returned success=False")
        return []

    resources = data.get("result", {}).get("resources", [])
    urls_to_process = []
    
    for res in resources:
        name = res.get("name", "").lower()
        if "new tender notices" in name:
            urls_to_process.append(("New", res.get("url")))
        elif "open tender notices" in name and not pulse_only:
            urls_to_process.append(("Open", res.get("url")))

    tenders = []
    
    for t_type, url in urls_to_process:
        logging.info(f"Downloading {t_type} Tenders from: {url}")
        try:
            # Streaming the response to save memory
            resp = requests.get(url, headers=Config.HEADERS, stream=True, timeout=120)
            resp.raise_for_status()
            
            # Using iter_lines with codecs to handle utf-8-sig (BOM) properly
            reader = csv.DictReader(codecs.iterdecode(resp.iter_lines(), 'utf-8-sig'))
            
            processed_count = 0
            match_count = 0
            
            for row in reader:
                processed_count += 1
                if processed_count == 1:
                    logging.info(f"DEBUG Row 1: link='{row.get('noticeURL-URLavis-eng')}', title='{row.get('title-titre-eng')}', desc_keys={[k for k in row.keys() if 'desc' in k.lower() or 'tit' in k.lower()]}")
                link = row.get("noticeURL-URLavis-eng", "")
                
                if not link or link in seen_links:
                    continue
                            title = row.get("title-titre-eng", "")
                                gsin_desc = row.get("gsinDescription-nibsDescription-eng", "")
                                unspsc_desc = row.get("unspscDescription-eng", "")
                                desc = f"{gsin_desc} {unspsc_desc}".strip()

                            text_to_search = (title + " " + desc).lower()
                                if not any(kw.lower() in text_to_search for kw in effective_keywords):
                                                    continue
                                                matched_kw = [kw for kw in effective_keywords if kw.lower() in text_to_search]
                                logging.info(f"MATCH: title='{title}', matched_kw={matched_kw}")
                close_date = row.get("tenderClosingDate-appelOffresDateCloture", "")
                pub_date = row.get("publicationDate-datePublication", "")
                amend_date = row.get("amendmentDate-dateModification", "")
                raw_province = row.get("regionsOfDelivery-regionsLivraison-eng", "")
                category = row.get("procurementCategory-categorieApprovisionnement", "Uncategorized").replace('*', '').strip()
                
                # Date filtering (skip expired)
                is_valid_date = True
                if close_date:
                    try:
                        dt = datetime.strptime(close_date[:10], "%Y-%m-%d")
                        if dt < datetime.now() - timedelta(days=1):
                            is_valid_date = False
                    except ValueError:
                        pass
                
                if title and link and is_valid_date:
                    if re.search(r'\bapn\b|\badvance procurement notice\b|\bpre-solicitation\b', text_to_search):
                        continue
                    
                    province = normalize_province(raw_province)
                    province_abbrev = Config.PROVINCE_ABBREV.get(province, "NAT")
                    
                    tenders.append(Tender(
                        type=t_type,
                        title=title[:200],
                        description=desc[:500] + "..." if len(desc) > 500 else desc,
                        link=link,
                        closing_date=close_date,
                        publication_date=pub_date or amend_date,
                        province=province,
                        province_abbrev=province_abbrev,
                        category=category
                    ))
                    seen_links.add(link)
                    match_count += 1
            
            logging.info(f"Processed {processed_count} {t_type} rows. Found {match_count} new high-signal matches.")
        except Exception as e:
            logging.error(f"Error parsing {t_type} tenders CSV: {e}")

    return tenders
