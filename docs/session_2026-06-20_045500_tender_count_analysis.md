Date: 2026-06-20
Time: 04:55 AM UTC
Title: Tender Count Analysis and Verification

## Activities & Tasks
- Investigated the reason why only one tender is displayed on the AMR Simulation dashboard.
- Verified the CanadaBuys CKAN database search results by running a local verification script `scratch/test_tenders_match.py`.
- Identified that the crawler matched exactly two tenders from the active open tenders database:
  1. `RFQ - Xeon NAS and Seagate Exos (NRC)` (matched via the short keyword `NRC`)
  2. `Evaluation Services for the InnoVet-AMR 2.0 program` (matched via `AMR` / `InnoVet`)
- Inspected the processed URL registry `processed_urls.json` on Azure Storage and confirmed both URLs were ingested.
- Verified that `RFQ - Xeon NAS and Seagate Exos (NRC)` was discarded by the Gemini AI filter because it represents generic IT storage hardware and does not contain strategic value for Antimicrobial Resistance, bioinformatics, or virtual pathogen modeling.
- Analyzed the historical keyword collision issue: prior to implementing regex word boundaries and LLM relevancy gating, the system pulled in numerous false positives (e.g. mining tenders for "Alpha Metallurgical Resources" matching the abbreviation "AMR"). These false positives have now been properly excluded.

Summary:
- Conducted root-cause analysis of the tender count on the dashboard.
- Verified that only one high-fidelity AMR tender is active on CanadaBuys.
- Confirmed that generic IT hardware and mining-related keyword collisions are successfully filtered out.

Issues:
- None.

Next Steps:
- Report findings to the user and explain the clean, high-precision results on the dashboard.
