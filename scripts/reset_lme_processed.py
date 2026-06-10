import sys
import os

# Set path to parent directory so generic_engine is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generic_engine.api.azure_client import AzureClient

def main():
    # Initialize Azure client targeting the mining-hubs-data container
    client = AzureClient(container_name="mining-hubs-data")
    
    blob_name = "processed_urls.json"
    data = client.download_json(blob_name)
    if not data:
        print("Could not download processed_urls.json or it is empty.")
        return
        
    print(f"Loaded processed_urls.json. Total URLs: {len(data)}")
    
    # Target URL to remove
    target_url = "https://www.lme.com/events/2026/06/smm-indonesia-critical-minerals-conference"
    if target_url in data:
        del data[target_url]
        print(f"Removed target URL: {target_url}")
        
        # Upload the updated dict back to Azure
        success = client.upload_json(blob_name, data)
        if success:
            print("Successfully uploaded updated processed_urls.json back to Azure.")
        else:
            print("Failed to upload updated processed_urls.json back to Azure.")
    else:
        print(f"Target URL not found in processed_urls.json. Current keys:")
        for k in data.keys():
            print(f"  {k}")

if __name__ == "__main__":
    main()
