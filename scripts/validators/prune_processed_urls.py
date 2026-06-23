#!/usr/bin/env python3
"""
TTL pruning for processed_urls.json on Azure Blob Storage.
Removes URLs older than 90 days to prevent unbounded registry growth.

Runs as a standalone weekly job in the GitHub Actions workflow.
Supports both legacy flat-list format and new timestamped-dict format.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TTL_DAYS = 90

def get_azure_client(container_name="data"):
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(project_root, "generic_engine"))
    from api.azure_client import AzureClient
    return AzureClient(container_name=container_name)

def prune(config_path=None):
    container_name = "data"
    urls_file = "processed_urls.json"

    if config_path:
        logging.info(f"Loading configuration from {config_path} for container-aware pruning...")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            storage_config = config_data.get("storage", {})
            container_name = storage_config.get("azure_container", "data")
            urls_file = storage_config.get("processed_urls_file", "processed_urls.json")
            logging.info(f"Resolved pruning target: Container='{container_name}', File='{urls_file}'")
        except Exception as e:
            logging.error(f"Failed to load configuration file: {e}")
            sys.exit(1)

    azure = get_azure_client(container_name=container_name)
    raw = azure.download_json(urls_file)

    if raw is None:
        logging.info(f"No {urls_file} found in Azure container '{container_name}'. Nothing to prune.")
        return

    # Handle legacy list format (migrate to dict)
    if isinstance(raw, list):
        logging.info(f"Legacy format detected: {len(raw)} URLs as flat list. Migrating to timestamped dict.")
        registry = {url: datetime.utcnow().isoformat() + "Z" for url in raw}
    elif isinstance(raw, dict):
        registry = raw
    else:
        logging.error(f"Unexpected format for URL registry: {type(raw).__name__}")
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
            # Keep URLs with unparseable timestamps
            pruned[url] = timestamp_str

    logging.info(f"Pruning: {original_count} total -> {expired_count} expired -> {len(pruned)} retained (TTL: {TTL_DAYS} days)")

    if expired_count > 0:
        success = azure.upload_json(urls_file, pruned)
        if success:
            logging.info(f"Successfully uploaded pruned registry ({len(pruned)} URLs) to Azure container '{container_name}'.")
        else:
            logging.error(f"Failed to upload pruned registry to Azure container '{container_name}'.")
            sys.exit(1)
    else:
        logging.info("No URLs expired. Registry unchanged.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prune processed URLs from Azure Blob Storage.")
    parser.add_argument("--config", help="Path to config JSON file to extract container details")
    args = parser.parse_args()
    prune(args.config)
