import os
import json
import logging
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO)

def main():
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        logging.error("AZURE_STORAGE_CONNECTION_STRING not found in environment.")
        return

    client = BlobServiceClient.from_connection_string(conn_str)
    # The grants pipeline container name is 'data' per config
    blob_client = client.get_blob_client(container="data", blob="processed_urls.json")

    try:
        data = blob_client.download_blob().readall()
        processed_urls = json.loads(data)
        logging.info(f"Loaded processed_urls.json with {len(processed_urls)} entries.")
        
        target_url = "https://www.youtube.com/watch?v=bySyMcg-p_4"
        if target_url in processed_urls:
            del processed_urls[target_url]
            logging.info(f"Successfully deleted target URL '{target_url}' from registry.")
            blob_client.upload_blob(json.dumps(processed_urls, indent=2), overwrite=True)
            logging.info("Uploaded updated processed_urls.json to Azure.")
        else:
            logging.info(f"Target URL '{target_url}' was not found in the registry. No changes made.")
    except Exception as e:
        logging.error(f"Failed to patch registry: {e}")

if __name__ == "__main__":
    main()
