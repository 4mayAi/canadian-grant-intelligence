#!/usr/bin/env python3
"""
Centralized two-tier cache invalidation utility for Azure Blob Storage.
Evicts specified URLs (by exact match or substring) from BOTH:
  1. processed_urls.json (the ingestion registry)
  2. <insights_file> (e.g., pmo_insights.json, mining_insights.json, etc., which populates existing_insights_map)

Can be invoked standalone or via GitHub Actions `pre_run_script` across all 6 pipelines:
  python scripts/validators/invalidate_cached_urls.py --config configs/canadian_grants.json --match "canada-strong"
"""

import argparse
import json
import logging
import os
import sys
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "generic_engine"))

from generic_engine.api.azure_client import AzureClient


def should_evict(url: str, exact_urls: List[str], substrings: List[str]) -> bool:
    if url in exact_urls:
        return True
    url_lower = url.lower()
    return any(sub.lower() in url_lower for sub in substrings)


def invalidate_cache(config_path: str, exact_urls: List[str], substrings: List[str]) -> None:
    if not exact_urls and not substrings:
        logging.warning("No --urls or --match patterns provided. Nothing to invalidate.")
        return

    full_config_path = config_path if os.path.isabs(config_path) else os.path.join(PROJECT_ROOT, config_path)
    if not os.path.exists(full_config_path):
        logging.error(f"Config file not found: {full_config_path}")
        sys.exit(1)

    with open(full_config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    storage_cfg = config_data.get("storage", {})
    container_name = storage_cfg.get("azure_container", "data")
    urls_file = storage_cfg.get("processed_urls_file", "processed_urls.json")
    insights_file = storage_cfg.get("insights_file", "pmo_insights.json")

    azure = AzureClient(container_name=container_name)
    if not azure.blob_service_client:
        logging.error("AzureClient not active (check AZURE_STORAGE_CONNECTION_STRING).")
        sys.exit(1)

    # 1. Evict from processed_urls.json
    raw_urls = azure.download_json(urls_file)
    if raw_urls is not None:
        if isinstance(raw_urls, list):
            filtered_urls = [u for u in raw_urls if not should_evict(u, exact_urls, substrings)]
            evicted_count = len(raw_urls) - len(filtered_urls)
        elif isinstance(raw_urls, dict):
            filtered_urls = {u: ts for u, ts in raw_urls.items() if not should_evict(u, exact_urls, substrings)}
            evicted_count = len(raw_urls) - len(filtered_urls)
        else:
            filtered_urls = raw_urls
            evicted_count = 0

        if evicted_count > 0:
            azure.upload_json(urls_file, filtered_urls)
            logging.info(f"Evicted {evicted_count} URL(s) from {container_name}/{urls_file}.")
        else:
            logging.info(f"No matching URLs found in {container_name}/{urls_file}.")

    # 2. Evict from <insights_file> (existing_insights_map source)
    raw_insights = azure.download_json(insights_file)
    if isinstance(raw_insights, dict) and "insights" in raw_insights:
        original_list = raw_insights.get("insights", [])
        retained_list = [
            item for item in original_list
            if not should_evict(item.get("link", ""), exact_urls, substrings)
        ]
        evicted_insights = len(original_list) - len(retained_list)
        if evicted_insights > 0:
            raw_insights["insights"] = retained_list
            azure.upload_json(insights_file, raw_insights)
            logging.info(f"Evicted {evicted_insights} cached insight(s) from {container_name}/{insights_file}.")
        else:
            logging.info(f"No matching insights found in {container_name}/{insights_file}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Invalidate cached URLs and insights in Azure Blob Storage.")
    parser.add_argument("--config", required=True, help="Path to topic config JSON (e.g. configs/canadian_grants.json)")
    parser.add_argument("--urls", nargs="*", default=[], help="Exact URL(s) to evict from cache")
    parser.add_argument("--match", nargs="*", default=[], help="Case-insensitive URL substring(s) to evict from cache")
    args = parser.parse_args()

    invalidate_cache(args.config, args.urls, args.match)
