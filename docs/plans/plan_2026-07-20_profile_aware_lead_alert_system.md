# Implementation Plan: Profile-Aware Multi-Tenant Lead Alert System (Refined)

*Goal: Transform the generic grant intelligence pipeline into a multi-tenant B2B lead generation service that privately matches incoming tenders to subscriber capability profiles and emails pre-drafted cold pitch drafts, while preserving the public showcase dashboard.*

## Overview & Architecture

```
                       ┌────────────────────────────────────────────────────────┐
                       │             Generic Ingestion Engine                   │
                       │     (GitHub Actions Serverless Runner - $0/mo)         │
                       └───────────────────┬────────────────────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
       [PUSH CHANNEL: High-Value]                   [PULL CHANNEL: Showcase]
  Private Subscriber Lead Alerts              Public Static HTML Dashboard
  • Delivered direct to email inbox           • Hosted at docs/index.html (GitHub Pages)
  • Pre-drafted B2B cold pitch emails         • Public portfolio & credibility builder
  • Zero friction (subscriber opens email)    • Searchable archive for deep dives
```

### Strategic Objectives
1.  **High-Value Delivery:** Move from a broadcast news firehose to targeted, high-match lead alerts for subscribers like **Mayai Market Intelligence**.
2.  **Strict Multi-Tenant Privacy:** Keep subscriber focus areas, capabilities, and pitch drafts 100% private. Never publish subscriber profiles or pitches to public GitHub Pages or public JSON files.
3.  **Low Operational Cost & High Performance:** Use local keyword pre-filtering before LLM invocation to keep API costs < $0.50/mo and execution runtime ~1–2 minutes.

---

## User Review Required

> [!IMPORTANT]
> **Data Boundaries & Storage Security:**
> *   **Repository Security:** A baseline `.gitignore` file will be created to prevent accidental commits of local secrets, `.env` files, or temporary subscriber data.
> *   **Azure Profile Storage:** Subscriber profiles will be stored in Azure Blob Storage (`subscriber_profiles.json`) alongside `subscribers.json`, loaded securely at runtime.
> *   **CLI Management Tool:** A helper script `scripts/manage_subscribers.py` will be created to add, list, and update subscriber profiles in Azure without needing manual portal edits.

---

## Proposed Technical Changes

### 1. Configuration & Schema Component

#### [NEW] [.gitignore](file:///c:/dev/canadian-grant-intelligence/.gitignore)
Create a root `.gitignore` file to exclude `.env`, `*.pem`, `*.key`, `scratch/`, and temporary local subscriber profiles.

#### [MODIFY] [schema.py](file:///c:/dev/canadian-grant-intelligence/generic_engine/schema.py)
Add `subscriber_profiles_file: Optional[str] = "subscriber_profiles.json"` to `StorageConfig`.

---

### 2. Subscriber Management CLI Component

#### [NEW] [manage_subscribers.py](file:///c:/dev/canadian-grant-intelligence/scripts/manage_subscribers.py)
A lightweight CLI tool using standard `argparse` and `azure_client` to manage profiles in Azure:
*   `list`: Lists all active subscriber profiles in Azure Storage.
*   `add`: Adds or updates a profile with `--id`, `--name`, `--email`, `--keywords`, `--capabilities`, and `--target-orgs`.
*   `delete`: Deletes a profile by `--id`.

---

### 3. Pipeline Ingestion & Matching Component

#### [NEW] [profile_matcher.py](file:///c:/dev/canadian-grant-intelligence/generic_engine/api/profile_matcher.py)
A dedicated, modular class handling subscriber evaluations:
1.  **Profile Ingestion:** Downloads `subscriber_profiles.json` from Azure.
2.  **Local Keyword Pre-Filter:** Evaluates new tender text against subscriber keywords using regex word boundaries (`\b`). Only candidate tenders passing the local filter proceed to Gemini.
3.  **Isolated LLM Fit-Scoring:** For candidate matches, sends the tender text + *only that specific subscriber's profile* to Gemini, requesting a `fit_score` (0-100%) and a 4-paragraph AIDA/PAS `custom_pitch` cold email.
4.  **Date-Scoped Audit Logging:** Appends match evaluations to a date-scoped JSON report in Azure (`lead_audit_YYYY-MM-DD.json`) for auditability.

#### [MODIFY] [gemini_client.py](file:///c:/dev/canadian-grant-intelligence/generic_engine/api/gemini_client.py)
Add a public method `evaluate_subscriber_fit(tender_text, subscriber_profile)` that uses `_retry_request()` with structured prompt instructions.

#### [MODIFY] [main.py](file:///c:/dev/canadian-grant-intelligence/generic_engine/main.py)
Integrate `ProfileMatcher` into the orchestration flow:
*   Run subscriber evaluation after tender extraction.
*   Gate lead alert dispatch behind `if not dry_run:` to ensure dry runs do not trigger email notifications.
*   Reuse `notifier.send_digest()` with custom subject and recipient parameters to dispatch private lead alerts directly to matching subscribers.

---

### 4. Testing & Verification Component

#### [NEW] [test_profile_matcher.py](file:///c:/dev/canadian-grant-intelligence/tests/test_profile_matcher.py)
Unit test suite validating:
* Keyword pre-filtering rules (verifying 0% LLM calls for non-matching tenders).
* Multi-tenant data isolation (verifying pitches are never written to public `tenders.json`).
* Schema validation of subscriber profile objects.

---

## Verification Plan

### Automated Tests
Execute individual unit tests using the local virtual environment Python interpreter:
```powershell
$env:PYTHONPATH="c:\dev\canadian-grant-intelligence"
c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\tests\test_profile_matcher.py
```

### Manual Verification
1. **Initialize Mayai Profile in Azure:**
   ```powershell
   c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_subscribers.py add --id mayai_market_intelligence --name "Mayai Market Intelligence" --email "masan.edgar@gmail.com" --keywords "database,spreadsheet,dashboard,analytics,market research" --capabilities "Development of relational database-spreadsheet hybrids (Airtable, SmartSuite), custom SQL schemas, and data integration pipelines."
   ```
2. **Execute Ingestion in Dry-Run Mode:**
   ```powershell
   c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\generic_engine\main.py --config c:\dev\canadian-grant-intelligence\configs\canadian_grants.json --dry-run --run-type pulse
   ```
3. **Privacy & Audit Verification:**
   * Verify that public file [tenders.json](file:///c:/dev/canadian-grant-intelligence/docs/data/canadian-grants/tenders.json) contains **no** private subscriber pitches or profile tags.
   * Verify that dry-run logs reflect match evaluations without dispatching live emails.
