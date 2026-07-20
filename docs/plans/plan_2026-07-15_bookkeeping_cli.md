# Implementation Plan: Local Bookkeeping & Tax CLI Utility
*Status: Postponed (Archived on 2026-07-15)*

This plan proposes the creation of a lightweight, local CLI bookkeeping tool inside the repository to automate income/expense tracking, ITC calculations, and tax reporting (GST/HST and CRA T2125 categories).

## Goal

Create a Python command-line utility `scripts/manage_finance.py` that reads and writes transactions to a structured CSV ledger (`docs/financial/ledger.csv`), organizes digital receipt files, and outputs tax reports. This allows us to act as our own financial controllers with zero subscription costs and complete data privacy.

---

## Proposed Changes

### Financial Component

#### [NEW] [manage_finance.py](file:///c:/dev/canadian-grant-intelligence/scripts/manage_finance.py)
A CLI tool using Python's standard `argparse` and `csv` modules. 

**Features:**
1.  `init`: Creates the base directory structure `docs/financial/receipts/` and initializes `docs/financial/ledger.csv` with standard headers.
2.  `log-income`: Appends a client invoice payment.
    *   *Parameters*: `--date`, `--invoice-id`, `--client`, `--amount`, `--gst`
3.  `log-expense`: Appends a business purchase, tracking the base cost, GST paid (for ITCs), and copying the associated receipt file to the local receipts folder.
    *   *Parameters*: `--date`, `--vendor`, `--category` (restricts to standard CRA operating/capital categories), `--amount`, `--gst`, `--receipt-path`
4.  `report`: Calculates totals for a given date range.
    *   Outputs: Gross Revenue, Net Profit, Total GST/HST Collected, Total Input Tax Credits (GST Paid), and Net GST/HST Remittance due.
    *   Outputs category-wise totals aligned with the CRA Form T2125.

#### [NEW] [test_manage_finance.py](file:///c:/dev/canadian-grant-intelligence/tests/test_manage_finance.py)
Unit tests verifying transaction parsing, file copying, validation rules (e.g., preventing duplicate invoice IDs), and reporting math.

---

## Verification Plan

### Automated Tests
Run unit tests using the workspace interpreter and explicit PYTHONPATH as required by project rules:
```powershell
$env:PYTHONPATH="c:\dev\canadian-grant-intelligence"
c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\tests\test_manage_finance.py
```

### Manual Verification
1.  Initialize the ledger:
    ```powershell
    c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_finance.py init
    ```
2.  Log a test income transaction:
    ```powershell
    c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_finance.py log-income --date 2026-07-15 --invoice-id INV001 --client "First Customer" --amount 1000 --gst 50
    ```
3.  Log a test expense transaction with a dummy receipt file:
    ```powershell
    c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_finance.py log-expense --date 2026-07-15 --vendor "Azure" --category "Software" --amount 100 --gst 5 --receipt-path "scratch/test_receipt.pdf"
    ```
4.  Run a tax report:
    ```powershell
    c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_finance.py report --start 2026-06-11 --end 2026-12-31
    ```
    Verify that the remittance balance and T2125 totals are calculated correctly.
