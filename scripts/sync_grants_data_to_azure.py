"""
Syncs local Canadian Grants backup JSON files to Azure Blob Storage container 'data'.
"""
import os
import sys
import json
import logging

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from generic_engine.api.azure_client import AzureClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def sync():
    azure = AzureClient("data")
    if not azure.blob_service_client:
        logging.error("AzureClient not configured (AZURE_STORAGE_CONNECTION_STRING missing).")
        sys.exit(1)
        
    pmo_path = os.path.join(PROJECT_ROOT, "docs", "data", "canadian-grants", "pmo_insights.json")
    if os.path.exists(pmo_path):
        with open(pmo_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        success = azure.upload_json("pmo_insights.json", data)
        logging.info(f"Uploaded pmo_insights.json to Azure: {success}")
    else:
        logging.error(f"File not found: {pmo_path}")
        sys.exit(1)

if __name__ == "__main__":
    sync()
