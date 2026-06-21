import os
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# We'll import AzureClient and PipelineConfig from generic_engine
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from generic_engine.api.azure_client import AzureClient
from generic_engine.schema import PipelineConfig

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    config_path = os.path.join(base_dir, "configs", "amr_simulation.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    
    # We will instantiate AzureClient using the container name in config
    container_name = config_data["storage"]["azure_container"]
    insights_file = config_data["storage"]["insights_file"]
    processed_urls_file = config_data["storage"]["processed_urls_file"]
    
    azure_client = AzureClient(container_name=container_name)
    
    # 1. Download and modify processed_urls.json
    print(f"Downloading {processed_urls_file} from Azure...")
    processed_urls = azure_client.download_json(processed_urls_file)
    if processed_urls:
        print(f"Current processed URLs: {len(processed_urls)}")
        urls_to_remove = [
            "https://canadabuys.canada.ca/tender-opportunities/tender-notice/cb-621-79539261",
            "https://canadabuys.canada.ca/tender-opportunities/tender-notice/SSC-26-00033879:T",
            "https://canadabuys.canada.ca/tender-opportunities/tender-notice/cb-198-86690256"
        ]
        removed_any = False
        for url in urls_to_remove:
            if url in processed_urls:
                del processed_urls[url]
                print(f"Removed URL from processed_urls: {url}")
                removed_any = True
                
        # Dynamically remove any bioRxiv or PHAC/CCDR URLs to force re-ingestion
        dynamic_removals = []
        for url in list(processed_urls.keys()):
            url_lower = url.lower()
            if "biorxiv" in url_lower:
                dynamic_removals.append(url)
            elif "canada.ca" in url_lower and "canadabuys" not in url_lower:
                dynamic_removals.append(url)
                
        for url in dynamic_removals:
            del processed_urls[url]
            print(f"Dynamically removed URL from processed_urls: {url}")
            removed_any = True
                
        if removed_any:
            azure_client.upload_json(processed_urls_file, processed_urls)
            print("Uploaded updated processed_urls.json to Azure.")
        else:
            print("No URLs needed removal from processed_urls.json.")
    else:
        print("processed_urls.json not found on Azure.")

    # 2. Download and modify amr_insights.json (existing cache)
    print(f"Downloading {insights_file} from Azure...")
    insights_data = azure_client.download_json(insights_file)
    if insights_data and "insights" in insights_data:
        print(f"Current insights: {len(insights_data['insights'])}")
        original_len = len(insights_data['insights'])
        
        # Filter out the InnoVet tender, Toronto access control tender, and any bioRxiv / PHAC/CCDR items
        insights_data['insights'] = [
            item for item in insights_data['insights']
            if "cb-621-79539261" not in item.get("link", "") and
               "cb-198-86690256" not in item.get("link", "") and
               "biorxiv" not in item.get("link", "").lower() and
               not ("canada.ca" in item.get("link", "").lower() and "canadabuys" not in item.get("link", "").lower())
        ]
        
        new_len = len(insights_data['insights'])
        print(f"Filtered insights length: {new_len}")
        
        if new_len < original_len:
            azure_client.upload_json(insights_file, insights_data)
            print("Uploaded updated amr_insights.json to Azure (target items removed to force re-evaluation).")
        else:
            print("No target items found in cached insights on Azure.")
            
    # Also delete the local cache files to make sure they are re-downloaded
    local_insights = os.path.join(base_dir, "docs", "data", "amr-simulation", "amr_insights.json")
    if os.path.exists(local_insights):
        os.remove(local_insights)
        print(f"Deleted local cache: {local_insights}")

if __name__ == "__main__":
    main()
