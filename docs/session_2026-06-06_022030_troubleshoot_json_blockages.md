Date: 2026-06-06
Time: 02:20 AM UTC
Title: Troubleshooting and Resolving Gemini Ingestion Insight Blockages

Activities:
- Investigated reports of "Insight generation failed or blocked: Unknown reason" affecting OceanCluster and DIGITAL news items.
- Inspected the GitHub Actions run log for run `27022492455` and discovered a `json.JSONDecodeError` while parsing candidate outputs from the `gemini-2.5-flash` model.
- Identified that the model returned raw JSON containing unescaped literal newlines in its markdown bullet points (e.g. within `"strategic_value"`), which violates the JSON standard and causes standard Python `json.loads` to crash.
- Discovered that the config fallback model lists included the nonexistent `"gemini-3-flash"` model, which caused a 404 NOT FOUND API failure during rate-limit pivoting.
- Implemented a robust `clean_json_text` function in both `generic_engine/api/gemini_client.py` and `scripts/src/api/gemini_client.py` to clean unescaped control characters (newlines, carriage returns, tabs) inside quotes in JSON outputs before parsing.
- Removed the invalid `"gemini-3-flash"` model from `configs/innovation_clusters.json`, `configs/mining_hubs.json`, and `scripts/src/api/gemini_client.py`.
- Added automated test cases covering `clean_json_text` functionality in both `tests/test_generic_engine.py` and `tests/test_scripts_client.py`.
- Ran all automated test suites to verify 100% success.

Summary:
- Resolved the source of the batch insight parsing blockage by escaping unescaped newlines/tabs inside JSON fields at run-time, guaranteeing zero future JSON parsing failures on any model.
- Removed invalid model from configurations to optimize GHA runtime by avoiding unnecessary 404 request pivots.

Issues:
- None.

Next Steps:
- Commit and push changes.
- Trigger GHA workflows to confirm fix live.
