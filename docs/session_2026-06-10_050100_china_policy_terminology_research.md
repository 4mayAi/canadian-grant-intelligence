Date: 2026-06-10
Time: 05:01 AM
Title: China Mining Policy Terminology and Multi-Language Feed Research

Session Content:
- Researched China's official forward guidance terminology for mining and critical minerals policy.
- Identified the key Chinese-language policy terms used by the State Council and Ministry of Natural Resources:
  1. 战略性矿产 (zhànlüè xìng kuàngchǎn) — "Strategic Minerals" — the State Council's official classification
  2. 关键矿产 (guānjiàn kuàngchǎn) — "Critical Minerals" — aligned with global economic competition discourse
  3. 矿产资源法 (kuàngchǎn zīyuán fǎ) — "Mineral Resources Law" — revised Nov 2024, effective July 1 2025
  4. 稀土管理条例 (xītǔ guǎnlǐ tiáolì) — "Rare Earth Management Regulations"
  5. 出口管制 (chūkǒu guǎnzhì) — "Export Controls"
  6. 高质量发展 (gāo zhìliàng fāzhǎn) — "High-Quality Development"
  7. 紫金矿业 (zǐjīn kuàngyè) — "Zijin Mining" in Chinese
- Tested all terms against Chinese-language Google News feeds (hl=zh-CN, gl=CN, ceid=CN:zh-Hans).
- Results showed massive coverage:
  - 战略性矿产: 100 total entries, 40 within 30 days, 63 within 90 days
  - 关键矿产 供应链: 100 total, 39 in 30d, 73 in 90d
  - 矿产资源法: 60 total, 29 in 30d, 33 in 90d
  - 出口管制 矿产: 100 total, 17 in 30d, 22 in 90d
  - 紫金矿业: 100 total, 65 in 30d, 90 in 90d
- Tested English-language feeds with China policy terms:
  - China export controls minerals rare earth: 100 total, 27 in 30d (excellent B2B articles on rare earth bans, Benchmark Mineral Intelligence)
  - China strategic minerals supply chain: 51 total, 7 in 30d (Mineral Resources Law implementation, EU stockpile responses)
  - Zijin + CMOC + Ganfeng strategic: 64 total, 4 in 30d (machinery agreements, Argentina expansion, Ganfeng orders)
- Identified that the most impactful English-language query is the export controls query (27 articles in 30 days covering rare earth export bans, EU/US responses, and policy tightening).

Summary:
- Chinese-language feeds are extremely rich — orders of magnitude more coverage than English feeds.
- The English export controls query alone yields 27 recent B2B articles, far exceeding the current 0.
- The Chinese terms "战略性矿产" and "关键矿产" are the State Council's actual forward guidance language.
- Multi-language feed ingestion is technically feasible via Google News locale parameters.

Issues:
- The pipeline currently has no translation capability for Chinese-language articles.
- Gemini can translate Chinese text natively, but this would increase token consumption.

Next Steps:
- Decide whether to add Chinese-language feeds (with LLM translation) or use the English export controls query.
- Update the implementation plan with the enriched China source options.
