Date: 2026-06-20
Time: 06:46 AM UTC
Title: Testing Recommended Feeds for AMR and Biotech Simulation

## Activities & Tasks
- Identified direct CDN-hosted feeds for the Public Health Agency of Canada (PHAC) to bypass dynamic XML feed timeouts.
- Wrote and executed `scratch/test_feedparser.py` inside the python virtual environment.
- Tested fetching and parsing the following feeds:
  1. **bioRxiv Microbiology subject collection**: `https://connect.biorxiv.org/biorxiv_xml.php?subject=microbiology`
  2. **PHAC Public Health Updates (CDN)**: `https://www.canada.ca/content/dam/phac-aspc/rss/new-eng.xml`
  3. **PHAC Communicable Disease Report (CCDR)**: `https://www.canada.ca/content/dam/phac-aspc/rss/ccdr-rmtc-eng.xml`
- Confirmed that `feedparser` successfully parses all three feeds, returning high-fidelity scientific preprints and official public health announcements.

Summary:
- Discovered that the dynamic `public-health.atom.xml` url times out, but static Akamai CDN endpoints like `new-eng.xml` resolve within 1 second.
- Confirmed that these feeds yield highly relevant results (e.g. tuberculosis travel guidelines, chronic disease research, microbiology preprints).

Issues:
- PHAC's dynamic media room atom feed is unstable/times out, but static updates feed works perfectly as a replacement.

Next Steps:
- Propose integrating these feeds into `configs/amr_simulation.json` in a subsequent task.
