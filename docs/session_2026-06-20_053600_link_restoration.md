Date: 2026-06-20
Time: 05:36 AM UTC
Title: Post-Processing Partner Link Restoration

## Activities & Tasks
- Identified that the LLM strips out raw markdown links when generating the co-bidding summary text.
- Formulated a robust post-processing replacement step in `generic_engine/main.py` using regular expressions.
- The step scans the scraped text (`text_to_search`) for any markdown links pointing to CanadaBuys `/en/node/preview/XXXXXX` and dynamically replaces plain-text occurrences in the LLM-generated `co_bidding_opportunity` field.
- Committed the changes and pushed to the repository.

Summary:
- Implemented deterministic partner link restoration in `generic_engine/main.py` to prevent LLM link stripping.
- Commited changes and prepared to re-trigger the GHA workflow.

Issues:
- None.

Next Steps:
- Push commits and re-trigger daily scraper pipeline to apply the changes.
