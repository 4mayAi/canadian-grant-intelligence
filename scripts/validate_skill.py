#!/usr/bin/env python3
import os
import sys
import json
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add project root and generic_engine to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "generic_engine"))

from generic_engine.main import load_and_validate_config
from generic_engine.api.azure_client import AzureClient
from generic_engine.api.gemini_client import GeminiClient

def run_validation(config_path):
    logging.info(f"=== Starting validation for {config_path} ===")
    
    # 1. Load and validate config against schema.py
    try:
        config = load_and_validate_config(config_path=config_path)
        logging.info("Step 1: Configuration Pydantic schema validation PASSED")
    except Exception as e:
        logging.error(f"Step 1: Configuration validation FAILED: {e}")
        return False

    success = True

    # 2. Check local anchors file
    if config.storage.anchors_file:
        local_anchors_path = os.path.join(PROJECT_ROOT, "configs", config.storage.anchors_file)
        if not os.path.exists(local_anchors_path):
            logging.error(f"Step 2: Local anchors file missing at {local_anchors_path}")
            success = False
        else:
            try:
                with open(local_anchors_path, "r", encoding="utf-8") as f:
                    anchors = json.load(f)
                logging.info(f"Step 2: Local anchors file parsed correctly. Found {len(anchors)} categories/hubs.")
                
                # Check anchor facts formatting
                for hub, facts in anchors.items():
                    if not isinstance(facts, list):
                        logging.error(f"Step 2: Anchors for hub '{hub}' must be a list, got {type(facts)}")
                        success = False
                    else:
                        for fact in facts:
                            if not isinstance(fact, dict):
                                logging.error(f"Step 2: Anchor fact in hub '{hub}' must be a dict, got {type(fact)}")
                                success = False
                            else:
                                if "id" not in fact and "fact_id" not in fact:
                                    logging.error(f"Step 2: Anchor fact missing 'id' or 'fact_id'")
                                    success = False
            except Exception as e:
                logging.error(f"Step 2: Failed to parse anchors file: {e}")
                success = False

    # 3. Check Azure Connection and Subscribers File
    if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
        try:
            azure_client = AzureClient(container_name=config.storage.azure_container)
            logging.info(f"Step 3: Azure Client initialized successfully for container '{config.storage.azure_container}'.")
            
            if config.storage.subscribers_file:
                try:
                    subscribers = azure_client.download_json(config.storage.subscribers_file)
                    if subscribers is not None:
                        logging.info(f"Step 3: Reachable subscribers file '{config.storage.subscribers_file}'. Contains {len(subscribers)} subscribers.")
                    else:
                        logging.warning(f"Step 3: Subscribers file '{config.storage.subscribers_file}' does not exist in Azure yet. This is expected if no subscribers signed up.")
                except Exception as se:
                    logging.error(f"Step 3: Error downloading subscribers file: {se}")
                    success = False
        except Exception as e:
            logging.error(f"Step 3: Azure Storage connection check failed: {e}")
            success = False
    else:
        logging.warning("Step 3: AZURE_STORAGE_CONNECTION_STRING not set. Skipping Azure check.")

    # 4. Check Gemini API Connection
    if os.getenv("GEMINI_API_KEY"):
        try:
            gemini = GeminiClient(
                primary_model=config.llm_settings.model_primary,
                fallback_models=config.llm_settings.model_fallbacks,
                system_instruction=config.llm_settings.system_instruction,
                persona=config.llm_settings.persona,
                classification_rules=config.llm_settings.classification_rules,
                grounding_rules=config.llm_settings.grounding_rules,
                translation_rules=config.llm_settings.translation_rules,
                output_format=config.llm_settings.output_format,
                topic_id=config.topic_id
            )
            # Test connectivity with a small prompt
            logging.info("Step 4: Sending test connection request to Gemini API...")
            test_priorities = gemini.get_strategic_priorities(["Test headline: Canada invests in green tech research."])
            if test_priorities:
                logging.info(f"Step 4: Gemini API test connection PASSED. Received response: {test_priorities}")
            else:
                logging.error("Step 4: Gemini API test connection FAILED (returned empty response).")
                success = False
        except Exception as e:
            logging.error(f"Step 4: Gemini API test connection FAILED with exception: {e}")
            success = False
    else:
        logging.warning("Step 4: GEMINI_API_KEY not set. Skipping Gemini connection check.")

    # 5. Check Sources Connectivity (Test scrape of first source item)
    logging.info("Step 5: Testing connectivity of ingest sources...")
    import requests
    for src in config.sources[:3]:  # Test first 3 sources to keep it quick
        try:
            # RSS or general HTTP check
            resp = requests.get(src.url, timeout=10)
            if resp.status_code == 200:
                logging.info(f"  Source '{src.name}' ({src.type}) reachable: HTTP 200")
            else:
                logging.warning(f"  Source '{src.name}' returned status code: {resp.status_code}")
        except Exception as e:
            logging.warning(f"  Source '{src.name}' connectivity check failed: {e}")

    if success:
        logging.info("=== VALIDATION COMPLETED: ALL CHECKS PASSED ===")
    else:
        logging.error("=== VALIDATION COMPLETED: CHECKS FAILED ===")
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Skill configuration and setup.")
    parser.add_argument("--config", required=True, help="Path to config JSON file")
    args = parser.parse_args()
    
    valid = run_validation(args.config)
    sys.exit(0 if valid else 1)
