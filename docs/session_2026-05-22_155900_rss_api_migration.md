Date: 2026-05-22
Time: 15:59 UTC
Title: RSS API Migration Session

Summary:
- Resolved the headless browser blocking issue on GitHub Actions by fully migrating the pipeline away from Playwright scraping.
- Replaced the DOM-based HTML scraping with lightweight XML fetching via `feedparser`.
- Identified and integrated the official backend `api.io.canada.ca` ATOM feeds for ISED and Finance Canada.
- Identified and integrated a strictly filtered Google News RSS proxy for Global Affairs Canada.
- Refactored `config.py` to move the three HTML_SOURCES into the FEEDS dictionary.
- Updated `rss.py` to support fallback to ATOM's `updated_parsed` dates if `published_parsed` is absent.
- Stripped the `fetch_html_news` calls from `main.py`, drastically reducing memory/CPU usage and resolving timeout/blocking issues.
- Pushed the changes to GitHub and triggered the `daily_grants_scraper.yml` workflow.

Issues:
- GitHub Actions runners (via Playwright headless mode) were getting hard-blocked by Canada.ca's Akamai Bot Manager, leading to missing insights.
- The official `/rss/` static endpoints for ISED, Finance, and Global Affairs were deprecated and returning 404s.

Next Steps:
- Monitor the triggered GitHub Actions workflow to ensure it successfully ingests and analyzes the new XML feeds.
- Verify the generated insights surface correctly on the dashboard.
