import logging
import re
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

SHINY_NOWCAST_URL = "https://canadianchamber.shinyapps.io/Nowcast/"
FALLBACK_HOST_URL = "https://businessdatalab.ca/bdlnow/"

def fetch_bdlnow_indicators(timeout_ms: int = 20000) -> Optional[Dict[str, Any]]:
    """
    Fetches real-time GDP growth nowcast estimates and high-frequency indicator impacts
    from the BDLNow R Shiny app. Performs defensive parsing with graceful fallback.
    """
    logging.info("Fetching BDLNow GDP Nowcast estimates via Playwright...")
    
    data_result: Dict[str, Any] = {
        "gdp_nowcast_quarter": None,
        "gdp_nowcast_estimate": None,
        "previous_estimate": None,
        "update_date": None,
        "change": None,
        "release_schedule": None,
        "impact_indicators": []
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            page = context.new_page()
            
            # 1. Navigate to Shiny app direct URL
            try:
                page.goto(SHINY_NOWCAST_URL, timeout=timeout_ms, wait_until="networkidle")
            except Exception as nav_err:
                logging.warning(f"Direct Shiny navigation timed out/failed: {nav_err}. Retrying fallback host page...")
                page.goto(FALLBACK_HOST_URL, timeout=timeout_ms, wait_until="domcontentloaded")

            # 2. Wait for h4 element or plotly container to render
            try:
                page.wait_for_selector("h4", timeout=10000)
            except Exception:
                logging.warning("Timed out waiting for 'h4' summary tag in BDLNow app.")

            # 3. Extract H4 Summary Text
            h4_elements = page.query_selector_all("h4")
            summary_text = ""
            for h4 in h4_elements:
                txt = h4.inner_text().strip()
                if "BDL Nowcast estimates" in txt:
                    summary_text = txt
                    break

            if summary_text:
                logging.info(f"Extracted BDLNow summary text: {summary_text}")
                data_result["raw_summary"] = summary_text
                
                # Regex Tier 1 Parsing
                pattern = r"As of (?P<update_date>[^,]+, \d{4}), the BDL Nowcast estimates that Canada's real GDP quarterly growth for (?P<quarter>Q\d \d{4}) will be (?P<current>[\d\.-]+)%?, compared with the previous estimate of (?P<prev>[\d\.-]+)%?, as of (?P<prev_date>[^,]+, \d{4}), representing a change of (?P<change>[\d\.-]+)"
                match = re.search(pattern, summary_text)
                if match:
                    data_result["update_date"] = match.group("update_date")
                    data_result["gdp_nowcast_quarter"] = match.group("quarter")
                    data_result["gdp_nowcast_estimate"] = f"{match.group('current')}%"
                    data_result["previous_estimate"] = f"{match.group('prev')}%"
                    data_result["change"] = match.group("change")
                else:
                    # Defensive Tier 2 Fallback extraction
                    logging.info("Regex tier 1 missed. Applying defensive tier 2 fallback extraction...")
                    q_match = re.search(r"(Q\d \d{4})", summary_text)
                    if q_match:
                        data_result["gdp_nowcast_quarter"] = q_match.group(1)
                    num_matches = re.findall(r"(\b\d+\.\d+\b)", summary_text)
                    if num_matches:
                        data_result["gdp_nowcast_estimate"] = f"{num_matches[0]}%"
                        if len(num_matches) > 1:
                            data_result["previous_estimate"] = f"{num_matches[1]}%"

            # 4. Extract Data Release Table if available
            try:
                rows = page.query_selector_all("div#table_dt table tbody tr")
                for row in rows[:5]:
                    cols = [td.inner_text().strip() for td in row.query_selector_all("td")]
                    if len(cols) >= 5:
                        data_result["impact_indicators"].append({
                            "date": cols[0],
                            "category": cols[1],
                            "indicator": cols[2],
                            "actual": cols[3],
                            "impact": cols[4]
                        })
            except Exception as e:
                logging.debug(f"Could not parse data release impact table: {e}")

            browser.close()
            return data_result

    except Exception as exc:
        logging.error(f"Failed to fetch BDLNow indicators: {exc}. Returning None for graceful fallback.")
        return None
