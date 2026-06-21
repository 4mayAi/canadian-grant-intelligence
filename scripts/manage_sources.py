import json
import argparse
import sys
import os

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'innovation_clusters.json'))

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Config file not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write('\n') # Ensure trailing newline

def list_sources(config):
    sources = config.get("sources", [])
    print(f"\n### Active Sources for {config.get('display_name')} ({len(sources)} total)\n")
    print(f"{'#':<3} | {'Name':<25} | {'Hub':<15} | {'Type':<15} | {'URL'}")
    print("-" * 100)
    for i, src in enumerate(sources, 1):
        name = src.get("name", "")
        hub = src.get("hub", "")
        stype = src.get("type", "")
        url = src.get("url", "")
        if len(url) > 60:
            url = url[:57] + "..."
        print(f"{i:<3} | {name:<25} | {hub:<15} | {stype:<15} | {url}")
    print()

def add_source(config, name, url, stype, hub, skip_query_refactoring):
    sources = config.setdefault("sources", [])
    
    # Check if duplicate name
    if any(s.get("name") == name for s in sources):
        print(f"Error: Source with name '{name}' already exists.", file=sys.stderr)
        sys.exit(1)
        
    new_src = {
        "name": name,
        "url": url,
        "type": stype,
        "hub": hub
    }
    if skip_query_refactoring:
        new_src["skip_query_refactoring"] = True
        
    sources.append(new_src)
    save_config(config)
    print(f"Successfully added source '{name}' to hub '{hub}'.")

def remove_source(config, name):
    sources = config.get("sources", [])
    initial_len = len(sources)
    config["sources"] = [s for s in sources if s.get("name") != name]
    
    if len(config["sources"]) == initial_len:
        print(f"Error: Source with name '{name}' not found.", file=sys.stderr)
        sys.exit(1)
        
    save_config(config)
    print(f"Successfully removed source '{name}'.")

def main():
    parser = argparse.ArgumentParser(description="Manage innovation cluster pipeline sources.")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # List command
    subparsers.add_parser("list", help="List all current sources")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new source")
    add_parser.add_argument("--name", required=True, help="Unique name for the source")
    add_parser.add_argument("--url", required=True, help="URL (feed address or website page)")
    add_parser.add_argument("--type", required=True, choices=["rss", "html_playwright"], help="Source type (rss or html_playwright)")
    add_parser.add_argument("--hub", required=True, choices=["DIGITAL", "ScaleAI", "Ocean", "NGen", "ProteinIndustries"], help="Cluster hub name")
    add_parser.add_argument("--skip-query-refactoring", action="store_true", help="Set skip_query_refactoring to true")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a source by name")
    remove_parser.add_argument("--name", required=True, help="Name of the source to remove")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config()

    if args.command == "list":
        list_sources(config)
    elif args.command == "add":
        add_source(config, args.name, args.url, args.type, args.hub, args.skip_query_refactoring)
    elif args.command == "remove":
        remove_source(config, args.name)

if __name__ == "__main__":
    main()
