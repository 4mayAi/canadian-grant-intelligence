"""One-time backfill script to retroactively label existing tenders with recommended_playbook.

Loads both pmo_insights.json and tenders.json from Azure blob storage,
applies the deterministic playbook classifier to each tender item,
and uploads the updated files back.

Usage:
    $env:PYTHONPATH="c:\dev\canadian-grant-intelligence"
    c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\scripts\backfill_playbook_labels.py
"""
import json
import logging
import os
import sys

# Ensure workspace root is on the path for generic_engine imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dotenv
dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

from generic_engine.extractors.ckan import determine_recommended_playbook
from generic_engine.azure_blob import AzureBlobClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AZURE_CONTAINER = "data"
FILES_TO_BACKFILL = ["pmo_insights.json", "tenders.json"]


def backfill_file(azure_client: AzureBlobClient, filename: str) -> int:
    """Apply playbook labels to all tender items in the given blob file.
    
    Returns the count of items labeled.
    """
    logging.info(f"Downloading {filename} from Azure...")
    items = azure_client.download_json(filename)
    if not items:
        logging.warning(f"{filename} is empty or not found. Skipping.")
        return 0

    labeled_count = 0
    for item in items:
        # Only label items that have tender metadata (notice_type field)
        if "notice_type" not in item:
            continue

        playbook = determine_recommended_playbook(
            item.get("notice_type", ""),
            item.get("procurement_method", ""),
            item.get("description", "")
        )
        item["recommended_playbook"] = playbook
        labeled_count += 1

    logging.info(f"Labeled {labeled_count}/{len(items)} items in {filename}.")

    # Upload via atomic temp-copy pattern
    temp_name = f"{os.path.splitext(filename)[0]}_backfill_temp.json"
    azure_client.upload_json(temp_name, items)
    azure_client.copy_blob(temp_name, filename)
    logging.info(f"Uploaded backfilled {filename} to Azure.")

    return labeled_count


def main():
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        logging.error("AZURE_STORAGE_CONNECTION_STRING not set. Aborting.")
        sys.exit(1)

    azure_client = AzureBlobClient(connection_string, AZURE_CONTAINER)

    total = 0
    for filename in FILES_TO_BACKFILL:
        total += backfill_file(azure_client, filename)

    logging.info(f"Backfill complete. Total items labeled: {total}")


if __name__ == "__main__":
    main()
