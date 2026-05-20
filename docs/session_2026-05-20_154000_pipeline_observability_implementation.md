Date: 2026-05-20
Time: 15:40 UTC
Title: Pipeline Observability and Resilience Implementation

Session Content:
- Analyzed the project validation posture: 32 success criteria across 6 dimensions, only 5 (16%) were previously verifiable with auditable evidence.
- Implemented a 4-phase observability improvement plan approved by the user.
- Phase 1 (Foundation):
  - Pinned all 5 Python dependencies to exact versions in `requirements.txt` (requests==2.32.4, feedparser==6.0.12, python-dateutil==2.9.0.post0, azure-storage-blob==12.26.0, playwright==1.56.0).
  - Created `scripts/validators/validate_output.py` — post-run validation checking schema, data freshness, deduplication, cross-consistency (KPI vs tender count), and LLM output quality metrics.
  - Created `scripts/validators/prune_processed_urls.py` — weekly TTL pruning to remove URLs older than 90 days from the processed registry.
  - Migrated `processed_urls.json` from a flat list to a `{url: ISO_timestamp}` dict format in `main.py` to support TTL pruning. Backwards-compatible with legacy format.
  - Updated `daily_grants_scraper.yml` to install from pinned `requirements.txt` instead of inline `pip install`.
  - Added "Validate Pipeline Output" step to the workflow after the main scraper.
  - Added weekly `prune` job to the workflow, triggered every Sunday at 22:00 UTC.
- Phase 2 (Data Integrity):
  - Added runtime integrity assertions in `main.py` after the tender merge step: duplicate link detection and required key validation.
  - Added HEALTH log line with tender count, PMO insight count, and KPI timestamp.
- Phase 3 (Intelligence Quality):
  - Added quality telemetry counters to `GeminiClient` class: requests_total, requests_success, requests_rate_limited, model_fallbacks, insights_no_value, insights_api_error.
  - Counters are incremented at appropriate points in `_retry_request` and `get_gemini_insights_batch`.
  - Added `get_stats()` method and LLM_STATS logging at end of pipeline.
- Phase 4 (Visibility):
  - Added GoatCounter analytics snippet to `docs/index.html` — privacy-respecting, cookie-free, open-source page view counter.
- Verified all 31 existing unit tests pass (9 + 22).
- Verified the new validation script runs cleanly against local data (all checks green except expected freshness warning on stale local copy).

Summary:
- Implemented pipeline observability across 4 phases: Foundation, Data Integrity, Intelligence Quality, and Visibility.
- Created 2 new standalone validator scripts in `scripts/validators/`.
- Modified 5 existing files: requirements.txt, main.py, gemini_client.py, daily_grants_scraper.yml, index.html.
- All tests pass. Validation report confirms zero duplicates, schema compliance, and KPI cross-consistency.

Issues:
- GoatCounter account at `mayai.goatcounter.com` needs to be created before analytics data will collect.
- The `processed_urls.json` format migration will occur automatically on the next pipeline run.

Next Steps:
- Commit and push all changes to `origin main`.
- Trigger a manual PULSE run to verify the workflow in production.
- Monitor the 7-day soak test (21 runs) for pipeline health.
- Create GoatCounter account at https://www.goatcounter.com/signup for `mayai` site code.
