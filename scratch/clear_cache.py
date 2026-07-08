"""
Selective cache reset: Clears only discarded URLs from processed_urls.json
that are NOT in the active cluster_insights.json cache.
This allows the pipeline to re-evaluate previously filtered articles
against an expanded keyword list, without re-processing already-analyzed items.
"""
import json
import os
import sys
import dotenv

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
    urls_file = "processed_urls.json"
    insights_file = "cluster_insights.json"

    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    print("AZURE_STORAGE_CONNECTION_STRING present in env:", bool(conn_str))

    print(f"Initializing Azure Client for container '{container}'...")
    azure_client = AzureClient(container_name=container)

    # Download both registries
    print(f"Downloading {urls_file} from Azure...")
    processed_urls = azure_client.download_json(urls_file)
    if not processed_urls:
        print("Failed to download processed_urls registry or empty.")
        return

    print(f"Downloading {insights_file} from Azure...")
    insights_data = azure_client.download_json(insights_file)
    if not insights_data:
        print("Failed to download insights data or empty. Proceeding with empty insights set.")
        insights_data = {}

    # Build set of URLs that are in the active insights cache
    cached_links = set()
    for item in insights_data.get("insights", []):
        if "link" in item:
            cached_links.add(item["link"])

    print(f"Processed URLs registry: {len(processed_urls)} entries")
    print(f"Active insights cache: {len(cached_links)} entries")

    # Remove only discarded URLs (processed but not in insights)
    removed = 0
    for url in list(processed_urls.keys()):
        if url not in cached_links:
            del processed_urls[url]
            removed += 1

    print(f"Removed {removed} discarded URLs from registry.")
    print(f"Retained {len(processed_urls)} URLs (active insights cache hits).")

    if removed > 0:
        print(f"Uploading updated registry ({len(processed_urls)} entries) back to Azure...")
        success = azure_client.upload_json(urls_file, processed_urls)
        if success:
            print("Successfully updated registry in Azure Storage.")
        else:
            print("Failed to upload registry.")
    else:
        print("No URLs were removed. No changes made.")

if __name__ == "__main__":
    main()
