Date: 2026-05-20
Time: 17:28 PM UTC
Title: Fix LinkedIn UI and Email Formatting

## Activities and Tasks Performed
- **Decoupled UI payload from Email markdown body**:
  - Modified `scripts/src/main.py` so that `pmo_insights.json` (`linkedin_post` key) holds the clean text format for UI display and clipboard copying (no Section 1/2/3 headers, no embedded markdown image).
  - Configured `latest_post.md` (the email newsletter body source) to render cleanly with the social card image at the top and the post text below it, completely free of "Section 1/2/3" draft headers.
- **Improved Clipboard Copying**:
  - Updated `docs/index.html` copy button (`data-raw` attribute) to store and copy the exact markdown layout of the post including emojis, instead of stripping format.
- **Upgraded LinkedIn Layout to CSS Grid**:
  - Redesigned `.linkedin-grid` in `docs/style.css` using `display: grid` with column proportions `1.2fr 1fr` and `32px` gaps on desktop, preventing image stacking and text column overlapping.
  - Increased `max-width` on `.linkedin-card` to `1000px` for better readability.
  - Implemented responsive styles to stack the grid vertically on devices under `768px` wide.
- **Enhanced Path Resiliency**:
  - Converted subprocess execution calls and template loading paths in `scripts/src/main.py` and `scripts/generate_social_card.py` to use absolute paths based on `__file__`, resolving OneDrive folder junction redirect issues.
- **Testing**:
  - Ran the existing test suites (31/31 assertions passing).
  - Executed a successful mock local pipeline run to generate output JSON and HTML.

## Summary
- Fixed duplicate and overlapping card images in dashboard.
- Redesigned card layout using CSS Grid and resolved right-side dead space.
- Decoupled newsletter formatting to clean up "Section" headers in email bodies.
- Made script path resolution resilient against OneDrive file system junctions.

## Issues
- None.

## Next Steps
- Commit and push changes.
- Trigger a manual deep run via GitHub Actions to verify production output.
