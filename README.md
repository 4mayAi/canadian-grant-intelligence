# Canadian Grant Intelligence Automator

An automated pipeline that monitors official Canadian government feeds (CanadaBuys, ISED, Finance Canada, PMO) for high-impact funding, stimulus, and RFP signals.

## Features
- **Multi-Feed Monitoring**: Aggregates data from four primary federal sources (PMO, ISED, Finance Canada, Global Affairs Canada) using `feedparser` to retrieve raw XML/Atom feeds, avoiding headless browser blocking.
- **AI Synthesis**: Uses Google Gemini API (primarily `gemini-2.5-flash-lite`, with automatic waterfall fallback to `gemini-3.1-flash-lite` and `gemini-1.5-flash`) to generate B2B-focused LinkedIn hooks, co-bidding insights, and newsletter content.
- **JSON-First Architecture**: Strictly-typed JSON payloads (`tenders.json`, `pmo_insights.json`, `kpis.json`) power a reactive, high-fidelity UI. Legacy Markdown parsing has been deprecated.
- **Azure Blob Storage**: Data is automatically synchronized and published to Azure for zero-persistence cloud delivery.

## Deployment & Secrets Setup

To run the pipeline and the CI/CD deployment, configure the following secrets in your GitHub repository:

### 1. Pipeline Execution Secrets
These secrets drive the daily scraper pipeline executed via GitHub Actions (`daily_grants_scraper.yml`):
- `GEMINI_API_KEY`: Required for generating strategic intelligence insights.
- `AZURE_STORAGE_CONNECTION_STRING`: Required for dashboard data persistence to Azure Blob Storage.
- `EMAIL_ADDRESS` / `EMAIL_APP_PASSWORD`: SMTP credentials for daily digest mail dispatch.
- `DISCORD_WEBHOOK_URL` (Optional): Target webhook URL for failure alerts.
- `ALERT_EMAIL_ADDRESS` (Optional): Notification recipient email address for system alerts.

### 2. CI/CD & Container Deployment Secrets
These secrets drive the container build-and-deploy pipeline targeting Azure Container Apps (`deploy_container.yml`):
- `AZURE_CREDENTIALS`: Azure Service Principal credentials for authentication.
- `ACR_REGISTRY` / `ACR_USERNAME` / `ACR_PASSWORD`: Azure Container Registry credentials.
- `ACA_JOB_NAME`: Name of the target Azure Container App Job.
- `AZURE_RESOURCE_GROUP`: Target resource group name.

## Environment & Run Configuration
The following environment variables can be configured to customize execution:
- `EMAIL_SMTP_SERVER` / `EMAIL_SMTP_PORT`: Defaults to `smtp.gmail.com` and `465` respectively.
- `RUN_TYPE`: Set to `test` for dry runs or `seed_strategy` to seed initial values. Defaults to `DEEP_DIVE`.
- `SCRAPE_LOOKBACK_DAYS`: Number of days of historical entries to fetch. Defaults to `7`.
- `STALE_THRESHOLD_SECONDS`: Custom age threshold (in seconds) for validation freshness. Defaults to `7200` (2 hours).

## Testing

Run the automated test suite locally to verify schema validation, email notifier flows, and subscribers distribution logic. 

**Recommended Command (Dot Notation)**:
```powershell
python -m unittest tests.test_dashboard tests.test_consolidation_and_provinces tests.test_date_and_hooks
```

**Alternative Command (Explicit Absolute Paths)**:
If you run into environment path resolution issues (e.g., due to OneDrive sync junctions), execute using absolute paths to python and test files:
```powershell
c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\tests\test_dashboard.py
```

## Structure
- `scripts/src/`: Core Python pipeline orchestrator (`main.py`) and external API integration wrappers (`api/`).
- `docs/`: React-inspired static frontend (`index.html`) featuring historical dates selection via a date dropdown.
- `tests/`: Automated unit and integration test suite (`test_dashboard.py`, `test_consolidation_and_provinces.py`, `test_date_and_hooks.py`).
- `.github/workflows/`: CI/CD and pipeline automation workflows:
  - `daily_grants_scraper.yml`: Main scheduled intelligence pipeline (3x daily).
  - `deploy_container.yml`: Deployment job targeting ACA.
