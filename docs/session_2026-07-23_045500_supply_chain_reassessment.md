Date: 2026-07-29
Time: 01:18 AM UTC
Title: Trade Compliance Dashboard Dropdown Ordering & News Freshness Fix

Activities:
- Diagnosed the two reported UI issues:
  1. **Archive Dropdown Ordering**: `docs/trade-compliance/index.html` was calling `.reverse()` on `manifest.json`, which inverted the dates from newest-to-oldest into oldest-to-newest (`2026-07-24` first). Removed `.reverse()` so dates render newest to oldest (`2026-07-30`, `2026-07-28`, `2026-07-27`, `2026-07-26`, `2026-07-24`), matching all other platform dashboards.
  2. **Perceived Static News**: Confirmed that news items in `trade_insights.json` are actively updating (fresh July 29 items ingested today). The inverted dropdown previously led users to select July 24 data by default when browsing the top of the archive list.

Summary:
- Fixed dropdown sorting in `docs/trade-compliance/index.html` and verified active news ingestion.

Next Steps:
- Commit and push HTML fix using OneDrive-safe Git flags.
