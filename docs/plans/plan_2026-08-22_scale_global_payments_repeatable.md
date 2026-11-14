# Implementation Plan: Scale Global Payments Intelligence Pipeline Repeatably

To transform the Global Payments & Settlement Intelligence pipeline into a repeatable, high-yield, zero-noise engine that consistently delivers fresh daily insights without rehashing old news or pulling in job board spam.

---

## User Review Required

> [!IMPORTANT]
> **Key Enhancements Proposed**:
> 1. **First-Party Direct Source Ingestion**: Adding direct RSS endpoints for official institutional sources (BIS, Payments Canada, Federal Reserve, Bank of England, SWIFT) alongside Google News RSS searches.
> 2. **Automated Noise & Recruitment Scrubbing**: Adding explicit `negative_keywords` (`"hiring"`, `"job"`, `"relationship manager"`, `"apply now"`, `"casino"`) to instantly discard recruitment ads and SEO spam before LLM processing.
> 3. **Canonical Title-Hash Deduplication**: Collapsing syndicated articles (e.g., identical state news releases published across 5 outlets) using normalized title hashes before URL registry logging.
> 4. **Zero-New-Item Email Gating**: Only dispatching email alerts when at least 1 fresh, uncached article is ingested on that day, preventing duplicate emails on low-volume news days.

---

## Proposed Changes

### Configuration Layer

#### [MODIFY] [global_payments.json](file:///c:/dev/canadian-grant-intelligence/configs/global_payments.json)
- Add first-party institutional RSS search feeds (BIS, Payments Canada, Federal Reserve, Bank of England).
- Add `negative_keywords` list to drop job board postings (`"job"`, `"hiring"`, `"relationship manager"`, `"apply now"`, `"career"`) and SEO spam (`"casino"`, `"withdrawal sites"`).

### Core Engine Processing Layer

#### [MODIFY] [main.py](file:///c:/dev/canadian-grant-intelligence/generic_engine/main.py)
- Implement Title-Hash deduplication (`hashlib.md5(title.lower().encode())`) prior to URL registry processing.
- Implement email gating: only call `notifier.send_digest()` when `new_today >= 1`.

---

## Verification Plan

### Automated Real-Data Test Script
We will execute a live empirical verification script [`scratch/test_repeatable_pipeline.py`](file:///c:/dev/canadian-grant-intelligence/scratch/test_repeatable_pipeline.py) using live data fetched from the internet right now to verify:
1. **Direct Feed Yield**: Confirm first-party feeds (BIS, Fed, Payments Canada) return 100% relevant settlement and central bank announcements.
2. **Noise Scrubbing Rate**: Confirm that 100% of job board postings (`Jobijoba`, `CTgoodjobs`) are dropped by `negative_keywords`.
3. **Syndication Collapse**: Confirm title-hash deduplication collapses duplicate press releases into single unique events.
4. **Fresh Executive Digest**: Confirm Gemini generates a crisp, non-repetitive Executive Digest covering fresh live data.

```powershell
c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scratch/test_repeatable_pipeline.py
```
