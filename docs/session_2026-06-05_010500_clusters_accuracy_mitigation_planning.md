Date: 2026-06-05
Time: 01:05 AM UTC
Title: Clusters Dashboard Accuracy Audit & Mitigation Planning

Activities:
- Fetched the live clusters dashboard at https://4mayai.github.io/canadian-grant-intelligence/clusters/ and identified it as a client-side rendered SPA loading data from Azure Blob Storage (`clusters-data/cluster_insights.json` and `clusters-data/kpis.json`).
- Inspected the local data backup at `docs/data/innovation-clusters/cluster_insights.json` — contains 7 insight cards and 1 LinkedIn executive digest post.
- Launched 4 parallel research subagents to fetch and fact-check all 7 original source articles:
  1. CANSEC article (Ocean Supercluster) — verified against oceansupercluster.ca
  2. BC Housing HGI article (DIGITAL) — verified against digitalsupercluster.ca
  3. 3 Protein Industries articles (Terra/GWBC, Indigenous Investment Group, Agi3/Aon) — verified against proteinindustriescanada.ca
  4. Ocean RFP + Web Summit / Minister Solomon articles — verified against oceansupercluster.ca and digitalsupercluster.ca
- Compared each dashboard insight card field (`linkedin_hook`, `strategic_value`, `co_bidding_opportunity`) against verified source content.
- Identified 2 factual inaccuracies (hallucinations):
  1. "Secure Units" — fabricated term; actual name is "DISH (Defence Innovation Secure Hubs)"
  2. "blockchain for transparent claims processing" and "IoT for crop monitoring" in the Agi3/Aon insight — neither technology is mentioned in the source article
- Identified 1 fabricated hashtag: `#BDC` in the LinkedIn post (BDC is never mentioned in any source)
- Identified systemic context starvation: all 7 insight cards omit dollar figures, company names, program names, and deadlines that are present in the source articles
- Identified 2 cases of misleading framing: presenting completed co-investment deals as open partnership opportunities
- Traced all issues to the same 4 root causes found in the PMO pipeline investigation
- Created a 4-layer mitigation plan covering enriched context, time-anchoring, factual boundary constraints, and unit tests

Summary:
- Completed a full accuracy audit of the live clusters dashboard against 7 verified source articles
- Found 2 hallucinated facts, 1 fabricated hashtag, systemic context starvation across all 7 cards, and 2 misleadingly framed insights
- Proposed 4-layer mitigation plan modifying `generic_engine/api/gemini_client.py` and `generic_engine/main.py`

Issues:
- "Secure Units" hallucination in CANSEC insight (should be "DISH")
- "blockchain" and "IoT" hallucination in Agi3/Aon insight
- "#BDC" fabricated hashtag in LinkedIn post
- All 7 insight cards omit key specifics (dollar figures, company names, deadlines)

Next Steps:
- Obtain user approval on the mitigation plan
- Execute the 4-layer code changes
- Run automated tests and trigger a dry-run pipeline execution
