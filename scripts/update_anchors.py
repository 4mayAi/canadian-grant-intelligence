import os
import sys
import json
import logging
import argparse
import io
import re
import requests
from urllib.parse import urljoin
from pypdf import PdfReader
from typing import Dict, List, Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add generic_engine to python path
script_dir = os.path.dirname(os.path.abspath(__file__))
engine_dir = os.path.abspath(os.path.join(script_dir, "..", "generic_engine"))
if engine_dir not in sys.path:
    sys.path.append(engine_dir)

from api.gemini_client import GeminiClient
from api.azure_client import AzureClient
from main import load_and_validate_config
from extractors.report_scraper import clean_extracted_text

def extract_pdf_text_deep(url: str, max_pages: int = 100, max_chars: int = 200000) -> str:
    """Downloads a PDF and extracts text from up to max_pages, capped at max_chars."""
    logging.info(f"Downloading PDF for deep extraction: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    
    pdf_file = io.BytesIO(response.content)
    reader = PdfReader(pdf_file)
    
    extracted_text = []
    pages_to_read = min(max_pages, len(reader.pages))
    logging.info(f"Extracting text from {pages_to_read} pages out of {len(reader.pages)} total pages...")
    
    for page_num in range(pages_to_read):
        try:
            text = reader.pages[page_num].extract_text()
            if text:
                extracted_text.append(text)
        except Exception as pe:
            logging.warning(f"Failed to extract text from page {page_num}: {pe}")
            
    full_text = "\n".join(extracted_text)
    cleaned = clean_extracted_text(full_text)
    return cleaned[:max_chars]

def curate_hub_anchors(gemini_client: GeminiClient, hub: str, report_text: str, report_source: str, report_url: str) -> List[Dict[str, Any]]:
    """Prompts Gemini to extract 7-10 high-value B2B facts from the report text."""
    logging.info(f"Prompting Gemini to curate anchors for hub '{hub}'...")
    
    prompt = f"""
    You are a senior research analyst and knowledge manager for the global mining industry.
    Analyze the following extracted text from the peak industry body report for the hub '{hub}'.
    
    Report Source Name: {report_source}
    Report URL: {report_url}
    
    Task:
    Extract exactly 7 to 10 high-value B2B baseline facts from the text.
    
    CRITICAL Requirements:
    1. Focus on specific regulatory, permitting, tax, infrastructure, operational, or trade metrics.
    2. Each fact MUST contain hard numbers (e.g., dollar amounts, percentages, years, ratios, metrics). Avoid vague qualitative statements.
    3. You MUST rationalize all local currencies (e.g., CAD, AUD, RMB) by showing the original value and adding a standardized USD equivalent in parentheses.
       Example: "...directly contributed CAD $111 billion (approx. USD $81.5 billion) to Canada's Gross Domestic Product..."
    4. For each fact, pinpoint the page or page range it was extracted from (e.g., "Page 5" or "Pages 12-14").
    5. Output the result as a raw JSON array of objects conforming to this schema:
       [
         {{
           "id": <temporary integer ID, e.g. 1, 2, 3...>,
           "fact": "<the rationalized fact text>",
           "source": "{report_source}",
           "pages": "<page range, e.g. 'Page 5' or 'Pages 12-14'>",
           "url": "{report_url}"
         }}
       ]
       
    Extracted Report Text:
    {report_text}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }
    
    data = gemini_client._retry_request(payload)
    if not data:
        raise RuntimeError("Failed to get response from Gemini API during curation.")
        
    try:
        text = data['candidates'][0]['content']['parts'][0]['text']
        # Clean JSON structure
        from api.gemini_client import clean_json_text
        parsed = json.loads(clean_json_text(text))
        if isinstance(parsed, list):
            validated = []
            for item in parsed:
                if "fact" in item and "pages" in item:
                    # Validate currency contains USD equivalent if it references local currency
                    fact_str = str(item["fact"])
                    if any(c in fact_str for c in ["CAD", "AUD", "RMB", "CHF"]) and "USD" not in fact_str:
                        logging.warning(f"Fact lacks USD standardization: '{fact_str}'")
                    
                    validated.append({
                        "id": int(item.get("id", 0)),
                        "fact": fact_str.strip(),
                        "source": str(item.get("source", report_source)).strip(),
                        "pages": str(item["pages"]).strip(),
                        "url": str(item.get("url", report_url)).strip()
                    })
            logging.info(f"Successfully curated {len(validated)} facts for hub '{hub}'.")
            return validated
        else:
            raise ValueError("LLM did not return a JSON list.")
    except Exception as e:
        logging.error(f"Error parsing curated facts: {e}")
        raise e

def reindex_all_facts(hub_anchors: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Reindexes all facts across all hubs sequentially from 1 to N to maintain ID uniqueness."""
    current_id = 1
    for hub in sorted(hub_anchors.keys()):
        for fact in hub_anchors[hub]:
            fact["id"] = current_id
            current_id += 1
    return hub_anchors

def main():
    parser = argparse.ArgumentParser(description="Automated Hub Anchors Update Engine")
    parser.add_argument("--config", type=str, default="configs/mining_hubs.json", help="Path to config file")
    parser.add_argument("--hub", type=str, help="Target hub name")
    parser.add_argument("--url", type=str, help="PDF Report URL to manually ingest")
    parser.add_argument("--source-name", type=str, help="Manual Report Source Name (e.g. MAC Facts & Figures 2026)")
    parser.add_argument("--force", action="store_true", help="Force curation on existing report URLs even if no new URL is detected")
    parser.add_argument("--dry-run", action="store_true", help="Run locally without uploading to Azure Storage")
    
    args = parser.parse_args()
    
    # 1. Load configuration
    config = load_and_validate_config(config_path=args.config)
    
    # 2. Instantiate clients
    azure_client = AzureClient(container_name=config.storage.azure_container)
    gemini_client = GeminiClient(
        primary_model=config.llm_settings.model_primary,
        fallback_models=config.llm_settings.model_fallbacks,
        system_instruction="You are an expert knowledge curator for the mining industry."
    )
    
    # 3. Load existing anchors
    local_anchors_path = os.path.join(os.path.dirname(args.config), config.storage.anchors_file)
    hub_anchors = {}
    
    # Load current file (Azure first, then local fallback)
    try:
        azure_anchors = azure_client.download_json(config.storage.anchors_file)
        if azure_anchors:
            hub_anchors = azure_anchors
            logging.info("Successfully loaded current anchors database from Azure.")
    except Exception as ae:
        logging.warning(f"Could not load anchors from Azure: {ae}. Falling back to local file.")
        
    if not hub_anchors:
        if os.path.exists(local_anchors_path):
            with open(local_anchors_path, "r", encoding="utf-8") as lf:
                hub_anchors = json.load(lf)
            logging.info(f"Successfully loaded current anchors database from local config: {local_anchors_path}")
        else:
            hub_anchors = {}
            logging.info("Created empty hub anchors database.")

    # 4. Handle manual or automatic ingestion
    target_url = args.url
    target_hub = args.hub
    target_source = args.source_name
    
    # Simple discovery scraper mapping
    discovery_targets = {
        "Canada": {
            "landing_page": "https://mining.ca/resources/reports/",
            "regex": r'href=["\'](https://mining\.ca/wp-content/uploads/\d{4}/\d{2}/Facts-Figures-[^"\']+\.pdf)["\']',
            "source_prefix": "MAC Facts & Figures"
        },
        "Australia": {
            "landing_page": "https://www.minerals.org.au/reports",
            "regex": r'href=["\'](https://[^\'"]+?Annual[^\'"]+?\.pdf)["\']',
            "source_prefix": "MCA Annual Report"
        }
    }
    
    if not target_url and target_hub:
        # Automatic Discovery Mode for a specific hub
        if target_hub in discovery_targets:
            target = discovery_targets[target_hub]
            logging.info(f"Running automated report discovery for '{target_hub}' on {target['landing_page']}...")
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = requests.get(target['landing_page'], headers=headers, timeout=30)
                resp.raise_for_status()
                
                matches = re.findall(target["regex"], resp.text, re.IGNORECASE)
                if matches:
                    discovered_url = matches[0]
                    logging.info(f"Discovered PDF URL on landing page: {discovered_url}")
                    
                    # Check if this is a new URL
                    existing_urls = {f["url"] for f in hub_anchors.get(target_hub, [])}
                    if discovered_url not in existing_urls or args.force:
                        target_url = discovered_url
                        # Extract year or prefix
                        year_match = re.search(r'20\d{2}', discovered_url)
                        year = year_match.group(0) if year_match else "Latest"
                        target_source = f"{target['source_prefix']} {year}"
                    else:
                        logging.info(f"Discovered URL is already cached. Skipping ingestion. Use --force to override.")
                else:
                    logging.warning(f"No PDF reports matching discovery pattern found on {target['landing_page']}")
            except Exception as de:
                logging.error(f"Discovery failed for hub '{target_hub}': {de}")
        else:
            logging.warning(f"No auto-discovery rule configured for hub '{target_hub}'. Please provide --url directly.")

    elif not target_url and not target_hub:
        # Full scan discovery mode across all configured discovery hubs
        for hub, target in discovery_targets.items():
            logging.info(f"Scanning hub '{hub}' for updates...")
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = requests.get(target['landing_page'], headers=headers, timeout=30)
                resp.raise_for_status()
                matches = re.findall(target["regex"], resp.text, re.IGNORECASE)
                if matches:
                    discovered_url = matches[0]
                    existing_urls = {f["url"] for f in hub_anchors.get(hub, [])}
                    if discovered_url not in existing_urls or args.force:
                        logging.info(f"New report discovered for hub '{hub}': {discovered_url}")
                        # Process this hub immediately
                        year_match = re.search(r'20\d{2}', discovered_url)
                        year = year_match.group(0) if year_match else "Latest"
                        source_name = f"{target['source_prefix']} {year}"
                        
                        pdf_text = extract_pdf_text_deep(discovered_url)
                        new_facts = curate_hub_anchors(gemini_client, hub, pdf_text, source_name, discovered_url)
                        
                        if new_facts:
                            hub_anchors[hub] = new_facts
                    else:
                        logging.info(f"Hub '{hub}' is already up-to-date.")
            except Exception as exc:
                logging.error(f"Full scan discovery failed for '{hub}': {exc}")

    # 5. Process target URL if set (manually or via discovery)
    if target_url:
        if not target_hub:
            logging.error("Hub name (--hub) must be provided when manually specifying a URL.")
            sys.exit(1)
        if not target_source:
            # Fallback source name
            target_source = f"{target_hub} Industry Report"
            
        logging.info(f"Starting curation process for hub '{target_hub}' using report: '{target_source}' ({target_url})")
        
        # Extract PDF text (Level 3 depth: up to 100 pages, 200k chars)
        pdf_text = extract_pdf_text_deep(target_url)
        if not pdf_text:
            logging.error("Failed to extract text from PDF. Exiting.")
            sys.exit(1)
            
        # Call LLM Curation
        new_facts = curate_hub_anchors(gemini_client, target_hub, pdf_text, target_source, target_url)
        
        # Merge new facts
        if new_facts:
            hub_anchors[target_hub] = new_facts

    # 6. Re-index and save
    hub_anchors = reindex_all_facts(hub_anchors)
    
    # Save local seed copy
    with open(local_anchors_path, "w", encoding="utf-8") as lf:
        json.dump(hub_anchors, lf, indent=2, ensure_ascii=False)
    logging.info(f"Saved local seed copy to: {local_anchors_path}")
    
    # Upload to Azure Blob Storage
    if not args.dry_run:
        logging.info(f"Uploading updated anchors database to Azure Storage: {config.storage.anchors_file}...")
        azure_client.upload_json(config.storage.anchors_file, hub_anchors)
        logging.info("Successfully updated anchors database in Azure Storage.")
    else:
        logging.info("Dry-run mode: skipping Azure Storage upload.")

if __name__ == "__main__":
    main()
