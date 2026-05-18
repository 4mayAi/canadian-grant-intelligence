import subprocess
import json
import sys

def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print(f"Error executing: {cmd}\n{result.stderr}", file=sys.stderr)
        return None
    return result.stdout

def main():
    print("Fetching last 50 workflow runs...")
    # Get last 50 runs of the workflow
    runs_json = run_command("gh run list --repo 4mayAi/canadian-grant-intelligence --workflow daily_grants_scraper.yml --limit 50 --json databaseId,createdAt,event")
    if not runs_json:
        return
    
    runs = json.loads(runs_json)
    print(f"Checking steps for {len(runs)} runs to find successful email digests...")
    
    found_any = False
    for i, run in enumerate(runs):
        run_id = run['databaseId']
        created_at = run['createdAt']
        event = run['event']
        
        # Query job steps for this run
        jobs_json = run_command(f"gh run view {run_id} --repo 4mayAi/canadian-grant-intelligence --json jobs")
        if not jobs_json:
            continue
            
        try:
            jobs_data = json.loads(jobs_json)
            for job in jobs_data.get('jobs', []):
                for step in job.get('steps', []):
                    if step.get('name') == 'Send Email Digest':
                        conclusion = step.get('conclusion')
                        status = step.get('status')
                        if conclusion == 'success':
                            print(f"\n[SUCCESS] Email successfully sent!")
                            print(f"Run ID: {run_id}")
                            print(f"Date/Time: {created_at} UTC")
                            print(f"Event: {event}")
                            found_any = True
                        elif conclusion == 'failure':
                            print(f"\n[FAILED] Email send failed!")
                            print(f"Run ID: {run_id}")
                            print(f"Date/Time: {created_at} UTC")
                            print(f"Event: {event}")
                            found_any = True
        except Exception as e:
            print(f"Error parsing run {run_id}: {e}", file=sys.stderr)
            
    if not found_any:
        print("\nNo emails sent or failed in the last 50 runs.")

if __name__ == "__main__":
    main()
