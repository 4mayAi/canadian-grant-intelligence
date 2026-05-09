Date: 2026-05-09
Time: 08:37 AM
Title: Fix UI Parsing and Category Mapping

* Investigated why "cnst srv gd" and other acronyms were not being mapped correctly to human-readable category labels in the active tenders view.
* Discovered that raw category codes from the API often include a leading asterisk (e.g., "*CNST"). 
* Updated `getCategoryLabel` mapping function in `docs/index.html` to strip leading asterisks before performing the dictionary lookup, successfully translating these to user-friendly labels.
* Investigated missing analysis sections for May 7 and May 8.
* Found that the Markdown parsing logic in `docs/index.html` was rigidly expecting `### ` headers followed by `**Source:**` metadata, which caused the May 7th report (using `## ` headers) to be skipped entirely and replaced with the empty state "No Actionable Insights" message.
* Updated the Regular Expression in `renderReport` to match `^#{2,3}\s+(?=.*\n\*\*Source:\*\*)`, making the extraction resilient to both `##` and `###` header hierarchies.
* Used the browser subagent to verify the UI changes locally.
* Committed and pushed fixes to the main repository.

Summary:
- Updated category acronym mapper to handle asterisks in raw tender codes.
- Fixed the markdown splitting logic to reliably extract insights from both May 7th and May 8th reports regardless of header depth (`##` or `###`).
- Verified fixes locally through browser subagent simulation.

Issues:
- GitHub API latency: Updates to `index.html` and Markdown files might take a minute to reflect on the live GitHub Pages environment due to edge caching.

Next Steps:
- Continue monitoring the daily LLM generations to ensure formatting remains relatively stable.
- Verify email automation once credentials are fixed.
