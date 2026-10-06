"""
Dispatch and monitor all production intelligence pipelines in Canadian Grant Intelligence.

Usage:
    python scripts/dispatch_all_pipelines.py [--monitor] [--lookback-days <N>]
"""

import argparse
import json
import logging
import subprocess
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

REPO = "4mayAi/canadian-grant-intelligence"

PIPELINES = [
    {
        "name": "Canadian Grants Intelligence Pipeline",
        "file": "daily_grants_scraper.yml",
        "inputs": {"run_type": "DEEP_DIVE"},
    },
    {
        "name": "Canadian Trade & Supply Chain Compliance Pipeline",
        "file": "daily_trade_compliance_scraper.yml",
        "inputs": {},
    },
    {
        "name": "Global Innovation Clusters Pipeline",
        "file": "daily_clusters_scraper.yml",
        "inputs": {},
    },
    {
        "name": "Global Mining Hubs Intelligence Pipeline",
        "file": "daily_mining_hubs_scraper.yml",
        "inputs": {},
    },
    {
        "name": "Global Payments Intelligence Pipeline",
        "file": "daily_payments_scraper.yml",
        "inputs": {},
    },
    {
        "name": "Health-Tech & Biotech Simulation Intelligence Pipeline",
        "file": "daily_amr_simulation_scraper.yml",
        "inputs": {},
    },
]


def dispatch_pipeline(workflow_file: str, inputs: dict) -> bool:
    cmd = ["gh", "workflow", "run", workflow_file, "-R", REPO]
    for key, value in inputs.items():
        cmd.extend(["-f", f"{key}={value}"])

    logging.info(f"Triggering {workflow_file} via: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logging.info(f"Successfully dispatched {workflow_file}.")
        return True
    else:
        logging.error(f"Failed to dispatch {workflow_file}: {result.stderr.strip()}")
        return False


def get_latest_runs(limit: int = 10) -> list:
    cmd = [
        "gh", "run", "list",
        "-R", REPO,
        "--limit", str(limit),
        "--json", "databaseId,name,status,conclusion,createdAt,url"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
    return []


def main():
    parser = argparse.ArgumentParser(description="Trigger all intelligence pipelines.")
    parser.add_argument("--monitor", action="store_true", help="Poll and report run statuses after dispatch.")
    parser.add_argument("--lookback-days", type=str, default=None, help="Override lookback days for news ingestion.")
    args = parser.parse_args()

    dispatched = []
    print("\n=======================================================")
    print("  Dispatching All Intelligence Pipelines")
    print(f"  Target Repository: {REPO}")
    print("=======================================================\n")

    for p in PIPELINES:
        inputs = dict(p["inputs"])
        if args.lookback_days:
            inputs["lookback_days"] = args.lookback_days
        success = dispatch_pipeline(p["file"], inputs)
        if success:
            dispatched.append(p["name"])
        time.sleep(2)  # Avoid burst throttling

    print(f"\nDispatched {len(dispatched)} of {len(PIPELINES)} pipelines successfully.\n")

    if args.monitor:
        print("Monitoring active runs (polling every 30 seconds, Ctrl+C to stop)...")
        time.sleep(10)  # Wait for GitHub to register new runs
        recent_runs = get_latest_runs(limit=10)
        for r in recent_runs:
            print(f"[{r.get('status')}] {r.get('name')} - {r.get('conclusion') or 'running'} ({r.get('url')})")


if __name__ == "__main__":
    main()
