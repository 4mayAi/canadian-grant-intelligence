import json
import os
import sys
from datetime import datetime, timezone

def validate_outputs_func(output_dir="reports/grants"):
    tenders_file = os.path.join(output_dir, "tenders.json")
    pmo_file = os.path.join(output_dir, "pmo_insights.json")
    kpi_file = os.path.join(output_dir, "kpis.json")

    errors = []

    def parse_iso(dt_str):
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            return None

    # Verify File Existence
    for f in [tenders_file, pmo_file, kpi_file]:
        if not os.path.exists(f):
            raise Exception(f"Missing output file: {f}")

    # 1. Validate KPIs Freshness and Schema
    try:
        with open(kpi_file, 'r', encoding='utf-8') as f:
            kpi_data = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse kpis.json: {e}")
        kpi_data = {}

    if kpi_data:
        required_kpi_keys = ["total_active", "new_today", "closing_this_week", "top_category", "hero_hook", "generated_at"]
        for key in required_kpi_keys:
            if key not in kpi_data:
                errors.append(f"kpis.json missing key: {key}")
        
        # Check Integer Types
        for int_key in ["total_active", "new_today", "closing_this_week"]:
            if int_key in kpi_data and not isinstance(kpi_data[int_key], int):
                errors.append(f"kpis.json field {int_key} must be int, got {type(kpi_data[int_key])}")
            elif int_key in kpi_data and kpi_data[int_key] < 0:
                errors.append(f"kpis.json field {int_key} is negative: {kpi_data[int_key]}")

        # Freshness Check (< 2 hours old)
        if "generated_at" in kpi_data:
            dt = parse_iso(kpi_data["generated_at"])
            if not dt:
                errors.append(f"kpis.json generated_at is invalid ISO: {kpi_data['generated_at']}")
            else:
                stale_threshold = int(os.environ.get("STALE_THRESHOLD_SECONDS", "7200"))
                age = (datetime.now(timezone.utc) - dt).total_seconds()
                if age > stale_threshold:
                    errors.append(f"kpis.json is stale: generated {age/60:.1f} minutes ago (threshold: {stale_threshold/60:.1f} mins)")

    # 2. Validate Tenders Integrity and Schema
    try:
        with open(tenders_file, 'r', encoding='utf-8') as f:
            tenders_data = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse tenders.json: {e}")
        tenders_data = []

    if not isinstance(tenders_data, list):
        errors.append(f"tenders.json root must be a list, got {type(tenders_data)}")
    else:
        valid_provinces = {
            "Alberta", "British Columbia", "Manitoba", "New Brunswick",
            "Newfoundland and Labrador", "Nova Scotia", "Ontario", "Prince Edward Island",
            "Quebec", "Saskatchewan", "Northwest Territories", "Nunavut", "Yukon",
            "National", "NCR (Ottawa/Gatineau)", "Multiple Provinces"
        }
        prov_map = {
            "National": "NAT", "NCR (Ottawa/Gatineau)": "NCR", "Ontario": "ON",
            "British Columbia": "BC", "Newfoundland and Labrador": "NL",
            "Prince Edward Island": "PE", "Northwest Territories": "NT",
            "New Brunswick": "NB", "Nova Scotia": "NS", "Quebec": "QC",
            "Alberta": "AB", "Manitoba": "MB", "Saskatchewan": "SK",
            "Nunavut": "NU", "Yukon": "YT", "Multiple Provinces": "MULT"
        }

        for idx, t in enumerate(tenders_data):
            required_tender_keys = ["type", "title", "description", "link", "closing_date", "publication_date", "province", "province_abbrev", "category"]
            for key in required_tender_keys:
                if key not in t:
                    errors.append(f"Tender {idx} missing key: {key}")
            
            if t.get("type") not in ["New", "Open"]:
                errors.append(f"Tender {idx} has invalid type: {t.get('type')}")
            
            link = t.get("link", "")
            if not (link.startswith("http://") or link.startswith("https://")):
                errors.append(f"Tender {idx} has invalid link: {link}")

            prov = t.get("province")
            if prov and prov not in valid_provinces:
                errors.append(f"Tender {idx} has invalid province: {prov}")
            
            abbrev = t.get("province_abbrev")
            if prov in prov_map and abbrev != prov_map[prov]:
                errors.append(f"Tender {idx} province abbreviation mismatch: {prov} -> {abbrev} (expected {prov_map[prov]})")

    # 3. Validate PMO Insights Schema & Formatting
    try:
        with open(pmo_file, 'r', encoding='utf-8') as f:
            pmo_data = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse pmo_insights.json: {e}")
        pmo_data = {}

    if pmo_data:
        required_pmo_keys = ["generated_at", "linkedin_post", "insights"]
        for key in required_pmo_keys:
            if key not in pmo_data:
                errors.append(f"pmo_insights.json missing key: {key}")

        # Insights List Structure
        insights = pmo_data.get("insights", [])
        if not isinstance(insights, list):
            errors.append(f"pmo_insights.json insights must be a list, got {type(insights)}")
        else:
            for idx, item in enumerate(insights):
                required_item_keys = ["source", "title", "link", "date", "insight"]
                for key in required_item_keys:
                    if key not in item:
                        errors.append(f"Insight {idx} missing key: {key}")
                
                ins = item.get("insight", {})
                required_ins_keys = ["linkedin_hook", "strategic_value", "co_bidding_opportunity"]
                for key in required_ins_keys:
                    if key not in ins:
                        errors.append(f"Insight {idx} nested 'insight' missing key: {key}")

    # 4. Cross-Check KPIs against Tender Data
    if kpi_data and isinstance(tenders_data, list):
        if kpi_data.get("total_active") != len(tenders_data):
            errors.append(f"KPI discrepancy: total_active ({kpi_data.get('total_active')}) != len(tenders) ({len(tenders_data)})")
        
        new_count = sum(1 for t in tenders_data if t.get('type') == 'New')
        if kpi_data.get("new_today") != new_count:
            errors.append(f"KPI discrepancy: new_today ({kpi_data.get('new_today')}) != count of New tenders ({new_count})")

    # Handle Validation Results
    if errors:
        error_msg = "\n".join([f"- {err}" for err in errors])
        raise Exception(f"Output verification failed:\n{error_msg}")

if __name__ == "__main__":
    try:
        validate_outputs_func()
        print("✅ Validation Successful! All outputs are fresh, complete, and properly formatted.")
        sys.exit(0)
    except Exception as exc:
        print(f"❌ Validation Failed:\n{exc}", file=sys.stderr)
        sys.exit(1)
