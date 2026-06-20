Date: 2026-06-20
Time: 05:28 AM UTC
Title: Formatting Partner Links as Markdown

## Activities & Tasks
- Investigated the CanadaBuys partnering list structure and verified that company profiles are links pointing to `/en/node/preview/XXXXXX`.
- Modified `generic_engine/extractors/report_scraper.py` to pre-process the DOM in Playwright before extracting inner text, replacing partner links with their markdown representation: `[Company Name](https://canadabuys.canada.ca/en/node/preview/XXXXXX)`.
- Verified that the local scraper now extracts text containing these formatted markdown links.
- Created `scratch/reprocess_innovet_tender.py` to clear the InnoVet tender from Azure Storage cache files (`amr_insights.json` and `processed_urls.json`) to force re-evaluation.
- Injected the cache-clearing step into the GitHub Actions workflow `.github/workflows/daily_amr_simulation_scraper.yml` temporarily.

Summary:
- Pre-processed page anchors to retain co-bidder profile links in scraped text.
- Formulated a temporary workflow cache-clearing step to force re-evaluation in the cloud.

Issues:
- None.

Next Steps:
- Commit and push changes to trigger the cloud scraper run.
