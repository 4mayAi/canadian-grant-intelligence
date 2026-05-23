Date: 2026-05-22
Time: 15:00 UTC
Title: RSS Feeds and Scraper Troubleshooting

Summary:
- Investigated the reason why ISED and Global Affairs feeds were not generating insights.
- Discovered that the previous URLs in `config.py` for ISED and Global Affairs were obsolete and returning 404s.
- Tested alternative native RSS endpoints for these departments, but confirmed Canada.ca does not expose department-level RSS feeds natively (they return 404/invalid XML).
- Validated that the Playwright scraper successfully scraped Finance Canada in the GitHub Actions environment, proving the Playwright architecture is sound.
- Identified that local Playwright testing is blocked by a Node.js `UNKNOWN: unknown error, read` exception caused by OneDrive directory junctions.
- Updated `config.py` to use the correct `advanced-news-search` endpoint URLs for ISED and Global Affairs.

Issues:
- Issue 1: ISED and Global Affairs URLs were broken.
- Issue 2: Local Playwright testing is completely broken due to a Node.js filesystem bug interacting with the user's OneDrive workspace.
- Issue 3: The underlying Canada.ca web architecture makes direct `urllib` / Python HTTP scraping fail or hang indefinitely due to anti-bot firewalls, necessitating the use of the Playwright headless browser.

Next Steps:
- Commit the updated `config.py` with the correct `advanced-news-search` URLs to GitHub.
- Let the GitHub Actions CI pipeline run the Playwright scraper in a clean, non-OneDrive environment where it has proven it can successfully scrape Canada.ca AEM pages.
