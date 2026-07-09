Date: 2026-07-09
Time: 05:10 AM UTC
Title: Fix LinkedIn Format Smushing

Describe the activities and tasks performed during the session:
- Investigated the reason why the LinkedIn/digest post summary was compiled into a single smushed paragraph.
- Found that the prompt instructions in `generic_engine/api/gemini_client.py` used a loose constraint: `- Do NOT use bullet points for the main body — use short paragraphs`.
- Refactored the prompt template to explicitly require separate paragraphs separated by blank lines (one paragraph per highlight event).
- Committed the changes and pushed them to `main`.

Summary:
- Hardened prompt constraints in `generic_engine/api/gemini_client.py` to enforce blank-line paragraph separation for LinkedIn digests.
- Pushed changes to `main`.

Issues:
- None.

Next Steps:
- None. The fix will be active on the next pipeline execution.
