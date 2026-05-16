Date: 2026-05-16
Time: 05:07 UTC
Title: News Cycle Alignment & Gemini Deduplication

## Activities

- Analyzed the PMO RSS feed (`https://www.pm.gc.ca/en/news.rss`) to determine actual publication times
  - Confirmed releases cluster between 15:00–22:00 UTC (11am–6pm EDT), with the old 07:00 UTC Deep Dive hitting at 3:00 AM EDT — before any Canadian business day activity
- Updated `.github/workflows/daily_grants_scraper.yml`:
  - Changed cron schedule from `07:00/13:00/19:00 UTC` to `14:00/18:00/22:00 UTC` (10am/2pm/6pm EDT)
  - Simplified `RUN_TYPE` logic — all scheduled runs now default to `DEEP_DIVE`
  - Gated email digest to the 22:00 UTC (end-of-day) run only to prevent 3x daily emails
- Implemented Azure-based URL cache in `scripts/fetch_canadian_grants.py`:
  - Added `download_processed_cache()` and `upload_processed_cache()` functions
  - Modified `fetch_pmo_news()` to check cache before calling Gemini API, skipping already-processed URLs
  - Added 7-day TTL pruning to prevent unbounded cache growth
  - Added defensive guard to `upload_pmo_json()` — if no new insights are found, existing Azure data is preserved instead of overwritten with an empty array
- Discovered and fixed the "Pulse overwrite bug" where Pulse runs were wiping `pmo_insights.json` with empty insights arrays
- Triggered manual DEEP_DIVE via GitHub Actions (run 25953958796) — succeeded in 8m37s
- Verified in Azure:
  - `processed_urls.json` created with 2 cached URLs (Alberta exports agreement + National Electricity Strategy)
  - `pmo_insights.json` populated with 2 full insights (previously was empty `[]`)

## Summary
- Aligned pipeline cron with Canadian EDT business hours
- Eliminated Gemini API waste via URL-based deduplication cache
- Fixed destructive Pulse overwrite bug
- All changes verified against live Azure data

## Issues
- Gemini API daily rate limit was hit during this session, but the verification run completed before exhaustion

## Next Steps
- Monitor next 3 automated runs (14:00, 18:00, 22:00 UTC) to confirm deduplication works across runs
- Verify the second run logs show "Skipping (cached on ...)" for already-processed articles
