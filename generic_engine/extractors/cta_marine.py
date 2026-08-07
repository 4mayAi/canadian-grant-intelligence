import logging
import requests
from datetime import datetime, timezone
from collections import Counter
from typing import List, Dict, Any, Optional

def fetch_cta_marine_notices(
    api_url: str = "https://portail-portal.otc-cta.gc.ca/api/MarineNotices",
    max_items: int = 10,
    source_name: str = "CTA_Coasting_Trade_Notices"
) -> List[Dict[str, Any]]:
    """Fetches CTA Marine Notices API, filters active/recent Coasting Trade notices,

    computes a deterministic metrics table, and formats items for B2B ingestion.
    """
    logging.info(f"Fetching CTA Marine Notices from {api_url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        resp = requests.get(api_url, headers=headers, timeout=15)
        resp.raise_for_status()
        raw_notices = resp.json()
    except Exception as e:
        logging.error(f"Failed to fetch CTA Marine Notices: {e}")
        return []

    if not isinstance(raw_notices, list):
        logging.error(f"Unexpected CTA Marine Notices payload type: {type(raw_notices)}")
        return []

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Filter active notices (deadlineDate in 2026/future or openPeriodToDate in 2026/future or active == True)
    active_notices = []
    for item in raw_notices:
        deadline = item.get("deadlineDateShort") or ""
        end_date = item.get("openPeriodToDateShort") or ""
        
        if item.get("active") is True or deadline >= "2026-01-01" or end_date >= "2026-08-01":
            active_notices.append(item)

    logging.info(f"Isolated {len(active_notices)} active/recent Coasting Trade notices out of {len(raw_notices)} total records.")

    # 2. Compute Deterministic Metrics Table
    regions = Counter()
    activities = Counter()
    charterers = Counter()
    foreign_flags = Counter()

    for item in active_notices:
        regions[item.get("areaOfOperationEn") or "Unknown"] += 1
        activities[item.get("proposedActivityEn") or "Unknown"] += 1
        charterers[item.get("applicantClientName") or "Unknown"] += 1
        foreign_flags[item.get("nationalityEn") or "Unknown"] += 1

    total_active = len(active_notices)
    foreign_flag_pct = round(
        (sum(count for nat, count in foreign_flags.items() if nat != "Canada") / max(total_active, 1)) * 100, 1
    )

    deterministic_metrics = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_active_notices": total_active,
        "capacity_deficit_foreign_flag_reliance": f"{foreign_flag_pct}%",
        "regional_breakdown": dict(regions.most_common(5)),
        "activity_surges": [
            {"activity": act, "active_notices": count, "pct_of_total": f"{round((count/max(total_active,1))*100, 1)}%"}
            for act, count in activities.most_common(6)
        ],
        "top_charterers_requesting_waivers": [app for app, _ in charterers.most_common(5)],
        "top_foreign_vessel_flags": dict(foreign_flags.most_common(5))
    }

    # 3. Format Extracted Ingestion Items
    extracted_items = []
    for item in active_notices[:max_items]:
        case_id = item.get("caseId")
        case_num = item.get("caseNumber") or f"ID-{case_id}"
        applicant = item.get("applicantClientName") or "Unknown Applicant"
        activity = item.get("proposedActivityEn") or "Coasting Trade Activity"
        vessel = item.get("vesselNames") or "Foreign Vessel"
        flag = item.get("nationalityEn") or "Foreign Flag"
        area = item.get("areaOfOperationEn") or "Canadian Waters"
        start_dt = item.get("openPeriodFromDateShort") or "TBD"
        end_dt = item.get("openPeriodToDateShort") or "TBD"

        # Unique permalink for cache deduplication
        permalink = f"https://portail-portal.otc-cta.gc.ca/en/marine-notices/details/{case_id}" if case_id else f"https://portail-portal.otc-cta.gc.ca/api/MarineNotices#{case_num}"

        title = f"Coasting Trade Notice {case_num}: {activity} by {applicant}"
        summary = (
            f"Coasting Trade Licence Application {case_num} submitted by {applicant} requesting foreign vessel "
            f"{vessel} ({flag}) for {activity} in {area}. Scheduled operational window: {start_dt} to {end_dt}. "
            f"Indicates domestic Canadian vessel capacity shortage for specialized maritime operations."
        )

        extracted_items.append({
            "title": title,
            "link": permalink,
            "published": item.get("deadlineDate") or item.get("openPeriodFromDate") or datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "text_to_search": (title + " " + summary).lower(),
            "source": source_name,
            "category": "Logistics & Marine Supply Chain",
            "hub": "TradeCompliance",
            "deterministic_metrics": deterministic_metrics
        })

    logging.info(f"Successfully constructed {len(extracted_items)} CTA Marine Notice ingestion items.")
    return extracted_items
