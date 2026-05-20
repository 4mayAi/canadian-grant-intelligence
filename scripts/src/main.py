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
    """Fetches PMO news, filters by lookback, and analyzes with LLM using batching."""
    raw_rss = fetch_rss_feeds(lookback_limit, max_items_per_feed)
    raw_html = fetch_html_news(lookback_limit, max_items_per_feed)
    
    all_raw_news = raw_rss + raw_html
    
    unprocessed_news = []
    for item in all_raw_news:
        if item['link'] not in processed_urls:
            unprocessed_news.append(item)
            
    if test_mode:
        unprocessed_news = unprocessed_news[:2]
        
    insights = []
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
            insights.append(report_item_dict)
            processed_urls.add(item['link'])
            processed_urls_registry[item['link']] = datetime.utcnow().isoformat() + "Z"
            
    return insights

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
        
        # Consolidate daily PMO insights by merging with existing insights from today
        if not seed_strategy:
            try:
                existing_pmo = azure_client.download_json("pmo_insights.json")
                if existing_pmo:
                    existing_gen_date = existing_pmo.get("generated_at", "")[:10]
                    today_utc_date = datetime.utcnow().strftime("%Y-%m-%d")
                    if existing_gen_date == today_utc_date:
                        existing_insights = existing_pmo.get("insights", [])
                        seen_links = {item["link"] for item in pmo_insights}
                        merged_insights = list(pmo_insights)
                        for item in existing_insights:
                            if item.get("link") not in seen_links:
                                merged_insights.append(item)
                                seen_links.add(item["link"])
                        pmo_insights = merged_insights
                        logging.info(f"Consolidated PMO insights: Merged {len(existing_insights)} existing insights from today. Total: {len(pmo_insights)}")
            except Exception as e:
                logging.error(f"Failed to consolidate existing PMO insights: {e}")
        
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
            post_content = f"## 📰 Section 1: Image\n![Social Card](https://canadiangrants.blob.core.windows.net/data/latest_social_card.png)\n\n"
            post_content += f"## 📝 Section 2: Title\n{linkedin_json.get('suggested_title', 'MayAi Daily Update')}\n\n"
            post_content += f"## 💡 Section 3: Content\n{linkedin_json.get('article_content', '')}"
        else:
            post_content = "LinkedIn post generation failed."

        os.makedirs("reports/linkedin", exist_ok=True)
        with open("reports/linkedin/latest_post.md", "w", encoding="utf-8") as f:
            f.write(post_content)
        logging.info("Saved latest_post.md in three-section format.")

        import subprocess
        try:
            logging.info("Generating social card...")
            subprocess.run([
                sys.executable, "scripts/generate_social_card.py", 
                hero_hook, top_category, "reports/linkedin/social_card.png"
            ], check=True)
        except Exception as e:
            logging.error(f"Failed to generate social card: {e}")

        pmo_wrapper = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "linkedin_post": post_content,
            "insights": pmo_insights
        }
        
        # 5. Local Storage (for UI/Dashboard artifacts)
        save_local_outputs(final_tenders, pmo_wrapper, kpis_dict)
        
        # 6. Azure Cloud Storage Upload
        if not test_mode:
            azure_client.upload_json("tenders.json", final_tenders)
            azure_client.upload_json("pmo_insights.json", pmo_wrapper)
            azure_client.upload_json("kpis.json", kpis_dict)
            
            try:
                date_str = datetime.utcnow().strftime("%Y-%m-%d")
                azure_client.upload_file("reports/linkedin/social_card.png", "latest_social_card.png", "image/png")
                azure_client.upload_file("reports/linkedin/social_card.png", f"social_card_{date_str}.png", "image/png")
                logging.info("Uploaded social cards to Azure.")
            except Exception as e:
                logging.error(f"Failed to upload social card to Azure: {e}")
                
            logging.info("Uploaded processed files to Azure.")

        # Log pipeline health and LLM quality telemetry
        stats = gemini_client.get_stats()
        logging.info(f"LLM_STATS: {json.dumps(stats)}")
        logging.info(f"HEALTH: Tenders={len(final_tenders)}, PMO_Insights={len(pmo_insights)}, "
                     f"KPI_generated_at={kpis_dict.get('generated_at')}")
            
    except Exception as e:
        logging.error(f"Pipeline crashed: {e}")
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
