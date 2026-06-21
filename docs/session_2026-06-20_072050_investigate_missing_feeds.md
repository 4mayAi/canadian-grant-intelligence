Date: 2026-06-20
Time: 07:20 AM UTC
Title: Investigate and Re-fetch Missing Feeds in AMR Dashboard

## Activities & Tasks
- Investigated processed URL caching logic in `generic_engine/main.py` and `scratch/reprocess_innovet_tender.py`.
- Identified that relevant bioRxiv preprints were historically processed and discarded as "low-value/irrelevant" due to strict LLM instructions, placing their URLs permanently in the `processed_urls.json` registry on Azure.
- Modified `scratch/reprocess_innovet_tender.py` to dynamically clear all bioRxiv and PHAC/CCDR URLs from `processed_urls.json` and `amr_insights.json` on Azure.
- Refined the system instructions in `configs/amr_simulation.json` to instruct Gemini on how to extract B2B simulation hooks from basic biology preprints.
- Refined the critical evaluation prompt in `generic_engine/api/gemini_client.py` to prevent the model from flagging relevant academic preprints and public health updates as lacking strategic value.
- Re-ran the GHA workflow and verified that all 5 bioRxiv microbiology preprints were successfully scraped, evaluated, and merged.
- Verified dashboard deployment and captured a new full-page screenshot of the updated live page.

Summary:
- Resolved the state invalidation issue by clearing the processed URL cache.
- Fixed the LLM evaluation issue by refining the system instructions and model prompt.
- Verified that all 5 bioRxiv preprints are successfully rendered on the live dashboard.

Issues:
- Headless Playwright extraction of full text from `www.biorxiv.org` was blocked by Cloudflare, but the system successfully fell back to default RSS metadata (abstracts/summaries) which was fully sufficient for Gemini synthesis.

Next Steps:
- Confirm with the user that the updated dashboard meets their expectations.
