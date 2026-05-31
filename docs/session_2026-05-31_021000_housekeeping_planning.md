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

Summary:
- Refactored hero hook generation, KPI calculation, and digest wording on the Innovation Clusters dashboard.
- Integrated automated Playwright-based social card image generation and side-by-side grid preview.
- Pushed final changes to the main branch.

Issues:
- Directory junction resolution during local dry-run resolved by passing absolute paths to python.exe.

Next Steps:
- Monitor the daily GHA scraper run to confirm that the live page displays the visual card and cleaned KPIs correctly on subsequent updates.
