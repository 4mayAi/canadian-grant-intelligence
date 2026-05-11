Date: 2026-05-11
Time: 05:00 UTC
Title: Canadian Intelligence Pipeline Optimization

Summary:
- Implemented a "Days to Expiry" filter in the CanadaBuys Intelligence Dashboard to filter tenders based on `daysLeft` calculations (<7 Days, <30 Days, >30 Days, Closed).
- Normalized technical UI terminology into human-readable industry categories (e.g., *CNST to Construction, *DER to Defence & Security).
- Updated backend pipeline (`fetch_canadian_grants.py`) to sanitize category strings before Azure JSON serialization.
- Re-architected PMO Insights navigation into a hybrid system fetching dates via GitHub API and attempting JSON retrieval from Azure before falling back to GitHub markdown rendering.
- Re-integrated historical PMO news insights for May 7th and May 8th ensuring long-term strategic context.

Issues:
- Automated email delivery remains offline due to 2FA. Requires a Google App Password to be stored in GitHub Secrets.

Next Steps:
- Fix SMTP password issue by adding the correct App Password to GitHub Secrets.
- Conduct live testing of the hybrid navigation architecture against newly generated data batches.
