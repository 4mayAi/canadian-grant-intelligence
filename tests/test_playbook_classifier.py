"""Unit tests for determine_recommended_playbook() classifier."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from generic_engine.extractors.ckan import determine_recommended_playbook


def test_acan_by_notice_type():
    result = determine_recommended_playbook("Advance Contract Award Notice (ACAN)", "", "")
    assert result == "Downstream Pivot (Sole-Source / ACAN)", f"Expected Downstream Pivot, got: {result}"


def test_acan_by_procurement_method():
    result = determine_recommended_playbook("", "Advance Contract Award Notice", "")
    assert result == "Downstream Pivot (Sole-Source / ACAN)", f"Expected Downstream Pivot, got: {result}"


def test_supply_arrangement():
    result = determine_recommended_playbook("RFP against Supply Arrangement", "", "")
    assert result == "Selective Partnering (Supply Arrangement)", f"Expected Selective Partnering, got: {result}"


def test_selective_tendering():
    result = determine_recommended_playbook("", "Selective Tendering", "")
    assert result == "Selective Partnering (Supply Arrangement)", f"Expected Selective Partnering, got: {result}"


def test_invitation_to_qualify():
    result = determine_recommended_playbook("Invitation to Qualify", "", "")
    assert result == "Prime-Tracking (Pre-Qualification)", f"Expected Prime-Tracking, got: {result}"


def test_standing_offer():
    result = determine_recommended_playbook("Request for Standing Offer", "", "")
    assert result == "Procurement Gateway Entry (RFSO / RFSA)", f"Expected Procurement Gateway Entry, got: {result}"


def test_rfi():
    result = determine_recommended_playbook("Request for Information", "", "")
    assert result == "Specification Shaping (RFI / EOI)", f"Expected Specification Shaping, got: {result}"


def test_eoi_in_description():
    result = determine_recommended_playbook("", "", "This is an Expression of Interest for consulting services")
    assert result == "Specification Shaping (RFI / EOI)", f"Expected Specification Shaping, got: {result}"


def test_standard_rfp():
    result = determine_recommended_playbook("Request for Proposal", "", "")
    assert result == "Standard Competitive Bidding (RFP)", f"Expected Standard Competitive Bidding, got: {result}"


def test_competitive_method():
    result = determine_recommended_playbook("", "Competitive", "")
    assert result == "Standard Competitive Bidding (RFP)", f"Expected Standard Competitive Bidding, got: {result}"


def test_empty_returns_unclassified():
    result = determine_recommended_playbook("", "", "")
    assert result == "Unclassified", f"Expected Unclassified, got: {result}"


def test_none_returns_unclassified():
    result = determine_recommended_playbook(None, None, None)
    assert result == "Unclassified", f"Expected Unclassified, got: {result}"


def test_not_applicable_returns_unclassified():
    result = determine_recommended_playbook("Not Applicable", "", "")
    assert result == "Unclassified", f"Expected Unclassified, got: {result}"


def test_priority_acan_over_rfp():
    """ACAN check must fire before RFP even if notice_type contains both terms."""
    result = determine_recommended_playbook("Advance Contract Award Notice (ACAN)", "Competitive", "Request for Proposal")
    assert result == "Downstream Pivot (Sole-Source / ACAN)", f"Expected Downstream Pivot, got: {result}"


def test_priority_supply_arrangement_over_rfp():
    """Supply Arrangement check must fire before standard RFP."""
    result = determine_recommended_playbook("RFP against Supply Arrangement", "Competitive", "")
    assert result == "Selective Partnering (Supply Arrangement)", f"Expected Selective Partnering, got: {result}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  PASS  {test_fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests.")
    sys.exit(1 if failed else 0)
