Date: 2026-05-16
Time: 21:10 PM UTC
Title: Research Session: Dashboard UI/UX & Data Integrity Diagnostics

Summary of activities:
- Conducted deep diagnostic of `scripts/fetch_canadian_grants.py` to identify root causes of date parsing issues.
- Located hardcoded UI labels and CSS constraints in `docs/index.html` and `docs/style.css`.
- Analyzed the "Hero Hook" and "Social Card" generation logic to address vagueness in LinkedIn engagement content.
- Reviewed persona definitions to align insight generation with professional user needs (Bid Managers, Sales Executives).

Findings:
- **Date Parsing Bug**: Identified that Playwright scraping hardcodes `time.gmtime()` as the publication date, causing historical news to appear as "Today's Insights". RSS parsing also lacks a robust fallback if `pubDate` is missing.
- **UI Redundancy**: Found the hardcoded "Generated Engagement Image" label in `index.html`.
- **CSS Issues**: Fixed width of 320px on the social card preview causes it to appear small on desktop; tender cards have excessive padding on mobile.
- **Hook Logic**: The social card hook is a simple concatenation of tender count and title, which is too vague for the identified professional personas.

Next Steps:
- Implement robust date extraction for Playwright scraper.
- Refactor social card hook to use Gemini-generated strategic summaries.
- Polish CSS for responsive image sizing and mobile-friendly tender cards.
- Remove redundant UI labels.
