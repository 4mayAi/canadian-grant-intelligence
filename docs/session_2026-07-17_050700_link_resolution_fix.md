Date: 2026-07-17
Time: 05:07 AM UTC
Title: Link Resolution Fix

- Intercepted broken Ariba-imported tender URLs in `generic_engine/extractors/ckan.py` and modified the engine parser to construct a search URL query fallback (search_api_fulltext=solicitation_number) instead of the standard public notice URL.
- Ran a migration script (`scratch/migrate_links.py`) to backfill all 7 pre-existing Ariba-imported tenders in the `tenders.json` cache with the healed search query URLs.
- Ran the dry-run pipeline to verify that new crawls compile correctly with the new link-healing logic.
- Tested the healed search link (e.g. `https://canadabuys.canada.ca/en/tender-opportunities?search_api_fulltext=BPM026194/34239`) and confirmed it opens successfully.
- Cleaned up the scratch migration script.

Summary:
- Fully resolved the broken dashboard links for Ariba-imported opportunities by implementing a search redirect fallback in the parser and migrating the existing cache.

Issues:
- None.

Next Steps:
- Share the new healed links and explanation with the user.
