# Canadian Grant Intelligence Automator

An automated pipeline that monitors official Canadian government feeds (CanadaBuys, ISED, Finance Canada, PMO) for high-impact funding, stimulus, and RFP signals.

## Features
- **Multi-Feed Monitoring**: Aggregates data from four primary federal sources using `feedparser` (PMO) and headless Playwright (ISED, Global Affairs, Finance Canada) to bypass brittle legacy RSS endpoints.
- **AI Synthesis**: Uses Gemini 2.5 Flash Lite to generate B2B-focused LinkedIn hooks and co-bidding insights.
- **JSON-First Architecture**: Strictly-typed JSON payloads (`tenders.json`, `pmo_insights.json`) power a reactive, high-fidelity UI. Legacy Markdown parsing has been deprecated.
- **Azure Blob Storage**: Data is automatically synchronized and published to Azure for zero-persistence cloud delivery.

## Setup
1. **GitHub Secrets**: Add the following secrets to your repository:
   - `GEMINI_API_KEY`: Required for generating strategic intelligence insights.
   - `AZURE_STORAGE_CONNECTION_STRING`: Required for dashboard data persistence to Azure Blob Storage.
2. **Workflow**: The scraper runs automatically every morning via GitHub Actions but can be triggered manually.

## Structure
- `scripts/`: Contains the core Python logic (`fetch_canadian_grants.py`) using `asyncio` Playwright for fetching and synthesizing data.
- `docs/`: Contains the frontend web application (`index.html`, `app.js`, `style.css`) that consumes the Azure JSON endpoints.
- `reports/`: Maintains the legacy local generation logs.
- `.github/workflows/`: Configuration for the daily automation runner.
