Date: 2026-05-18
Time: 05:48 AM UTC
Title: Gemini API Bad Request Remediation & Workflow Optimization

Activities:
- Investigated the root cause of the `400 Bad Request` error when calling the Gemini API during PMO news ingestion.
- Traced the error to empty, null, or boilerplate text content scraped from PMO articles (like "Switch to basic HTML version" links under `/wbdisable=true`).
- Refactored `scripts/src/api/gemini_client.py` to:
  - Consolidate redundant `get_hero_hook` implementations.
  - Sanitize the input prompt before calling the Gemini API to filter out empty/whitespace-only texts.
  - Wrap the call in exception handling that captures the raw HTTP request/response to aid future troubleshooting.
- Refactored `scripts/src/extractors/playwright_scraper.py` to expand junk navigation filtering (e.g., matching on "Switch to basic HTML" and checking paths like `/wbdisable=true`).
- Refactored `.github/workflows/daily_grants_scraper.yml` to dynamically calculate today's date in a dedicated step using `date` and the GitHub `$GITHUB_ENV` variable, replacing the inline command block in the SMTP email subject line.
- Tested the modified pipeline locally in `test` mode to verify it compiles and runs flawlessly without exceptions.
- Committed and pushed all changes to the GitHub remote `4mayAi/canadian-grant-intelligence`.
- Triggered the GitHub Actions workflow using the GitHub CLI (`gh`) and monitored its execution.

Summary:
- Resolved the Gemini 400 Bad Request issues by sanitizing article texts and filtering boilerplate content.
- Consolidated duplicate client logic.
- Optimized the daily workflow to format dates correctly in the email subject.
- Successfully pushed to GitHub and triggered a run.

Issues:
- None.

Next Steps:
- Monitor the triggered GitHub Actions workflow to verify that it completes successfully and sends the email digest with the formatted subject.
