#!/usr/bin/env python3
"""
manage_finance.py - Local Bookkeeping & Strategic Tax Engine for MAYAI MARKET INTELLIGENCE.
Compliant with CRA Form T2125, Excise Tax Act (GST/HST), and cross-border export zero-rating rules.
"""

import os
import sys
import csv
import hashlib
import shutil
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Platform-independent root path resolution
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FINANCIAL_DIR = os.path.join(PROJECT_ROOT, "docs", "financial")
RECEIPTS_DIR = os.path.join(FINANCIAL_DIR, "receipts")
LEDGER_PATH = os.path.join(FINANCIAL_DIR, "ledger.csv")

LEDGER_HEADERS = [
    "Transaction_ID",
    "Date",
    "Type",
    "Entity_Name",
    "Jurisdiction",
    "Currency",
    "FX_Rate",
    "Gross_Amount_Orig",
    "Tax_Type",
    "GST_HST_Paid_Claimable",
    "Net_Amount_CAD",
    "Total_Amount_CAD",
    "T2125_Line",
    "T2125_Category",
    "Home_Office_Pct",
    "Deductible_Amount_CAD",
    "Receipt_Hash",
    "Receipt_Path",
    "Notes",
]

# Statutory CRA Form T2125 Part 17 Line Mapping
T2125_LINES = {
    "8521": "Advertising",
    "8523": "Meals and entertainment (50% statutory limit)",
    "8690": "Insurance",
    "8710": "Interest and bank charges (FX & payment fees)",
    "8760": "Business taxes, licenses, memberships, subscriptions",
    "8810": "Office expenses (non-capital software/hardware)",
    "8811": "Office stationery and supplies",
    "8860": "Professional fees (legal and accounting)",
    "8871": "Management and administration fees",
    "8910": "Rent",
    "9200": "Travel expenses",
    "9220": "Utilities",
    "9270": "Other expenses (AI tokens, cloud compute, data feeds)",
    "9945": "Business-use-of-home expenses",
}

# Canadian Place of Supply GST/HST Rates (Excise Tax Act)
PLACE_OF_SUPPLY_RATES = {
    "ON": 0.13,
    "NS": 0.15,
    "NB": 0.15,
    "NL": 0.15,
    "PE": 0.15,
    "AB": 0.05,
    "BC": 0.05,
    "MB": 0.05,
    "SK": 0.05,
    "QC": 0.05,  # Federal GST portion
    "NT": 0.05,
    "YT": 0.05,
    "NU": 0.05,
    "US": 0.00,  # Zero-rated export (Schedule VI, Part V)
    "INTL": 0.00,  # Zero-rated export
}


def ensure_directories():
    """Ensure docs/financial and docs/financial/receipts directories exist."""
    os.makedirs(FINANCIAL_DIR, exist_ok=True)
    os.makedirs(RECEIPTS_DIR, exist_ok=True)


def init_ledger(force: bool = False):
    """Initialize ledger.csv if it does not already exist."""
    ensure_directories()
    if not os.path.exists(LEDGER_PATH) or force:
        with open(LEDGER_PATH, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(LEDGER_HEADERS)
        print(f"Initialized financial ledger at: {LEDGER_PATH}")
    else:
        print(f"Financial ledger already exists at: {LEDGER_PATH}")


def read_ledger() -> List[Dict[str, str]]:
    """Read all entries from the ledger."""
    if not os.path.exists(LEDGER_PATH):
        init_ledger()
        return []
    with open(LEDGER_PATH, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def compute_file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file for cryptographic audit integrity."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def log_income(
    date: str,
    invoice_id: str,
    client: str,
    jurisdiction: str,
    currency: str,
    amount: float,
    fx_rate: float = 1.0,
    notes: str = "",
) -> Dict[str, str]:
    """
    Log an income transaction (client payment / invoice).
    Calculates applicable GST/HST based on jurisdiction place of supply.
    Zero-rates US/International exports while preserving gross taxable revenue in CAD.
    """
    ensure_directories()
    records = read_ledger()

    # Check for duplicate Invoice ID
    for row in records:
        if row.get("Type") == "Income" and row.get("Transaction_ID") == invoice_id:
            raise ValueError(f"Duplicate Invoice ID '{invoice_id}' already exists in ledger.")

    jur_clean = jurisdiction.upper().strip()
    tax_rate = PLACE_OF_SUPPLY_RATES.get(jur_clean, 0.0)

    tax_type = "ZERO_RATED_EXPORT" if jur_clean in ["US", "INTL"] else "DOMESTIC_TAXABLE"
    if jur_clean not in PLACE_OF_SUPPLY_RATES:
        # Default to 0.0 if international
        tax_type = "ZERO_RATED_EXPORT"

    net_orig = amount
    tax_orig = round(net_orig * tax_rate, 2)
    gross_orig = round(net_orig + tax_orig, 2)

    net_cad = round(net_orig * fx_rate, 2)
    tax_cad = round(tax_orig * fx_rate, 2)
    total_cad = round(gross_orig * fx_rate, 2)

    row = {
        "Transaction_ID": invoice_id,
        "Date": date,
        "Type": "Income",
        "Entity_Name": client,
        "Jurisdiction": jur_clean,
        "Currency": currency.upper().strip(),
        "FX_Rate": f"{fx_rate:.4f}",
        "Gross_Amount_Orig": f"{gross_orig:.2f}",
        "Tax_Type": tax_type,
        "GST_HST_Paid_Claimable": f"{tax_cad:.2f}",  # GST/HST collected (in CAD)
        "Net_Amount_CAD": f"{net_cad:.2f}",
        "Total_Amount_CAD": f"{total_cad:.2f}",
        "T2125_Line": "Part3C",
        "T2125_Category": "Gross Sales/Professional Fees",
        "Home_Office_Pct": "0.0",
        "Deductible_Amount_CAD": "0.0",
        "Receipt_Hash": "",
        "Receipt_Path": "",
        "Notes": notes,
    }

    with open(LEDGER_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_HEADERS)
        writer.writerow(row)

    print(f"Logged Income [{invoice_id}] from {client} ({currency} {net_orig:.2f} -> CAD {net_cad:.2f}, Tax: CAD {tax_cad:.2f})")
    return row


def log_expense(
    date: str,
    ref_id: str,
    vendor: str,
    line_code: str,
    currency: str,
    amount: float,
    fx_rate: float = 1.0,
    tax_type: str = "STANDARD_ITC",
    gst_paid: float = 0.0,
    home_office_pct: float = 0.0,
    receipt_path: Optional[str] = None,
    notes: str = "",
) -> Dict[str, str]:
    """
    Log a business expense.
    Handles:
    - Input Tax Credit (ITC) eligibility vs Foreign Simplified Digital tax.
    - 50% statutory deduction limit for meals/entertainment (Line 8523).
    - Pro-rated home office expenses (Line 9945 or home-office-pct).
    - Cryptographic SHA-256 receipt deduplication and immutable archiving.
    """
    ensure_directories()
    records = read_ledger()

    # Check for duplicate Reference ID
    for row in records:
        if row.get("Type") == "Expense" and row.get("Transaction_ID") == ref_id:
            raise ValueError(f"Duplicate Expense Ref ID '{ref_id}' already exists in ledger.")

    line_clean = str(line_code).strip()
    if line_clean not in T2125_LINES:
        raise ValueError(f"Invalid T2125 Line Code '{line_code}'. Allowed lines: {list(T2125_LINES.keys())}")

    category_name = T2125_LINES[line_clean]

    # Receipt processing and SHA-256 fingerprinting
    receipt_hash = ""
    archived_receipt_rel_path = ""

    if receipt_path and os.path.exists(receipt_path):
        receipt_hash = compute_file_sha256(receipt_path)
        # Check if hash already exists in ledger
        for row in records:
            if row.get("Receipt_Hash") and row.get("Receipt_Hash") == receipt_hash:
                raise ValueError(
                    f"Duplicate receipt detected! File hash {receipt_hash[:8]} was already claimed in transaction '{row.get('Transaction_ID')}'."
                )

        ext = os.path.splitext(receipt_path)[1].lower() or ".pdf"
        sanitized_vendor = "".join(c if c.isalnum() else "_" for c in vendor).strip("_")
        dest_filename = f"{date}_{sanitized_vendor}_{amount:.2f}_{receipt_hash[:8]}{ext}"
        dest_full_path = os.path.join(RECEIPTS_DIR, dest_filename)
        shutil.copy2(receipt_path, dest_full_path)
        archived_receipt_rel_path = os.path.relpath(dest_full_path, PROJECT_ROOT).replace("\\", "/")

    # Tax & Deduction Calculations
    tax_type_clean = tax_type.upper().strip()
    # If Simplified Digital (e.g. OpenAI/Anthropic EU ID), GST cannot be claimed as an ITC; it is added to the deductible expense.
    claimable_itc_cad = 0.0
    net_orig = amount
    gst_orig = gst_paid
    gross_orig = net_orig + gst_orig

    net_cad = round(net_orig * fx_rate, 2)
    gst_cad = round(gst_orig * fx_rate, 2)
    total_cad = round(gross_orig * fx_rate, 2)

    if tax_type_clean == "STANDARD_ITC":
        claimable_itc_cad = gst_cad
        base_expense_cad = net_cad
    elif tax_type_clean == "SIMPLIFIED_DIGITAL":
        # GST is not an ITC, but part of deductible business expense
        claimable_itc_cad = 0.0
        base_expense_cad = total_cad
    else:  # NONE or EXEMPT
        claimable_itc_cad = 0.0
        base_expense_cad = total_cad

    # Apply statutory limits
    deductible_cad = base_expense_cad
    if line_clean == "8523":  # Meals & Entertainment: 50% CRA limit
        deductible_cad = round(deductible_cad * 0.50, 2)
    elif home_office_pct > 0:  # Pro-rated Home Office
        pct_factor = min(max(home_office_pct, 0.0), 100.0) / 100.0
        deductible_cad = round(deductible_cad * pct_factor, 2)
    elif line_clean == "9945":
        # If line 9945 is selected without home_office_pct, assume 100% of the allocated portion was entered
        pass

    row = {
        "Transaction_ID": ref_id,
        "Date": date,
        "Type": "Expense",
        "Entity_Name": vendor,
        "Jurisdiction": "CA" if tax_type_clean == "STANDARD_ITC" else "FOREIGN",
        "Currency": currency.upper().strip(),
        "FX_Rate": f"{fx_rate:.4f}",
        "Gross_Amount_Orig": f"{gross_orig:.2f}",
        "Tax_Type": tax_type_clean,
        "GST_HST_Paid_Claimable": f"{claimable_itc_cad:.2f}",
        "Net_Amount_CAD": f"{net_cad:.2f}",
        "Total_Amount_CAD": f"{total_cad:.2f}",
        "T2125_Line": line_clean,
        "T2125_Category": category_name,
        "Home_Office_Pct": f"{home_office_pct:.1f}",
        "Deductible_Amount_CAD": f"{deductible_cad:.2f}",
        "Receipt_Hash": receipt_hash,
        "Receipt_Path": archived_receipt_rel_path,
        "Notes": notes,
    }

    with open(LEDGER_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_HEADERS)
        writer.writerow(row)

    print(
        f"Logged Expense [{ref_id}] to {vendor} (CAD {total_cad:.2f}, Deductible: CAD {deductible_cad:.2f}, ITC: CAD {claimable_itc_cad:.2f})"
    )
    return row


def generate_report(year: Optional[int] = None, report_format: str = "summary") -> Dict:
    """
    Generate financial reports matching CRA GST/HST Return (GST34) and Form T2125.
    """
    records = read_ledger()
    if year:
        records = [r for r in records if r.get("Date", "").startswith(str(year))]

    total_sales_cad = 0.0
    domestic_sales_cad = 0.0
    export_sales_cad = 0.0
    gst_collected_cad = 0.0

    total_expenses_cad = 0.0
    total_deductible_cad = 0.0
    itcs_claimable_cad = 0.0

    t2125_expenses_by_line: Dict[str, float] = {line: 0.0 for line in T2125_LINES}

    for r in records:
        rtype = r.get("Type")
        if rtype == "Income":
            net_cad = float(r.get("Net_Amount_CAD", 0.0) or 0.0)
            tax_cad = float(r.get("GST_HST_Paid_Claimable", 0.0) or 0.0)
            tax_type = r.get("Tax_Type", "")

            total_sales_cad += net_cad
            gst_collected_cad += tax_cad

            if tax_type == "ZERO_RATED_EXPORT":
                export_sales_cad += net_cad
            else:
                domestic_sales_cad += net_cad

        elif rtype == "Expense":
            total_cad = float(r.get("Total_Amount_CAD", 0.0) or 0.0)
            ded_cad = float(r.get("Deductible_Amount_CAD", 0.0) or 0.0)
            itc_cad = float(r.get("GST_HST_Paid_Claimable", 0.0) or 0.0)
            line = r.get("T2125_Line", "")

            total_expenses_cad += total_cad
            total_deductible_cad += ded_cad
            itcs_claimable_cad += itc_cad

            if line in t2125_expenses_by_line:
                t2125_expenses_by_line[line] += ded_cad

    net_gst_remittance = round(gst_collected_cad - itcs_claimable_cad, 2)
    net_business_income = round(total_sales_cad - total_deductible_cad, 2)

    data = {
        "year": year or "All Time",
        "gst_return": {
            "Line_101_Total_Sales": round(total_sales_cad, 2),
            "Line_101a_Domestic_Sales": round(domestic_sales_cad, 2),
            "Line_101b_Zero_Rated_Export_Sales": round(export_sales_cad, 2),
            "Line_103_GST_HST_Collected": round(gst_collected_cad, 2),
            "Line_105_Total_GST_HST": round(gst_collected_cad, 2),
            "Line_106_ITCs_Claimable": round(itcs_claimable_cad, 2),
            "Line_108_Total_ITCs": round(itcs_claimable_cad, 2),
            "Line_109_Net_Tax": net_gst_remittance,
            "Remittance_Status": "REFUND_DUE" if net_gst_remittance < 0 else "AMOUNT_OWING",
        },
        "t2125": {
            "Part_3C_Gross_Income": round(total_sales_cad, 2),
            "Part_17_Operating_Expenses": {k: round(v, 2) for k, v in t2125_expenses_by_line.items() if v > 0},
            "Total_Deductible_Expenses": round(total_deductible_cad, 2),
            "Net_Business_Income": net_business_income,
        },
    }

    if report_format == "json":
        import json

        print(json.dumps(data, indent=2))
        return data

    year_str = f"FY {year}" if year else "All Time"
    print("=" * 70)
    print(f" MAYAI MARKET INTELLIGENCE - FINANCIAL & TAX REPORT ({year_str})")
    print("=" * 70)

    if report_format in ["summary", "gst-return"]:
        gst = data["gst_return"]
        print("\n--- [CRA GST/HST RETURN SCHEDULE (FORM GST34)] ---")
        print(f"  Line 101 - Total Sales & Revenue (CAD):        ${gst['Line_101_Total_Sales']:>10.2f}")
        print(f"    - Domestic Canadian Supplies:                ${gst['Line_101a_Domestic_Sales']:>10.2f}")
        print(f"    - Zero-Rated Export Supplies (US/Intl):      ${gst['Line_101b_Zero_Rated_Export_Sales']:>10.2f}")
        print(f"  Line 105 - Total GST/HST Collected:            ${gst['Line_105_Total_GST_HST']:>10.2f}")
        print(f"  Line 108 - Total Input Tax Credits (ITCs):     ${gst['Line_108_Total_ITCs']:>10.2f}")
        if gst["Line_109_Net_Tax"] < 0:
            print(f"  Line 109 - Net Tax REFUND Due from CRA:        ${abs(gst['Line_109_Net_Tax']):>10.2f} (Refund)")
        else:
            print(f"  Line 109 - Net Tax REMITTANCE Due to CRA:      ${gst['Line_109_Net_Tax']:>10.2f} (Owing)")

    if report_format in ["summary", "t2125"]:
        t21 = data["t2125"]
        print("\n--- [CRA FORM T2125 STATEMENT OF BUSINESS ACTIVITIES] ---")
        print(f"  Part 3C - Gross Business Income (CAD):         ${t21['Part_3C_Gross_Income']:>10.2f}")
        print("  Part 17 - Operating Expenses Breakdown:")
        if t21["Part_17_Operating_Expenses"]:
            for code, amt in t21["Part_17_Operating_Expenses"].items():
                desc = T2125_LINES.get(code, "Expense")
                print(f"    Line {code} ({desc:<42}): ${amt:>10.2f}")
        else:
            print("    (No deductible expenses logged for this period)")
        print(f"  Total Deductible Business Expenses:            ${t21['Total_Deductible_Expenses']:>10.2f}")
        print(f"  Net Business Income (Profit / Loss):           ${t21['Net_Business_Income']:>10.2f}")

    print("=" * 70 + "\n")
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Local Bookkeeping & Strategic Tax CLI for MAYAI MARKET INTELLIGENCE"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: init
    init_parser = subparsers.add_parser("init", help="Initialize financial ledger and receipt directory")
    init_parser.add_argument("--force", action="store_true", help="Force overwrite existing empty ledger")

    # Command: log-income
    inc_parser = subparsers.add_parser("log-income", help="Log client invoice or payment")
    inc_parser.add_argument("--date", required=True, help="Invoice/payment date (YYYY-MM-DD)")
    inc_parser.add_argument("--invoice-id", required=True, help="Unique Invoice Reference (e.g. INV-2026-001)")
    inc_parser.add_argument("--client", required=True, help="Client or organization name")
    inc_parser.add_argument("--jurisdiction", required=True, help="Place of Supply: ON, BC, AB, QC, US, INTL, etc.")
    inc_parser.add_argument("--currency", default="CAD", help="Currency code (CAD, USD, etc.)")
    inc_parser.add_argument("--amount", type=float, required=True, help="Pre-tax invoice subtotal in original currency")
    inc_parser.add_argument("--fx-rate", type=float, default=1.0, help="Exchange rate to CAD (1.0 for CAD)")
    inc_parser.add_argument("--notes", default="", help="Optional transaction description/notes")

    # Command: log-expense
    exp_parser = subparsers.add_parser("log-expense", help="Log business purchase or operating expense")
    exp_parser.add_argument("--date", required=True, help="Expense date (YYYY-MM-DD)")
    exp_parser.add_argument("--ref-id", required=True, help="Unique Expense Reference (e.g. EXP-2026-001)")
    exp_parser.add_argument("--vendor", required=True, help="Vendor or merchant name")
    exp_parser.add_argument(
        "--line-code",
        required=True,
        help=f"CRA T2125 Line Code ({', '.join(T2125_LINES.keys())})",
    )
    exp_parser.add_argument("--currency", default="CAD", help="Currency code (CAD, USD, etc.)")
    exp_parser.add_argument("--amount", type=float, required=True, help="Pre-tax expense amount in original currency")
    exp_parser.add_argument("--fx-rate", type=float, default=1.0, help="Exchange rate to CAD (1.0 for CAD)")
    exp_parser.add_argument(
        "--tax-type",
        default="STANDARD_ITC",
        choices=["STANDARD_ITC", "SIMPLIFIED_DIGITAL", "NONE"],
        help="STANDARD_ITC (eligible for Line 106 ITC), SIMPLIFIED_DIGITAL (foreign SaaS e.g. OpenAI EU id, tax is deductible expense, 0 ITC), NONE",
    )
    exp_parser.add_argument("--gst-paid", type=float, default=0.0, help="GST/HST amount paid in original currency")
    exp_parser.add_argument("--home-office-pct", type=float, default=0.0, help="Pro-rated workspace % (e.g. 25.0 for internet/utilities)")
    exp_parser.add_argument("--receipt-path", default=None, help="Path to digital receipt file (PDF/JPG/PNG)")
    exp_parser.add_argument("--notes", default="", help="Optional notes or details")

    # Command: report
    rep_parser = subparsers.add_parser("report", help="Generate CRA GST/HST return and T2125 tax reports")
    rep_parser.add_argument("--year", type=int, default=None, help="Fiscal year to filter (e.g. 2026)")
    rep_parser.add_argument(
        "--format",
        default="summary",
        choices=["summary", "gst-return", "t2125", "json"],
        help="Report format: summary (both), gst-return, t2125, json",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "init":
            init_ledger(force=args.force)
        elif args.command == "log-income":
            log_income(
                date=args.date,
                invoice_id=args.invoice_id,
                client=args.client,
                jurisdiction=args.jurisdiction,
                currency=args.currency,
                amount=args.amount,
                fx_rate=args.fx_rate,
                notes=args.notes,
            )
        elif args.command == "log-expense":
            log_expense(
                date=args.date,
                ref_id=args.ref_id,
                vendor=args.vendor,
                line_code=args.line_code,
                currency=args.currency,
                amount=args.amount,
                fx_rate=args.fx_rate,
                tax_type=args.tax_type,
                gst_paid=args.gst_paid,
                home_office_pct=args.home_office_pct,
                receipt_path=args.receipt_path,
                notes=args.notes,
            )
        elif args.command == "report":
            generate_report(year=args.year, report_format=args.format)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
