Date: 2026-05-28
Time: 01:53 AM UTC
Title: Fix Cloud Scheduler Content-Type Header

## Activities
- Investigated the failure of the Google Cloud Scheduler job (`daily-grants-scraper-eod-trigger`).
- Inspected the job configuration using `gcloud scheduler jobs describe`.
- Discovered that the request was rejected with gRPC status code 3 (INVALID_ARGUMENT) because the payload was sent with `Content-Type: application/octet-stream` instead of `application/json`.
- Modified [deploy_schedulers.ps1](file:///c:/dev/canadian-grant-intelligence/scratch/deploy_schedulers.ps1) to explicitly add `Content-Type=application/json` to the HTTP headers.
- Discovered that PowerShell was stripping unescaped double quotes from the `--message-body` parameter, sending invalid JSON (e.g. `{ref:main...}`) to GitHub and resulting in HTTP 400.
- Updated [deploy_schedulers.ps1](file:///c:/dev/canadian-grant-intelligence/scratch/deploy_schedulers.ps1) to escape JSON double quotes with backslashes (`\"`) in the single-quoted `$body` variable.
- Re-ran the deployment script to recreate the three jobs with the correct headers and escaped message body.
- Manually triggered `daily-grants-scraper-eod-trigger` using `gcloud scheduler jobs run`.
- Confirmed that the execution succeeded (reporting `status: {}` in GCP) and triggered the pipeline run successfully on GitHub Actions.

## Summary
- Fixed a Cloud Scheduler payload issue where the request failed with HTTP 400 Bad Request.
- Resolved two underlying problems: missing `Content-Type: application/json` header and stripped double quotes in the JSON payload (caused by PowerShell parsing).
- Re-deployed and successfully verified the scheduler triggers the GitHub Actions pipeline.

## Issues
- Resolved: Missing `Content-Type` header and PowerShell double-quote stripping.

## Next Steps
- Monitor automated schedule triggers.

