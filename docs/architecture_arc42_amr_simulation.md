# AMR & Biotech Simulation Intelligence Pipeline — arc42 Architecture Documentation

This document describes the software architecture of the AMR & Biotech Simulation Intelligence Pipeline (mayAi).

---

## 1. Introduction and Goals

### 1.1 Requirements Overview
The AMR & Biotech Simulation Intelligence Pipeline is a serverless, scheduled, config-driven monitoring and synthesis system. It tracks Antimicrobial Resistance (AMR) policies, bacterial and pathogen spread modeling, and biotech R&D procurement opportunities across Canada.

Key features:
- **Direct Database Integration (CKAN API)**: Crawls the live CanadaBuys dataset API to stream and parse tender rows directly, bypassing traditional RSS limitations.
- **Dual-Speed Ingestion**: Integrates slow-moving, long-term biological strategies and regulatory baselines (Anchors) with fast-moving daily news and tender signals (Signals).
- **METS Taxonomy Classification**: Classifies opportunities into three mutually exclusive, collectively exhaustive (MECE) biotech categories: **METS-Digital** (simulation software, modeling), **METS-PMO** (program management, evaluation), and **METS-Ops** (laboratory operations, biosafety, equipment).
- **Precision Keyword Mapping**: Enforces regex word boundaries (`\b`) for short keywords (length $\le 4$) like `AMR`, `NRC`, `CIHR`, and `PHAC` to eliminate false positive matches (e.g., preventing `nrcan` from matching `nrc`).
- **State-Preserving Cache Merging**: Carries forward unexpired open tenders and recent news across scraper executions to keep the dashboard accurate and comprehensive.

### 1.2 Quality Goals
1. **Auditable Reference Traceability**: Every biotech insight grounded in a slow-moving anchor must display a verified reference tracing back to the official health strategy or funding report.
2. **Metadata Integrity**: Preserves and carries forward tender-specific attributes (e.g. closing dates, delivery provinces, categories, and partnering options) from the source database.
3. **Resilience**: The system falls back to generating notice URLs from the reference number if the `noticeURL-URLavis-eng` field is missing, ensuring tenders are not skipped.
4. **Layout Separation**: The frontend dashboard divides active procurement opportunities ("Simulation Tracker") from general news signals ("Biotech Insights") based on the presence of a closing date.

### 1.3 Stakeholders & Personas
- **Biotech Founder / R&D Director**: Uses the *Simulation Tracker* to identify upcoming bids, funding opportunities, and consortia for computational pathology and modeling software.
- **Health-Tech Consultant**: Analyzes the *Biotech Insights* tab for policy signals from WHO, PHAC, and CIHR to align client consulting proposals with national funding priorities.

---

## 2. Architecture Constraints

- **Storage Constraint**: Zero relational database footprint; all state registries (processed URLs, KPIs, curated anchors, insights list) are stored as raw JSON files in Azure Blob Storage under the `amr-simulation-data` container.
- **Serverless Trigger**: Execution runs entirely serverless, triggered daily by GitHub Actions workflow schedulers.
- **Client-Side Rendering**: The dashboard renders dynamically using client-side JavaScript, fetching data directly from Azure Storage.

---

## 3. System Context

```mermaid
graph TD
    subgraph External Ingestion Sources
        CB[CanadaBuys CKAN API]
        CIHR[CIHR AMR Google News Feed]
        NRC[NRC Health Google News Feed]
        PHAC[PHAC Health Google News Feed]
    end

    subgraph mayAi Cloud Context
        GHA[GitHub Actions Runner]
        AZ[Azure Blob Storage: amr-simulation-data]
        LLM[Gemini API Cascade]
        SMTP[SMTP Email Server]
    end

    subgraph Client Presentation Channels
        GH[GitHub Pages Dashboard: /amr-simulation/]
        DIS[Discord Channel]
        USR[Subscribers Inbox]
    end

    CB -->|CKAN CSV Ingestion| GHA
    CIHR -->|RSS Ingestion| GHA
    NRC -->|RSS Ingestion| GHA
    PHAC -->|RSS Ingestion| GHA

    GHA -->|Batch Ingestion & Synthesis| LLM
    LLM -->|JSON Response| GHA

    GHA -->|Upload JSON feeds & PNG social card| AZ
    GHA -->|Push warnings/failure alerts| DIS
    GHA -->|Dispatch formatted newsletters| SMTP

    AZ -->|Fetch dynamic JSON data| GH
    SMTP -->|Formatted HTML Digest| USR
```

---

## 4. Solution Strategy

The pipeline implements three core design strategies to handle the integration of slow and fast data speeds:

1. **Dual-Speed Cross-Synthesis**: Slow-moving biotech anchors are indexed with unique integer Fact IDs in `configs/amr_anchors.json`. When daily signals are scraped, they are grouped by hub, and the matching hub anchors are appended to the Gemini prompt context.
2. **Programmatic Reference Resolution**: The model returns the list of selected integer `grounded_fact_ids`, and the Python script programmatically resolves the source name, page range, and URL from the local anchors database.
3. **METS Biotech Taxonomy**: Gemini classifies insights into the three categories, which the frontend JS parses to map onto standard CSS styles:
   - `METS-Digital` (Pathogen modeling, in silico simulation, data analytics)
   - `METS-PMO` (Program evaluation, consulting, strategy)
   - `METS-Ops` (Laboratory equipment, biosafety operations, diagnostics)

---

## 5. Building Block View

```
generic_engine/
├── main.py                     # Main orchestrator (fetches feeds, groups by hub, calls Gemini, merges cache)
├── models.py                   # Dataclass schemas for Insights and KPIs
├── schema.py                   # Pydantic V2 configuration validator
└── extractors/
    └── ckan.py                 # Direct CanadaBuys CKAN API database crawler

configs/
├── amr_simulation.json         # Ingestion sources, search terms, and model parameters
└── amr_anchors.json            # Local seed database for slow-moving payment anchors

docs/
├── amr-simulation/
│   └── index.html              # Frontend presentation dashboard
└── architecture_arc42_amr_simulation.md # This architecture document
```

---

## 6. Runtime View

### 6.1 Daily Ingestion & Synthesizer Flow

```mermaid
sequenceDiagram
    participant Runner as GitHub Actions Runner
    participant Azure as Azure Blob Storage
    participant CKAN as CanadaBuys CKAN API
    participant RSS as RSS news extractors
    participant LLM as Gemini API Cascade
    
    Runner->>Azure: Download processed_urls.json & amr_anchors.json & amr_insights.json
    Runner->>Runner: Check amr_insights.json for active tenders
    alt Cache has active tenders
        Runner->>Runner: Set pulse_only = True
    else Cache lacks active tenders
        Runner->>Runner: Set pulse_only = False
    end
    
    Runner->>CKAN: Query CKAN package URL
    alt pulse_only is True
        CKAN-->>Runner: Stream "new tender notices" CSV
    else pulse_only is False
        CKAN-->>Runner: Stream "new" and "open" tender notices CSVs
    end
    
    loop For Each Tender Row
        Runner->>Runner: Generate fallback URL if noticeURL-URLavis-eng is missing
        Runner->>Runner: Match keywords enforcing regex word boundaries (\b) for short terms
    end
    
    Runner->>RSS: Ingest CIHR, PHAC, and NRC news releases
    
    Runner->>Runner: Combine items and deduplicate URLs
    Runner->>Runner: Carry forward active/recent items from amr_insights.json cache
    Runner->>Runner: Exclude duplicates using LLM event clustering
    
    loop For New Scraped Items
        Runner->>LLM: Batch query Gemini (Signals + Anchors context)
        LLM-->>Runner: Return JSON insight (hooks, strategic value, categories, grounded_fact_ids)
        Runner->>Runner: Programmatically resolve anchor references from fact IDs
    end
    
    Runner->>Runner: Generate amr_insights.json and amr_kpis.json
    Runner->>Runner: Validate output schemas
    Runner->>Azure: Upload final reports to cloud storage
    Runner->>Runner: Push local backup commits to repository
```

---

## 7. Deployment View

- **GitHub Actions Runner**: Executed daily on Ubuntu runners via `daily_amr_scraper.yml` calling `run_pipeline.yml`.
- **Azure Integration**: Reads and writes to the `amr-simulation-data` storage container.
- **Dashboard Deployment**: Dynamic Javascript in [docs/amr-simulation/index.html](file:///c:/dev/canadian-grant-intelligence/docs/amr-simulation/index.html) pulls directly from Azure. The dashboard links to [style.css](file:///c:/dev/canadian-grant-intelligence/docs/style.css).

---

## 8. Concepts

### 8.1 Markdown-to-HTML Parsing
To avoid external dependencies and keep the engine lightweight, a custom line-by-line parser compiles markdown text into newsletter-friendly HTML:
- **Lists (`-` or `*`)** are caught, grouped, and wrapped inside native `<ul>` and `<li>` tags with matching inline margins and padding.
- **Headers (`#` to `####`)** are mapped to `<h1-h4>` tags styled in brand gold (`#ffd700`).
- **Inline Bold (`**text**`)** is replaced with `<strong>` tags.
- **Hyperlinks (`[text](url)`)** are wrapped in anchor tags with text-decoration disabled and colored gold to ensure high visibility.

### 8.2 Brand Link Injections & Regex Constraints
During the post-synthesis phase, a regex mapper runs lookarounds to detect text mentions of agencies and portals, hyper-linking them to their official domains:
- **CIHR** -> `https://cihr-irsc.gc.ca/`
- **NRC** -> `https://nrc.canada.ca/`
- **PHAC** -> `https://www.canada.ca/en/public-health.html`
- **CanadaBuys** -> `https://canadabuys.canada.ca/`

#### Technical Constraints:
* **Lookup Safeguards (Lookarounds)**: The regex engine applies negative lookarounds `(?<!\[){re.escape(name)}(?!\])` to match only plain text mentions, preventing double-hyperlinking of terms that are already part of markdown links.
* **Ordering Dependency**: The replacement dictionary is ordered strictly from longest name to shortest name. This sequence avoids partial-match corruption.

### 8.3 State-Preserving Cache Merging (Tenders Lifecycle)
Unlike simple news signals, procurement opportunities have a distinct lifecycle:
- **Active Union**: The system downloads existing items from `amr_insights.json`, retains unexpired tenders, and merges them with fresh extraction records.
- **State Transition**: Closed or expired tenders are filtered out during the daily execution, keeping the active simulation tracker accurate and clean.

### 8.4 Precision Keyword Mapping
To avoid false-positive matches (e.g. matching `nrcan` as `nrc`), the engine enforces word boundaries `\b` for keywords that are 4 characters or shorter. This ensures that only exact matches to `AMR`, `NRC`, `CIHR`, or `PHAC` are processed.

### 8.5 Stateless CKAN Database Ingestion
The system connects directly to the CanadaBuys CKAN API to ingest federal tender data. It streams the CSV package data, parses individual rows, and isolates relevant health-tech and bio-simulation rows using keyword filters.

---

## 9. Design Decisions

- **Config-Driven Generalization**: Storing pipeline parameters (keywords, source lists, container settings) in JSON files allows adding new portals or pipelines without changing core orchestrator code.
- **Zero-Relational-Database JSON Storage**: Storing datasets as structured, static JSON files in Azure Blob allows the frontend to operate without a server-side backend, reducing hosting costs.
- **Low-RPM, High-TPM Optimization Strategy**: To safeguard Gemini API request quotas, new news items are batch-processed in groups of 5. This design aggregates texts into single API calls, taking advantage of Gemini's high token-per-minute (TPM) limit while staying well below the low requests-per-minute (RPM) threshold.
- **Telemetry Observability**: The orchestrator automatically logs total API transaction sizes and token stats (`gemini_client.get_stats()`) at the end of each execution, providing complete visibility into usage costs and pipeline efficiency.
- **Collapsible Events & Milestones Deck**: Implemented a dynamic, collapsible card deck directly above the daily signals list. It fetches conformed summits, webinars, and global conference facts from a static anchors database (`amr_anchors.json`) based on their type, and handles empty states by hiding the component if no active events exist for a hub, ensuring clean visual presentation.
- **Bypass Refactoring for AMR/Biotech Feeds**: Google News searches and scientific RSS feeds bypass query refactoring (`skip_query_refactoring: true`) because search queries are already highly targeted and refactoring would yield zero results.

---

## 10. Skills Registry Governance

The AMR & Biotech Simulation Intelligence pipeline is fully decoupled under the central Skills Registry pattern:
- **Skill Boundary**: The Skill boundary encompasses the configuration layer (`amr_simulation.json`, `amr_anchors.json`) defining the scraper sources, keyword pre-filters, and LLM system instruction components (persona, classification, grounding, translation, formatting). The Harness boundary governs validation, telemetry metrics collection, cloud synchronization, and dynamic email dispatch.
- **Per-Skill Subscribers**: Audience records reside in `subscribers.json` inside the `amr-simulation-data` storage container, ensuring email distribution is strictly isolated per topic.

