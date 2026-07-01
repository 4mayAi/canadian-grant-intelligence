Date: 2026-07-01
Time: 04:22 PM UTC
Title: Fixed LinkedIn Digest Hub Capping Logic

Session Content:
- Identified that the PM YouTube video was successfully processed but not featured in the LinkedIn post because of regional balance capping (max 2 items per hub).
- Since Canadian Grants is a single-topic pipeline, all sources defaulted to the "Global" hub, capping the post content to only the first 2 items.
- Configured "hub": "Canada" on all sources in `configs/canadian_grants.json`.
- Modified `generic_engine/main.py` to dynamically adjust `max_per_hub` to 5 if there is only 1 unique hub, otherwise defaulting to 2 (for multi-hub pipelines like Global Mining Hubs).
- Staged, committed, and pushed changes to GitHub.
- Triggered Canadian Grants GHA workflow.

Summary:
- Resolved single-hub pipeline lumping which was capping LinkedIn posts.
- Restored YouTube video visibility in the digest post.

Issues:
- None.

Next Steps:
- Verify GHA workflow runs successfully and includes the PM YouTube card in the LinkedIn post body.
