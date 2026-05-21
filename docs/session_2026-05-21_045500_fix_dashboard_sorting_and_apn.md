Date: 2026-05-21
Time: 04:55 AM UTC
Title: Fixing Dashboard Sorting and APN Filter

## Activities and Tasks
- **APN Filtering Fix**: Investigated the matching issue for `APN_EDMONTON` tenders. Determined that the regex word boundaries (`\b`) fail on underscores (`_`) because underscores are counted as word characters (`\w`). Added `.replace('_', ' ')` to `text_to_search` in `scripts/src/extractors/ckan.py`.
- **Chronological Sorting Fix**: Investigated the incorrect "Newest First" ordering. Discovered that the sort logic inside `docs/index.html` returned `0` when comparing two tenders of the same status (e.g. both `Open` or both `New`), resulting in arbitrary ordering. Rewrote the sorting algorithm to compare publication dates descending.
- **Testing**: Added `test_canadabuys_apn_exclusion` in `tests/test_dashboard.py` to ensure that both space-separated and underscore-prefixed APN notices are filtered out. Ran the test suite successfully (all 10 tests passed).
- **Git Push**: Staged, committed, and pushed the updates to the main branch.

Summary:
- Implemented and verified the underscore-friendly APN exclusion filter.
- Fixed the newest-first sorting algorithm to use publication dates.
- Verified test suite pass status (10/10 OK).

Issues:
- None.

Next Steps:
- Allow the scheduled pipeline run to update the data files and verify sorting order visually.
