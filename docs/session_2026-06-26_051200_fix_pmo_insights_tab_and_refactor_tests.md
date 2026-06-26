Date: 2026-06-26
Time: 05:12 AM UTC
Title: Fix PMO News tab cross-browser bug, refactor test suites, and update strategic keywords

- Resumed work on the Canadian Grant Intelligence dashboard.
- Investigated the absence of PMO news releases in the dashboard. Identified the cause:
  - Cross-browser JavaScript ReferenceError in the `switchTab` function: it accessed the global `event` object without declaring it in the parameter list. In non-Chrome browsers like Firefox, this results in a ReferenceError, halting execution and causing the tab to fail to load/switch.
  - Double-filtering logic (the RSS crawler filters out PMO entries whose URLs do not contain `/news-releases/`, along with lookback and keyword filters) naturally filters out political or non-B2B news.
  - The generic engine is designed to merge both tenders and news releases through the same pipeline and strategically analyze them, resulting in tenders also populating the "PMO News & Insights" section.
- Fixed the cross-browser event bug in `docs/index.html` by passing `event` explicitly into `switchTab` and adding a robust ID-based fallback.
- Refactored `tests/test_dashboard.py` and `tests/test_scripts_client.py` to fix all deprecated package imports (replacing the old `src` structure with the correct `generic_engine` and local module references).
- Simplified mocking in `tests/test_dashboard.py` by using a module-level global `MagicMock` for the `azure_client` dependency, removing complex patch paths.
- Fixed `GeminiClient` instantiation and mock assertions in `tests/test_scripts_client.py` to match the refactored config-driven generic engine layout.
- Performed research on missing rallying keywords used by global leaders in news releases. Proposed and implemented the addition of 12 strategic B2B keywords (`resilience`, `prosperity`, `sovereignty`, `competitiveness`, `transition`, `partnership`, `collaboration`, `supply chain`, `net-zero`, `decarbonization`, `reconciliation`, `modernization`) in `configs/canadian_grants.json` to prevent discarding high-value PMO and ministerial announcements.
- Verified that all unit tests and standalone validation test scripts pass successfully.

Summary:
- Resolved the PMO News tab cross-browser navigation issue.
- Expanded the pre-filter keyword list with 12 strategic/rallying terms to improve PMO/ministerial news capture.
- Refactored the entire unit test suite to be green and aligned with the new Generic Engine layout.

Issues:
- None.

Next Steps:
- Commit and push all changes to GitHub using the OneDrive Snag bypass.
- Trigger the pipeline to run in GitHub Actions.
