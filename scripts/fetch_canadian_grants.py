#!/usr/bin/env python3
"""
Wrapper script for the Canadian Grant Intelligence pipeline.
This script replaces the legacy 1,125-line monolith to maintain compatibility
with existing GitHub Actions workflows while delegating execution to the
refactored modular ELT pipeline in `src/main.py`.
"""

import sys
import logging
from src.main import run_pipeline

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        logging.error(f"Execution failed: {e}")
        sys.exit(1)
