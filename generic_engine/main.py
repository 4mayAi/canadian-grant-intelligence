import argparse
import json
import logging
import os
import sys
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set, Optional
import requests

from schema import PipelineConfig
from models import GeminiInsight, ReportItem, NewsWrapper, KPIDashboard
from extractors.rss import fetch_rss_feeds
from extractors.playwright_scraper import fetch_html_news
from extractors.ckan import fetch_canadabuys_tenders
from extractors.report_scraper import (
    resolve_google_news_url,
    scrape_html_report,
    scrape_pdf_report
)
from api.gemini_client import GeminiClient
from api.azure_client import AzureClient
from api.notifier import Notifier

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

def interpolate_env_vars(data: Any) -> Any:
    """Recursively resolves ${ENV_VAR} strings inside configuration data."""
    pattern = re.compile(r"\$\{(\w+)\}")
    if isinstance(data, dict):
        return {k: interpolate_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [interpolate_env_vars(item) for item in data]
    elif isinstance(data, str):
        match = pattern.match(data)
        if match:
            env_var = match.group(1)
            # Fetch env var or keep placeholder if empty
            return os.getenv(env_var, data)
    return data

def load_and_validate_config(config_path: Optional[str] = None, config_url: Optional[str] = None) -> PipelineConfig:
    """Loads JSON config (local or remote), interpolates env variables, and validates via Pydantic V2."""
    config_data = {}
    
    if config_url:
        logging.info(f"Downloading remote configuration from {config_url}...")
        try:
            response = requests.get(config_url, timeout=30)
            response.raise_for_status()
            config_data = response.json()
        except Exception as e:
            logging.error(f"Failed to fetch config from URL: {e}")
            raise e
    elif config_path:
        logging.info(f"Loading local configuration from {config_path}...")
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    else:
        raise ValueError("Either config_path or config_url must be provided.")

    # 1. Resolve environment placeholders
    resolved_data = interpolate_env_vars(config_data)

    # 2. Enforce schema structure via Pydantic V2
    validated_config = PipelineConfig.model_validate(resolved_data)
    logging.info(f"Successfully loaded and validated configuration for topic: {validated_config.topic_id}")
    return validated_config

def clean_source_display_name(source_name: str) -> str:
    """Standardizes feed source names for presentation in KPIs and LinkedIn posts."""
    # 1. Strip news suffix and replace underscores
    display_src = source_name.replace('_News', '').replace('_', ' ')
    
    # 2. Apply display overrides
    display_src = display_src.replace('ScaleAI', 'Scale AI')
    display_src = display_src.replace('ProteinIndustries', 'Protein Industries Canada')
    
    # 3. Clean up Cluster suffix (ensure space before Supercluster)
    if 'Cluster' in display_src and 'Supercluster' not in display_src:
        display_src = display_src.replace('Cluster', ' Supercluster')
    
    # Clean up any accidental double spaces
    return display_src.replace('  ', ' ').strip()

def get_hub_from_source(source_name: str) -> str:
    source_lower = source_name.lower()
    if "canada" in source_lower or "nrcan" in source_lower:
        return "Canada"
    elif "australia" in source_lower:
        return "Australia"
    elif "china" in source_lower:
        return "China"
    elif "switzerland" in source_lower or "geneva" in source_lower:
        return "Switzerland"
    elif "uk" in source_lower or "lme" in source_lower:
        return "UK"
    else:
        return "Global"


def fetch_and_process_news(
    config: PipelineConfig,
    azure_client: AzureClient,
    gemini_client: GeminiClient,
    lookback_limit: Optional[datetime],
    processed_urls: Set[str],
    test_mode: bool = False
) -> List[dict]:
    """Fetches feed data (RSS + Playwright) concurrently, compares cache, and analyzes new items."""
    failed_feeds = []
    
    # Load Hub Anchors Database (with Azure loading, fallback seed, and auto-upload)
    hub_anchors = {}
    local_seed_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', config.storage.anchors_file))
    
    try:
        logging.info(f"Downloading hub anchors database from Azure: {config.storage.anchors_file}...")
        azure_anchors = azure_client.download_json(config.storage.anchors_file)
        if azure_anchors:
            hub_anchors = azure_anchors
            logging.info("Successfully loaded hub anchors from Azure Storage.")
        else:
            logging.warning("Hub anchors file not found in Azure. Seeding from local configs...")
    except Exception as e:
        logging.error(f"Error downloading hub anchors from Azure: {e}. Falling back to local seed...")
        
    if not hub_anchors:
        try:
            with open(local_seed_path, 'r', encoding='utf-8') as sf:
                hub_anchors = json.load(sf)
            logging.info(f"Loaded hub anchors from local seed file: {local_seed_path}")
            
            try:
                logging.info(f"Uploading seed hub anchors to Azure: {config.storage.anchors_file}...")
                azure_client.upload_json(config.storage.anchors_file, hub_anchors)
                logging.info("Successfully seeded hub anchors in Azure Storage.")
            except Exception as ue:
                logging.error(f"Failed to seed hub anchors in Azure: {ue}")
        except Exception as se:
            logging.error(f"Failed to load local seed hub anchors: {se}")
    
    # Translate config schema objects to raw dicts for scraper engines and construct dynamic search query parameters using keywords
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    sources_dict = []
    for src in config.sources:
        src_dict = src.model_dump()
        url = src_dict.get("url", "")
        if src_dict.get("type") == "rss" and "news.google.com" in url and config.keywords and not src_dict.get("skip_query_refactoring"):
            try:
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                if 'q' in query_params:
                    original_q = query_params['q'][0]
                    formatted_kws = [f'"{kw}"' if " " in kw else kw for kw in config.keywords]
                    keywords_or = " OR ".join(formatted_kws)
                    new_q = f"({original_q}) AND ({keywords_or})"
                    query_params['q'] = [new_q]
                    new_query = urlencode(query_params, doseq=True)
                    new_url = urlunparse(parsed._replace(query=new_query))
                    logging.info(f"Dynamically refactored query for source '{src_dict['name']}': {new_url}")
                    src_dict["url"] = new_url
            except Exception as e:
                logging.error(f"Failed to dynamically construct search query for source '{src_dict['name']}': {e}")
        
        fallback_url = src_dict.get("fallback_url", "")
        if fallback_url and src_dict.get("fallback_type") == "rss" and "news.google.com" in fallback_url and config.keywords and not src_dict.get("skip_query_refactoring"):
            try:
                parsed = urlparse(fallback_url)
                query_params = parse_qs(parsed.query)
                if 'q' in query_params:
                    original_q = query_params['q'][0]
                    formatted_kws = [f'"{kw}"' if " " in kw else kw for kw in config.keywords]
                    keywords_or = " OR ".join(formatted_kws)
                    new_q = f"({original_q}) AND ({keywords_or})"
                    query_params['q'] = [new_q]
                    new_query = urlencode(query_params, doseq=True)
                    new_fallback_url = urlunparse(parsed._replace(query=new_query))
                    logging.info(f"Dynamically refactored fallback query for source '{src_dict['name']}': {new_fallback_url}")
                    src_dict["fallback_url"] = new_fallback_url
            except Exception as e:
                logging.error(f"Failed to dynamically construct search query for fallback source '{src_dict['name']}': {e}")
        
        sources_dict.append(src_dict)


    # Load existing cached insights from Azure Blob early to determine if we need a deep dive
    existing_insights_list = []
    try:
        logging.info(f"Downloading cache file {config.storage.insights_file} from Azure early...")
        existing_insights = azure_client.download_json(config.storage.insights_file)
        if existing_insights and "insights" in existing_insights:
            for item in existing_insights["insights"]:
                ins_val = item.get("insight", {})
                if ins_val.get("strategic_value") == "No insight available":
                    continue
                
                # Prune tenders closed more than 30 days ago
                close_date_str = item.get("closing_date")
                if close_date_str:
                    try:
                        close_dt = datetime.strptime(close_date_str[:10], "%Y-%m-%d")
                        if datetime.utcnow() - close_dt > timedelta(days=30):
                            logging.info(f"Pruning expired cached tender: {item.get('title')} (closed on {close_date_str})")
                            continue
                    except Exception as date_err:
                        logging.warning(f"Error checking closing_date for pruning: {date_err}")
                
                existing_insights_list.append(item)
    except Exception as e:
        logging.error(f"Failed to load existing cache file {config.storage.insights_file} from storage: {e}")

    existing_insights_map = {item["link"]: item for item in existing_insights_list if "link" in item}

    # Determine pulse_only mode by checking if we have active tenders in the cache
    has_active_tenders_in_cache = False
    for item in existing_insights_list:
        close_date_str = item.get("closing_date")
        if close_date_str:
            try:
                close_dt = datetime.strptime(close_date_str[:10], "%Y-%m-%d")
                if close_dt > datetime.utcnow():
                    has_active_tenders_in_cache = True
                    break
            except:
                pass

    pulse_only = has_active_tenders_in_cache
    logging.info(f"Cache check: has_active_tenders_in_cache={has_active_tenders_in_cache}. Set pulse_only={pulse_only}")

    # Ingest RSS feeds (max items slots per cluster)
    max_items = 3 if test_mode else config.max_items_per_source
    raw_rss = fetch_rss_feeds(sources_dict, lookback_limit, max_items, failed_feeds)

    # Ingest Playwright HTML pages if any are configured
    raw_html = fetch_html_news(sources_dict, lookback_limit, max_items, failed_feeds)

    # Ingest CKAN API databases if any are configured
    raw_ckan = []
    ckan_sources = [s for s in sources_dict if s.get("type") == "ckan"]
    if ckan_sources:
        logging.info(f"Querying {len(ckan_sources)} CKAN database sources...")
        for src in ckan_sources:
            try:
                items = fetch_canadabuys_tenders(
                    ckan_api_url=src["url"],
                    keywords=config.keywords,
                    max_items=max_items,
                    lookback_days=7,
                    source_name=src["name"],
                    pulse_only=pulse_only
                )
                raw_ckan.extend(items)
            except Exception as ckan_err:
                logging.error(f"Failed to fetch CKAN tenders for source '{src['name']}': {ckan_err}")
                if failed_feeds is not None:
                    failed_feeds.append(src["name"])

    # Check if any failed Playwright feeds have a fallback RSS configured
    playwright_fallbacks = []
    for src in sources_dict:
        if src.get("name") in failed_feeds and src.get("type") == "html_playwright":
            if src.get("fallback_url") and src.get("fallback_type") == "rss":
                fallback_src = {
                    "name": src["name"],
                    "url": src["fallback_url"],
                    "type": "rss"
                }
                playwright_fallbacks.append(fallback_src)

    if playwright_fallbacks:
        logging.info(f"Attempting RSS fallback for failed Playwright sources: {[f['name'] for f in playwright_fallbacks]}")
        # Remove from failed_feeds list so if they succeed, they aren't marked as failed.
        # If they fail again, fetch_rss_feeds will add them back to failed_feeds!
        for f in playwright_fallbacks:
            if f["name"] in failed_feeds:
                failed_feeds.remove(f["name"])
        
        fallback_rss_items = fetch_rss_feeds(playwright_fallbacks, lookback_limit, max_items, failed_feeds)
        raw_html.extend(fallback_rss_items)

    # existing_insights_list and existing_insights_map were already loaded early.

    # Resiliency Fallback: If a feed failed, retain its cached items so data is not lost
    retained_items = []
    if failed_feeds:
        logging.warning(f"Failed feeds: {failed_feeds}. Retaining their cached entries.")
        for link, item in existing_insights_map.items():
            if item.get("source") in failed_feeds:
                dt_val = item.get("date")
                parsed_date = None
                if isinstance(dt_val, str):
                    try:
                        date_str = dt_val.rstrip("Z")
                        if "." in date_str:
                            parsed_date = datetime.fromisoformat(date_str)
                        else:
                            parsed_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                    except:
                        pass
                if not parsed_date:
                    parsed_date = datetime.utcnow()

                retained_items.append({
                    "source": item.get("source"),
                    "title": item.get("title"),
                    "link": link,
                    "date": parsed_date,
                    "text_to_search": (item.get("title", "") + " " + item.get("insight", {}).get("strategic_value", "")).lower()
                })

    # Combine feeds
    combined_items = raw_rss + raw_html + raw_ckan + retained_items
    
    # Resolve Google News redirect URLs offline to original destination URLs
    logging.info("Resolving Google News redirect URLs for ingested news items...")
    for item in combined_items:
        original_link = item['link']
        try:
            resolved_link = resolve_google_news_url(original_link)
            if resolved_link != original_link:
                item['link'] = resolved_link
        except Exception as err:
            logging.error(f"Failed to resolve URL {original_link}: {err}")
            
    # Deduplicate URL keys
    seen_links = set()
    deduped_items = []
    for item in combined_items:
        if item['link'] not in seen_links:
            deduped_items.append(item)
            seen_links.add(item['link'])

    unprocessed_items = []
    final_insights = []

    for item in deduped_items:
        link = item['link']
        if link in existing_insights_map:
            # Re-use cached analysis (no LLM call)
            cached_item = existing_insights_map[link]
            # Copy/update tender metadata fields from the crawled item if present
            for field in ["closing_date", "province", "province_abbrev", "category", "category_label", "description", "type"]:
                if field in item:
                    cached_item[field] = item[field]
            final_insights.append(cached_item)
            processed_urls.add(link)
        elif link in processed_urls:
            # Already processed (either discarded or old). Skip!
            logging.info(f"Skipping already processed URL: {link}")
        else:
            unprocessed_items.append(item)

    # 3. LLM-Assisted Event Clustering Deduplication
    if len(unprocessed_items) > 1:
        logging.info(f"Running LLM clustering to deduplicate {len(unprocessed_items)} new unprocessed articles...")
        unprocessed_metadata = [{"id": idx, "title": item["title"], "source": item["source"]} for idx, item in enumerate(unprocessed_items)]
        try:
            selected_ids = gemini_client.filter_duplicate_articles(unprocessed_metadata)
            
            # Safety Gate: If returned selected_ids is empty but input was not, fall back to retaining all items
            if not selected_ids:
                logging.warning("LLM clustering returned empty list of selected IDs. Falling back to retaining all articles.")
                selected_ids = list(range(len(unprocessed_items)))
            else:
                # Safety Gate: Defensively filter out invalid/out-of-bounds indices
                selected_ids = [idx for idx in selected_ids if isinstance(idx, int) and 0 <= idx < len(unprocessed_items)]
                
            # Filter unprocessed items to selected ones
            selected_unprocessed = [unprocessed_items[idx] for idx in selected_ids]
            
            # Record skipped duplicate URLs as processed in registry to avoid re-evaluating on future runs
            selected_links = {item["link"] for item in selected_unprocessed}
            skipped_count = 0
            for item in unprocessed_items:
                if item["link"] not in selected_links:
                    processed_urls.add(item["link"])
                    skipped_count += 1
            
            logging.info(f"LLM clustering finished. Selected {len(selected_unprocessed)} unique articles, skipped {skipped_count} duplicates.")
            unprocessed_items = selected_unprocessed
            
        except Exception as e:
            logging.error(f"Error during LLM event clustering deduplication: {e}. Retaining all articles as fallback.")

    if test_mode:
        unprocessed_items = unprocessed_items[:2]

    # Enrich news items with full-text content prior to analysis
    for item in unprocessed_items:
        logging.info(f"Running text extraction for: '{item['title']}'...")
        try:
            if ".pdf" in item['link'].lower():
                extracted_text = scrape_pdf_report(item['link'])
            else:
                extracted_text = scrape_html_report(item['link'])
            
            if extracted_text and len(extracted_text.strip()) > 200:
                item['text_to_search'] = extracted_text
                logging.info(f"Enriched '{item['title'][:40]}...' with {len(extracted_text)} characters of full text. Preview: {extracted_text[:100]}...")
            else:
                logging.warning(f"Extracted content was empty or too thin. Falling back to default metadata.")
        except Exception as exc:
            logging.error(f"Error scraping news item: {exc}. Falling back to default metadata.")

    # Group unprocessed items by hub to prevent context contamination
    source_hubs = {src.name: (src.hub if src.hub else get_hub_from_source(src.name)) for src in config.sources}
    items_by_hub = {}
    for item in unprocessed_items:
        hub = source_hubs.get(item['source']) or get_hub_from_source(item['source'])
        if hub not in items_by_hub:
            items_by_hub[hub] = []
        items_by_hub[hub].append(item)

    # Batch process new items by hub
    for hub, hub_items in items_by_hub.items():
        hub_facts = hub_anchors.get(hub, [])
        anchor_context = ""
        if hub_facts:
            anchor_lines = []
            for fact_obj in hub_facts:
                anchor_lines.append(f"[Fact ID: {fact_obj['id']}] {fact_obj['fact']}")
            anchor_context = "\n".join(anchor_lines)

        BATCH_SIZE = 5
        for i in range(0, len(hub_items), BATCH_SIZE):
            batch = hub_items[i:i + BATCH_SIZE]
            logging.info(f"Analyzing batch of {len(batch)} news items for hub '{hub}' with Gemini...")
            
            contents = [
                f"Title: {item['title']}\nSource: {item['source']}\nDate: {item.get('date', 'Unknown')}\nContext: {item['text_to_search']}"
                for item in batch
            ]
            
            today_str = datetime.utcnow().strftime("%B %d, %Y")
            insight_models = gemini_client.get_gemini_insights_batch(
                contents,
                anchor_context=anchor_context,
                current_date=today_str
            )
            
            for item, insight_model in zip(batch, insight_models):
                processed_urls.add(item['link'])
                
                # Relevancy Filtering: If Gemini returned "No insight available", discard the item
                if insight_model.strategic_value == "No insight available":
                    logging.info(f"Discarding irrelevant/low-value news item: {item['title']}")
                    continue

                # Dynamically resolve references from grounded_fact_ids to prevent LLM hallucinations
                anchor_reference = None
                if insight_model.grounded_fact_ids:
                    resolved_facts = []
                    for fid in insight_model.grounded_fact_ids:
                        matching_fact = next((f for f in hub_facts if f["id"] == fid), None)
                        if matching_fact:
                            resolved_facts.append({
                                "source_name": matching_fact["source"],
                                "page_range": matching_fact["pages"],
                                "url": matching_fact["url"]
                            })
                    if resolved_facts:
                        # Standardize reference on the primary utilized fact
                        anchor_reference = resolved_facts[0]
                
                insight_model.anchor_reference = anchor_reference

                dt = item.get('date')
                date_str = dt.isoformat() + "Z" if isinstance(dt, datetime) else str(dt)

                report_item_dict = {
                    "source": item['source'],
                    "title": item['title'],
                    "link": item['link'],
                    "date": date_str,
                    "insight": insight_model.to_dict()
                }
                # Copy tender metadata fields from raw item if present
                for field in ["closing_date", "province", "province_abbrev", "category", "category_label", "description", "type"]:
                    if field in item:
                        report_item_dict[field] = item[field]
                final_insights.append(report_item_dict)

    # Sort final insights descending by date
    def parse_date_safely(item):
        d = item.get("date")
        if isinstance(d, datetime):
            return d
        if isinstance(d, str):
            try:
                return datetime.fromisoformat(d.rstrip("Z"))
            except:
                pass
        return datetime.min

    final_insights.sort(key=parse_date_safely, reverse=True)
    return final_insights

def generate_dashboard_kpis(insights: List[dict], gemini_client: GeminiClient) -> dict:
    """Consolidates metrics for the run insights."""
    total_active = len(insights)
    
    new_today = 0
    for ins in insights:
        try:
            dt_str = ins.get('date', '').rstrip("Z")
            if "." in dt_str:
                dt = datetime.fromisoformat(dt_str)
            else:
                dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
            if (datetime.utcnow() - dt).days <= 1:
                new_today += 1
        except Exception:
            pass
            
    # Calculate tenders closing in the next 7 days
    closing_this_week = 0
    now = datetime.utcnow()
    one_week_later = now + timedelta(days=7)
    for ins in insights:
        close_date_str = ins.get("closing_date")
        if close_date_str:
            try:
                close_dt = datetime.strptime(close_date_str[:10], "%Y-%m-%d")
                if now <= close_dt <= one_week_later:
                    closing_this_week += 1
            except:
                pass

    # Calculate top contributing source/category
    source_counts = {}
    for ins in insights:
        src = ins.get("source", "")
        # Clean display name: replace underscores with spaces, strip _News, and apply known overrides
        display_src = clean_source_display_name(src)
        if display_src:
            source_counts[display_src] = source_counts.get(display_src, 0) + 1
            
    top_category = "Mixed Sectors"
    if source_counts:
        max_count = max(source_counts.values())
        top_sources = [src for src, count in source_counts.items() if count == max_count]
        if len(top_sources) == 1:
            top_category = top_sources[0]
        else:
            top_category = "Mixed Sectors"  # Explicit tie = no single winner

    hero_hook = gemini_client.get_hero_hook(insights)
    
    return KPIDashboard(
        total_active=total_active,
        new_today=new_today,
        closing_this_week=closing_this_week,
        top_category=top_category,
        hero_hook=hero_hook,
        generated_at=datetime.utcnow().isoformat() + "Z"
    ).to_dict()

def validate_dynamic_outputs(output_dir: str, config: PipelineConfig):
    """Enforces dynamic layout rules for outputs prior to Azure cloud upload."""
    logging.info("Running automated schema validation checks...")
    
    insights_file = os.path.join(output_dir, config.storage.insights_file)
    kpis_file = os.path.join(output_dir, config.storage.kpis_file)

    for path in (insights_file, kpis_file):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Validation failure: missing file {path}")
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if not data:
                    raise ValueError(f"Validation failure: empty data in {path}")
            except json.JSONDecodeError:
                raise ValueError(f"Validation failure: malformed JSON in {path}")

    # Specific schema checks
    with open(kpis_file, "r") as f:
        kpis = json.load(f)
        for key in ("total_active", "new_today", "hero_hook", "generated_at"):
            if key not in kpis:
                raise ValueError(f"KPI schema violation: missing key {key}")

    with open(insights_file, "r") as f:
        insights_wrapper = json.load(f)
        if "insights" not in insights_wrapper or not isinstance(insights_wrapper["insights"], list):
            raise ValueError("Insights wrapper violation: missing insights list array")

def run_engine_pipeline(config_path: Optional[str] = None, config_url: Optional[str] = None, dry_run: bool = False):
    setup_logging()
    logging.info("Initializing Config-driven Pipeline Execution...")
    
    # 1. Load config
    config = load_and_validate_config(config_path, config_url)
    
    # 2. Instantiate Clients
    azure_client = AzureClient(container_name=config.storage.azure_container)
    gemini_client = GeminiClient(
        primary_model=config.llm_settings.model_primary,
        fallback_models=config.llm_settings.model_fallbacks,
        system_instruction=config.llm_settings.system_instruction
    )
    notifier = Notifier(
        discord_url=config.distribution.discord_webhook,
        alert_email=config.distribution.smtp_recipient
    )

    try:
        # Define Lookback
        lookback_days = int(os.getenv("SCRAPE_LOOKBACK_DAYS", "30"))
        lookback_limit = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Load processed URL history registry
        processed_urls_raw = azure_client.download_json(config.storage.processed_urls_file) or {}
        processed_urls_registry = processed_urls_raw if isinstance(processed_urls_raw, dict) else {}
        processed_urls = set(processed_urls_registry.keys())
        initial_url_count = len(processed_urls)
        
        # 3. Extract and Process News/Tenders
        insights = fetch_and_process_news(
            config=config,
            azure_client=azure_client,
            gemini_client=gemini_client,
            lookback_limit=lookback_limit,
            processed_urls=processed_urls,
            test_mode=dry_run
        )

        # 4. Consolidate Dashboard KPIs
        kpis = generate_dashboard_kpis(insights, gemini_client)

        # Select top 5 featured items for digest, capping at 2 items per hub to ensure regional balance
        source_hubs = {src.name: (src.hub if src.hub else get_hub_from_source(src.name)) for src in config.sources}
        featured_insights = []
        hub_counts = {}
        for item in insights:
            src = item.get("source", "")
            hub = source_hubs.get(src) or get_hub_from_source(src)
            count = hub_counts.get(hub, 0)
            if count < 2:
                featured_insights.append(item)
                hub_counts[hub] = count + 1
            if len(featured_insights) == 5:
                break

        # 5. Compile LinkedIn summary post
        # Build enriched context: title + hook + full strategic_value for top 5 items
        news_summaries_list = []
        for item in featured_insights:
            title = item.get('title', '')
            hook = item.get('insight', {}).get('linkedin_hook', '')
            strat = item.get('insight', {}).get('strategic_value', '')
            news_summaries_list.append(f"- **{title}**\n  *Hook:* {hook}\n  *Key Insights:* {strat}")
        summaries_str = "\n\n".join(news_summaries_list)

        today_str = datetime.utcnow().strftime("%B %d, %Y")
        linkedin_post = gemini_client.generate_linkedin_post(summaries_str, current_date=today_str, dashboard_url=config.dashboard_url)
        suggested_post = linkedin_post.get("article_content", "No post text compiled.") if linkedin_post else ""

        # Post-process: Automatically hyperlink names in the body (using lookarounds to prevent double-wrapping)
        hyperlinks = config.localization_mappings
        for name, link in hyperlinks.items():
            pattern = re.compile(rf'(?<!\[){re.escape(name)}(?!\])')
            suggested_post = pattern.sub(link, suggested_post)

        # Append source references for clean tracking
        if featured_insights:
            suggested_post += "\n\n### Featured News & Sources\n"
            for item in featured_insights:
                src_name = clean_source_display_name(item.get("source", ""))
                suggested_post += f"- [{item['title']}]({item['link']}) ({src_name})\n"

        pmo_wrapper = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "linkedin_post": suggested_post,
            "insights": insights
        }

        # Resolve output directory relative to this script's directory instead of process Cwd
        engine_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(engine_root, "docs", "data", config.topic_id)
        os.makedirs(output_dir, exist_ok=True)
        
        insights_local_path = os.path.join(output_dir, config.storage.insights_file)
        kpis_local_path = os.path.join(output_dir, config.storage.kpis_file)

        with open(insights_local_path, "w", encoding="utf-8") as f:
            json.dump(pmo_wrapper, f, indent=2, ensure_ascii=False)
        with open(kpis_local_path, "w", encoding="utf-8") as f:
            json.dump(kpis, f, indent=2, ensure_ascii=False)
            
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        local_manifest = []
        if config.storage.manifest_file:
            manifest_local_path = os.path.join(output_dir, config.storage.manifest_file)
            if os.path.exists(manifest_local_path):
                try:
                    with open(manifest_local_path, "r", encoding="utf-8") as f:
                        local_manifest = json.load(f)
                except Exception as e:
                    logging.warning(f"Failed to load local manifest: {e}")
            if not isinstance(local_manifest, list):
                local_manifest = []
            if date_str not in local_manifest:
                local_manifest.append(date_str)
            local_manifest.sort(reverse=True)
            with open(manifest_local_path, "w", encoding="utf-8") as f:
                json.dump(local_manifest, f, indent=2, ensure_ascii=False)
            logging.info(f"Local manifest updated at {manifest_local_path}: {local_manifest}")

        logging.info(f"Local files generated successfully inside: {output_dir}")

        # 6. Generate social card image using Playwright
        social_card_local_path = os.path.join(output_dir, "social_card.png")
        script_path = os.path.join(engine_root, "scripts", "generate_social_card.py")
        
        if os.path.exists(script_path):
            logging.info("Generating social card image via Playwright...")
            import subprocess
            clean_url = (config.dashboard_url or "").replace("https://", "").replace("http://", "")
            try:
                subprocess.run([
                    sys.executable, script_path,
                    kpis.get("hero_hook", ""), kpis.get("top_category", "Mixed Sectors"), social_card_local_path,
                    clean_url
                ], check=True)
                logging.info(f"Successfully generated social card locally at {social_card_local_path}")
            except Exception as e:
                logging.error(f"Failed to generate social card: {e}")
        else:
            logging.warning(f"Social card generator script not found at {script_path}. Skipping card generation.")

        # 7. Validate Outputs before uploading to storage
        validate_dynamic_outputs(output_dir, config)
        logging.info("Dynamic output verification passed successfully.")

        # 8. Upload to cloud storage
        if not dry_run:
            # Temporary file names for atomic deployment staging
            insights_temp = f"{os.path.splitext(config.storage.insights_file)[0]}_temp.json"
            kpis_temp = f"{os.path.splitext(config.storage.kpis_file)[0]}_temp.json"
            
            # Stage temporary files on Azure
            insights_ok = azure_client.upload_json(insights_temp, pmo_wrapper)
            kpis_ok = azure_client.upload_json(kpis_temp, kpis)
            
            if insights_ok and kpis_ok:
                # Perform fast server-side copies to final files
                azure_client.copy_blob(insights_temp, config.storage.insights_file)
                azure_client.copy_blob(kpis_temp, config.storage.kpis_file)
                
                # Cleanup temp files
                azure_client.delete_blob(insights_temp)
                azure_client.delete_blob(kpis_temp)
            else:
                logging.error("Failed to upload temporary staged files. Aborting main swap.")
                raise RuntimeError("Failed to upload primary dashboard data to Azure Storage.")
            
            # Upload social card binary image
            if os.path.exists(social_card_local_path):
                azure_client.upload_file(social_card_local_path, "latest_social_card.png", "image/png")
                azure_client.upload_file(social_card_local_path, f"social_card_{date_str}.png", "image/png")
            
            # Historical backup archive - staged and swapped atomically
            hist_insights_file = f"reports/{config.topic_id}_insights_{date_str}.json"
            hist_kpis_file = f"reports/{config.topic_id}_kpis_{date_str}.json"
            hist_insights_temp = f"reports/{config.topic_id}_insights_{date_str}_temp.json"
            hist_kpis_temp = f"reports/{config.topic_id}_kpis_{date_str}_temp.json"
            
            hist_insights_ok = azure_client.upload_json(hist_insights_temp, pmo_wrapper)
            hist_kpis_ok = azure_client.upload_json(hist_kpis_temp, kpis)
            
            if hist_insights_ok and hist_kpis_ok:
                azure_client.copy_blob(hist_insights_temp, hist_insights_file)
                azure_client.copy_blob(hist_kpis_temp, hist_kpis_file)
                azure_client.delete_blob(hist_insights_temp)
                azure_client.delete_blob(hist_kpis_temp)
            else:
                logging.error("Failed to upload historical temporary staged files. Aborting historical swap.")
                raise RuntimeError("Failed to upload historical backup data to Azure Storage.")

            # Compile and upload remote manifest
            if config.storage.manifest_file:
                remote_manifest = azure_client.download_json(config.storage.manifest_file)
                if remote_manifest is None or not isinstance(remote_manifest, list):
                    logging.info("Remote manifest not found or invalid. Initializing from local manifest.")
                    remote_manifest = local_manifest
                else:
                    if date_str not in remote_manifest:
                        remote_manifest.append(date_str)
                    remote_manifest.sort(reverse=True)
                manifest_ok = azure_client.upload_json(config.storage.manifest_file, remote_manifest)
                if not manifest_ok:
                    raise RuntimeError("Failed to upload date manifest to Azure Storage.")
                logging.info(f"Uploaded updated manifest to Azure: {remote_manifest}")

            # Sync processed URLs list
            if len(processed_urls) > initial_url_count:
                for url in processed_urls:
                    if url not in processed_urls_registry:
                        processed_urls_registry[url] = datetime.utcnow().isoformat() + "Z"
                urls_ok = azure_client.upload_json(config.storage.processed_urls_file, processed_urls_registry)
                if not urls_ok:
                    raise RuntimeError("Failed to upload processed URL state registry to Azure Storage.")
                logging.info(f"Updated URL state registry (Total URLs: {len(processed_urls_registry)}) uploaded to Azure.")

        # 9. SMTP Email Distribution
        if not dry_run:
            try:
                email_subject = f"{datetime.now().strftime('%b %d, %Y')} — {config.display_name} — {kpis.get('hero_hook', '')}"
                
                # Assemble the markdown content for the email
                digest_md = f"# {kpis.get('hero_hook', f'{config.display_name} Daily Digest')}\n\n"
                digest_md += f"**Top Contributor**: {kpis.get('top_category', 'Mixed Sectors')}\n\n"
                digest_md += f"### Strategic B2B Digest\n\n"
                digest_md += f"{suggested_post}\n\n"
                digest_md += f"---\n\n"
                digest_md += f"**View Full Interactive Dashboard**: {config.dashboard_url}\n"
                
                logging.info("Sending success digest email via SMTP...")
                topic_name = config.display_name
                from_name = config.display_name
                if from_name.endswith(" Intelligence"):
                    from_name = from_name[:-13]
                notifier.send_digest(
                    subject=email_subject,
                    markdown_content=digest_md,
                    social_card_path=social_card_local_path,
                    from_name=from_name,
                    topic_name=topic_name
                )
            except Exception as mail_err:
                logging.error(f"Failed to distribute daily clusters email digest: {mail_err}")
                raise mail_err

        logging.info(f"Pipeline job completed successfully. Items processed: {len(insights)}.")
        logging.info(f"Telemetry metrics: {json.dumps(gemini_client.get_stats())}")

    except Exception as e:
        logging.error(f"Pipeline run encountered crash error: {e}")
        if not dry_run:
            notifier.notify_failure("Pipeline orchestrator", str(e), topic_name=config.display_name)
        raise e

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generic Config-Driven Ingestion Engine")
    parser.add_argument("--config", type=str, help="Absolute or relative path to local config JSON")
    parser.add_argument("--config-url", type=str, help="URL to download configuration JSON remotely")
    parser.add_argument("--dry-run", action="store_true", help="Run checks locally without committing files or alerts")
    
    # Read environment variables as fallbacks
    args = parser.parse_args()
    cfg_path = args.config
    cfg_url = args.config_url or os.getenv("CONFIG_URL")
    
    if not cfg_path and not cfg_url:
        # Fallback default configuration for local testing
        cfg_path = "configs/innovation_clusters.json"

    run_engine_pipeline(config_path=cfg_path, config_url=cfg_url, dry_run=args.dry_run)
