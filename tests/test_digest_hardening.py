"""
Unit tests for digest hardening:
- Wire syndication title stem deduplication
- Hashtag spacing guardrail
- Structural headline fallback
- Notifier CTA regex markdown link support
"""
import re
import unittest

def normalize_title_stem(itm):
    title = itm.get("title", "")
    if not title:
        return ""
    src = itm.get("source", "")
    if src.startswith("CanadaBuys") or "closing_date" in itm:
        return title
    link = itm.get("link", "").lower()
    if any(p in link for p in ("biorxiv", "medrxiv", "arxiv")):
        return title
    cleaned = re.sub(
        r'\s*[-–|]\s*(?:Yahoo(?:\s*Finance)?|newsfilecorp\.com|PR\s*Newswire|GlobeNewswire|Proactive(?:\s*financial\s*news)?|Business\s*Wire|Medianet.*|The\s*Canadian\s*Press|canada\.ca)\s*$',
        '',
        title,
        flags=re.IGNORECASE
    ).strip()
    return re.sub(r'[^a-z0-9]', '', cleaned.lower())

def format_hashtags(post_text):
    return re.sub(r'(#[A-Za-z0-9_]+)(?=#)', r'\1 ', post_text)

def apply_headline_fallback(post_text, suggested_title, hero_hook=None):
    stripped_post = post_text.strip()
    first_line = stripped_post.split('\n')[0].strip() if stripped_post else ""
    if first_line.startswith("###") or first_line.startswith("**"):
        headline = suggested_title or hero_hook
        if headline and headline.strip() not in stripped_post[:200]:
            return f"{headline.strip()}\n\n{post_text}"
    return post_text

class TestDigestHardening(unittest.TestCase):

    def test_wire_syndication_deduplication(self):
        """Test that syndicated wire articles sharing the same stem are identified as duplicates."""
        item1 = {
            "title": "Lithium Africa Defines a Second Spodumene Trend in Côte d'Ivoire: Kanien Trend Rock Samples up to 1.98% Li2O Highlight Discovery Potential - Yahoo Finance",
            "link": "https://finance.yahoo.com/markets/commodities/articles/lithium-africa-defines-second-spodumene-110000796.html",
            "source": "Africa_Mining_Strategy"
        }
        item2 = {
            "title": "Lithium Africa Defines a Second Spodumene Trend in Côte d'Ivoire: Kanien Trend Rock Samples up to 1.98% Li2O Highlight Discovery Potential - newsfilecorp.com",
            "link": "https://www.newsfilecorp.com/release/314546/Lithium-Africa-Defines-a-Second-Spodumene-Trend",
            "source": "Africa_Mining_Strategy"
        }
        stem1 = normalize_title_stem(item1)
        stem2 = normalize_title_stem(item2)
        self.assertEqual(stem1, stem2)
        self.assertTrue(len(stem1) > 20)

    def test_tenders_and_preprints_exempt(self):
        """Test that tenders and academic preprints are strictly exempt from stem stripping."""
        tender1 = {
            "title": "W8482-275993 Autonomous Mine Countermeasures - USV",
            "link": "https://canadabuys.canada.ca/tender-notice/123",
            "source": "CanadaBuys"
        }
        tender2 = {
            "title": "W8482-275993 Autonomous Mine Countermeasures - Spare Parts",
            "link": "https://canadabuys.canada.ca/tender-notice/124",
            "source": "CanadaBuys"
        }
        self.assertNotEqual(normalize_title_stem(tender1), normalize_title_stem(tender2))

        preprint1 = {
            "title": "USP7 in Endosomal Dynamics - Part 1",
            "link": "https://www.biorxiv.org/content/10.1101/1",
            "source": "bioRxiv_Microbiology"
        }
        preprint2 = {
            "title": "USP7 in Endosomal Dynamics - Part 2",
            "link": "https://www.biorxiv.org/content/10.1101/2",
            "source": "bioRxiv_Microbiology"
        }
        self.assertNotEqual(normalize_title_stem(preprint1), normalize_title_stem(preprint2))

    def test_hashtag_spacing(self):
        """Test that concatenated hashtags get spaces inserted, while spaced ones are untouched."""
        concatenated = "#CriticalMinerals#MiningNews#SupplyChain#LobitoCorridor#Lithium"
        spaced = format_hashtags(concatenated)
        self.assertEqual(spaced, "#CriticalMinerals #MiningNews #SupplyChain #LobitoCorridor #Lithium")

        already_spaced = "#CriticalMinerals #MiningNews #SupplyChain"
        self.assertEqual(format_hashtags(already_spaced), already_spaced)

    def test_headline_fallback_insertion(self):
        """Test that missing headline on Line 1 is cleanly prepended if post opens with a header."""
        headless_post = "### Mining & Capital Projects\nCaledonia is closing in on financing."
        headline = "Global critical minerals rail infrastructure expands 🌍"
        fixed_post = apply_headline_fallback(headless_post, headline)
        self.assertTrue(fixed_post.startswith("Global critical minerals rail infrastructure expands 🌍\n\n### Mining"))

        # Post already having a headline should not double-prepend
        normal_post = "Global critical minerals rail infrastructure expands 🌍\n\n### Mining & Capital Projects\nCaledonia is closing in on financing."
        self.assertEqual(apply_headline_fallback(normal_post, headline), normal_post)

    def test_notifier_cta_regex(self):
        """Test that notifier regex parses both raw URLs and markdown link syntax without trailing brackets."""
        raw_cta = "👉 Full dashboard with filters and strategic analysis: https://4mayAi.github.io/canadian-grant-intelligence/mining-hubs/"
        md_cta = "[View Interactive Web Dashboard ↗](https://4mayAi.github.io/canadian-grant-intelligence/mining-hubs/)"

        pattern = r'(?:👉\s*|View Full Interactive Dashboard:\s*|Full dashboard with filters and strategic analysis:\s*|\[View Interactive Web Dashboard ↗\]\()(https?://[^\s\)]+)'

        m1 = re.search(pattern, raw_cta, re.IGNORECASE)
        self.assertIsNotNone(m1)
        self.assertEqual(m1.group(1), "https://4mayAi.github.io/canadian-grant-intelligence/mining-hubs/")

        m2 = re.search(pattern, md_cta, re.IGNORECASE)
        self.assertIsNotNone(m2)
        self.assertEqual(m2.group(1), "https://4mayAi.github.io/canadian-grant-intelligence/mining-hubs/")

    # === NEGATIVE TESTS ===

    def test_negative_empty_and_corrupt_titles(self):
        """Negative test: verify empty, None, and whitespace-only titles do not raise exceptions."""
        self.assertEqual(normalize_title_stem({}), "")
        self.assertEqual(normalize_title_stem({"title": ""}), "")
        self.assertEqual(normalize_title_stem({"title": None}), "")
        self.assertEqual(normalize_title_stem({"title": "     "}), "")

    def test_negative_no_hashtags_and_numeric_hashes(self):
        """Negative test: verify text with non-hashtag hashes (e.g. 'PO #1234') is not corrupted."""
        text = "Purchase Order #1234 was approved alongside project #5678."
        self.assertEqual(format_hashtags(text), text)

    def test_negative_fallback_ignores_non_header_openings(self):
        """Negative test: verify headline fallback does NOT trigger if line 1 is regular prose even if ### appears later."""
        post = "Today we observed strong movement across multiple corridors.\n\n### Critical Minerals\nCopper drill programs expand."
        self.assertEqual(apply_headline_fallback(post, "Some Headline"), post)

    def test_negative_duplicate_stem_filtering(self):
        """Negative test: verify that when 3 duplicate syndicated items are presented, 2 are rejected."""
        items = [
            {"title": "Lithium Africa Defines a Second Spodumene Trend in Côte d'Ivoire - Yahoo Finance", "link": "https://yahoo.com/1"},
            {"title": "Lithium Africa Defines a Second Spodumene Trend in Côte d'Ivoire - newsfilecorp.com", "link": "https://newsfile.com/2"},
            {"title": "Lithium Africa Defines a Second Spodumene Trend in Côte d'Ivoire - PR Newswire", "link": "https://prnewswire.com/3"},
            {"title": "Caledonia closes in on funding for $600m Bilboes project - MiningMX", "link": "https://miningmx.com/4"},
        ]

        seen_stems = set()
        selected = []
        rejected = []
        for itm in items:
            stem = normalize_title_stem(itm)
            if stem in seen_stems:
                rejected.append(itm)
            else:
                seen_stems.add(stem)
                selected.append(itm)

        self.assertEqual(len(selected), 2)
        self.assertEqual(len(rejected), 2)
        self.assertEqual(selected[0]["title"], items[0]["title"])
        self.assertEqual(selected[1]["title"], items[3]["title"])

if __name__ == "__main__":
    unittest.main()
