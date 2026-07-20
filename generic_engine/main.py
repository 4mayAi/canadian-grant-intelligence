import argparse
import json
import logging
import os
import sys
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set, Optional
import requests

# Load environment variables for local runs/tests
try:
    import dotenv
    dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))
except ImportError:
    pass

from schema import PipelineConfig
from models import GeminiInsight, ReportItem, NewsWrapper, KPIDashboard
from extractors.rss import fetch_rss_feeds
from extractors.playwright_scraper import fetch_html_news
from extractors.youtube import fetch_youtube_videos
from extractors.ckan import fetch_canadabuys_tenders, get_category_label
from extractors.report_scraper import (
    resolve_google_news_url,
    scrape_html_report,
    scrape_pdf_report
)
from api.gemini_client import GeminiClient
from api.azure_client import AzureClient
from api.notifier import Notifier
from api.profile_matcher import ProfileMatcher

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

def matches_keywords(text: str, keywords: List[str]) -> bool:
    """Performs case-insensitive word-boundary matching for short acronyms and substring matching for longer terms."""
    if not text:
        return False
    text_lower = text.lower().replace('_', ' ')
    for kw in keywords:
        kw_lower = kw.lower()
        if len(kw) <= 4:
            if re.search(r'\b' + re.escape(kw_lower) + r'\b', text_lower):
                return True
        else:
            if kw_lower in text_lower:
                return True
    return False

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
    test_mode: bool = False,
    pulse_only_override: Optional[bool] = None
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

    # Validate anchor lifecycle metadata
    if hub_anchors:
        try:
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            for hub_name, facts in hub_anchors.items():
                if isinstance(facts, list):
                    for fact in facts:
                        if isinstance(fact, dict):
                            review_by = fact.get("review_by")
                            fact_id = fact.get("id") or fact.get("fact_id")
                            if review_by and review_by < today_str:
                                logging.warning(
                                    f"STALE ANCHOR: Fact ID {fact_id} in hub '{hub_name}' has expired review date '{review_by}' (today: '{today_str}')."
                                )
        except Exception as ve:
            logging.error(f"Error validating anchor lifecycle metadata: {ve}")

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

    if pulse_only_override is not None:
        pulse_only = pulse_only_override
        logging.info(f"Override: Set pulse_only={pulse_only} via parameter")
    else:
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

    # Ingest YouTube channel videos if any are configured
    raw_youtube = fetch_youtube_videos(sources_dict, lookback_limit, max_items, failed_feeds)

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
                    max_items=150,
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
    combined_items = raw_rss + raw_html + raw_ckan + raw_youtube + retained_items
    
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
            for field in ["closing_date", "province", "province_abbrev", "category", "category_label", "description", "type", "partner_list", "organization", "solicitation_number", "notice_type", "procurement_method", "selection_criteria", "trade_agreements", "recommended_playbook"]:
                if field in item:
                    cached_item[field] = item[field]
            final_insights.append(cached_item)
            processed_urls.add(link)
        elif link in processed_urls:
            # Already processed (either discarded or old). Skip!
            logging.info(f"Skipping already processed URL: {link}")
        else:
            # Relevancy pre-filter: discard news/tenders that don't match any keywords early
            skip_kw = False
            if "source" in item:
                source_name = item["source"]
                if source_name.endswith("_fallback"):
                    source_name = source_name[:-9]
                src_config = next((s for s in config.sources if s.name == source_name), None)
                if src_config and getattr(src_config, "skip_keyword_filter", False):
                    skip_kw = True

            text_to_search = (item.get("title", "") + " " + item.get("text_to_search", "")).lower()
            if skip_kw or "youtube.com/watch" in link or "youtu.be/" in link or matches_keywords(text_to_search, config.keywords):
                unprocessed_items.append(item)
            else:
                logging.info(f"Discarding newly scraped item due to keyword mismatch (pre-filter): {item.get('title')}")
                processed_urls.add(link)

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
            if "youtube.com/watch" in item['link'] or "youtu.be/" in item['link']:
                extracted_text = gemini_client.analyze_video(item['link'])
            elif ".pdf" in item['link'].lower():
                extracted_text = scrape_pdf_report(item['link'])
            else:
                extracted_text = scrape_html_report(item['link'], item)
            
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
            
            contents = []
            for item in batch:
                base = (
                    f"Title: {item['title']}\n"
                    f"Source: {item['source']}\n"
                    f"Date: {item.get('date', 'Unknown')}\n"
                    f"Context: {item['text_to_search']}"
                )
                # Inject playbook label for CKAN tenders only.
                # "Unclassified" is intentionally excluded — it is a data-only label
                # for the dashboard and must never reach the LLM.
                playbook = item.get("recommended_playbook")
                if playbook and playbook != "Unclassified":
                    base += f"\nRecommended Playbook: {playbook}"
                contents.append(base)
            
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

                # Post-process co-bidding alignments to restore markdown links
                co_bid = insight_model.co_bidding_opportunity
                if co_bid and item.get("text_to_search"):
                    try:
                        md_links = re.findall(r'\[([^\]]+)\]\((https?://canadabuys\.canada\.ca/en/node/preview/[^\)]+)\)', item["text_to_search"])
                        for name, url in md_links:
                            # Safely replace company name with its markdown link (case-insensitive, preventing double-wrapping)
                            pattern = re.compile(rf'(?<!\[){re.escape(name)}(?!\])', re.IGNORECASE)
                            co_bid = pattern.sub(f'[{name}]({url})', co_bid)
                        insight_model.co_bidding_opportunity = co_bid
                    except Exception as link_err:
                        logging.warning(f"Failed to post-process co-bidding links: {link_err}")

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
                if isinstance(dt, datetime):
                    date_str = dt.replace(microsecond=0).isoformat() + "Z"
                else:
                    date_str = str(dt)

                report_item_dict = {
                    "source": item['source'],
                    "title": item['title'],
                    "link": item['link'],
                    "date": date_str,
                    "insight": insight_model.to_dict()
                }
                # Copy tender metadata fields from raw item if present
                for field in ["closing_date", "province", "province_abbrev", "category", "category_label", "description", "type", "partner_list", "organization", "solicitation_number", "notice_type", "procurement_method", "selection_criteria", "trade_agreements", "recommended_playbook"]:
                    if field in item:
                        report_item_dict[field] = item[field]
                final_insights.append(report_item_dict)

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

    # Carry forward cached insights that were not scraped in the current run but are still valid and match keywords
    for link, item in existing_insights_map.items():
        if link not in seen_links:
            title_val = item.get("title", "")
            desc_val = item.get("description", "")
            strat_val = ""
            if isinstance(item.get("insight"), dict):
                strat_val = item["insight"].get("strategic_value", "")
            
            text_to_search = (title_val + " " + desc_val + " " + strat_val).lower().replace('_', ' ')
            
            if not matches_keywords(text_to_search, config.keywords):
                logging.info(f"Pruning cached item due to keyword mismatch (false positive check): {title_val}")
                continue
                
            is_active_tender = False
            close_date_str = item.get("closing_date")
            if close_date_str:
                try:
                    close_dt = datetime.strptime(close_date_str[:10], "%Y-%m-%d")
                    if close_dt > datetime.utcnow():
                        is_active_tender = True
                except:
                    pass
            
            is_recent = False
            try:
                dt = parse_date_safely(item)
                if datetime.utcnow() - dt <= timedelta(days=30):
                    is_recent = True
            except:
                pass
                
            if is_active_tender or is_recent:
                final_insights.append(item)
                seen_links.add(link)

    final_insights.sort(key=parse_date_safely, reverse=True)
    return final_insights

def generate_dashboard_kpis(insights: List[dict], gemini_client: GeminiClient, tenders: Optional[List[dict]] = None) -> dict:
    """Consolidates metrics for the run insights."""
    if tenders is not None:
        total_active = len(tenders)
        
        new_today = sum(1 for t in tenders if t.get('type') == 'New')
        
        closing_this_week = 0
        now_dt = datetime.utcnow()
        one_week_later = now_dt + timedelta(days=7)
        for t in tenders:
            close_date_str = t.get("closing_date")
            if close_date_str:
                try:
                    close_dt = datetime.strptime(close_date_str[:10], "%Y-%m-%d")
                    if now_dt <= close_dt <= one_week_later:
                        closing_this_week += 1
                except:
                    pass
                    
        # Calculate top category from tenders
        categories = {}
        for t in tenders:
            cat = t.get('category', 'Uncategorized').replace('*', '').strip()
            categories[cat] = categories.get(cat, 0) + 1
            
        top_category = "Mixed Sectors"
        if categories:
            sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
            lead = sorted_cats[0]
            percentage = round((lead[1] / max(1, total_active)) * 100)
            is_tie = len(sorted_cats) > 1 and sorted_cats[0][1] == sorted_cats[1][1]
            is_diversified = len(sorted_cats) > 1 and percentage < 50
            if is_tie:
                top_category = "Mixed Sectors"
            elif is_diversified:
                top_category = "Diversified"
            else:
                name = lead[0][:15] + "..." if len(lead[0]) > 18 else lead[0]
                top_category = f"{name} ({percentage}%)"
                
        hero_hook = gemini_client.get_hero_hook(insights, tenders)
    else:
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

    files_to_check = [insights_file, kpis_file]
    if config.storage.tenders_file:
        files_to_check.append(os.path.join(output_dir, config.storage.tenders_file))

    for path in files_to_check:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Validation failure: missing file {path}")
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if config.storage.tenders_file and path == os.path.join(output_dir, config.storage.tenders_file):
                    if not isinstance(data, list):
                        raise ValueError(f"Validation failure: tenders data in {path} must be a list")
                else:
                    if not data:
                        raise ValueError(f"Validation failure: empty data in {path}")
            except json.JSONDecodeError:
                raise ValueError(f"Validation failure: malformed JSON in {path}")

    # Specific schema checks
    with open(kpis_file, "r", encoding="utf-8") as f:
        kpis = json.load(f)
        for key in ("total_active", "new_today", "hero_hook", "generated_at"):
            if key not in kpis:
                raise ValueError(f"KPI schema violation: missing key {key}")

    with open(insights_file, "r", encoding="utf-8") as f:
        insights_wrapper = json.load(f)
        if "insights" not in insights_wrapper or not isinstance(insights_wrapper["insights"], list):
            raise ValueError("Insights wrapper violation: missing insights list array")

def run_engine_pipeline(config_path: Optional[str] = None, config_url: Optional[str] = None, dry_run: bool = False, run_type: str = "deep_dive"):
    setup_logging()
    logging.info("Initializing Config-driven Pipeline Execution...")
    
    # 1. Load config
    config = load_and_validate_config(config_path, config_url)
    logging.info(f"Running Skill '{config.topic_id}' v{config.skill_version} (Schema v{config.schema_version})")
    
    # 2. Instantiate Clients
    azure_client = AzureClient(container_name=config.storage.azure_container)
    gemini_client = GeminiClient(
        primary_model=config.llm_settings.model_primary,
        fallback_models=config.llm_settings.model_fallbacks,
        system_instruction=config.llm_settings.system_instruction,
        persona=config.llm_settings.persona,
        classification_rules=config.llm_settings.classification_rules,
        grounding_rules=config.llm_settings.grounding_rules,
        translation_rules=config.llm_settings.translation_rules,
        output_format=config.llm_settings.output_format,
        topic_id=config.topic_id,
        classification_categories=config.classification_categories
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
        
        seed_strategy = (run_type == "seed_strategy")
        pulse_only = (run_type == "pulse")
        
        if seed_strategy:
            # Clear all historical tender URLs from processed_urls for the seeding run
            news_domains = ['pm.gc.ca', 'ised-isde.canada.ca', 'international.gc.ca', 'canada.ca', 'finance.gc.ca']
            tender_urls = [url for url in processed_urls if not any(d in url.lower() for d in news_domains)]
            logging.info(f"Seeding mode: Clearing {len(tender_urls)} historical tender URLs from processed_urls to trigger re-evaluation.")
            for url in tender_urls:
                processed_urls.discard(url)
                if url in processed_urls_registry:
                    del processed_urls_registry[url]

        # Load subscribers if subscribers_file is set
        subscribers = []
        if config.storage.subscribers_file:
            try:
                logging.info(f"Downloading subscribers list from Azure: {config.storage.subscribers_file}...")
                raw_subs = azure_client.download_json(config.storage.subscribers_file)
                if isinstance(raw_subs, list):
                    subscribers = [s.strip() for s in raw_subs if isinstance(s, str) and "@" in s]
                    logging.info(f"Loaded {len(subscribers)} subscribers for distribution.")
            except Exception as e:
                logging.warning(f"Failed to load subscribers from Azure: {e}")

        # 3. Extract and Process News/Tenders
        insights = fetch_and_process_news(
            config=config,
            azure_client=azure_client,
            gemini_client=gemini_client,
            lookback_limit=lookback_limit,
            processed_urls=processed_urls,
            test_mode=dry_run,
            pulse_only_override=pulse_only
        )

        # 3.5 Merge with existing active tenders from Azure if tenders_file is set
        final_tenders = None
        if config.storage.tenders_file:
            # Gather tenders from current run's insights
            tenders_in_run = []
            for item in insights:
                if "closing_date" in item or item.get("source") == "CanadaBuys":
                    tenders_in_run.append(item)
            
            existing_tenders = []
            if not seed_strategy:
                try:
                    existing_tenders = azure_client.download_json(config.storage.tenders_file) or []
                    logging.info(f"Loaded {len(existing_tenders)} existing tenders from Azure.")
                except Exception as e:
                    logging.error(f"Failed to load existing tenders from Azure: {e}")
                    
            # Filter and normalize existing tenders
            active_tenders = []
            now_date = datetime.utcnow().date()
            cutoff_date = now_date - timedelta(days=1)
            for t in existing_tenders:
                t['category_label'] = get_category_label(t.get('category_label') or t.get('category', ''))
                closing_date_str = t.get('closing_date')
                if closing_date_str:
                    try:
                        dt = datetime.strptime(closing_date_str[:10], "%Y-%m-%d").date()
                        if dt < cutoff_date:
                            logging.info(f"Pruning expired tender: {t.get('title')} (Closed: {closing_date_str})")
                            continue
                    except Exception as e:
                        logging.warning(f"Error parsing closing_date '{closing_date_str}': {e}")
                
                # Downgrade historical 'New' tenders to 'Open'
                if t.get('type') == 'New':
                    t['type'] = 'Open'
                active_tenders.append(t)
                
            # Merge new tenders (prioritize fresh data by overwriting matching links)
            merged_tenders = {}
            for t in active_tenders:
                merged_tenders[t['link']] = t
            for t in tenders_in_run:
                merged_tenders[t['link']] = t
                
            final_tenders = list(merged_tenders.values())
            logging.info(f"Merged state: {len(existing_tenders)} existing -> {len(active_tenders)} active -> {len(final_tenders)} total merged tenders.")

        # 3.8 Multi-Tenant Subscriber Profile Matching & Private Lead Generation
        if getattr(config.storage, "subscriber_profiles_file", None):
            try:
                matcher = ProfileMatcher(azure_client=azure_client, gemini_client=gemini_client, notifier=notifier)
                profiles = matcher.load_profiles(blob_name=config.storage.subscriber_profiles_file)
                if profiles and final_tenders:
                    # Target new tenders first, or active tenders if in pulse/dry_run/seeding
                    tenders_to_eval = [t for t in final_tenders if t.get("type") == "New" or seed_strategy or dry_run]
                    if not tenders_to_eval:
                        tenders_to_eval = final_tenders[:25]
                    logging.info(f"Running subscriber profile evaluation across {len(tenders_to_eval)} candidate tenders...")
                    matcher.process_tenders(tenders=tenders_to_eval, profiles=profiles, dry_run=dry_run)
            except Exception as match_err:
                logging.warning(f"Subscriber profile matching encountered an error: {match_err}")

        # 4. Consolidate Dashboard KPIs
        kpis = generate_dashboard_kpis(insights, gemini_client, tenders=final_tenders)
        kpis["skill_version"] = config.skill_version

        # Select top 5 featured items for digest, capping at 2 items per hub to ensure regional balance (or 5 if single-hub)
        source_hubs = {src.name: (src.hub if src.hub else get_hub_from_source(src.name)) for src in config.sources}
        featured_insights = []
        hub_counts = {}
        unique_hubs = {h for h in source_hubs.values() if h}
        max_per_hub = 2 if len(unique_hubs) > 1 else 5
        
        for item in insights:
            src = item.get("source", "")
            hub = source_hubs.get(src) or get_hub_from_source(src)
            count = hub_counts.get(hub, 0)
            if count < max_per_hub:
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

        tender_context = None
        if config.storage.tenders_file and final_tenders:
            tender_lines = []
            for t in final_tenders[:5]:
                close_info = f" (Closes: {t['closing_date'][:10]})" if t.get('closing_date') else ""
                tender_lines.append(f"- **{t['title']}** - Region: {t.get('province', 'National')}{close_info}")
            tender_context = "\n".join(tender_lines)

        today_str = datetime.utcnow().strftime("%B %d, %Y")
        linkedin_post = gemini_client.generate_linkedin_post(
            summaries_str, 
            current_date=today_str, 
            dashboard_url=config.dashboard_url,
            tender_context=tender_context
        )
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

        # Enforce per-source cap to prevent single-source flooding on the dashboard
        max_per_src = getattr(config, 'max_items_per_source_on_dashboard', 4)
        if not isinstance(max_per_src, int):
            max_per_src = 4
        source_counts = {}
        capped_insights = []
        for item in insights:
            src = item.get("source", "")
            count = source_counts.get(src, 0)
            if count < max_per_src:
                capped_insights.append(item)
                source_counts[src] = count + 1
            else:
                logging.info(f"Per-source cap ({max_per_src}) reached for '{src}'. Dropping: {item.get('title', '?')[:60]}")
        if len(capped_insights) < len(insights):
            logging.info(f"Per-source cap reduced insights from {len(insights)} to {len(capped_insights)}.")
        insights = capped_insights

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
            
        if config.storage.tenders_file and final_tenders is not None:
            tenders_local_path = os.path.join(output_dir, config.storage.tenders_file)
            with open(tenders_local_path, "w", encoding="utf-8") as f:
                json.dump(final_tenders, f, indent=2, ensure_ascii=False)
            
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
            
            tenders_ok = True
            if config.storage.tenders_file and final_tenders is not None:
                tenders_temp = f"{os.path.splitext(config.storage.tenders_file)[0]}_temp.json"
                tenders_ok = azure_client.upload_json(tenders_temp, final_tenders)
            
            if insights_ok and kpis_ok and tenders_ok:
                # Perform fast server-side copies to final files
                azure_client.copy_blob(insights_temp, config.storage.insights_file)
                azure_client.copy_blob(kpis_temp, config.storage.kpis_file)
                if config.storage.tenders_file and final_tenders is not None:
                    azure_client.copy_blob(tenders_temp, config.storage.tenders_file)
                
                # Cleanup temp files
                azure_client.delete_blob(insights_temp)
                azure_client.delete_blob(kpis_temp)
                if config.storage.tenders_file and final_tenders is not None:
                    azure_client.delete_blob(tenders_temp)
            else:
                logging.error("Failed to upload temporary staged files. Aborting main swap.")
                raise RuntimeError("Failed to upload primary dashboard data to Azure Storage.")
            
            # Upload social card binary image
            if os.path.exists(social_card_local_path):
                azure_client.upload_file(social_card_local_path, "latest_social_card.png", "image/png")
                azure_client.upload_file(social_card_local_path, f"social_card_{date_str}.png", "image/png")
            
            # Historical backup archive - staged and swapped atomically
            if getattr(config.storage, "prefix_historical_files", True):
                prefix = f"{config.topic_id}_"
                insights_base = "insights"
                kpis_base = "kpis"
                tenders_base = "tenders"
            else:
                prefix = ""
                insights_base = os.path.splitext(config.storage.insights_file)[0]
                kpis_base = os.path.splitext(config.storage.kpis_file)[0]
                tenders_base = os.path.splitext(config.storage.tenders_file)[0] if config.storage.tenders_file else "tenders"

            hist_insights_file = f"reports/{prefix}{insights_base}_{date_str}.json"
            hist_kpis_file = f"reports/{prefix}{kpis_base}_{date_str}.json"
            hist_insights_temp = f"reports/{prefix}{insights_base}_{date_str}_temp.json"
            hist_kpis_temp = f"reports/{prefix}{kpis_base}_{date_str}_temp.json"
            
            hist_insights_ok = azure_client.upload_json(hist_insights_temp, pmo_wrapper)
            hist_kpis_ok = azure_client.upload_json(hist_kpis_temp, kpis)
            
            hist_tenders_ok = True
            if config.storage.tenders_file and final_tenders is not None:
                hist_tenders_file = f"reports/{prefix}{tenders_base}_{date_str}.json"
                hist_tenders_temp = f"reports/{prefix}{tenders_base}_{date_str}_temp.json"
                hist_tenders_ok = azure_client.upload_json(hist_tenders_temp, final_tenders)
                
            if hist_insights_ok and hist_kpis_ok and hist_tenders_ok:
                azure_client.copy_blob(hist_insights_temp, hist_insights_file)
                azure_client.copy_blob(hist_kpis_temp, hist_kpis_file)
                if config.storage.tenders_file and final_tenders is not None:
                    azure_client.copy_blob(hist_tenders_temp, hist_tenders_file)
                    
                azure_client.delete_blob(hist_insights_temp)
                azure_client.delete_blob(hist_kpis_temp)
                if config.storage.tenders_file and final_tenders is not None:
                    azure_client.delete_blob(hist_tenders_temp)
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
                    topic_name=topic_name,
                    recipients=subscribers
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
    parser.add_argument("--run-type", type=lambda s: s.lower(), choices=["deep_dive", "pulse", "seed_strategy"], default="deep_dive", help="Pipeline run type mode")
    
    # Read environment variables as fallbacks
    args = parser.parse_args()
    cfg_path = args.config
    cfg_url = args.config_url or os.getenv("CONFIG_URL")
    
    if not cfg_path and not cfg_url:
        # Fallback default configuration for local testing
        cfg_path = "configs/innovation_clusters.json"

    run_engine_pipeline(config_path=cfg_path, config_url=cfg_url, dry_run=args.dry_run, run_type=args.run_type)
