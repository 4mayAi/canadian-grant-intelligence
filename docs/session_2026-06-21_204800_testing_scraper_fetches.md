Date: 2026-06-21
Time: 08:48 PM UTC
Title: Testing Scraper Fetches, Integrating NRCan, and Optimizing Queries

Session Content:
- Tested the proposed Google News RSS queries using Python scratch scripts.
- Found that name-based queries like `"Fisheries and Oceans Canada" OR "DFO" OR "Canadian Coast Guard" ocean` missed the target June 8, 2026 announcement: "Our Ocean Conference in spring 2027" because the indexed title and snippet lacked the exact department phrase in the search index.
- Discovered that using `site:.../news` subpaths of the departments on `canada.ca` is extremely precise, filters out general/administrative noise (such as course enrolment, air cadet notices, building codes, and product assessments), and captures all news releases directly.
- Tested and integrated **Natural Resources Canada (NRCan)** via `site:canada.ca/en/natural-resources-canada/news` to capture critical energy and mining releases (e.g., nuclear energy announcements, solar projects, geothermal roadmap, energy infrastructure).
- Optimized queries for all five clusters:
  1. DIGITAL (ISED): `site:ised-isde.canada.ca` with digital/AI keywords.
  2. Scale AI (Transport Canada): `site:canada.ca/en/transport-canada/news` with supply chain/logistics keywords.
  3. Ocean (DFO & NRCan): Combined DFO and NRCan news subpaths (`site:canada.ca/en/fisheries-oceans/news OR site:canada.ca/en/natural-resources-canada/news`) with ocean/marine/clean-energy keywords.
  4. NGen (NRC, DND, & NRCan): Combined NRC, DND, and NRCan news subpaths (`site:canada.ca/en/national-research-council/news OR site:canada.ca/en/department-national-defence/news OR site:canada.ca/en/natural-resources-canada/news`) with advanced manufacturing/aerospace/defence/critical-minerals keywords. This avoids CCMC building code registry spam while capturing aerospace and clean energy policy announcements.
  5. Protein Industries (AAFC): `site:canada.ca/en/agriculture-agri-food/news` with plant-protein/agri-food keywords.
- Updated `implementation_plan.md` to incorporate these optimized, high-precision search queries and optimized `Canada_NRCan_News` in `mining_hubs.json`.

Summary:
- Validated all scraper fetches and successfully optimized them to capture the target June 8, 2026 DFO conference announcement.
- Integrated Natural Resources Canada (NRCan) as a federal news source for clean energy, critical minerals, and green mining.
- Updated the implementation plan with these optimized queries and requested user feedback.

Issues:
- None.

Next Steps:
- Obtain user approval on the implementation plan.
- Update `innovation_clusters.json` and `mining_hubs.json` configurations.
- Run local dry run and verify parsing.
- Commit and deploy the configurations.
