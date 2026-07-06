import json
import os
import sys
import dotenv

# Load environment variables for local runs/tests
dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "generic_engine"))

import logging
from generic_engine.api.azure_client import AzureClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    container = "clusters-data"
    filename = "processed_urls.json"
    
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    print("AZURE_STORAGE_CONNECTION_STRING present in env:", bool(conn_str))
    
    print(f"Initializing Azure Client for container '{container}'...")
    azure_client = AzureClient(container_name=container)
    
    print(f"Downloading {filename} from Azure...")
    processed_urls_registry = azure_client.download_json(filename)
    
    if not processed_urls_registry:
        print("Failed to download registry or empty.")
        return
        
    print(f"Current registry has {len(processed_urls_registry)} entries.")
    
    urls_to_remove = [
        "https://www.proteinindustriescanada.ca/news-releases/crushdynamics-atomic47labs",
        "https://www.proteinindustriescanada.ca/news-releases/supply-chain-program-third-cohort",
        "https://digitalsupercluster.ca/welcoming-rhonda-barnet-interim-ceo/",
        "https://digitalsupercluster.ca/celebrating-sue-paishs-impact-and-leadership/",
        # Include variation with query parameters
        "https://digitalsupercluster.ca/welcoming-rhonda-barnet-interim-ceo/?utm_source=rss&utm_medium=rss&utm_campaign=welcoming-rhonda-barnet-interim-ceo",
        "https://digitalsupercluster.ca/celebrating-sue-paishs-impact-and-leadership/?utm_source=rss&utm_medium=rss&utm_campaign=celebrating-sue-paishs-impact-and-leadership"
    ]
    
    removed_count = 0
    for url in urls_to_remove:
        # Check direct match or variations
        if url in processed_urls_registry:
            del processed_urls_registry[url]
            print(f"Removed URL: {url}")
            removed_count += 1
            
    # Also check case-insensitive or partial matches just in case
    for key in list(processed_urls_registry.keys()):
        for url in urls_to_remove:
            if url.rstrip('/') == key.rstrip('/') and key in processed_urls_registry:
                del processed_urls_registry[key]
                print(f"Removed key variation: {key}")
                removed_count += 1
                
    if removed_count > 0:
        print(f"Uploading updated registry ({len(processed_urls_registry)} entries) back to Azure...")
        success = azure_client.upload_json(filename, processed_urls_registry)
        if success:
            print("Successfully updated registry in Azure Storage.")
        else:
            print("Failed to upload registry.")
    else:
        print("No URLs were found in the registry. No changes made.")

if __name__ == "__main__":
    main()
