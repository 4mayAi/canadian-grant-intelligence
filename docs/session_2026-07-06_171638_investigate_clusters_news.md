# Session Log

Date: 2026-07-06
Time: 5:16 PM UTC
Title: Investigation of Innovation Clusters News Ingestion Freshness

## Activities and Tasks
* Investigated why the clusters digest and signals have not shown more recent news since June 26, 2026.
* Inspected the local configuration file [innovation_clusters.json](file:///c:/dev/canadian-grant-intelligence/configs/innovation_clusters.json) to understand ingestion sources and keyword settings.
* Created a scratch script [check_feeds.py](file:///c:/dev/canadian-grant-intelligence/scratch/check_feeds.py) to check the live RSS/Atom feeds and fallbacks.
* Executed the news feed check and generated [feeds_status.json](file:///c:/dev/canadian-grant-intelligence/scratch/feeds_status.json) to analyze publishing dates for each source.
* Run a pipeline dry-run to check for execution log outputs and verify the ingestion pipeline behaviour.
* Created a simulation script [simulate_run.py](file:///c:/dev/canadian-grant-intelligence/scratch/simulate_run.py) to trace which fetched items pass or fail the pre-filter.
* Identified that major announcements from first-party cluster news portals (such as Protein Industries Canada and DIGITAL) and ecosystem news were discarded early by the pre-filter due to keyword mismatches (e.g., titles not containing exact words like "funding", "grant", "consortium", etc., despite being highly relevant project announcements).
* Investigated the trade-offs of limiting ingestion sources strictly to first-party cluster sites (removing ecosystem and federal feeds) to eliminate keyword constraints.
* Analyzed the impact on data completeness (losing federal policy alerts and ecosystem partner press releases).
* Implemented the Option 1 schema and logic changes locally (updated [schema.py](file:///c:/dev/canadian-grant-intelligence/generic_engine/schema.py), [main.py](file:///c:/dev/canadian-grant-intelligence/generic_engine/main.py), and [innovation_clusters.json](file:///c:/dev/canadian-grant-intelligence/configs/innovation_clusters.json)).
* Executed [simulate_run.py](file:///c:/dev/canadian-grant-intelligence/scratch/simulate_run.py) to verify the new filter bypass results.
* Fixed a missing GHA dependency issue by making the `dotenv` import optional and safe in [main.py](file:///c:/dev/canadian-grant-intelligence/generic_engine/main.py), and adding `python-dotenv` to [requirements.txt](file:///c:/dev/canadian-grant-intelligence/requirements.txt).

## Summary of Work Completed
- Documented why keyword pre-filtering was implemented (cost, rate-limiting, noise suppression).
- Formulated two concrete remediation options (expanding keywords vs. implementing a `skip_keyword_filter` schema flag).
- Assessed the feasibility and trade-offs of a first-party-only architecture.
- Successfully implemented and verified Option 1 (Hybrid Selective Bypass), capturing all previously discarded direct cluster announcements (including DIGITAL CEO changes and the Protein Industries Canada AI fermentation project) while keeping ecosystem and federal coverage fully intact.

## Issues
- None. The Option 1 bypass logic resolves the pre-filter keyword constraints for direct cluster feeds while maintaining targeted filters for noisy search feeds.

## Next Steps
- Present the verified Option 1 outputs to the user.
- Await confirmation to push these tested files to git/production.

