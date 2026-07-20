# Implementation Plan: Local Bookkeeping & Tax CLI Utility
*Status: Postponed (Archived on 2026-07-16)*

This plan proposes the creation of a lightweight, local CLI bookkeeping tool inside the repository to automate income/expense tracking, ITC calculations, and tax reporting (GST/HST and CRA T2125 categories).

## Goal Description
Create a Python command-line utility [manage_finance.py](file:///c:/dev/canadian-grant-intelligence/scripts/manage_finance.py) that reads and writes transactions to a structured CSV ledger [ledger.csv](file:///c:/dev/canadian-grant-intelligence/docs/financial/ledger.csv), organizes digital receipt files under `docs/financial/receipts/`, and outputs formatted tax reports. This establishes a private, subscription-free bookkeeping system matching Canadian tax requirements.

---

## User Review Required

> [!IMPORTANT]
> **CRA Form T2125 Expense Categories:** To prevent tax audit errors, the CLI tool will enforce matching expenses to one of the official CRA Form T2125 Part 17 operating expense categories:
> * `Advertising`
> * `Bad debts`
> * `Business taxes, fees, licenses, dues, memberships, and subscriptions`
> * `Delivery, shipping, and express`
> * `Fuel costs (except for motor vehicles)`
> * `Insurance`
> * `Interest and bank charges`
> * `Legal, accounting, and other professional fees`
> * `Management and administration fees`
> * `Maintenance and repairs`
> * `Motor vehicle expenses (except interest and leasing costs)`
> * `Office expenses`
> * `Office stationery and supplies`
> * `Other expenses` (e.g. software/subscriptions)
> * `Rent`
> * `Salaries, wages, and benefits`
> * `Travel expenses`
> * `Utilities`
> * `Telephone and utilities`
>
> Please confirm if you would like any custom sub-categories or if the standard list is sufficient.

---

## Open Questions

> [!IMPORTANT]
> **Receipt Filename Formatting:** When logging an expense, the CLI tool can copy the file from `--receipt-path` to the local `docs/financial/receipts/` directory. Should the tool automatically rename the receipt files to a standard format (e.g., `YYYY-MM-DD_vendor_amount.pdf`) to keep the receipts folder highly organized?

---

## Proposed Changes

### Financial Component

#### [NEW] [manage_finance.py](file:///c:/dev/canadian-grant-intelligence/scripts/manage_finance.py)
A CLI tool using Python's standard `argparse` and `csv` modules. It will support:
* `init`: Creates the directories `docs/financial/receipts/` and initializes `docs/financial/ledger.csv` with the headers: `Type` (Income/Expense), `Date`, `ID/Ref`, `Vendor/Client`, `Category`, `Amount`, `GST`, `Total`, `Receipt`.
* `log-income`: Appends a client invoice payment. Parameters: `--date`, `--invoice-id`, `--client`, `--amount`, `--gst`
* `log-expense`: Appends a business purchase, validates the category, tracks base cost + GST (Input Tax Credit), copies and renames the receipt file if supplied. Parameters: `--date`, `--vendor`, `--category`, `--amount`, `--gst`, `--receipt-path`
* `report`: Calculates Gross Revenue, Net Profit, GST Collected, GST Paid (ITCs), and Net GST/HST Remittance due for a given date range. Also outputs category-wise totals.

#### [NEW] [test_manage_finance.py](file:///c:/dev/canadian-grant-intelligence/tests/test_manage_finance.py)
A unit test file validating:
* Parser arguments and command routing.
* Ledger initialization and header structure.
* Income and expense validation rules (including duplicate invoice ID prevention).
* Tax calculation formulas and report generation math.
* Safe copying and renaming of receipt files.

---

## Verification Plan

### Automated Tests
Run unit tests individually using the local virtual environment Python interpreter with `PYTHONPATH` set to the workspace root:
```powershell
$env:PYTHONPATH="c:\dev\canadian-grant-intelligence"
c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\tests\test_manage_finance.py
```

### Manual Verification
1. **Initialize the Ledger:**
   ```powershell
   c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_finance.py init
   ```
2. **Log Test Income:**
   ```powershell
   c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_finance.py log-income --date 2026-07-16 --invoice-id INV-2026-001 --client "Acme Corp" --amount 2500 --gst 125
   ```
3. **Log Test Expense with Receipt:**
   ```powershell
   # Create a mock receipt
   New-Item -Path scratch/test_receipt.pdf -ItemType File -Value "Mock Receipt Content"
   
   c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_finance.py log-expense --date 2026-07-16 --vendor "Azure Hosting" --category "Other expenses" --amount 100 --gst 5 --receipt-path scratch/test_receipt.pdf
   ```
4. **Verify Receipt Storage:** Confirm that the receipt is copied to `docs/financial/receipts/` and renamed appropriately.
5. **Run Report:**
   ```powershell
   c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/manage_finance.py report --start 2026-06-11 --end 2026-12-31
   ```
   Verify that Gross Revenue is $2500, Net Profit is $2400, GST Collected is $125, GST Paid (ITCs) is $5, and Net GST Remittance due is $120.
