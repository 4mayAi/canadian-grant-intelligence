# Systemic Anti-Brittle Remediation & Rule Learning Session

Date: 2026-11-11
Time: 02:51 AM UTC (7:51 PM MST, Nov 10)
Title: Systemic Anti-Brittle Remediation & Rule Learning

## Session Content
- Reviewed root causes of recent Canada Strong Fund insight conflation and brittle remediation patterns via `/learn`.
- Updated `.agents/AGENTS.md`:
  - Removed duplicated 120-line header section.
  - Replaced `Pipeline Filter Changes Cache Side-Effect Resolution` with `Pipeline Cache & Rerun Invalidation Rule`, documenting both `processed_urls.json` and `<insights_file>` (`existing_insights_map`).
  - Expanded `Shared Engine Topic Isolation and Prompt Leakage Prevention Rule` into `Shared Engine Topic Isolation and Anti-Brittle Remediation Rule`, prohibiting entity-specific prompt patches ("whack-a-mole"), manual JSON output editing, and ad-hoc sync workflows.
- Cleaned `configs/canadian_grants.json` to remove the entity-specific `"Canada Strong Fund"` reference in `system_instruction` in favor of a structural governance/operational milestone instruction.
- Removed ad-hoc `.github/workflows/sync_azure_data.yml` and `scripts/sync_grants_data_to_azure.py`.
- Created centralized, reusable `scripts/validators/invalidate_cached_urls.py` utility and wired `pre_run_script` input forwarding in `.github/workflows/daily_grants_scraper.yml`.

Summary:
- Codified anti-brittle engineering and two-tier cache invalidation rules in `.agents/AGENTS.md`.
- Replaced brittle entity-specific config text and one-off sync scripts with a reusable cache-invalidation validator (`scripts/validators/invalidate_cached_urls.py`).

Issues:
- None.

Next Steps:
- Use `scripts/validators/invalidate_cached_urls.py` via `pre_run_script` whenever re-evaluating cached items across any pipeline.
