# Session Log: Regional Hub Quota Enforcement (`max_items_per_hub`)

Date: 2026-08-12
Time: 05:46 PM UTC
Title: Implementation Session — Per-Hub Quota Enforcement for Regional Balance

## Session Content
- Identified root cause of thematic dominance on the dashboard: `max_items_per_source` allowed hubs with 4–6 feeds (e.g. Africa or Canada) to capture up to 16–24 items, while hubs with 1–2 feeds (e.g. China or Switzerland) were limited to 4–8 items.
- Added `max_items_per_hub: Optional[int] = None` to `PipelineConfig` in `generic_engine/schema.py`.
- Added `hub: Optional[str] = None` to `SourceConfig` in `generic_engine/schema.py`.
- Implemented `get_hub_for_source(source_name, sources_config)` helper in `generic_engine/main.py` for deterministic hub budget resolution.
- Re-architected `generic_engine/main.py` post-processing to sort candidate insights chronologically and apply combined `src_ok` and `hub_ok` capping *before* `featured_insights` selection and LinkedIn newsletter synthesis, preventing desynchronization between summary text and dashboard items.
- Configured `"max_items_per_hub": 5` in `configs/mining_hubs.json` and explicitly labeled all 20 feeds with their target hub (`Canada`, `Australia`, `China`, `Switzerland`, `Africa`, `Global`).
- Executed `scripts/validate_skill.py` (ALL CHECKS PASSED) and `scratch/audit_arc42.py` (100% Alignment).

## Summary
- Regional hub quota enforcement implemented and validated. Every hub is now capped at $\le 5$ top insights per digest run.

## Next Steps
- Stage, commit, and push changes to `main`.
- Trigger live workflow run on GitHub Actions (`Global Mining Hubs Intelligence Pipeline`).
