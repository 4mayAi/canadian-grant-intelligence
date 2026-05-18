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
    """Fetches PMO news, filters by lookback, and analyzes with LLM."""
    raw_rss = fetch_rss_feeds(lookback_limit, max_items_per_feed)
    raw_html = fetch_html_news(lookback_limit, max_items_per_feed)
    
    all_raw_news = raw_rss + raw_html
    
    insights = []
    
    for item in all_raw_news:
        link = item['link']
        if link in processed_urls:
            continue
            
        logging.info(f"Analyzing with LLM: {item['title']} - {link}")
        content = f"Title: {item['title']}\nSource: {item['source']}\nDate: {item.get('date', 'Unknown')}\nContext: {item['text_to_search']}"
        
        insight_model = gemini_client.get_gemini_insight(content)
        
        if insight_model:
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
                "link": link,
                "date": date_str,
                "insight": insight_model.to_dict()
            }
            insights.append(report_item_dict)
            
        processed_urls.add(link)
        if test_mode and len(insights) >= 2:
            break
            
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
        
    # Load State
    processed_urls_list = azure_client.download_json("processed_urls.json") or []
    processed_urls = set(processed_urls_list)
    logging.info(f"Loaded {len(processed_urls)} processed URLs from Azure.")
    
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
        
        # 3. Transform Tenders to dicts
        tenders_dict_list = [t.to_dict() for t in tenders]
        if test_mode:
            tenders_dict_list = tenders_dict_list[:5]
            
        # 4. Generate KPIs
        kpis_dict = generate_kpis(tenders_dict_list, pmo_insights)
        
        # 4.5. Generate LinkedIn Post, Social Card, and Wrap Insights
        tender_context = "\n".join([f"- {t.get('title')} (Closing: {t.get('closing_date', 'N/A')})" for t in tenders_dict_list[:5]])
        news_summaries = "\n".join([f"- {n.get('title')}: {n.get('insight', {}).get('linkedin_hook', '')}" for n in pmo_insights[:5]])
        
        linkedin_json = gemini_client.generate_linkedin_post(news_summaries, tender_context)
        hero_hook = kpis_dict.get('hero_hook', 'mayAi | Delivering Golden Opportunities Daily')
        top_category = kpis_dict.get('top_category', 'Mixed Sectors')

        if linkedin_json:
            post_content = f"## 📰 Section 1: Image\n![Social Card](https://canadiangrantintel.blob.core.windows.net/public/latest_social_card.png)\n\n"
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
        save_local_outputs(tenders_dict_list, pmo_wrapper, kpis_dict)
        
        # 6. Azure Cloud Storage Upload
        if not test_mode and not seed_strategy:
            azure_client.upload_json("tenders.json", tenders_dict_list)
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
            
    except Exception as e:
        logging.error(f"Pipeline crashed: {e}")
        raise e
    finally:
        # State Protection: ALWAYS attempt to save state
        if len(processed_urls) > initial_processed_count:
            if not test_mode and not seed_strategy:
                azure_client.upload_json("processed_urls.json", list(processed_urls))
                logging.info(f"Successfully saved updated processed_urls.json (Total: {len(processed_urls)}) to Azure.")
            else:
                logging.info(f"Skipping Azure state upload due to {Config.RUN_TYPE} mode.")

if __name__ == "__main__":
    run_pipeline()
