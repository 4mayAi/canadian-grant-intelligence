Date: 2026-05-16
Time: 01:49 UTC
Title: Enable 3x Daily Pages Rebuilds

Summary:
- Investigated why the 3x daily scheduled "Pulse" runs were not triggering a GitHub Pages rebuild.
- Identified that the `daily_grants_scraper.yml` workflow was intentionally restricting the `git commit` and `git push` actions to `DEEP_DIVE` runs to reduce repository noise.
- Modified `.github/workflows/daily_grants_scraper.yml` to remove the `if: env.RUN_TYPE == 'DEEP_DIVE'` condition from the commit step, ensuring that all 3 automated runs commit their fresh data to the repo.
- Maintained the restriction on the Email Digest so that users still only receive one email per day.
- Pushed the fix to the `main` branch.
- Triggered a manual `PULSE` run via GitHub CLI to verify.
- Confirmed that the `PULSE` run successfully generated a commit, which in turn successfully triggered a `pages-build-deployment` workflow.

Issues:
- None.

Next Steps:
- None. The dashboard will now reflect fresh data 3x per day.
