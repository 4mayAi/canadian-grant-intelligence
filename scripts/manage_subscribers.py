import os
import sys
import json
import argparse
import logging
import dotenv

# Dynamically resolve project root relative to script file
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load environment variables anchored to CWD for OneDrive compatibility
dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))

from generic_engine.api.azure_client import AzureClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BLOB_NAME = "subscriber_profiles.json"
CONTAINER = "data"

def get_profiles(azure_client: AzureClient) -> list:
    data = azure_client.download_json(BLOB_NAME)
    if isinstance(data, list):
        return data
    return []

def save_profiles(azure_client: AzureClient, profiles: list) -> bool:
    return azure_client.upload_json(BLOB_NAME, profiles)

def list_profiles(azure_client: AzureClient):
    profiles = get_profiles(azure_client)
    print(f"\n--- Active Subscriber Profiles in Azure ({len(profiles)}) ---")
    for p in profiles:
        print(f"ID: {p.get('subscriber_id')}")
        print(f"  Name:         {p.get('name')}")
        print(f"  Email:        {p.get('email')}")
        print(f"  Keywords:     {', '.join(p.get('keywords', []))}")
        print(f"  Capabilities: {p.get('capabilities')}")
        print(f"  Target Orgs:  {', '.join(p.get('target_organizations', []))}")
        print("-" * 50)

def add_profile(azure_client: AzureClient, args):
    profiles = get_profiles(azure_client)
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    target_orgs = [o.strip() for o in args.target_orgs.split(",") if o.strip()] if args.target_orgs else []

    new_profile = {
        "subscriber_id": args.id,
        "name": args.name,
        "email": args.email,
        "keywords": keywords,
        "capabilities": args.capabilities,
        "target_organizations": target_orgs
    }

    # Update if existing ID, else append
    updated = False
    for i, p in enumerate(profiles):
        if p.get("subscriber_id") == args.id:
            profiles[i] = new_profile
            updated = True
            break
    
    if not updated:
        profiles.append(new_profile)

    if save_profiles(azure_client, profiles):
        action = "Updated" if updated else "Added"
        print(f"Successfully {action} subscriber profile: '{args.id}' in Azure Blob Storage.")
    else:
        print(f"Failed to save profile '{args.id}' to Azure Blob Storage.")

def delete_profile(azure_client: AzureClient, args):
    profiles = get_profiles(azure_client)
    initial_count = len(profiles)
    profiles = [p for p in profiles if p.get("subscriber_id") != args.id]
    
    if len(profiles) == initial_count:
        print(f"No profile found with ID: '{args.id}'")
        return

    if save_profiles(azure_client, profiles):
        print(f"Successfully deleted subscriber profile: '{args.id}'")
    else:
        print(f"Failed to update Azure Blob Storage after deleting '{args.id}'")

def main():
    parser = argparse.ArgumentParser(description="Manage subscriber capability profiles in Azure Blob Storage.")
    parser.add_argument("--container", default=CONTAINER, help="Azure Blob container name")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List all subscriber profiles")

    # add
    add_parser = subparsers.add_parser("add", help="Add or update a subscriber profile")
    add_parser.add_argument("--id", required=True, help="Unique subscriber ID (e.g. mayai_market_intelligence)")
    add_parser.add_argument("--name", required=True, help="Subscriber business name")
    add_parser.add_argument("--email", required=True, help="Alert recipient email address")
    add_parser.add_argument("--keywords", required=True, help="Comma-separated keywords for local pre-filtering")
    add_parser.add_argument("--capabilities", required=True, help="Detailed description of business capabilities and offerings")
    add_parser.add_argument("--target-orgs", default="", help="Comma-separated target purchasing organizations")

    # delete
    del_parser = subparsers.add_parser("delete", help="Delete a subscriber profile by ID")
    del_parser.add_argument("--id", required=True, help="Subscriber ID to delete")

    args = parser.parse_args()
    azure_client = AzureClient(container_name=args.container)

    if args.command == "list":
        list_profiles(azure_client)
    elif args.command == "add":
        add_profile(azure_client, args)
    elif args.command == "delete":
        delete_profile(azure_client, args)

if __name__ == "__main__":
    main()
