#!/usr/bin/env python3
"""
Post-run validation script for the Canadian Grant Intelligence pipeline.
Validates schema, data freshness, deduplication, and LLM output quality.

Called as a standalone step in the GitHub Actions workflow after the main
pipeline completes. Exits 1 on critical failures, 0 with logged warnings
for quality metrics.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports", "grants")
TENDERS_FILE = os.path.join(REPORTS_DIR, "tenders.json")
PMO_FILE = os.path.join(REPORTS_DIR, "pmo_insights.json")
KPI_FILE = os.path.join(REPORTS_DIR, "kpis.json")

REQUIRED_TENDER_KEYS = {"title", "link", "province", "category", "closing_date", "type"}
REQUIRED_KPI_KEYS = {"total_active", "new_today", "closing_this_week", "top_category", "generated_at"}
REQUIRED_PMO_KEYS = {"generated_at", "insights"}

# Quality thresholds
MAX_NO_INSIGHT_RATIO = 0.50  # Warn if >50% of insights are "No insight available"
FRESHNESS_HOURS = 4  # Data must be generated within the last N hours


def load_json(filepath, label):
    """Load and return JSON data from a file, or None on failure."""
    if not os.path.exists(filepath):
        logging.error(f"CRITICAL: {label} file not found at {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"CRITICAL: {label} is not valid JSON: {e}")
        return None


def validate_schema(data, required_keys, label, is_list=False):
    """Validate that data contains all required keys."""
    if is_list:
        if not isinstance(data, list):
            logging.error(f"CRITICAL: {label} should be a list, got {type(data).__name__}")
            return False
        for i, item in enumerate(data):
            missing = required_keys - set(item.keys())
            if missing:
                logging.error(f"CRITICAL: {label}[{i}] missing keys: {missing}")
                return False
    else:
        if not isinstance(data, dict):
            logging.error(f"CRITICAL: {label} should be a dict, got {type(data).__name__}")
            return False
        missing = required_keys - set(data.keys())
        if missing:
            logging.error(f"CRITICAL: {label} missing keys: {missing}")
            return False
    return True


def validate_freshness(generated_at_str, label):
    """Validate that the generated_at timestamp is recent."""
    try:
        generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
        now = datetime.now(generated_at.tzinfo) if generated_at.tzinfo else datetime.utcnow()
        age = now - generated_at.replace(tzinfo=None) if generated_at.tzinfo is None else now - generated_at
        if age > timedelta(hours=FRESHNESS_HOURS):
            logging.warning(f"STALE DATA: {label} generated_at is {age} old (threshold: {FRESHNESS_HOURS}h)")
            return False
        logging.info(f"FRESH: {label} generated {age} ago")
        return True
    except (ValueError, TypeError) as e:
        logging.error(f"CRITICAL: Could not parse {label} generated_at '{generated_at_str}': {e}")
        return False


def validate_duplicates(tenders):
    """Check for duplicate tender links."""
    links = [t.get('link', '') for t in tenders]
    unique_links = set(links)
    if len(links) != len(unique_links):
        dupes = len(links) - len(unique_links)
        logging.error(f"CRITICAL: {dupes} duplicate tender links detected")
        return False
    logging.info(f"CLEAN: {len(links)} tenders, zero duplicates")
    return True


def validate_cross_consistency(tenders, kpis):
    """Cross-validate KPI counts against tender data."""
    actual_total = len(tenders)
    reported_total = kpis.get("total_active", -1)
    if actual_total != reported_total:
        logging.warning(f"MISMATCH: kpis.total_active={reported_total} but tenders.json has {actual_total} items")
        return False
    logging.info(f"CONSISTENT: KPI total_active={reported_total} matches tender count")
    return True


def validate_llm_quality(pmo_data):
    """Measure LLM output quality metrics."""
    insights = pmo_data.get("insights", [])
    if not insights:
        logging.info("LLM_QUALITY: No insights to evaluate")
        return True

    total = len(insights)
    no_value_count = 0
    api_error_count = 0

    for item in insights:
        insight = item.get("insight", item)  # handle both nested and flat formats
        sv = insight.get("strategic_value", "")
        if sv == "No insight available":
            no_value_count += 1
        if "Gemini API Error" in sv:
            api_error_count += 1

    no_value_ratio = no_value_count / max(1, total)
    logging.info(f"LLM_QUALITY: {total} insights, {no_value_count} no-value ({no_value_ratio:.0%}), {api_error_count} API errors")

    if api_error_count > 0:
        logging.warning(f"LLM_QUALITY: {api_error_count} API errors leaked into production output")
    if no_value_ratio > MAX_NO_INSIGHT_RATIO:
        logging.warning(f"LLM_QUALITY: {no_value_ratio:.0%} of insights are 'No insight available' (threshold: {MAX_NO_INSIGHT_RATIO:.0%})")

    return api_error_count == 0


def run_validation():
    """Run all validation checks and produce a report."""
    results = {}
    critical_failure = False

    # 1. Load files
    tenders = load_json(TENDERS_FILE, "tenders.json")
    pmo = load_json(PMO_FILE, "pmo_insights.json")
    kpis = load_json(KPI_FILE, "kpis.json")

    if tenders is None or pmo is None or kpis is None:
        logging.error("CRITICAL: One or more required output files are missing or invalid.")
        critical_failure = True
        results["files_exist"] = False
    else:
        results["files_exist"] = True

    # 2. Schema validation
    if tenders is not None:
        results["tenders_schema"] = validate_schema(tenders, REQUIRED_TENDER_KEYS, "tenders", is_list=True)
        if not results["tenders_schema"]:
            critical_failure = True
    if kpis is not None:
        results["kpis_schema"] = validate_schema(kpis, REQUIRED_KPI_KEYS, "kpis")
        if not results["kpis_schema"]:
            critical_failure = True
    if pmo is not None:
        results["pmo_schema"] = validate_schema(pmo, REQUIRED_PMO_KEYS, "pmo_insights")
        if not results["pmo_schema"]:
            critical_failure = True

    # 3. Data freshness
    if kpis is not None and kpis.get("generated_at"):
        results["data_freshness"] = validate_freshness(kpis["generated_at"], "kpis.json")

    # 4. Duplicate detection
    if tenders is not None:
        results["no_duplicates"] = validate_duplicates(tenders)
        if not results["no_duplicates"]:
            critical_failure = True

    # 5. Cross-validation
    if tenders is not None and kpis is not None:
        results["cross_consistency"] = validate_cross_consistency(tenders, kpis)

    # 6. LLM quality metrics
    if pmo is not None:
        results["llm_quality"] = validate_llm_quality(pmo)

    # Write validation report
    report = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "critical_failure": critical_failure,
    }

    report_path = os.path.join(REPORTS_DIR, "validation_report.json")
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    logging.info(f"Validation report written to {report_path}")

    if critical_failure:
        logging.error("VALIDATION FAILED: Critical issues detected.")
        return 1

    logging.info("VALIDATION PASSED: All critical checks green.")
    return 0


if __name__ == "__main__":
    sys.exit(run_validation())
