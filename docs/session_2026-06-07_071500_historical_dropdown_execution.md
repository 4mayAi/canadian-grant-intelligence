Date: 2026-06-07
Time: 07:15 AM UTC
Title: Mining Hubs Historical Archive Dropdown Execution

## Activities and Tasks
- Refactored `generic_engine/schema.py` and `configs/mining_hubs.json` to configure `"manifest_file": "manifest.json"`.
- Updated Python orchestrator `generic_engine/main.py` to compile the local `manifest.json` on each pipeline run and compile/upload the remote `manifest.json` to Azure Blob Storage container (`mining-hubs-data`).
- Refactored `docs/mining-hubs/index.html` to add the styled Archive selector dropdown element inside the header controls block.
- Updated `docs/mining-hubs/index.html` script to dynamically load the date manifest from Azure/local fallback, resolve date-scoped JSON report URLs, and re-fetch dashboard KPIs and insights upon archive date selection.
- Performed a local pipeline dry-run to verify schema compatibility and ensure manifest compilation compiles correctly.
- Updated `docs/architecture_arc42.md` architecture documentation to cover generic engine multi-topic layout, mining hubs diagram connections, and self-healing container bootstrap design decisions.

Summary:
- Refactored orchestrator storage upload phase to support compiling and uploading `manifest.json` for mining hubs and other topic configurations.
- Integrated Archive dropdown selector on the Global Mining Hubs frontend dashboard.
- Verified local manifest compilation and file generation.
- Added self-healing container bootstrapping checks in `AzureClient`.
- Updated arc42 architecture documentation.

Issues:
- None.

Next Steps:
- None. All tasks completed successfully.
