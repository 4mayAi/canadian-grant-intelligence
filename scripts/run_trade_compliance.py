#!/usr/bin/env python3
"""
Wrapper script for the Canadian Trade & Supply Chain Intelligence pipeline.
Delegates execution to the config-driven generic engine.
"""

import sys
import os
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "generic_engine"))

from generic_engine.main import run_engine_pipeline

if __name__ == "__main__":
    try:
        config_path = os.path.join(PROJECT_ROOT, "configs", "trade_compliance.json")
        run_type = os.getenv("RUN_TYPE", "deep_dive").lower()
        if run_type not in ["deep_dive", "pulse", "seed_strategy"]:
            run_type = "deep_dive"
            
        run_engine_pipeline(config_path=config_path, run_type=run_type)
    except Exception as e:
        logging.error(f"Trade compliance execution failed: {e}")
        sys.exit(1)
