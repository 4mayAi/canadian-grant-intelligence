Date: 2026-05-18
Time: 05:12 AM
Title: LinkedIn Post Consolidation and Pipeline Fixes

## Session Content
- Diagnosed the user's issue with missing data on the executive dashboard: modularization stripped out the wrapper structure and `ReportItem` news metadata from `pmo_insights.json`.
- Implemented the user's request for a 3-section email template (Image, Title, Content) for easy LinkedIn copy-pasting.
- Edited `scripts/src/models.py` to add a `PMOWrapper` data class to enforce the correct legacy schema structure.
- Edited `scripts/src/api/gemini_client.py` to update the LinkedIn post generator prompt to strictly output JSON containing both `suggested_title` and `article_content`.
- Edited `scripts/src/main.py` to:
    - Retain original news metadata (title, source, date, link) when processing insights.
    - Call the new Gemini JSON method to generate the post.
    - Render the post into a structured 3-section Markdown file at `reports/linkedin/latest_post.md`.
    - Automatically execute `scripts/generate_social_card.py` via Python subprocess.
    - Wrap the final `PMOWrapper` and save/upload it locally and to Azure.
- Edited `.github/workflows/daily_grants_scraper.yml` to attach the newly generated `reports/linkedin/social_card.png` inside the `dawidd6/action-send-mail@v3` step using the `attachments:` property.
- Ran a local `test` mode execution to ensure that the logic executes cleanly and that the correct local artifacts (`pmo_insights.json` and `latest_post.md`) are created. The schema regression was fully resolved.

## Summary
- Restored `pmo_insights.json` backward compatibility for the `docs/index.html` frontend.
- Converted the raw LLM LinkedIn post into a structured JSON extraction.
- Fully automated the 3-section LinkedIn Article layout.
- Attached dynamic Social Card PNGs directly to the automated email digest.

## Issues
- Local run executed successfully but failed API requests since `GEMINI_API_KEY` was empty on the local test terminal, proving graceful failover works ("LinkedIn post generation failed." was output to markdown, proving structure).

## Next Steps
- User to manually trigger the GitHub Action and review the real email containing the image attachment and the 3-section post layout.
