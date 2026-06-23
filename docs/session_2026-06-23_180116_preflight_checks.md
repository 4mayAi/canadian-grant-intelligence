Date: 2026-06-23
Time: 06:01 PM UTC
Title: Canadian Grants Migration Pre-Flight Checks

## Activities
- Initiated pre-flight checks to inspect differences and gaps between legacy and generic engine scripts before migration.
- Investigated difference between legacy markdown-to-HTML conversion and the generic engine's notifier.
- Analyzed `prune_processed_urls.py` for container-awareness.
- Checked `docs/index.html` dashboard fetching paths and files.

## Findings
1. **Markdown-to-HTML Parity**: The subagent analysis identified that `generic_engine/api/notifier.py` lacks the image regex substitution steps present in `mail_sender.py`, which will prevent inline images (`![alt](url)`) from rendering in emails. Tagline and footer subscription texts are slightly different (which is acceptable/intended).
2. **Container-Aware Pruning**: The script `scripts/validators/prune_processed_urls.py` currently hardcodes the `"data"` container and lacks command-line arguments. It needs modification to support an optional `--container` argument.
3. **Dashboard Data Paths**: The dashboard (`docs/index.html`) fetches `tenders.json`, `pmo_insights.json`, `kpis.json`, and `manifest.json` from the root of the `"data"` container, and historical runs from `/reports/` in the same container. The generic engine's output paths must match this.

- Patched `implementation_plan.md` to cover all three gaps:
  1. Image regex conversion in `notifier.py`.
  2. `--config` argument in `prune_processed_urls.py` for container-aware pruning.
  3. `prefix_historical_files` option in `StorageConfig` for legacy dashboard filename compatibility.

## Next Steps
- Wait for user approval on the updated implementation plan.
- Create `task.md` checklist upon approval.
- Proceed to execution of Phase 1 (migration of Canadian Grants).
