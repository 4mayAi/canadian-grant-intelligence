Date: 2026-06-04
Time: 10:03 PM UTC
Title: Mining Pipeline Alignment Session

Inside this session file, we document the activities performed to align the schedule, triggers, and execution setup of the Global Mining Hubs pipeline with the rest of the intelligence pipelines.

## Activities and Tasks
- Inspected [.github/workflows/daily_mining_hubs_scraper.yml](file:///c:/dev/canadian-grant-intelligence/.github/workflows/daily_mining_hubs_scraper.yml) to see its active GHA scheduler cron trigger.
- Verified that [.github/workflows/daily_clusters_scraper.yml](file:///c:/dev/canadian-grant-intelligence/.github/workflows/daily_clusters_scraper.yml) and [.github/workflows/daily_grants_scraper.yml](file:///c:/dev/canadian-grant-intelligence/.github/workflows/daily_grants_scraper.yml) run externally via Google Cloud Scheduler, having their native crons commented out.
- Modified [.github/workflows/daily_mining_hubs_scraper.yml](file:///c:/dev/canadian-grant-intelligence/.github/workflows/daily_mining_hubs_scraper.yml) to comment out lines 4-5, disabling the native cron to prevent duplicate triggers.
- Created the GCP configuration script [setup_gcp_mining_hubs_scheduler.ps1](file:///c:/dev/canadian-grant-intelligence/scratch/setup_gcp_mining_hubs_scheduler.ps1) to define and set up the HTTP dispatch trigger job `daily-mining-hubs-scraper-trigger` targeting the workflow at 12:00 PM Eastern/New York Time (16:00 UTC).
- Executed the script programmatically via PowerShell and successfully registered the new Cloud Scheduler job in your GCP project `project-f0d36d83-0e2f-4d56-aad` (region `us-west1`).
- Staged, committed, pulled/rebased remote changes, and successfully pushed the codebase updates to GitHub.

Summary:
- Commented out the native GHA cron trigger in the Mining Hubs workflow.
- Created and executed a GCP Cloud Scheduler provisioning script to create `daily-mining-hubs-scraper-trigger`.
- Successfully pushed the alignment configurations back to GitHub `main` branch.

Issues:
- None.

Next Steps:
- Monitor GHA run logs driven by the new GCP Cloud Scheduler job.
