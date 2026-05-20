# Canadian Grant Intelligence Automator

An automated pipeline that monitors official Canadian government feeds (CanadaBuys, ISED, Finance Canada, PMO) for high-impact funding, stimulus, and RFP signals.

## Features
- **Multi-Feed Monitoring**: Aggregates data from four primary federal sources using `feedparser` (PMO) and headless Playwright (ISED, Global Affairs, Finance Canada) to bypass brittle legacy RSS endpoints.
- **AI Synthesis**: Uses Gemini 2.5 Flash Lite to generate B2B-focused LinkedIn hooks and co-bidding insights.
- **JSON-First Architecture**: Strictly-typed JSON payloads (`tenders.json`, `pmo_insights.json`) power a reactive, high-fidelity UI. Legacy Markdown parsing has been deprecated.
- **Azure Blob Storage**: Data is automatically synchronized and published to Azure for zero-persistence cloud delivery.

## Deployment & Container Setup
1. **GitHub Secrets**: Add the following secrets to your repository to drive the CI/CD pipeline:
   - `AZURE_CREDENTIALS`: Azure Service Principal credentials for authentication.
   - `ACR_REGISTRY` / `ACR_USERNAME` / `ACR_PASSWORD`: Azure Container Registry credentials.
   - `ACA_JOB_NAME`: Name of the target Azure Container App Job.
   - `AZURE_RESOURCE_GROUP`: Target resource group name.

2. **Container Runtime Configuration**: Ensure the following environment variables are configured on the Azure Container App Job:
   - `GEMINI_API_KEY`: Required for generating strategic intelligence insights.
   - `AZURE_STORAGE_CONNECTION_STRING`: Required for dashboard data persistence to Azure Blob Storage.
   - `DISCORD_WEBHOOK_URL` (Optional): Target webhook URL for failure alerts.
   - `ALERT_EMAIL_ADDRESS` (Optional): Notification recipient email address for system alerts.
   - `EMAIL_ADDRESS` / `EMAIL_APP_PASSWORD`: SMTP credentials for daily digest mail dispatch.
   - `EMAIL_SMTP_SERVER` / `EMAIL_SMTP_PORT`: Defaults to `smtp.gmail.com` and `465` respectively.
   - `RUN_TYPE` (Optional): Set to `test` for dry runs or `seed_strategy` to seed initial values.
   - `STALE_THRESHOLD_SECONDS` (Optional): Custom age threshold (in seconds) for validation freshness. Defaults to `7200` (2 hours).

## Testing
Run the automated test suite locally to verify schema validation, email notifier flows, and subscribers distribution logic:
```powershell
.\.venv_new\Scripts\python.exe tests/test_dashboard.py
```

## Structure
- `scripts/src/`: Core Python pipeline orchestrator (`main.py`) and external API integration wrappers (`api/`).
- `docs/`: React-inspired static frontend (`index.html`) featuring historical dates selection via a date dropdown.
- `tests/`: Automated unit and integration test suite (`test_dashboard.py`).
- `.github/workflows/`: CI/CD automation workflow (`deploy_container.yml`) for container build-and-deploy targeting ACA.
