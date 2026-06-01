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
    
    # Translate config schema objects to raw dicts for scraper engines
    sources_dict = [src.model_dump() for src in config.sources]

    # Ingest RSS feeds (max items slots per cluster)
    max_items = 3 if test_mode else 5
    raw_rss = fetch_rss_feeds(sources_dict, lookback_limit, max_items, failed_feeds)

    # Ingest Playwright HTML pages if any are configured
    raw_html = fetch_html_news(sources_dict, lookback_limit, max_items, failed_feeds)

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

    # Load existing cached insights from Azure Blob
    existing_insights_list = []
    try:
        existing_insights = azure_client.download_json(config.storage.insights_file)
        if existing_insights and "insights" in existing_insights:
            existing_insights_list = existing_insights["insights"]
    except Exception as e:
        logging.error(f"Failed to load existing cache file {config.storage.insights_file} from storage: {e}")

    existing_insights_map = {item["link"]: item for item in existing_insights_list if "link" in item}

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
    combined_items = raw_rss + raw_html + retained_items
    
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
            final_insights.append(existing_insights_map[link])
            processed_urls.add(link)
        else:
            unprocessed_items.append(item)

    if test_mode:
        unprocessed_items = unprocessed_items[:2]

    # Batch process new items to protect RPM ceilings
    BATCH_SIZE = 5
    for i in range(0, len(unprocessed_items), BATCH_SIZE):
        batch = unprocessed_items[i:i + BATCH_SIZE]
        logging.info(f"Analyzing batch of {len(batch)} new news items with Gemini...")
        
        contents = [
            f"Title: {item['title']}\nSource: {item['source']}\nDate: {item.get('date', 'Unknown')}\nContext: {item['text_to_search']}"
            for item in batch
        ]
        
        insight_models = gemini_client.get_gemini_insights_batch(contents)
        
        for item, insight_model in zip(batch, insight_models):
            dt = item.get('date')
            date_str = dt.isoformat() + "Z" if isinstance(dt, datetime) else str(dt)

            report_item_dict = {
                "source": item['source'],
                "title": item['title'],
                "link": item['link'],
                "date": date_str,
                "insight": insight_model.to_dict()
            }
            final_insights.append(report_item_dict)
            processed_urls.add(item['link'])

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
            
    # Calculate top contributing source/category
    source_counts = {}
    for ins in insights:
        src = ins.get("source", "")
        # Clean display name for known sources
        display_src = src.replace('_News', '').replace('Cluster_News', ' Supercluster').replace('ScaleAI', 'Scale AI').replace('NGen', 'NGen').replace('ProteinIndustries', 'Protein Industries Canada').replace('DIGITAL', 'DIGITAL')
        if display_src:
            source_counts[display_src] = source_counts.get(display_src, 0) + 1
            
    top_category = "Mixed Sectors"
    if source_counts:
        top_category = max(source_counts, key=source_counts.get)

    hero_hook = gemini_client.get_hero_hook(insights)
    
    return KPIDashboard(
        total_active=total_active,
        new_today=new_today,
        closing_this_week=0,  # No tenders closing date in generic RSS
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
        fallback_model=config.llm_settings.model_fallback,
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

        # 5. Compile LinkedIn summary post
        summaries_str = "\n".join([f"- {item['title']}: {item['insight'].get('linkedin_hook', '')}" for item in insights[:5]])
        linkedin_post = gemini_client.generate_linkedin_post(summaries_str)
        suggested_post = linkedin_post.get("article_content", "No post text compiled.") if linkedin_post else ""

        # Post-process: Automatically hyperlink cluster names in the body (using lookarounds to prevent double-wrapping)
        cluster_links = {
            "Protein Industries Canada": "[Protein Industries Canada](https://www.proteinindustriescanada.ca/)",
            "Protein Industries": "[Protein Industries](https://www.proteinindustriescanada.ca/)",
            "Scale AI": "[Scale AI](https://www.scaleai.ca/)",
            "ScaleAI": "[ScaleAI](https://www.scaleai.ca/)",
            "Ocean Supercluster": "[Ocean Supercluster](https://oceansupercluster.ca/)",
            "NGen": "[NGen](https://www.ngen.ca/)",
            "DIGITAL": "[Digital Supercluster](https://digitalsupercluster.ca/)",
            "Digital Supercluster": "[Digital Supercluster](https://digitalsupercluster.ca/)"
        }
        for name, link in cluster_links.items():
            pattern = re.compile(rf'(?<!\[){re.escape(name)}(?!\])')
            suggested_post = pattern.sub(link, suggested_post)

        # Append source references for clean tracking
        if insights:
            suggested_post += "\n\n### Featured News & Sources\n"
            for item in insights[:5]:
                src_name = item.get("source", "").replace("_News", "").replace("Cluster", "").replace("ScaleAI", "Scale AI")
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
            azure_client.upload_json(config.storage.insights_file, pmo_wrapper)
            azure_client.upload_json(config.storage.kpis_file, kpis)
            
            # Upload social card binary image
            if os.path.exists(social_card_local_path):
                azure_client.upload_file(social_card_local_path, "latest_social_card.png", "image/png")
                date_str = datetime.utcnow().strftime("%Y-%m-%d")
                azure_client.upload_file(social_card_local_path, f"social_card_{date_str}.png", "image/png")
            
            # Historical backup archive
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            azure_client.upload_json(f"reports/{config.topic_id}_insights_{date_str}.json", pmo_wrapper)
            azure_client.upload_json(f"reports/{config.topic_id}_kpis_{date_str}.json", kpis)

            # Sync processed URLs list
            if len(processed_urls) > initial_url_count:
                for url in processed_urls:
                    if url not in processed_urls_registry:
                        processed_urls_registry[url] = datetime.utcnow().isoformat() + "Z"
                azure_client.upload_json(config.storage.processed_urls_file, processed_urls_registry)
                logging.info(f"Updated URL state registry (Total URLs: {len(processed_urls_registry)}) uploaded to Azure.")

        # 9. SMTP Email Distribution
        if not dry_run:
            try:
                email_subject = f"{datetime.now().strftime('%b %d, %Y')} — 🇨🇦 Innovation Clusters — {kpis.get('hero_hook', '')}"
                
                # Assemble the markdown content for the email
                digest_md = f"# {kpis.get('hero_hook', 'Canadian Innovation Clusters Daily Digest')}\n\n"
                digest_md += f"**Top Contributor**: {kpis.get('top_category', 'Mixed Sectors')}\n\n"
                digest_md += f"### Strategic B2B Digest\n\n"
                digest_md += f"{suggested_post}\n\n"
                digest_md += f"---\n\n"
                digest_md += f"**View Full Interactive Dashboard**: {config.dashboard_url}\n"
                
                logging.info("Sending success digest email via SMTP...")
                notifier.send_digest(email_subject, digest_md, social_card_local_path)
            except Exception as mail_err:
                logging.error(f"Failed to distribute daily clusters email digest: {mail_err}")

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
