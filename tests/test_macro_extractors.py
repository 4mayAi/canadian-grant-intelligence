import unittest
import os
import sys

# Platform-independent path resolution
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from generic_engine.extractors.ised_newsletter import fetch_ised_business_insights
from generic_engine.extractors.bdlnow import fetch_bdlnow_indicators
from generic_engine.models import GeminiInsight, KPIDashboard

class TestMacroExtractors(unittest.TestCase):

    def test_gemini_insight_optional_fields(self):
        insight = GeminiInsight(
            linkedin_hook="🚀 Testing hook",
            strategic_value="* Point 1\n* Point 2\n* **Consulting Pivot:** Pivot angle",
            program_validation_status="Verified via ISED GC Business Insights",
            export_risk_advisory="EDC Trade Credit Insurance recommended"
        )
        self.assertEqual(insight.program_validation_status, "Verified via ISED GC Business Insights")
        self.assertEqual(insight.export_risk_advisory, "EDC Trade Credit Insurance recommended")
        d = insight.to_dict()
        self.assertIn("program_validation_status", d)
        self.assertIn("export_risk_advisory", d)

    def test_kpi_dashboard_macro_indicators(self):
        kpi = KPIDashboard(
            total_active=10,
            macro_indicators={
                "gdp_nowcast_quarter": "Q2 2026",
                "gdp_nowcast_estimate": "+4.61%"
            }
        )
        self.assertEqual(kpi.macro_indicators["gdp_nowcast_quarter"], "Q2 2026")
        d = kpi.to_dict()
        self.assertIn("macro_indicators", d)

    def test_ised_newsletter_extraction_structure(self):
        # Perform live sanity test on ISED newsletter extractor
        items = fetch_ised_business_insights(max_issues=1)
        self.assertIsInstance(items, list)
        if items:
            first = items[0]
            self.assertIn("title", first)
            self.assertIn("url", first)
            self.assertEqual(first["source_name"], "ISED_GC_Business_Insights")
            print(f"  PASS: Successfully extracted {len(items)} items from ISED Business Insights.")

if __name__ == "__main__":
    unittest.main()
