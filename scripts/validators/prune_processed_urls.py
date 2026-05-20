#!/usr/bin/env python3
"""
TTL pruning for processed_urls.json on Azure Blob Storage.
Removes URLs older than 90 days to prevent unbounded registry growth.

Runs as a standalone weekly job in the GitHub Actions workflow.
Supports both legacy flat-list format and new timestamped-dict format.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TTL_DAYS = 90

# Lazy import to avoid hard dependency when testing locally without Azure
def get_azure_client():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
    from src.api.azure_client import azure_client
    return azure_client


def prune():
    azure = get_azure_client()
    raw = azure.download_json("processed_urls.json")

    if raw is None:
        logging.info("No processed_urls.json found on Azure. Nothing to prune.")
        return

    # Handle legacy list format (migrate to dict)
    if isinstance(raw, list):
        logging.info(f"Legacy format detected: {len(raw)} URLs as flat list. Migrating to timestamped dict.")
        # Assign current timestamp to all existing URLs (we don't know when they were added)
        registry = {url: datetime.utcnow().isoformat() + "Z" for url in raw}
    elif isinstance(raw, dict):
        registry = raw
    else:
        logging.error(f"Unexpected format for processed_urls.json: {type(raw).__name__}")
        return

    original_count = len(registry)
    cutoff = datetime.utcnow() - timedelta(days=TTL_DAYS)

    pruned = {}
    expired_count = 0
    for url, timestamp_str in registry.items():
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).replace(tzinfo=None)
            if ts >= cutoff:
                pruned[url] = timestamp_str
            else:
                expired_count += 1
        except (ValueError, TypeError):
            # Keep URLs with unparseable timestamps (don't lose data)
            pruned[url] = timestamp_str

    logging.info(f"Pruning: {original_count} total -> {expired_count} expired -> {len(pruned)} retained (TTL: {TTL_DAYS} days)")

    if expired_count > 0:
        success = azure.upload_json("processed_urls.json", pruned)
        if success:
            logging.info(f"Successfully uploaded pruned registry ({len(pruned)} URLs) to Azure.")
        else:
            logging.error("Failed to upload pruned registry to Azure.")
            sys.exit(1)
    else:
        logging.info("No URLs expired. Registry unchanged.")


if __name__ == "__main__":
    prune()
