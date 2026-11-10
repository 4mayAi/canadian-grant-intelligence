# Fix Canada Strong Fund Insight and Prompt Fidelity

Date: 2026-11-10
Time: 04:12 AM UTC (8:12 PM PST, Nov 9)
Title: Fix Canada Strong Fund Insight and Prompt Fidelity

## Session Content
- User flagged a hallucination/conflation in the daily briefing:
  The headline was "Prime Minister Carney announces Chief Executive Officer of the Canada Strong Fund" (appointing former Bridgewater Co-CIO Karen Karniol-Tambour as inaugural CEO), but the generated briefing stated "Prime Minister Mark Carney launches the $25B Canada Strong Fund...". The fund itself had been established prior.
- Investigated root cause:
  - In `get_gemini_insights_batch`, there was no explicit constraint preventing the model from conflating leadership appointments with fund/initiative launches.
  - In `generate_linkedin_post`, the executive summary aggregated the individual hook and propagated the claim that the fund was newly launched today.
- Implemented fixes:
  - Added topic-agnostic `CRITICAL EVENT FIDELITY & MILESTONES` constraint in `generic_engine/api/gemini_client.py` (`get_gemini_insights_batch` and `generate_linkedin_post`).
  - Added specific instruction in `configs/canadian_grants.json` to accurately distinguish leadership/governance appointments from fund inception.
  - Corrected `docs/data/canadian-grants/pmo_insights.json` (`linkedin_post` and the specific insight object for the PMO announcement).
  - Fixed `docs/index.html` data path to check `data/canadian-grants/` before falling back.
  - Added `scripts/sync_grants_data_to_azure.py` and `.github/workflows/sync_azure_data.yml` to synchronize corrected JSON to Azure Blob Storage.

Summary:
- Corrected Canada Strong Fund insight to accurately report the appointment of Karen Karniol-Tambour as CEO.
- Enforced prompt-level event fidelity constraints across the generic engine and topic configuration.
- Updated dashboard fallback paths and synchronized data.

Issues:
- Conflation of executive appointments with institutional launches in LLM output. Resolved with explicit negative constraints and data correction.

Next Steps:
- Commit and push changes to `origin/main`.
- Dispatch `sync_azure_data.yml` to synchronize Azure Blob Storage.
