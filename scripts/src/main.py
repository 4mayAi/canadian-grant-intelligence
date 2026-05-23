import json
import logging
import os
import sys
from datetime import datetime, timedelta
import asyncio

# Setup local imports
from src.config import Config
from src.api.azure_client import azure_client
from src.api.gemini_client import gemini_client
from src.extractors.ckan import fetch_canadabuys_csvs
from src.extractors.rss import fetch_rss_feeds
from src.extractors.playwright_scraper import fetch_html_news
from src.models import Tender, GeminiInsight, KPI

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Suppress verbose loggers
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

def fetch_and_process_news(lookback_limit, max_items_per_feed, processed_urls, test_mode=False):
    """Fetches PMO news, filters by lookback, and analyzes with LLM using batching with a self-healing cache."""
    failed_feeds = []
    raw_rss = fetch_rss_feeds(lookback_limit, max_items_per_feed, failed_feeds)
    
    # Load existing cached insights
    existing_insights_list = []
    try:
        existing_pmo = azure_client.download_json("pmo_insights.json")
        if existing_pmo and "insights" in existing_pmo:
            existing_insights_list = existing_pmo["insights"]
    except Exception as e:
        logging.error(f"Failed to load existing pmo_insights.json from Azure: {e}")
        
    existing_insights_map = {item["link"]: item for item in existing_insights_list if "link" in item}
    
    # Handle feed failures: Retain existing insights for failed feeds
    retained_items = []
    if failed_feeds:
        logging.warning(f"Failed feeds detected: {failed_feeds}. Retaining their cached insights.")
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
                    except Exception as parse_err:
                        logging.warning(f"Error parsing date string {dt_val}: {parse_err}")
                
                if not parsed_date:
                    parsed_date = datetime.utcnow()
                    
                retained_items.append({
                    "source": item.get("source"),
                    "title": item.get("title"),
                    "link": link,
                    "date": parsed_date,
                    "text_to_search": (item.get("title", "") + " " + item.get("insight", {}).get("summary", "")).lower()
                })
                logging.info(f"Retained cached item from failed feed {item.get('source')}: {item.get('title')}")
                
    # Combine active items from successful feeds with retained items from failed feeds
    all_raw_news = raw_rss + retained_items
    
    # Deduplicate in case of unexpected overlaps
    seen_links = set()
    deduped_raw_news = []
    for item in all_raw_news:
        if item['link'] not in seen_links:
            deduped_raw_news.append(item)
            seen_links.add(item['link'])
            
    unprocessed_news = []
    final_insights = []
    
    for item in deduped_raw_news:
        link = item['link']
        if link in existing_insights_map:
            # Reuse cached insight directly (no LLM call)
            final_insights.append(existing_insights_map[link])
            processed_urls.add(link)
        else:
            # New active item, needs LLM processing
            unprocessed_news.append(item)
            
    if test_mode:
        unprocessed_news = unprocessed_news[:2]
        
    BATCH_SIZE = 5
    for i in range(0, len(unprocessed_news), BATCH_SIZE):
        batch = unprocessed_news[i:i + BATCH_SIZE]
        logging.info(f"Analyzing batch of {len(batch)} news items with LLM...")
        
        contents = [
            f"Title: {item['title']}\nSource: {item['source']}\nDate: {item.get('date', 'Unknown')}\nContext: {item['text_to_search']}"
            for item in batch
        ]
        
        insight_models = gemini_client.get_gemini_insights_batch(contents)
        
        for item, insight_model in zip(batch, insight_models):
            dt = item.get('date')
            if isinstance(dt, datetime):
                date_str = dt.isoformat() + "Z"
            elif isinstance(dt, str):
                date_str = dt
            else:
                date_str = datetime.utcnow().isoformat() + "Z"
                
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
    def get_parse_date(item):
        d = item.get("date")
        if isinstance(d, datetime):
            return d
        if isinstance(d, str):
            try:
                return datetime.fromisoformat(d.rstrip("Z"))
            except:
                pass
        return datetime.min
        
    final_insights.sort(key=get_parse_date, reverse=True)
    return final_insights


def generate_kpis(tenders: list, pmo_insights: list) -> dict:
    now = datetime.now()
    total_active = len(tenders)
    new_today = sum(1 for t in tenders if t.get('type') == 'New')
    
    closing_this_week = 0
    categories = {}
    
    for t in tenders:
        if t.get('closing_date'):
            try:
                dt = datetime.strptime(t['closing_date'][:10], "%Y-%m-%d")
                if 0 <= (dt - now).days <= 7:
                    closing_this_week += 1
            except:
                pass
                
        cat = t.get('category', 'Uncategorized').replace('*', '').strip()
        categories[cat] = categories.get(cat, 0) + 1
        
    top_cat_name = "Mixed Sectors"
    if categories:
        sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        lead = sorted_cats[0]
        percentage = round((lead[1] / max(1, total_active)) * 100)
        is_tie = len(sorted_cats) > 1 and sorted_cats[0][1] == sorted_cats[1][1]
        is_diversified = len(sorted_cats) > 1 and percentage < 50
        
        if is_tie:
            top_cat_name = "Mixed Sectors"
        elif is_diversified:
            top_cat_name = "Diversified"
        else:
            name = lead[0][:15] + "..." if len(lead[0]) > 18 else lead[0]
            top_cat_name = f"{name} ({percentage}%)"
            
    hero_hook = gemini_client.get_hero_hook(tenders, pmo_insights)
    
    return KPI(
        total_active=total_active,
        new_today=new_today,
        closing_this_week=closing_this_week,
        top_category=top_cat_name,
        hero_hook=hero_hook
    ).to_dict()

def save_local_outputs(tenders_dict_list, insights_dict_list, kpi_dict):
    """Saves the output to the root outputs dir to match legacy pipeline."""
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    
    with open(Config.TENDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tenders_dict_list, f, indent=4, ensure_ascii=False)
        
    with open(Config.PMO_FILE, 'w', encoding='utf-8') as f:
        json.dump(insights_dict_list, f, indent=4, ensure_ascii=False)
        
    with open(Config.KPI_FILE, 'w', encoding='utf-8') as f:
        json.dump(kpi_dict, f, indent=4, ensure_ascii=False)
        
    logging.info(f"Locally saved {len(tenders_dict_list)} tenders, {len(insights_dict_list)} PMO insights, and KPIs.")

def run_pipeline():
    setup_logging()
    logging.info(f"Starting Modularized Canadian Grant Intelligence Pipeline. Mode: {Config.RUN_TYPE}")
    
    test_mode = (Config.RUN_TYPE == 'test')
    seed_strategy = (Config.RUN_TYPE == 'seed_strategy')
    pulse_only = (Config.RUN_TYPE in ('pulse', 'test'))
    
    # Define Lookback
    lookback_limit = None
    if not seed_strategy:
        lookback_limit = datetime.now() - timedelta(days=Config.SCRAPE_LOOKBACK_DAYS)
        logging.info(f"Scrape lookback limit: {lookback_limit.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        logging.info("Running in Strategy Seeding mode: Using limits per source.")
        
    # Load State — supports both legacy list and new timestamped dict format
    processed_urls_raw = azure_client.download_json("processed_urls.json") or []
    if isinstance(processed_urls_raw, list):
        # Migration: legacy flat list -> timestamped dict
        processed_urls_registry = {url: datetime.utcnow().isoformat() + "Z" for url in processed_urls_raw}
        logging.info(f"Migrated {len(processed_urls_registry)} URLs from legacy list to timestamped dict.")
    elif isinstance(processed_urls_raw, dict):
        processed_urls_registry = processed_urls_raw
    else:
        processed_urls_registry = {}
    
    # Set view for fast lookups (compatible with ckan.py seen_links parameter)
    processed_urls = set(processed_urls_registry.keys())
    logging.info(f"Loaded {len(processed_urls)} processed URLs from Azure.")
    
    if seed_strategy:
        # Clear all historical tender URLs from processed_urls for the seeding run
        # Keep only PMO/news urls (pm.gc.ca, ised-isde, international.gc.ca, canada.ca)
        news_domains = ['pm.gc.ca', 'ised-isde.canada.ca', 'international.gc.ca', 'canada.ca']
        tender_urls = [url for url in processed_urls if not any(d in url.lower() for d in news_domains)]
        logging.info(f"Seeding mode: Clearing {len(tender_urls)} historical tender URLs from processed_urls to trigger re-evaluation.")
        for url in tender_urls:
            processed_urls.discard(url)
            del processed_urls_registry[url]
            
    initial_processed_count = len(processed_urls)
    
    try:
        # 1. CanadaBuys CKAN Extractor
        tenders = fetch_canadabuys_csvs(
            pulse_only=pulse_only,
            seen_links=processed_urls
        )
        
        # 2. PMO News Extractor (RSS + Playwright) -> LLM
        max_items = 5 if test_mode else 15
        pmo_insights = fetch_and_process_news(lookback_limit, max_items, processed_urls, test_mode=test_mode)
        
        # Daily consolidation is handled inside fetch_and_process_news via the self-healing cache
        pass

        # 3. Transform Tenders to dicts
        tenders_dict_list = [t.to_dict() for t in tenders]
        if test_mode:
            tenders_dict_list = tenders_dict_list[:5]
            
        # 3.5 Merge with existing active tenders from Azure
        existing_tenders = []
        if not seed_strategy:
            try:
                existing_tenders = azure_client.download_json("tenders.json") or []
                logging.info(f"Loaded {len(existing_tenders)} existing tenders from Azure.")
            except Exception as e:
                logging.error(f"Failed to load existing tenders from Azure: {e}")
        
        # Filter and normalize existing tenders
        active_tenders = []
        now_date = datetime.utcnow().date()
        cutoff_date = now_date - timedelta(days=1)
        for t in existing_tenders:
            closing_date_str = t.get('closing_date')
            if closing_date_str:
                try:
                    dt = datetime.strptime(closing_date_str[:10], "%Y-%m-%d").date()
                    if dt < cutoff_date:
                        logging.info(f"Pruning expired tender: {t.get('title')} (Closed: {closing_date_str})")
                        continue
                except Exception as e:
                    logging.warning(f"Error parsing closing_date '{closing_date_str}': {e}")
            
            # Downgrade historical 'New' tenders to 'Open' since they are from a previous run
            if t.get('type') == 'New':
                t['type'] = 'Open'
            active_tenders.append(t)
            
        # Merge new tenders (overwriting matching links to prioritize fresh data)
        merged_tenders = {}
        for t in active_tenders:
            merged_tenders[t['link']] = t
        for t in tenders_dict_list:
            merged_tenders[t['link']] = t
            
        final_tenders = list(merged_tenders.values())
        logging.info(f"Merged state: {len(existing_tenders)} existing -> {len(active_tenders)} active -> {len(final_tenders)} total merged tenders.")

        # INTEGRITY ASSERTIONS
        tender_links = [t['link'] for t in final_tenders]
        assert len(tender_links) == len(set(tender_links)), f"DUPLICATE TENDERS DETECTED: {len(tender_links)} total, {len(set(tender_links))} unique"
        for t in final_tenders:
            for key in ('title', 'link', 'province', 'category'):
                assert key in t, f"MISSING KEY '{key}' in tender: {t.get('title', 'UNKNOWN')}"

        # 4. Generate KPIs
        kpis_dict = generate_kpis(final_tenders, pmo_insights)
        
        # 4.5. Generate LinkedIn Post, Social Card, and Wrap Insights
        # Context uses only the newly scraped tenders to keep the daily LinkedIn post fresh
        tender_context = "\n".join([f"- {t.get('title')} (Closing: {t.get('closing_date', 'N/A')})" for t in tenders_dict_list[:5]])
        news_summaries = "\n".join([f"- {n.get('title')}: {n.get('insight', {}).get('linkedin_hook', '')}" for n in pmo_insights[:5]])
        
        linkedin_json = gemini_client.generate_linkedin_post(news_summaries, tender_context)
        hero_hook = kpis_dict.get('hero_hook', 'mayAi | Delivering Golden Opportunities Daily')
        top_category = kpis_dict.get('top_category', 'Mixed Sectors')

        if linkedin_json:
            # Clean text formatting for UI copy-paste (no image, no Section headings)
            ui_post_content = f"# {linkedin_json.get('suggested_title', 'MayAi Daily Update')}\n\n"
            ui_post_content += f"{linkedin_json.get('article_content', '')}"

            # Format for email body (with banner image, no draft headers)
            email_post_content = f"![Social Card](https://canadiangrants.blob.core.windows.net/data/latest_social_card.png)\n\n"
            email_post_content += f"# {linkedin_json.get('suggested_title', 'MayAi Daily Update')}\n\n"
            email_post_content += f"{linkedin_json.get('article_content', '')}"
        else:
            ui_post_content = "LinkedIn post generation failed."
            email_post_content = "LinkedIn post generation failed."

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        linkedin_dir = os.path.join(project_root, "reports", "linkedin")
        os.makedirs(linkedin_dir, exist_ok=True)
        
        with open(os.path.join(linkedin_dir, "latest_post.md"), "w", encoding="utf-8") as f:
            f.write(email_post_content)
        logging.info("Saved latest_post.md in professional newsletter format.")

        import subprocess
        try:
            logging.info("Generating social card...")
            script_path = os.path.join(project_root, "scripts", "generate_social_card.py")
            output_path = os.path.join(linkedin_dir, "social_card.png")
            subprocess.run([
                sys.executable, script_path, 
                hero_hook, top_category, output_path
            ], check=True)
        except Exception as e:
            logging.error(f"Failed to generate social card: {e}")

        pmo_wrapper = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "linkedin_post": ui_post_content,
            "insights": pmo_insights
        }
        
        # 5. Local Storage (for UI/Dashboard artifacts)
        save_local_outputs(final_tenders, pmo_wrapper, kpis_dict)
        
        # 5.5. Validate Generated Outputs
        try:
            scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if scripts_dir not in sys.path:
                sys.path.append(scripts_dir)
            from validate_outputs import validate_outputs_func
            validate_outputs_func(Config.OUTPUT_DIR)
            logging.info("Automated output validation passed successfully.")
        except Exception as val_err:
            logging.error(f"Automated output validation failed: {val_err}")
            raise Exception(f"Output validation failed: {val_err}")

        # 6. Azure Cloud Storage Upload
        if not test_mode:
            azure_client.upload_json("tenders.json", final_tenders)
            azure_client.upload_json("pmo_insights.json", pmo_wrapper)
            azure_client.upload_json("kpis.json", kpis_dict)
            
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Historical date-stamped backups
            azure_client.upload_json(f"reports/tenders_{date_str}.json", final_tenders)
            azure_client.upload_json(f"reports/pmo_insights_{date_str}.json", pmo_wrapper)
            azure_client.upload_json(f"reports/kpis_{date_str}.json", kpis_dict)
            
            # Manifest updates for date dropdown
            try:
                manifest = azure_client.download_json("manifest.json") or []
                if not isinstance(manifest, list):
                    manifest = []
                if date_str not in manifest:
                    manifest.append(date_str)
                    manifest.sort(reverse=True)
                    azure_client.upload_json("manifest.json", manifest)
                    logging.info(f"Updated date manifest in Azure with date: {date_str}")
            except Exception as manifest_err:
                logging.error(f"Failed to update manifest.json in Azure: {manifest_err}")
            
            try:
                azure_client.upload_file("reports/linkedin/social_card.png", "latest_social_card.png", "image/png")
                azure_client.upload_file("reports/linkedin/social_card.png", f"social_card_{date_str}.png", "image/png")
                logging.info("Uploaded social cards to Azure.")
            except Exception as e:
                logging.error(f"Failed to upload social card to Azure: {e}")
                
            logging.info("Uploaded processed files and historical backups to Azure.")

        # 7. SMTP Email Distribution
        if not test_mode:
            try:
                from src.api.mail_sender import mail_sender
                markdown_path = os.path.join(linkedin_dir, "latest_post.md")
                social_card_path = os.path.join(linkedin_dir, "social_card.png")
                mail_sender.send_daily_digest(markdown_path, social_card_path)
            except Exception as mail_err:
                logging.error(f"Failed to distribute daily email digest: {mail_err}")

        # Log pipeline health and LLM quality telemetry
        stats = gemini_client.get_stats()
        logging.info(f"LLM_STATS: {json.dumps(stats)}")
        logging.info(f"HEALTH: Tenders={len(final_tenders)}, PMO_Insights={len(pmo_insights)}, "
                     f"KPI_generated_at={kpis_dict.get('generated_at')}")
            
    except Exception as e:
        logging.error(f"Pipeline crashed: {e}")
        try:
            from src.api.notifier import notifier
            notifier.notify_failure("Canadian Grants Pipeline", str(e))
        except Exception as alert_err:
            logging.error(f"Failed to send failure alert notification: {alert_err}")
        raise e
    finally:
        # State Protection: ALWAYS attempt to save state (now as timestamped dict)
        if not test_mode:
            if seed_strategy or len(processed_urls) > initial_processed_count:
                # Sync set additions back to registry
                for url in processed_urls:
                    if url not in processed_urls_registry:
                        processed_urls_registry[url] = datetime.utcnow().isoformat() + "Z"
                azure_client.upload_json("processed_urls.json", processed_urls_registry)
                logging.info(f"Successfully saved updated processed_urls.json (Total: {len(processed_urls_registry)}) to Azure.")
            else:
                logging.info(f"Skipping Azure state upload (no new URLs added).")

if __name__ == "__main__":
    run_pipeline()
