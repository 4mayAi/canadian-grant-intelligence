# Session Log: Mining Digest Remediation & Shared Engine Hardening

Date: 2026-09-17
Time: 01:45 AM UTC
Title: Mining Digest Remediation & Shared Engine Hardening

## Session Content
- Conducted deep QA review of raw mining briefing output identifying six distinct issues: headline typo (`Minning`), missing Line 1 hero hook, duplicate wire syndications in *Featured News & Sources*, unspaced concatenated hashtags, plain unformatted category headers, and internal taxonomy leakage (`METS-PMO`).
- Assessed architectural impact across all 6 production pipelines (`canadian-grants`, `innovation-clusters`, `trade-compliance`, `amr-simulation`, `payments`, `mining-hubs`) to ensure shared engine changes in `generic_engine/` remain topic-agnostic and avoid cross-pipeline regressions.
- Enforced the **Shared Engine Topic Isolation Rule** (`AGENTS.md`) by keeping prompt constraints and regex guardrails topic-agnostic in `gemini_client.py` and `main.py`, while isolating mining-specific directives (`max_items_per_hub: 2`, critical minerals weighting, anti-METS phrasing) to `configs/mining_hubs.json`.
- Implemented `normalize_title_stem` in `generic_engine/main.py` to strip known wire aggregator suffixes (`- Yahoo Finance`, `- newsfilecorp.com`, `- PR Newswire`, `- GlobeNewswire`, `- Proactive financial news`, `- Medianet News Hub`, etc.) before selecting `featured_insights`. Strictly exempted CanadaBuys tenders and academic preprints (bioRxiv, medRxiv, arXiv).
- Added idempotent hashtag spacer regex (`re.sub(r'(#[A-Za-z0-9_]+)(?=#)', r'\1 ', suggested_post)`) and structural headline fallback in `generic_engine/main.py`.
- Updated CTA regex in `generic_engine/api/notifier.py` to support markdown link formats alongside raw URLs.
- Created `tests/test_digest_hardening.py` with 5 automated unit tests verifying wire deduplication, tender/preprint exemptions, hashtag spacing, headline fallbacks, and CTA parsing.
- Executed full procedural test suite via local virtual environment interpreter (`.venv_new\Scripts\python.exe`) with dual-directory `PYTHONPATH`.

## Summary
- Remediated all formatting, deduplication, and editorial defects identified in the mining workflow output.
- Hardened shared engine modules and verified that all 6 production pipelines benefit without breaking topic isolation.
- All unit tests passed (`test_digest_hardening.py`: 5/5, `test_news_prioritization.py`: 4/4, `test_deduplication.py`: 13/13, `test_generic_engine.py`: 7/7).

## Issues
- None encountered. All validations passed cleanly.

## Next Steps
- Verify live GitHub Actions automated ingestion runs for `mining-hubs` and review published newsletter outputs.
