#!/usr/bin/env python3
"""
test_manage_finance.py - Test suite for manage_finance.py.
Verifies CRA Form T2125 line mapping, place of supply rules, US zero-rated export calculations,
foreign digital SaaS tax routing, SHA-256 receipt deduplication, and GST34 return reconciliation.
"""

import os
import sys
import shutil
import tempfile
import unittest

# Ensure workspace root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import scripts.manage_finance as mf


class TestManageFinance(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.orig_financial_dir = mf.FINANCIAL_DIR
        self.orig_receipts_dir = mf.RECEIPTS_DIR
        self.orig_ledger_path = mf.LEDGER_PATH

        mf.FINANCIAL_DIR = os.path.join(self.test_dir, "financial")
        mf.RECEIPTS_DIR = os.path.join(mf.FINANCIAL_DIR, "receipts")
        mf.LEDGER_PATH = os.path.join(mf.FINANCIAL_DIR, "ledger.csv")
        mf.init_ledger(force=True)

    def tearDown(self):
        mf.FINANCIAL_DIR = self.orig_financial_dir
        mf.RECEIPTS_DIR = self.orig_receipts_dir
        mf.LEDGER_PATH = self.orig_ledger_path
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_ledger_initialization(self):
        """Test ledger creation and header correctness."""
        self.assertTrue(os.path.exists(mf.LEDGER_PATH))
        self.assertTrue(os.path.exists(mf.RECEIPTS_DIR))
        records = mf.read_ledger()
        self.assertEqual(len(records), 0)

    def test_log_canadian_income_ontario_hst(self):
        """Test Canadian client in Ontario subject to 13% HST."""
        row = mf.log_income(
            date="2026-09-01",
            invoice_id="INV-CA-001",
            client="Toronto Enterprise Ltd",
            jurisdiction="ON",
            currency="CAD",
            amount=10000.00,
            fx_rate=1.0,
            notes="Grant intelligence consulting",
        )
        self.assertEqual(row["Transaction_ID"], "INV-CA-001")
        self.assertEqual(row["Net_Amount_CAD"], "10000.00")
        self.assertEqual(row["GST_HST_Paid_Claimable"], "1300.00")  # 13% of 10,000
        self.assertEqual(row["Total_Amount_CAD"], "11300.00")
        self.assertEqual(row["Tax_Type"], "DOMESTIC_TAXABLE")

    def test_log_us_export_zero_rated(self):
        """Test US client export: 0% GST/HST zero-rated, converted from USD to CAD."""
        row = mf.log_income(
            date="2026-09-02",
            invoice_id="INV-US-001",
            client="Delaware Tech Inc",
            jurisdiction="US",
            currency="USD",
            amount=5000.00,
            fx_rate=1.35,
            notes="Cross-border market advisory",
        )
        self.assertEqual(row["Transaction_ID"], "INV-US-001")
        self.assertEqual(row["Tax_Type"], "ZERO_RATED_EXPORT")
        self.assertEqual(row["GST_HST_Paid_Claimable"], "0.00")  # 0% tax
        self.assertEqual(row["Net_Amount_CAD"], "6750.00")  # 5000 * 1.35
        self.assertEqual(row["Total_Amount_CAD"], "6750.00")

    def test_duplicate_invoice_id_rejected(self):
        """Test that duplicate invoice IDs are strictly rejected."""
        mf.log_income(
            date="2026-09-01",
            invoice_id="INV-DUP-01",
            client="Client A",
            jurisdiction="BC",
            currency="CAD",
            amount=1000.00,
        )
        with self.assertRaises(ValueError):
            mf.log_income(
                date="2026-09-02",
                invoice_id="INV-DUP-01",
                client="Client B",
                jurisdiction="BC",
                currency="CAD",
                amount=2000.00,
            )

    def test_standard_canadian_expense_with_itc(self):
        """Test regular Canadian vendor with eligible Input Tax Credit."""
        row = mf.log_expense(
            date="2026-09-03",
            ref_id="EXP-AZURE-01",
            vendor="Microsoft Canada",
            line_code="8760",
            currency="CAD",
            amount=200.00,
            fx_rate=1.0,
            tax_type="STANDARD_ITC",
            gst_paid=10.00,
            notes="Cloud infrastructure hosting",
        )
        self.assertEqual(row["GST_HST_Paid_Claimable"], "10.00")  # Eligible ITC
        self.assertEqual(row["Deductible_Amount_CAD"], "200.00")  # Base expense on T2125
        self.assertEqual(row["Total_Amount_CAD"], "210.00")

    def test_simplified_digital_saas_no_itc_tax_is_deductible(self):
        """Test foreign SaaS (e.g. OpenAI EU ID) where GST is NOT an ITC, but a deductible expense."""
        row = mf.log_expense(
            date="2026-09-04",
            ref_id="EXP-OPENAI-01",
            vendor="OpenAI LLC",
            line_code="9270",
            currency="USD",
            amount=100.00,
            fx_rate=1.35,
            tax_type="SIMPLIFIED_DIGITAL",
            gst_paid=5.00,  # $5 USD digital tax
            notes="AI API token compute",
        )
        # 105 USD * 1.35 = 141.75 CAD total
        self.assertEqual(row["GST_HST_Paid_Claimable"], "0.00")  # Must be 0 ITC!
        self.assertEqual(row["Total_Amount_CAD"], "141.75")
        self.assertEqual(row["Deductible_Amount_CAD"], "141.75")  # Full cost including tax is deductible

    def test_meals_and_entertainment_50_percent_statutory_limit(self):
        """Test Line 8523 strictly applies CRA 50% deduction limit."""
        row = mf.log_expense(
            date="2026-09-05",
            ref_id="EXP-MEAL-01",
            vendor="Bistro Client Lunch",
            line_code="8523",
            currency="CAD",
            amount=100.00,
            fx_rate=1.0,
            tax_type="STANDARD_ITC",
            gst_paid=5.00,
            notes="B2B client business lunch",
        )
        self.assertEqual(row["Deductible_Amount_CAD"], "50.00")  # 50% of 100
        self.assertEqual(row["GST_HST_Paid_Claimable"], "5.00")

    def test_home_office_pro_rating(self):
        """Test pro-rated home office expenses (e.g. 25% of internet bill)."""
        row = mf.log_expense(
            date="2026-09-06",
            ref_id="EXP-TELCO-01",
            vendor="Telecom Provider",
            line_code="9945",
            currency="CAD",
            amount=120.00,
            fx_rate=1.0,
            tax_type="STANDARD_ITC",
            gst_paid=6.00,
            home_office_pct=25.0,
            notes="Home office gigabit fiber internet",
        )
        self.assertEqual(row["Deductible_Amount_CAD"], "30.00")  # 25% of 120

    def test_receipt_sha256_deduplication(self):
        """Test cryptographic receipt hashing and duplicate prevention."""
        receipt_path = os.path.join(self.test_dir, "sample_receipt.pdf")
        with open(receipt_path, "wb") as f:
            f.write(b"SAMPLE RECEIPT DATA FOR AUDIT PROOF")

        row1 = mf.log_expense(
            date="2026-09-07",
            ref_id="EXP-RCPT-01",
            vendor="Staples",
            line_code="8811",
            currency="CAD",
            amount=45.00,
            receipt_path=receipt_path,
        )
        self.assertTrue(len(row1["Receipt_Hash"]) > 0)
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, row1["Receipt_Path"])))

        # Attempting to log the same receipt file under a different ref ID must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            mf.log_expense(
                date="2026-09-08",
                ref_id="EXP-RCPT-02",
                vendor="Staples Copy",
                line_code="8811",
                currency="CAD",
                amount=45.00,
                receipt_path=receipt_path,
            )
        self.assertIn("Duplicate receipt detected", str(ctx.exception))

    def test_full_tax_report_reconciliation(self):
        """Test complete financial reporting reconciling GST34 Return and T2125."""
        # 1. Domestic Canadian Income: 10,000 CAD + 1,300 HST (ON)
        mf.log_income("2026-09-01", "INV-01", "Client CA", "ON", "CAD", 10000.0, 1.0)
        # 2. US Export Income: 4,000 USD * 1.35 = 5,400 CAD, 0 tax
        mf.log_income("2026-09-02", "INV-02", "Client US", "US", "USD", 4000.0, 1.35)

        # 3. Canadian Expense with ITC: 1,000 CAD + 50 GST (Line 8760)
        mf.log_expense("2026-09-03", "EXP-01", "Vendor CA", "8760", "CAD", 1000.0, 1.0, "STANDARD_ITC", 50.0)
        # 4. Foreign SaaS (OpenAI): 100 USD * 1.35 = 135 CAD deductible (Line 9270)
        mf.log_expense("2026-09-04", "EXP-02", "OpenAI", "9270", "USD", 100.0, 1.35, "SIMPLIFIED_DIGITAL", 0.0)

        report = mf.generate_report(year=2026, report_format="json")

        gst = report["gst_return"]
        self.assertEqual(gst["Line_101_Total_Sales"], 15400.00)  # 10,000 + 5,400
        self.assertEqual(gst["Line_101a_Domestic_Sales"], 10000.00)
        self.assertEqual(gst["Line_101b_Zero_Rated_Export_Sales"], 5400.00)
        self.assertEqual(gst["Line_105_Total_GST_HST"], 1300.00)
        self.assertEqual(gst["Line_108_Total_ITCs"], 50.00)
        self.assertEqual(gst["Line_109_Net_Tax"], 1250.00)  # 1300 - 50 = 1250 owing
        self.assertEqual(gst["Remittance_Status"], "AMOUNT_OWING")

        t21 = report["t2125"]
        self.assertEqual(t21["Part_3C_Gross_Income"], 15400.00)
        self.assertEqual(t21["Total_Deductible_Expenses"], 1135.00)  # 1000 + 135
        self.assertEqual(t21["Net_Business_Income"], 14265.00)  # 15400 - 1135


if __name__ == "__main__":
    unittest.main()
