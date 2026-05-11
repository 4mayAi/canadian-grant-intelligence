Date: 2026-05-11
Time: 09:30 PM
Title: Dashboard Layout & Source Verification

- **KPI Relocation**: Moved the KPI container to the global dashboard header (above tabs) for better executive visibility across both Tenders and PMO News views.
- **Layout Readability**: Fixed the "large empty space on the right" issue by introducing a centered `.report-section` container with an 850px maximum width.
- **Source Verification**: Confirmed hybrid data fetching strategy:
    - Primary: Azure Blob Storage (`tenders.json` and `pmo_insights_[date].json`).
    - Fallback: GitHub API for legacy Markdown reports.
- **Error Handling**: Enhanced the "Error loading report" view with diagnostic details (CORS advice, attempted paths).

Summary:
- Resolved critical layout regression regarding text alignment and whitespace.
- Verified data sources are correctly configured for Azure migration.
- Restored "Executive" density at 100% zoom.

Issues:
- Local browser view may still show "Error loading report" due to CORS on `file://` URIs; recommended checking via dev server or live deployment.

Next Steps:
- Merge changes to `main` to update the live GitHub Pages dashboard.
- Verify if real-time KPI counters are correctly aggregating Azure data in the production environment.
