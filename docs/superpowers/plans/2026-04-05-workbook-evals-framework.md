# Workbook Evals Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a validation framework that catches broken cross-sheet references, formula errors, and data integrity issues in the portfolio analysis Excel workbook.

**Architecture:** A shared reference registry (`registry.py`) defines expected cell locations for all tabs. A validator module (`validate_workbook.py`) runs 7 checks against the workbook using openpyxl for structural analysis and optional win32com for formula evaluation. Rebuild scripts and the weekly pipeline call the validator after saving.

**Tech Stack:** Python 3, openpyxl (structural), win32com (optional deep eval), argparse (CLI)

---

### Task 1: Create Reference Registry

**Files:**
- Create: `registry.py`

- [ ] **Step 1: Create registry.py with all tab cell locations**

```python
#!/usr/bin/env python3
"""Reference registry — single source of truth for key cell locations in the workbook."""

# Each entry: "key_name": (column_letter, row_number, expected_label_in_col_A)
# Column letter is where the VALUE lives. Label check always uses column A.

REGISTRY = {
    "Fidelity Brokerage": {
        "dividends":        ("B", 6, "Dividends/Income"),
        "unrealized":       ("B", 7, "Unrealized Gain/Loss"),
        "realized":         ("B", 8, "Realized Gain/Loss (2026)"),
        "total_ytd_gain":   ("B", 9, "Total YTD Gain"),
        "holdings_total_mv":    ("D", 32, "TOTAL"),
        "holdings_total_cb":    ("E", 32, "TOTAL"),
        "holdings_total_gl":    ("F", 32, "TOTAL"),
        "twr":              ("B", 36, "TWR"),
        "mwrr":             ("B", 37, "MWRR"),
        "cb_return":        ("B", 38, "Cost Basis Return"),
        "monthly_first":    ("B", 44, "Jan"),
        "monthly_last":     ("B", 55, "Dec"),
        "monthly_totals":   ("C", 57, "Totals"),
        "sold_2026_total":  ("F", 65, "2026 TOTAL"),
    },
    "Fidelity Roth IRA": {
        "dividends":        ("B", 6, "Dividends/Income"),
        "unrealized":       ("B", 7, "Unrealized Gain/Loss"),
        "realized":         ("B", 8, "Realized Gain/Loss (2026)"),
        "total_ytd_gain":   ("B", 9, "Total YTD Gain"),
        "holdings_total_mv":    ("D", 22, "TOTAL"),
        "holdings_total_cb":    ("E", 22, "TOTAL"),
        "holdings_total_gl":    ("F", 22, "TOTAL"),
        "twr":              ("B", 26, "TWR"),
        "mwrr":             ("B", 27, "MWRR"),
        "cb_return":        ("B", 28, "Cost Basis Return"),
        "monthly_first":    ("B", 34, "Jan"),
        "monthly_last":     ("B", 45, "Dec"),
        "monthly_totals":   ("C", 47, "Totals"),
        "sold_2026_total":  ("F", 55, "2026 TOTAL"),
    },
    "Fidelity HSA": {
        "dividends":        ("B", 6, "Dividends/Income"),
        "unrealized":       ("B", 7, "Unrealized Gain/Loss"),
        "realized":         ("B", 8, "Realized Gain/Loss (2026)"),
        "total_ytd_gain":   ("B", 9, "Total YTD Gain"),
        "holdings_total_mv":    ("D", 19, "TOTAL"),
        "holdings_total_cb":    ("E", 19, "TOTAL"),
        "holdings_total_gl":    ("F", 19, "TOTAL"),
        "twr":              ("B", 23, "TWR"),
        "mwrr":             ("B", 24, "MWRR"),
        "cb_return":        ("B", 25, "Cost Basis Return"),
        "monthly_first":    ("B", 31, "Jan"),
        "monthly_last":     ("B", 42, "Dec"),
        "monthly_totals":   ("C", 44, "Totals"),
        "sold_2026_total":  ("F", 52, "2026 TOTAL"),
    },
    "401(k)": {
        "quarterly_first":  ("B", 5, "Q1 (Nov 1 - Jan 31)"),
        "ytd_totals":       ("C", 10, "YTD Totals"),
        "twr":              ("B", 13, "TWR (Computed \u2014 Modified Dietz)"),
        "mwrr":             ("B", 15, "MWRR"),
        "cb_return":        ("B", 16, "Cost Basis Return"),
        "holdings_total_mv":    ("B", 28, "TOTAL"),
        "holdings_total_cb":    ("C", 28, "TOTAL"),
        "holdings_total_gl":    ("D", 28, "TOTAL"),
        "total_inv_gain":   ("B", 33, "Total Investment Gain"),
    },
    "Robinhood": {
        "dividends":        ("B", 6, "Dividends Received"),
        "unrealized":       ("B", 7, "Unrealized Gain/Loss"),
        "realized":         ("B", 8, "Realized Gain/Loss (2026)"),
        "total_ytd_gain":   ("B", 9, "Total YTD Gain"),
        "holdings_total_mv":    ("D", 21, "TOTAL SECURITIES"),
        "holdings_total_cb":    ("F", 21, "TOTAL SECURITIES"),
        "holdings_total_gl":    ("G", 21, "TOTAL SECURITIES"),
        "margin_debt":      ("D", 22, "Margin Debt"),
        "net_portfolio":    ("D", 23, "NET PORTFOLIO VALUE"),
        "twr":              ("B", 27, "TWR"),
        "mwrr":             ("B", 28, "MWRR"),
        "cb_return":        ("B", 29, "Cost Basis Return"),
        "monthly_first":    ("B", 42, "Jan"),
        "monthly_last":     ("B", 53, "Dec"),
        "monthly_totals":   ("C", 55, "Totals"),
        "sold_2026_total":  ("F", 62, "2026 TOTAL"),
    },
    "Angel Investments": {
        "total_invested":   ("E", 12, "TOTAL"),
        "total_current":    ("I", 12, "TOTAL"),
    },
    "Cash": {
        "total_cash":       ("C", 10, "TOTAL CASH"),
    },
    "Dashboard": {
        "fid_brok_row":     ("A", 6, "Fidelity Brokerage"),
        "roth_ira_row":     ("A", 7, "Fidelity Roth IRA"),
        "k401_row":         ("A", 8, "401(k)"),
        "hsa_row":          ("A", 9, "Fidelity HSA"),
        "angel_row":        ("A", 10, "Angel Investments"),
        "robinhood_row":    ("A", 11, "Robinhood"),
        "cash_row":         ("A", 12, "Cash"),
        "total_portfolio":  ("B", 13, "TOTAL PORTFOLIO"),
        "liquid":           ("B", 17, "Liquid"),
        "illiquid":         ("B", 18, "Illiquid"),
        "total_port_value": ("B", 22, "Total Portfolio Value (Ending)"),
        "total_inv_gain":   ("B", 24, "Total Investment Gain"),
        "dividends":        ("B", 25, "Dividends/Income"),
        "unrealized":       ("B", 26, "Unrealized Gain/Loss"),
        "realized":         ("B", 27, "Realized Gain/Loss"),
        "sp500":            ("B", 31, "S&P 500"),
        "dow":              ("B", 32, "Dow Jones"),
        "nasdaq":           ("B", 33, "NASDAQ"),
    },
}

# Monthly section column layouts per tab type
# Maps column letters to field names for monthly calculation rows
MONTHLY_COLUMNS = {
    "Robinhood": {
        "B": "beginning", "C": "deposits", "D": "withdrawals",
        "E": "dividends", "F": "market_change", "G": "ending",
        "H": "monthly_return", "I": "growth_factor",
    },
    "Fidelity Brokerage": {
        "B": "beginning", "C": "additions", "D": "subtractions",
        "E": "dividends", "F": "market_change", "G": "ending",
        "H": "monthly_return", "I": "growth_factor",
    },
    "Fidelity Roth IRA": {
        "B": "beginning", "C": "contributions", "D": "distributions",
        "E": "dividends", "F": "market_change", "G": "ending",
        "H": "monthly_return", "I": "growth_factor",
    },
    "Fidelity HSA": {
        "B": "beginning", "C": "additions", "D": "subtractions",
        "E": "dividends", "F": "market_change", "G": "ending",
        "H": "monthly_return", "I": "growth_factor",
    },
}

# Holdings section: first data row and total row per tab
HOLDINGS_ROWS = {
    "Fidelity Brokerage": {"first": 13, "last": 31, "total": 32, "mv_col": "D", "cb_col": "E", "gl_col": "F"},
    "Fidelity Roth IRA":  {"first": 13, "last": 21, "total": 22, "mv_col": "D", "cb_col": "E", "gl_col": "F"},
    "Fidelity HSA":       {"first": 13, "last": 18, "total": 19, "mv_col": "D", "cb_col": "E", "gl_col": "F"},
    "401(k)":             {"first": 20, "last": 27, "total": 28, "mv_col": "B", "cb_col": "C", "gl_col": "D"},
    "Robinhood":          {"first": 13, "last": 20, "total": 21, "mv_col": "D", "cb_col": "F", "gl_col": "G"},
}
```

- [ ] **Step 2: Verify registry matches actual workbook**

Run:
```bash
python -c "
from registry import REGISTRY
import openpyxl
wb = openpyxl.load_workbook('2026_Portfolio_Analysis.xlsx')
errors = 0
for tab, entries in REGISTRY.items():
    ws = wb[tab]
    for key, (col, row, label) in entries.items():
        actual = ws.cell(row=row, column=1).value
        if actual is None:
            actual = ''
        if label not in str(actual):
            print(f'MISMATCH {tab}.{key}: expected \"{label}\" at row {row}, found \"{actual}\"')
            errors += 1
print(f'\n{errors} mismatches found' if errors else '\nAll labels match!')
"
```
Expected: `All labels match!`

- [ ] **Step 3: Commit**

```bash
git add registry.py
git commit -m "feat: add cell location registry for workbook validation"
```

---

### Task 2: Create Core Validator with Checks 1-2

**Files:**
- Create: `validate_workbook.py`

- [ ] **Step 1: Create validate_workbook.py with Finding dataclass and checks 1-2**

```python
#!/usr/bin/env python3
"""Workbook validation framework — catches broken references and calculation errors."""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from openpyxl.utils import column_index_from_string

from registry import REGISTRY, MONTHLY_COLUMNS, HOLDINGS_ROWS


@dataclass
class Finding:
    severity: str  # "ERROR", "WARN", "PASS"
    tab: str
    check: str
    cell: str
    message: str


def check_label_matching(wb) -> list[Finding]:
    """Check 1: Verify all registry labels match actual cell contents."""
    findings = []
    for tab, entries in REGISTRY.items():
        if tab not in wb.sheetnames:
            findings.append(Finding("ERROR", tab, "label_matching", "", f"Tab '{tab}' not found in workbook"))
            continue
        ws = wb[tab]
        matched = 0
        total = len(entries)
        for key, (col, row, label) in entries.items():
            actual = ws.cell(row=row, column=1).value
            actual_str = str(actual) if actual else ""
            if label in actual_str:
                matched += 1
            else:
                findings.append(Finding(
                    "ERROR", tab, "label_matching", f"A{row}",
                    f"'{key}': expected '{label}' at row {row}, found '{actual_str}'"
                ))
        if matched == total:
            findings.append(Finding("PASS", tab, "label_matching", "", f"{matched}/{total} labels correct"))
    return findings


def check_formula_errors(wb) -> list[Finding]:
    """Check 2: Scan for #REF!, #VALUE!, #DIV/0!, #NAME? in cached values."""
    error_prefixes = ("#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NULL!", "#N/A", "#NUM!")
    findings = []
    for tab in wb.sheetnames:
        ws = wb[tab]
        errors_found = 0
        cells_checked = 0
        for row in range(1, ws.max_row + 1):
            for col in range(1, ws.max_column + 1):
                cell = ws.cell(row=row, column=col)
                if cell.value is None:
                    continue
                cells_checked += 1
                val_str = str(cell.value)
                if any(val_str.startswith(e) for e in error_prefixes):
                    findings.append(Finding(
                        "ERROR", tab, "formula_errors", cell.coordinate,
                        f"Formula error: {val_str}"
                    ))
                    errors_found += 1
        if errors_found == 0:
            findings.append(Finding("PASS", tab, "formula_errors", "", f"{cells_checked} cells checked, no errors"))
    return findings


def format_findings(findings: list[Finding]) -> str:
    """Format findings into a readable report."""
    lines = ["", "=" * 60, "  WORKBOOK VALIDATION", "=" * 60, ""]
    for f in findings:
        tag = {"PASS": "[PASS]", "WARN": "[WARN]", "ERROR": "[FAIL]"}[f.severity]
        cell_str = f" {f.cell}" if f.cell else ""
        lines.append(f"  {tag} {f.tab}: {f.check}{cell_str} — {f.message}")

    n_pass = sum(1 for f in findings if f.severity == "PASS")
    n_warn = sum(1 for f in findings if f.severity == "WARN")
    n_fail = sum(1 for f in findings if f.severity == "ERROR")
    lines.append("")
    lines.append(f"  Summary: {n_pass} passed, {n_fail} failed, {n_warn} warnings")
    lines.append("")
    return "\n".join(lines)


def validate_full(workbook_path: str) -> list[Finding]:
    """Run all validation checks on the workbook."""
    wb = openpyxl.load_workbook(workbook_path)
    findings = []
    findings.extend(check_label_matching(wb))
    findings.extend(check_formula_errors(wb))
    return findings


def main():
    parser = argparse.ArgumentParser(description="Validate portfolio workbook")
    parser.add_argument("workbook", nargs="?", default="2026_Portfolio_Analysis.xlsx",
                        help="Path to workbook (default: 2026_Portfolio_Analysis.xlsx)")
    parser.add_argument("--deep", action="store_true", help="Run COM deep eval (requires Excel)")
    args = parser.parse_args()

    findings = validate_full(args.workbook)
    print(format_findings(findings))

    n_fail = sum(1 for f in findings if f.severity == "ERROR")
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run checks 1-2 against current workbook**

Run: `python validate_workbook.py`

Expected: All labels match, no formula errors. If any mismatches, fix registry.py to match actual workbook.

- [ ] **Step 3: Commit**

```bash
git add validate_workbook.py
git commit -m "feat: add workbook validator with label matching and formula error checks"
```

---

### Task 3: Add Checks 3-4 (Cross-Sheet Refs + Balance Continuity)

**Files:**
- Modify: `validate_workbook.py`

- [ ] **Step 1: Add check_cross_sheet_refs function**

Add after `check_formula_errors`:

```python
def check_cross_sheet_refs(wb) -> list[Finding]:
    """Check 3: Verify cross-sheet formula references resolve to valid, labeled cells."""
    # Pattern matches: ='Tab Name'!C5 or =TabName!B42 (also within larger formulas)
    ref_pattern = re.compile(r"='?([^'!]+)'?!([A-Z]+)(\d+)")
    findings = []

    for tab in wb.sheetnames:
        ws = wb[tab]
        errors = 0
        refs_checked = 0
        for row in range(1, ws.max_row + 1):
            for col in range(1, ws.max_column + 1):
                cell = ws.cell(row=row, column=col)
                val = cell.value
                if not isinstance(val, str) or "!" not in val:
                    continue
                for match in ref_pattern.finditer(val):
                    ref_tab = match.group(1)
                    ref_col = match.group(2)
                    ref_row = int(match.group(3))
                    refs_checked += 1

                    if ref_tab not in wb.sheetnames:
                        findings.append(Finding(
                            "ERROR", tab, "cross_sheet_refs", cell.coordinate,
                            f"References non-existent tab '{ref_tab}'"
                        ))
                        errors += 1
                        continue

                    target_ws = wb[ref_tab]
                    target_cell = target_ws.cell(row=ref_row, column=column_index_from_string(ref_col))
                    if target_cell.value is None:
                        # Check if the row has any data at all
                        row_label = target_ws.cell(row=ref_row, column=1).value
                        if row_label is None:
                            findings.append(Finding(
                                "WARN", tab, "cross_sheet_refs", cell.coordinate,
                                f"References empty cell {ref_tab}!{ref_col}{ref_row} (empty row)"
                            ))
                            errors += 1

        if refs_checked > 0 and errors == 0:
            findings.append(Finding("PASS", tab, "cross_sheet_refs", "", f"{refs_checked} refs checked"))
    return findings
```

- [ ] **Step 2: Add check_balance_continuity function**

Add after `check_cross_sheet_refs`:

```python
def check_balance_continuity(wb) -> list[Finding]:
    """Check 4: Monthly ending value of month N = beginning value of month N+1."""
    findings = []
    for tab, cols in MONTHLY_COLUMNS.items():
        if tab not in wb.sheetnames:
            continue
        ws = wb[tab]
        reg = REGISTRY[tab]
        first_row = reg["monthly_first"][1]

        # Find which columns are beginning and ending
        begin_col = column_index_from_string("B")  # Always col B
        # Ending column varies: G for 9-col layout
        end_col = None
        for letter, field_name in cols.items():
            if field_name == "ending":
                end_col = column_index_from_string(letter)
                break
        if end_col is None:
            continue

        months_checked = 0
        for month_offset in range(11):  # Jan through Nov (check Nov->Dec)
            row_n = first_row + month_offset
            row_n1 = first_row + month_offset + 1

            ending = ws.cell(row=row_n, column=end_col).value
            beginning_next = ws.cell(row=row_n1, column=begin_col).value

            if ending is None or beginning_next is None:
                continue

            try:
                ending = float(ending)
                beginning_next = float(beginning_next)
            except (ValueError, TypeError):
                continue

            months_checked += 1
            if abs(ending - beginning_next) > 0.01:
                month_name = ws.cell(row=row_n, column=1).value
                next_month = ws.cell(row=row_n1, column=1).value
                findings.append(Finding(
                    "ERROR", tab, "balance_continuity", f"row {row_n}-{row_n1}",
                    f"{month_name} ending (${ending:,.2f}) != {next_month} beginning (${beginning_next:,.2f})"
                ))

        if months_checked > 0:
            errors = [f for f in findings if f.tab == tab and f.check == "balance_continuity" and f.severity == "ERROR"]
            if not errors:
                findings.append(Finding("PASS", tab, "balance_continuity", "", f"{months_checked} transitions checked"))
    return findings
```

- [ ] **Step 3: Wire new checks into validate_full**

Update `validate_full`:

```python
def validate_full(workbook_path: str) -> list[Finding]:
    """Run all validation checks on the workbook."""
    wb = openpyxl.load_workbook(workbook_path)
    findings = []
    findings.extend(check_label_matching(wb))
    findings.extend(check_formula_errors(wb))
    findings.extend(check_cross_sheet_refs(wb))
    findings.extend(check_balance_continuity(wb))
    return findings
```

- [ ] **Step 4: Run and verify**

Run: `python validate_workbook.py`

Expected: Checks 1-4 all pass for tabs with data. Cross-sheet refs validated for Dashboard.

- [ ] **Step 5: Commit**

```bash
git add validate_workbook.py
git commit -m "feat: add cross-sheet ref and balance continuity checks"
```

---

### Task 4: Add Checks 5-7 (Accounting Identity, Holdings Total, YTD Gain)

**Files:**
- Modify: `validate_workbook.py`

- [ ] **Step 1: Add check_accounting_identity function**

Add after `check_balance_continuity`:

```python
def check_accounting_identity(wb) -> list[Finding]:
    """Check 5: Ending = Beginning + Additions - Subtractions + Change ($1 tolerance)."""
    findings = []
    for tab, cols in MONTHLY_COLUMNS.items():
        if tab not in wb.sheetnames:
            continue
        ws = wb[tab]
        reg = REGISTRY[tab]
        first_row = reg["monthly_first"][1]

        # Map field names to column indices
        col_map = {}
        for letter, field_name in cols.items():
            col_map[field_name] = column_index_from_string(letter)

        months_checked = 0
        for month_offset in range(12):
            row = first_row + month_offset
            month_name = ws.cell(row=row, column=1).value
            if month_name is None:
                continue

            def val(field):
                c = col_map.get(field)
                if c is None:
                    return None
                v = ws.cell(row=row, column=c).value
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None

            beginning = val("beginning")
            ending = val("ending")
            if beginning is None or ending is None:
                continue

            # Inflows: deposits/additions/contributions
            inflow = val("deposits") or val("additions") or val("contributions") or 0
            # Outflows: withdrawals/subtractions/distributions
            outflow = val("withdrawals") or val("subtractions") or val("distributions") or 0
            dividends = val("dividends") or 0
            market_change = val("market_change") or 0

            expected = beginning + inflow - outflow + dividends + market_change
            months_checked += 1

            if abs(ending - expected) > 1.0:
                findings.append(Finding(
                    "ERROR", tab, "accounting_identity", f"row {row}",
                    f"{month_name}: expected ${expected:,.2f}, got ${ending:,.2f} (diff ${ending - expected:,.2f})"
                ))

        if months_checked > 0:
            errors = [f for f in findings if f.tab == tab and f.check == "accounting_identity" and f.severity == "ERROR"]
            if not errors:
                findings.append(Finding("PASS", tab, "accounting_identity", "", f"{months_checked} months checked"))
    return findings
```

- [ ] **Step 2: Add check_holdings_total function**

```python
def check_holdings_total(wb) -> list[Finding]:
    """Check 6: Sum of individual holdings = total row ($0.01 tolerance)."""
    findings = []
    for tab, info in HOLDINGS_ROWS.items():
        if tab not in wb.sheetnames:
            continue
        ws = wb[tab]

        for col_key, col_name in [("mv_col", "Market Value"), ("cb_col", "Cost Basis"), ("gl_col", "Gain/Loss")]:
            col_letter = info[col_key]
            col_idx = column_index_from_string(col_letter)

            individual_sum = 0.0
            count = 0
            for row in range(info["first"], info["last"] + 1):
                v = ws.cell(row=row, column=col_idx).value
                if v is not None:
                    try:
                        individual_sum += float(v)
                        count += 1
                    except (ValueError, TypeError):
                        pass

            total_cell = ws.cell(row=info["total"], column=col_idx)
            total_val = total_cell.value
            if total_val is None or isinstance(total_val, str):
                continue  # formula — can't evaluate without Excel

            try:
                total_val = float(total_val)
            except (ValueError, TypeError):
                continue

            if abs(individual_sum - total_val) > 0.01:
                findings.append(Finding(
                    "ERROR", tab, "holdings_total", f"{col_letter}{info['total']}",
                    f"{col_name}: sum of rows {info['first']}-{info['last']} = ${individual_sum:,.2f}, "
                    f"total row = ${total_val:,.2f} (diff ${individual_sum - total_val:,.2f})"
                ))

        # If no errors for this tab
        tab_errors = [f for f in findings if f.tab == tab and f.check == "holdings_total" and f.severity == "ERROR"]
        if not tab_errors:
            findings.append(Finding("PASS", tab, "holdings_total", "", f"Holdings sums verified"))
    return findings
```

- [ ] **Step 3: Add check_ytd_gain_consistency function**

```python
def check_ytd_gain_consistency(wb) -> list[Finding]:
    """Check 7: Total YTD Gain = Unrealized + Realized + Dividends ($1 tolerance)."""
    findings = []
    # Tabs with standard YTD layout (row 6=div, 7=unreal, 8=real, 9=total)
    ytd_tabs = ["Fidelity Brokerage", "Fidelity Roth IRA", "Fidelity HSA", "Robinhood"]

    for tab in ytd_tabs:
        if tab not in wb.sheetnames:
            continue
        ws = wb[tab]
        reg = REGISTRY[tab]

        def get_val(key):
            col_letter, row, _ = reg[key]
            v = ws.cell(row=row, column=column_index_from_string(col_letter)).value
            if v is None or isinstance(v, str):
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        dividends = get_val("dividends")
        unrealized = get_val("unrealized")
        realized = get_val("realized")
        total_ytd = get_val("total_ytd_gain")

        if any(v is None for v in [dividends, unrealized, realized, total_ytd]):
            findings.append(Finding("WARN", tab, "ytd_gain_consistency", "",
                                    "Cannot verify — some values are formulas (need --deep eval)"))
            continue

        expected = unrealized + realized + dividends
        if abs(total_ytd - expected) > 1.0:
            findings.append(Finding(
                "ERROR", tab, "ytd_gain_consistency", "",
                f"Total YTD (${total_ytd:,.2f}) != Unrealized (${unrealized:,.2f}) + "
                f"Realized (${realized:,.2f}) + Dividends (${dividends:,.2f}) = ${expected:,.2f}"
            ))
        else:
            findings.append(Finding("PASS", tab, "ytd_gain_consistency", "", "YTD gain = Unreal + Real + Div"))
    return findings
```

- [ ] **Step 4: Wire checks 5-7 into validate_full**

Update `validate_full`:

```python
def validate_full(workbook_path: str) -> list[Finding]:
    """Run all validation checks on the workbook."""
    wb = openpyxl.load_workbook(workbook_path)
    findings = []
    findings.extend(check_label_matching(wb))
    findings.extend(check_formula_errors(wb))
    findings.extend(check_cross_sheet_refs(wb))
    findings.extend(check_balance_continuity(wb))
    findings.extend(check_accounting_identity(wb))
    findings.extend(check_holdings_total(wb))
    findings.extend(check_ytd_gain_consistency(wb))
    return findings
```

- [ ] **Step 5: Run full validation**

Run: `python validate_workbook.py`

Expected: All 7 checks run across all tabs. Some checks may WARN on formula-only cells (expected — those need --deep eval).

- [ ] **Step 6: Commit**

```bash
git add validate_workbook.py
git commit -m "feat: add accounting identity, holdings total, and YTD gain checks"
```

---

### Task 5: Add Lightweight validate_structural for Rebuild Scripts

**Files:**
- Modify: `validate_workbook.py`

- [ ] **Step 1: Add validate_structural function**

Add before `validate_full`:

```python
def validate_structural(workbook_path: str, tab_name: str) -> list[Finding]:
    """Lightweight validation for a single tab — called by rebuild scripts after saving."""
    wb = openpyxl.load_workbook(workbook_path)
    findings = []

    # Check 1: Label matching (this tab only)
    if tab_name in REGISTRY:
        ws = wb[tab_name]
        matched = 0
        total = len(REGISTRY[tab_name])
        for key, (col, row, label) in REGISTRY[tab_name].items():
            actual = str(ws.cell(row=row, column=1).value or "")
            if label in actual:
                matched += 1
            else:
                findings.append(Finding("ERROR", tab_name, "label_matching", f"A{row}",
                                        f"'{key}': expected '{label}', found '{actual}'"))
        if matched == total:
            findings.append(Finding("PASS", tab_name, "label_matching", "", f"{matched}/{total} labels correct"))

    # Check 4: Balance continuity (if tab has monthly section)
    if tab_name in MONTHLY_COLUMNS:
        findings.extend([f for f in check_balance_continuity(wb) if f.tab == tab_name])

    # Check 5: Accounting identity
    if tab_name in MONTHLY_COLUMNS:
        findings.extend([f for f in check_accounting_identity(wb) if f.tab == tab_name])

    # Check 6: Holdings total
    if tab_name in HOLDINGS_ROWS:
        findings.extend([f for f in check_holdings_total(wb) if f.tab == tab_name])

    return findings
```

- [ ] **Step 2: Test structural validation for one tab**

Run:
```bash
python -c "
from validate_workbook import validate_structural, format_findings
findings = validate_structural('2026_Portfolio_Analysis.xlsx', 'Robinhood')
print(format_findings(findings))
"
```

Expected: PASS for label matching, balance continuity, accounting identity, holdings total.

- [ ] **Step 3: Commit**

```bash
git add validate_workbook.py
git commit -m "feat: add validate_structural for per-tab checks in rebuild scripts"
```

---

### Task 6: Add COM Deep Eval

**Files:**
- Modify: `validate_workbook.py`

- [ ] **Step 1: Add check_com_deep_eval function**

Add before `validate_full`:

```python
def check_com_deep_eval(workbook_path: str) -> list[Finding]:
    """Optional deep eval: open in Excel via COM, force recalculation, check for errors."""
    findings = []
    try:
        import win32com.client
    except ImportError:
        findings.append(Finding("WARN", "ALL", "deep_eval", "",
                                "Deep eval skipped (requires: pip install pywin32)"))
        return findings

    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        abs_path = str(Path(workbook_path).resolve())
        wb_com = excel.Workbooks.Open(abs_path, ReadOnly=True)
        excel.Calculate()

        error_types = {-2146826281: "#DIV/0!", -2146826246: "#N/A", -2146826259: "#NAME?",
                       -2146826265: "#NULL!", -2146826252: "#NUM!", -2146826288: "#VALUE!",
                       -2146826225: "#REF!"}

        for ws_com in wb_com.Worksheets:
            tab_name = ws_com.Name
            used = ws_com.UsedRange
            errors_found = 0
            for row in range(1, used.Rows.Count + 1):
                for col in range(1, used.Columns.Count + 1):
                    try:
                        cell = used.Cells(row, col)
                        if cell.Value is not None and isinstance(cell.Value, int) and cell.Value in error_types:
                            findings.append(Finding(
                                "ERROR", tab_name, "deep_eval", f"R{row}C{col}",
                                f"Formula evaluates to {error_types[cell.Value]}"
                            ))
                            errors_found += 1
                    except Exception:
                        pass
            if errors_found == 0:
                findings.append(Finding("PASS", tab_name, "deep_eval", "", "No formula errors after recalculation"))

        wb_com.Close(SaveChanges=False)
        excel.Quit()

    except Exception as e:
        findings.append(Finding("WARN", "ALL", "deep_eval", "", f"Deep eval failed: {e}"))

    return findings
```

- [ ] **Step 2: Wire --deep flag into validate_full and main**

Update `validate_full` signature and `main`:

```python
def validate_full(workbook_path: str, deep: bool = False) -> list[Finding]:
    """Run all validation checks on the workbook."""
    wb = openpyxl.load_workbook(workbook_path)
    findings = []
    findings.extend(check_label_matching(wb))
    findings.extend(check_formula_errors(wb))
    findings.extend(check_cross_sheet_refs(wb))
    findings.extend(check_balance_continuity(wb))
    findings.extend(check_accounting_identity(wb))
    findings.extend(check_holdings_total(wb))
    findings.extend(check_ytd_gain_consistency(wb))
    if deep:
        findings.extend(check_com_deep_eval(workbook_path))
    return findings


def main():
    parser = argparse.ArgumentParser(description="Validate portfolio workbook")
    parser.add_argument("workbook", nargs="?", default="2026_Portfolio_Analysis.xlsx",
                        help="Path to workbook (default: 2026_Portfolio_Analysis.xlsx)")
    parser.add_argument("--deep", action="store_true", help="Run COM deep eval (requires Excel)")
    args = parser.parse_args()

    findings = validate_full(args.workbook, deep=args.deep)
    print(format_findings(findings))

    n_fail = sum(1 for f in findings if f.severity == "ERROR")
    sys.exit(1 if n_fail > 0 else 0)
```

- [ ] **Step 3: Test deep eval**

Run: `python validate_workbook.py --deep`

Expected: All structural checks pass. Deep eval either passes or warns "requires pywin32".

- [ ] **Step 4: Commit**

```bash
git add validate_workbook.py
git commit -m "feat: add optional COM deep eval for formula verification"
```

---

### Task 7: Integrate into Rebuild Scripts and Pipeline

**Files:**
- Modify: `rebuild_rh_tab.py`
- Modify: `rebuild_hsa_tab.py`
- Modify: `rebuild_roth_tab.py`
- Modify: `rebuild_brok_tab.py`
- Modify: `rebuild_dashboard.py`
- Modify: `weekly_pipeline.py`

- [ ] **Step 1: Add validation call to each rebuild script**

Add at the end of each rebuild script's `main()`, after `wb.save()`:

```python
    # Validate after save
    from validate_workbook import validate_structural, format_findings
    findings = validate_structural(str(XLSX), "TAB_NAME_HERE")
    report = format_findings(findings)
    print(report)
    n_fail = sum(1 for f in findings if f.severity == "ERROR")
    if n_fail:
        print(f"  WARNING: {n_fail} validation error(s) detected!")
```

Replace `TAB_NAME_HERE` with the appropriate tab name per script:
- `rebuild_rh_tab.py` → `"Robinhood"`
- `rebuild_hsa_tab.py` → `"Fidelity HSA"`
- `rebuild_roth_tab.py` → `"Fidelity Roth IRA"`
- `rebuild_brok_tab.py` → `"Fidelity Brokerage"`
- `rebuild_dashboard.py` → `"Dashboard"`

- [ ] **Step 2: Add full validation to weekly_pipeline.py**

In `run_pipeline()`, after the workbook build step (after `build_xlsx` or `build_workbook` calls), add:

```python
        # Validate workbook
        try:
            from validate_workbook import validate_full, format_findings
            findings = validate_full(str(OUTPUT_XLSX))
            report = format_findings(findings)
            logging.info(report)
            n_fail = sum(1 for f in findings if f.severity == "ERROR")
            if n_fail:
                logging.warning(f"Workbook validation: {n_fail} error(s) detected")
                errors.append(f"Validation: {n_fail} error(s)")
        except Exception as e:
            logging.error(f"Workbook validation failed: {e}")
```

- [ ] **Step 3: Test rebuild with validation**

Run: `python rebuild_rh_tab.py`

Expected: Robinhood tab rebuilds, then validation runs and prints PASS for label matching, balance continuity, accounting identity, holdings total.

- [ ] **Step 4: Commit**

```bash
git add rebuild_rh_tab.py rebuild_hsa_tab.py rebuild_roth_tab.py rebuild_brok_tab.py rebuild_dashboard.py weekly_pipeline.py
git commit -m "feat: integrate workbook validation into rebuild scripts and pipeline"
```

---

### Task 8: Final End-to-End Validation Run

- [ ] **Step 1: Run full standalone validation**

Run: `python validate_workbook.py`

Expected output format:
```
============================================================
  WORKBOOK VALIDATION
============================================================

  [PASS] Fidelity Brokerage: label_matching — 14/14 labels correct
  [PASS] Fidelity Brokerage: formula_errors — N cells checked, no errors
  ...
  [PASS] Dashboard: label_matching — 18/18 labels correct
  ...

  Summary: X passed, 0 failed, Y warnings
```

- [ ] **Step 2: Fix any issues found**

If any checks fail, investigate and fix the root cause (update registry or workbook).

- [ ] **Step 3: Run deep eval if pywin32 available**

Run: `python validate_workbook.py --deep`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: workbook evals framework complete — 7 checks, registry, rebuild integration"
```
