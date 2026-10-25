# Architectural Review & Phased Remediation Plan: `arc42` Documentation Suite

## Goal Description
Bring the `canadian-grant-intelligence` `arc42` documentation suite to **100% empirical parity** with the active codebase (`generic_engine/`) and pipeline configurations (`configs/*.json`), while respecting your architectural boundaries:
1. **Manageable Work Breakdown**: Split the updates into **4 small, self-contained Pieces (Phases)** that can be executed and verified incrementally.
2. **Preserve Standalone Scope**: Keep [arc42_future_skills_evaluation_engine.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture/arc42_future_skills_evaluation_engine.md) as a standalone 12-section `arc42` document for the ESDC solicitation (`#100032488`), and preserve the established **Sections 1–10** (*Introduction* through *Skills Registry Governance*) structure across the core `generic_engine` platform documents without forcing Sections 11–12 onto them.
3. **Keep File Paths Intact**: Maintain all existing `docs/architecture_arc42*.md` file locations to preserve historical session log links, and add a central **Architecture Documentation Index** table to [architecture_arc42.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42.md) linking all 9 documents.

---

## Summary of Empirical Discrepancies to Remediate

| Discrepancy Category | Empirical Evidence from Codebase | Affected `arc42` Documents |
| :--- | :--- | :--- |
| **1. 28 Undocumented Config Sources** | `configs/*.json` contain 103 total sources across 6 pipelines, but only 75 are listed in the docs (`canadian_grants`: 8/13; `amr_simulation`: 7/8; `innovation_clusters`: 14/27; `global_payments`: 9/13; `trade_compliance`: 12/17; `mining_hubs`: 25/25). | `grants`, `amr_simulation`, `clusters`, `payments`, `trade_compliance`, plus `architecture_arc42.md` & `arc42_and_dashboard_fidelity_audit.md` |
| **2. 5 Undocumented `generic_engine/` Modules** | Section 5.1 Building Block trees omit [`api/profile_matcher.py`](file:///c:/dev/canadian-grant-intelligence/generic_engine/api/profile_matcher.py), [`extractors/bdlnow.py`](file:///c:/dev/canadian-grant-intelligence/generic_engine/extractors/bdlnow.py), [`extractors/cta_marine.py`](file:///c:/dev/canadian-grant-intelligence/generic_engine/extractors/cta_marine.py), [`extractors/esdc_lmia.py`](file:///c:/dev/canadian-grant-intelligence/generic_engine/extractors/esdc_lmia.py), and [`extractors/ised_newsletter.py`](file:///c:/dev/canadian-grant-intelligence/generic_engine/extractors/ised_newsletter.py). | All 7 core `architecture_arc42*.md` documents |
| **3. LLM Fallback Chain Drift** | All 6 `configs/*.json` files specify `"model_fallbacks": ["gemini-flash-lite-latest", "gemini-3.8-flash", "gemini-3.7-flash", "gemma-4-31b-it"]`, whereas the 7 core `arc42` docs still list deprecated `gemini-3.5-flash-lite`. | All 7 core `architecture_arc42*.md` documents |
| **4. Stale Claims & Copy-Paste Typos** | • [architecture_arc42_grants.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_grants.md#L119) states `grants_anchors.json` is `(currently empty)`, but [grants_anchors.json](file:///c:/dev/canadian-grant-intelligence/configs/grants_anchors.json) holds 7 curated anchors.<br>• [architecture_arc42_amr_simulation.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_amr_simulation.md#L112) calls `amr_anchors.json` *"payment anchors"*.<br>• [architecture_arc42_trade_compliance.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_trade_compliance.md) is missing Section 10 (*Skills Registry Governance*). | `grants`, `amr_simulation`, `trade_compliance`, `architecture_arc42.md` |

---

## Phased Execution Plan (4 Manageable Pieces)

### Piece 1: Master Platform Architecture & Fidelity Audit (`2 files`)
Establish the top-level index and synchronize the shared `generic_engine/` building blocks.

#### [MODIFY] [architecture_arc42.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42.md)
- **Add Architecture Documentation Index Table** (Section 1.4): Link all 9 `arc42` documents in the repository (the Master doc, the 6 core Skill pipeline docs, the standalone [arc42_future_skills_evaluation_engine.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture/arc42_future_skills_evaluation_engine.md), and the archived [architecture_arc42_retired.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_retired.md)) without moving any files.
- **Update Section 1.1 & Section 3**: Update source counts (e.g., 17 operational feeds for Trade Compliance) and include the newly integrated extractors in the System Context diagram.
- **Update Section 5.1 (`generic_engine/` Directory Tree)**:
  ```text
  generic_engine/
  ├── main.py                    # Orchestrates extraction, analysis, validation, and upload
  ├── schema.py                  # Pydantic V2 schemas validating configs (PipelineConfig)
  ├── models.py                  # Dataclass schemas for Tenders, Insights, and KPIs
  ├── extractors/
  │   ├── bdlnow.py              # Chamber of Commerce BDL Nowcast macroeconomic indicator scraper
  │   ├── ckan.py                # Interacts with CanadaBuys CKAN API for CSV files
  │   ├── cta_marine.py          # CTA coasting trade and marine vessel notice extractor
  │   ├── esdc_lmia.py           # Open Government CKAN Positive LMIA dataset extractor
  │   ├── ised_newsletter.py     # ISED GC Business Insights newsletter scraper
  │   ├── playwright_scraper.py  # Headless browser crawler for JS-rendered news feeds
  │   ├── report_scraper.py      # Parses PDFs and documents for slow-moving anchors
  │   ├── rss.py                 # Fetches and parses RSS/Atom feeds with dynamic keyword parameters
  │   └── youtube.py             # Scrapes YouTube channel videos tab
  └── api/
      ├── azure_client.py        # Wrapper for Azure Blob Storage with auto-bootstrap checks
      ├── gemini_client.py       # Batch querying wrapper for Gemini LLM cascade
      ├── notifier.py            # Failure notification and HTML digest SMTP mailer (Discord + Email)
      └── profile_matcher.py     # Profile-aware B2B lead alert and co-bidding matcher
  ```
- **Reconcile Section 6, 7 & 9**: Align trigger descriptions with GCP Cloud Scheduler / [`scripts/dispatch_all_pipelines.py`](file:///c:/dev/canadian-grant-intelligence/scripts/dispatch_all_pipelines.py), replace deprecated `validate_outputs.py` references with [`scripts/validators/validate_output.py`](file:///c:/dev/canadian-grant-intelligence/scripts/validators/validate_output.py), and update the fallback model waterfall to `gemini-flash-lite-latest` $\rightarrow$ `gemini-3.8-flash` $\rightarrow$ `gemini-3.7-flash` $\rightarrow$ `gemma-4-31b-it`.

#### [MODIFY] [arc42_and_dashboard_fidelity_audit.md](file:///c:/dev/canadian-grant-intelligence/docs/arc42_and_dashboard_fidelity_audit.md)
- Update Section 1 table source counts (`canadian-grants`: 13, `amr-simulation`: 8, `innovation-clusters`: 27, `payments`: 13, `mining-hubs`: 25, `trade-compliance`: 17) and add a note referencing the standalone Future Skills dashboard (`/future-skills/`).

---

### Piece 2: Canadian Procurement & Domestic Pipelines (`3 files`)
Synchronize the 3 federal/domestic procurement and regulatory pipelines (`Grants`, `AMR Simulation`, `Trade Compliance`).

#### [MODIFY] [architecture_arc42_grants.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_grants.md)
- **Section 5.1**: Add `bdlnow.py`, `cta_marine.py`, `ised_newsletter.py`, `profile_matcher.py`, and `configs/subscriber_profiles.json`; update `grants_anchors.json` comment from `(currently empty)` to `# Local seed database with 7 statutory telecom, privacy & corridor anchors`.
- **Section 5.2**: Update fallback chain (`gemini-3.7-flash`) and add the **5 missing sources** from [canadian_grants.json](file:///c:/dev/canadian-grant-intelligence/configs/canadian_grants.json):
  - `ISED_GC_Business_Insights` (`ised_newsletter` scraper)
  - `BDLNow_Economic_Indicator` (`bdl_nowcast` macroeconomic indicator scraper)
  - `CTA_Coasting_Trade_Notices` (`cta_marine` API extractor)
  - `CRTC_Telecom_Decisions_News` (GC News API Atom feed)
  - `IAAC_Major_Project_Notices` (IAAC RSS feed)

#### [MODIFY] [architecture_arc42_amr_simulation.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_amr_simulation.md)
- **Section 3**: Expand the Mermaid System Context diagram to include `Canada_HealthCanada_MedTech`, `bioRxiv_Microbiology`, `Canada_PHAC_Public_Health_Updates`, and `Canada_PHAC_CCDR`.
- **Section 5.1**: Fix line 112 typo (`slow-moving payment anchors` $\rightarrow$ `slow-moving biotech and AMR policy anchors`).
- **Section 5.2**: Update fallback chain (`gemini-3.7-flash`) and add the **1 missing source** from [amr_simulation.json](file:///c:/dev/canadian-grant-intelligence/configs/amr_simulation.json):
  - `Canada_HealthCanada_MedTech` (Health Canada Medical Devices, Drug & Laboratory Compliance Feed)

#### [MODIFY] [architecture_arc42_trade_compliance.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_trade_compliance.md)
- **Section 1.1, 3, 5.1, 5.2 & 6.1**: Update source count from 12 to **17 sources**, add `cta_marine.py` and `esdc_lmia.py` to Section 5.1, update fallback chain (`gemini-3.7-flash`), and list the **5 missing sources** from [trade_compliance.json](file:///c:/dev/canadian-grant-intelligence/configs/trade_compliance.json):
  - `CTA_Coasting_Trade_Notices` (`cta_marine` vessel application API)
  - `ISED_ICA_Investment_News` (GC News API Atom — Investment Canada Act notifications)
  - `CRTC_Telecom_Decisions_News` (GC News API Atom — Telecom regulatory notices)
  - `ESDC_LMIA_Positive_Approvals` (`esdc_lmia` Open Government CKAN dataset)
  - `IAAC_Major_Project_Notices` (Google News RSS proxy for Impact Assessment Agency notices)
- **Section 10**: Append standard `## 10. Skills Registry Governance` section to match the other 5 domain pipeline docs.

---

### Piece 3: Ecosystem & Global Pipelines (`3 files`)
Synchronize the 3 ecosystem and international hub pipelines (`Clusters`, `Payments`, `Mining Hubs`).

#### [MODIFY] [architecture_arc42_clusters.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_clusters.md)
- **Section 3 & 5.2**: Update fallback chain (`gemini-3.7-flash`) and add the **13 missing sources** from [innovation_clusters.json](file:///c:/dev/canadian-grant-intelligence/configs/innovation_clusters.json) grouped by hub:
  - **Ocean Hub**: `Ocean_BlueEconomy`
  - **Protein Industries Hub**: `ProteinIndustries_FoodSecurity`, `ProteinIndustries_AgriFood_Federal`, `ProteinIndustries_CanadaBuys` (`ckan`)
  - **CanadianTech Hub**: `CanTech_BetaKit`, `CanTech_AI_Ecosystem`, `CanTech_Federal_AI`
  - **SpaceDefence Hub**: `SpaceDef_CSA`, `SpaceDef_Defence`, `SpaceDef_Industry`
  - **EnergyEnvironment Hub**: `Energy_Transport`, `Energy_CleanTech`, `Energy_Conservation`

#### [MODIFY] [architecture_arc42_payments.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_payments.md)
- **Section 5.2**: Update fallback chain (`gemini-3.7-flash`) and add the **4 missing sources** from [global_payments.json](file:///c:/dev/canadian-grant-intelligence/configs/global_payments.json):
  - `BIS_Official_Press` (Bank for International Settlements CBDC/mBridge/Settlement Feed)
  - `Federal_Reserve_Payments` (US Federal Reserve FedNow/Fedwire/Payments Feed)
  - `Bank_of_England_CHAPS` (Bank of England CHAPS & ISO 20022 Feed)
  - `SWIFT_Official_News` (SWIFT Official ISO 20022, Swift GO & gpi Feed)

#### [MODIFY] [architecture_arc42_mining_hubs.md](file:///c:/dev/canadian-grant-intelligence/docs/architecture_arc42_mining_hubs.md)
- **Section 4 & 5.2**: Update the fallback model reference from `gemini-3.5-flash-lite` to `gemini-3.7-flash` to match [mining_hubs.json](file:///c:/dev/canadian-grant-intelligence/configs/mining_hubs.json#L346).

---

### Piece 4: Multi-Pipeline Automated Parity Validator (`1 file`)
Upgrade the existing single-pipeline scratch script so config/documentation drift can never recur silently.

#### [MODIFY] [audit_arc42.py](file:///c:/dev/canadian-grant-intelligence/scratch/audit_arc42.py)
- Expand [`scratch/audit_arc42.py`](file:///c:/dev/canadian-grant-intelligence/scratch/audit_arc42.py) to iterate over all 6 `configs/<pipeline>.json` files and their mapped `docs/architecture_arc42_<pipeline>.md` documents, verifying:
  1. 100% of `sources[i]["name"]` in each JSON config appear in its corresponding `arc42` markdown file.
  2. 100% of `llm_settings["model_fallbacks"]` in each JSON config match the documented fallback chain.
  3. All `generic_engine/extractors/*.py` and `generic_engine/api/*.py` modules are documented in the Master `docs/architecture_arc42.md`.
  4. Exits with code `0` only if all checks pass across all pipelines.

---

## Verification Plan

### Automated Verification
After completing each Piece, run the upgraded verification script using the local virtual environment interpreter:
```powershell
$env:PYTHONPATH="c:\dev\canadian-grant-intelligence"; c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\scratch\audit_arc42.py
```
And run the existing skill validator across all 6 configurations:
```powershell
$env:PYTHONPATH="c:\dev\canadian-grant-intelligence"; c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\scripts\validate_skill.py --config configs/canadian_grants.json
```
