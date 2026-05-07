# Canadian Grant Intelligence Automator

An automated pipeline that monitors official Canadian government feeds (CanadaBuys, ISED, Finance Canada, PMO) for high-impact funding, stimulus, and RFP signals. 

## Features
- **Multi-Feed Monitoring**: Aggregates data from four primary federal sources.
- **AI Synthesis**: Uses Gemini 1.5 Flash to generate B2B-focused LinkedIn hooks and co-bidding insights.
- **Daily Automation**: Runs daily at 8:00 AM UTC via GitHub Actions.
- **Audit History**: Stores all daily reports in the `reports/grants/` directory.

## Setup
1. **GitHub Secret**: Add your Gemini API key as a Repository Secret named `GEMINI_API_KEY`.
2. **Workflow**: The scraper will run automatically every morning, but you can also trigger it manually from the "Actions" tab.

## Structure
- `scripts/`: Contains the core logic for fetching and synthesizing data.
- `reports/grants/`: Daily intelligence reports in Markdown format.
- `.github/workflows/`: Configuration for the daily automation runner.
