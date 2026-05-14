
import requests
import json

def test_ckan():
    URL = "https://open.canada.ca/data/api/action/package_show?id=68683935-7164-4e42-995f-3315758a0e8d"
    try:
        res = requests.get(URL, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("success"):
            resources = data.get("result", {}).get("resources", [])
            print(f"Success! Found {len(resources)} resources.")
            for r in resources:
                name = r.get("name", {}).get("en", "Unknown")
                print(f"- {name}: {r.get('url')}")
        else:
            print("API returned failure")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ckan()
