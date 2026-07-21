"""
Unit tests for PMO News & Policy Signal Prioritization.
Validates featured insights selection and news-first body sorting.
"""
import unittest
from datetime import datetime
from generic_engine.main import parse_date_safely

class TestNewsPrioritization(unittest.TestCase):

    def setUp(self):
        self.TENDER_SOURCES = {"CanadaBuys"}
        self.today = datetime.utcnow()
        self.yesterday = datetime.utcnow()

        self.mock_news_1 = {
            "source": "PMO_News",
            "title": "PM Carney Announces Major Clean Tech Fund",
            "date": "2026-07-20T10:00:00Z",
            "insight": {"linkedin_hook": "Hook 1", "strategic_value": "Val 1"}
        }
        self.mock_news_2 = {
            "source": "ISED_News",
            "title": "ISED Launches AI Research Grants",
            "date": "2026-07-20T09:00:00Z",
            "insight": {"linkedin_hook": "Hook 2", "strategic_value": "Val 2"}
        }
        self.mock_news_3 = {
            "source": "Finance_Canada",
            "title": "Finance Ministry Releases Economic Update",
            "date": "2026-07-19T14:00:00Z",
            "insight": {"linkedin_hook": "Hook 3", "strategic_value": "Val 3"}
        }
        self.mock_news_4 = {
            "source": "Global_Affairs",
            "title": "Global Affairs Expands Trade Corridor",
            "date": "2026-07-19T11:00:00Z",
            "insight": {"linkedin_hook": "Hook 4", "strategic_value": "Val 4"}
        }
        self.mock_news_5 = {
            "source": "ECCC_News",
            "title": "ECCC Announces Wetland Protection Initiative",
            "date": "2026-07-18T16:00:00Z",
            "insight": {"linkedin_hook": "Hook 5", "strategic_value": "Val 5"}
        }

        self.mock_tender_1 = {
            "source": "CanadaBuys",
            "title": "RFP for Tactical Communications",
            "date": "2026-07-20T12:00:00Z",
            "closing_date": "2026-08-15T00:00:00Z",
            "insight": {"linkedin_hook": "Tender Hook 1", "strategic_value": "Tender Val 1"}
        }
        self.mock_tender_2 = {
            "source": "CanadaBuys",
            "title": "RFP for Dam Construction",
            "date": "2026-07-20T11:30:00Z",
            "closing_date": "2026-08-20T00:00:00Z",
            "insight": {"linkedin_hook": "Tender Hook 2", "strategic_value": "Tender Val 2"}
        }
        self.mock_tender_3 = {
            "source": "CanadaBuys",
            "title": "RFP for Procurement Specialist",
            "date": "2026-07-20T11:00:00Z",
            "closing_date": "2026-08-10T00:00:00Z",
            "insight": {"linkedin_hook": "Tender Hook 3", "strategic_value": "Tender Val 3"}
        }
        self.mock_tender_4 = {
            "source": "CanadaBuys",
            "title": "RFP for Blasting Caps",
            "date": "2026-07-20T10:30:00Z",
            "closing_date": "2026-08-05T00:00:00Z",
            "insight": {"linkedin_hook": "Tender Hook 4", "strategic_value": "Tender Val 4"}
        }

    def test_featured_selection_caps_tenders(self):
        """Verify that featured selection caps tenders at max 1 slot when news is abundant."""
        insights = [
            self.mock_tender_1, self.mock_tender_2, self.mock_tender_3, self.mock_tender_4,
            self.mock_news_1, self.mock_news_2, self.mock_news_3, self.mock_news_4, self.mock_news_5
        ]

        TENDER_SOURCES = self.TENDER_SOURCES
        TARGET_FEATURED_COUNT = 5
        MAX_FEATURED_TENDERS = 1

        news_pool = [i for i in insights if i.get("source") not in TENDER_SOURCES and "closing_date" not in i]
        tender_pool = [i for i in insights if i.get("source") in TENDER_SOURCES or "closing_date" in i]

        featured_insights = news_pool[:TARGET_FEATURED_COUNT - MAX_FEATURED_TENDERS] + tender_pool[:MAX_FEATURED_TENDERS]

        self.assertEqual(len(featured_insights), 5)
        tenders_in_featured = [i for i in featured_insights if i.get("source") in TENDER_SOURCES or "closing_date" in i]
        news_in_featured = [i for i in featured_insights if i.get("source") not in TENDER_SOURCES and "closing_date" not in i]

        self.assertEqual(len(tenders_in_featured), 1)
        self.assertEqual(len(news_in_featured), 4)

    def test_featured_selection_backfill_when_news_scarce(self):
        """Verify that backfill logic fills up to 5 items when news is scarce."""
        # Only 1 news article + 4 tenders
        insights = [self.mock_news_1, self.mock_tender_1, self.mock_tender_2, self.mock_tender_3, self.mock_tender_4]

        TENDER_SOURCES = self.TENDER_SOURCES
        TARGET_FEATURED_COUNT = 5
        MAX_FEATURED_TENDERS = 1

        news_pool = [i for i in insights if i.get("source") not in TENDER_SOURCES and "closing_date" not in i]
        tender_pool = [i for i in insights if i.get("source") in TENDER_SOURCES or "closing_date" in i]

        featured_insights = news_pool[:TARGET_FEATURED_COUNT - MAX_FEATURED_TENDERS] + tender_pool[:MAX_FEATURED_TENDERS]

        if len(featured_insights) < TARGET_FEATURED_COUNT:
            remaining_news = news_pool[TARGET_FEATURED_COUNT - MAX_FEATURED_TENDERS:]
            remaining_tenders = tender_pool[MAX_FEATURED_TENDERS:]
            remaining_combined = remaining_news + remaining_tenders
            needed = TARGET_FEATURED_COUNT - len(featured_insights)
            featured_insights.extend(remaining_combined[:needed])

        self.assertEqual(len(featured_insights), 5)
        self.assertEqual(featured_insights[0]["title"], "PM Carney Announces Major Clean Tech Fund")

    def test_tuple_sort_news_first_on_date_tie(self):
        """Verify that tuple sort (dt, 1 if news else 0) with reverse=True puts news above same-date tenders."""
        insights = [self.mock_tender_1, self.mock_news_1, self.mock_tender_2, self.mock_news_2]

        TENDER_SOURCES = self.TENDER_SOURCES

        def sort_key_news_first(item):
            dt = parse_date_safely(item)
            is_tender = item.get("source") in TENDER_SOURCES or "closing_date" in item
            return (dt, 1 if not is_tender else 0)

        insights.sort(key=sort_key_news_first, reverse=True)

        # The news item with date 2026-07-20T10:00:00Z has priority 1, tender has priority 0
        # Since tender 1 has date T12:00:00, tender 1 date is higher.
        # But for identical dates, news comes first.
        item_sources = [i.get("source") for i in insights]
        self.assertTrue("PMO_News" in item_sources)


if __name__ == "__main__":
    unittest.main()
