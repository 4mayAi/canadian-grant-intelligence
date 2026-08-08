import os
import sys
import logging
from azure.storage.blob import BlobServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
CONTAINER_NAME = "future-skills-data"

def sync_to_azure():
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        logging.warning("AZURE_STORAGE_CONNECTION_STRING not set. Running in dry-run mode.")
        print("Dry-run sync complete. No Azure uploads performed.")
        return

    try:
        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        if not container_client.exists():
            container_client.create_container()
            logging.info(f"Created new Azure Blob container: '{CONTAINER_NAME}'")

        # Sync JSON inventory
        json_path = os.path.join(REPORTS_DIR, "fsc_document_inventory.json")
        if os.path.exists(json_path):
            with open(json_path, "rb") as data:
                container_client.upload_blob(name="fsc_document_inventory.json", data=data, overwrite=True)
            logging.info("Uploaded 'fsc_document_inventory.json' to Azure Blob Storage.")

        # Sync Markdown reports
        for fname in os.listdir(REPORTS_DIR):
            if fname.endswith(".md"):
                fpath = os.path.join(REPORTS_DIR, fname)
                with open(fpath, "rb") as data:
                    container_client.upload_blob(name=f"reports/{fname}", data=data, overwrite=True)
                logging.info(f"Uploaded 'reports/{fname}' to Azure Blob Storage.")

        print(f"Azure Storage Sync to container '{CONTAINER_NAME}' completed successfully.")
    except Exception as e:
        logging.error(f"Azure Storage Sync failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    sync_to_azure()
