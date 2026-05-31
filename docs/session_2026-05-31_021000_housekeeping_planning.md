Date: 2026-05-31
Time: 02:10 AM UTC
Title: Landing Page Housekeeping & Social Card Integration Planning

## Activities and Tasks
- Analyzed the user request to clean up the landing page hook, re-purpose the KPI cards, clean up "LinkedIn/draft" references, and generate a social card image for the Canadian Innovation Clusters Intelligence dashboard.
- Researched existing social card generation code (`scripts/generate_social_card.py`, `scripts/templates/social_card.html`) and how it's integrated with the PMO News page.
- Created the implementation plan `implementation_plan.md` outlining changes to:
  - `generic_engine/api/gemini_client.py` (enforce hero hook length and formatting limits)
  - `generic_engine/main.py` (subprocess execution of the social card generator, dynamic top category extraction, and blob storage upload)
  - `docs/clusters/index.html` (rename tab buttons and card titles, implement client-side dynamic KPI calculation, and embed side-by-side executive digest card layout).
- Filed the implementation plan for user feedback and approval.

- Pushed changes, executed remote GHA builds, and verified that Pages is fully serving the dynamic fallback data.
- Refined GeminiClient.get_hero_hook to enforce a single-sentence Bloomberg-style hero hook (<20 words) with no markdown headers, lists, or bold formatting.
- Updated docs/clusters/index.html to dynamically compute all three KPIs in the browser, rename tabs/card titles, and implement side-by-side executive digest layout.
- Integrated playwright social card generation into main.py and verified it runs successfully locally and uploads to Azure.
- Added dynamic URL support to scripts/templates/social_card.html and scripts/generate_social_card.py, and updated generic_engine/main.py to clean and pass config.dashboard_url to the card generator, ensuring the URL printed on the card matches the clusters subdomain clusters path (4mayAi.github.io/canadian-grant-intelligence/clusters/).

Summary:
- Refactored hero hook generation, KPI calculation, and digest wording on the Innovation Clusters dashboard.
- Integrated automated Playwright-based social card image generation and side-by-side grid preview.
- Fixed social card URL branding on the card from the default grant scraper URL to the clusters path.
- Pushed final changes to the main branch.

Issues:
- Directory junction resolution during local dry-run resolved by passing absolute paths to python.exe.
- Corrected python f-string bracket escaping syntax error in generate_social_card.py by doubling JS brackets.

Next Steps:
- Trigger the GHA run to update the live social card image on Azure Blob storage and push the latest committed outputs.
