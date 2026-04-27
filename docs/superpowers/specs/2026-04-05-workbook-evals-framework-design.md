# Workbook Evals Framework Design

**Date:** 2026-04-05
**Status:** Approved

## Problem

The portfolio analysis workbook has 8 tabs with cross-sheet references that break when tabs are restructured (rows added/removed). During today's session we hit: stale cross-sheet refs after tab rebuilds, `insert_rows` breaking formulas, wrong data source in dividend formulas, and formula drift in monthly calculations. Financial data requires high accuracy — silent errors are unacceptable.

## Design

### 1. Reference Registry (`registry.py`)

A single source of truth for where key cells live in each tab. Every rebuild script and the Dashboard use this registry. The validator checks that actual cell labels match expected labels.

```python
REGISTRY = {
    "TabName": {
        "key_name": ("column", row_number, "expected_label_in_col_A"),
        ...
    },
    ...
}
```

**Entries per tab:** TWR, MWRR, Cost Basis Return, Total YTD Gain, Dividends, Unrealized G/L, Realized G/L, Holdings Total (MV, Cost Basis, G/L), Monthly first/last/totals rows, Net Portfolio Value.

**Dashboard entries:** Each account row, total portfolio row, liquidity rows, benchmark rows, key metrics rows.

### 2. Validation Checks

Seven checks, each returns a list of `{severity, tab, cell, message}` findings.

| # | Check | What it catches | Severity |
|---|---|---|---|
| 1 | **Label matching** | Row drift after insert/delete | ERROR |
| 2 | **Formula error scan** | #REF!, #VALUE!, #DIV/0!, #NAME? | ERROR |
| 3 | **Cross-sheet reference integrity** | Broken refs to other tabs, wrong row targets | ERROR |
| 4 | **Balance continuity** | Monthly ending != next month beginning ($0.01 tolerance) | ERROR |
| 5 | **Accounting identity** | Ending != Begin + Adds - Subs + Change ($1 tolerance) | ERROR |
| 6 | **Holdings total** | Individual holdings don't sum to total row ($0.01 tolerance) | ERROR |
| 7 | **YTD gain consistency** | Total YTD != Unrealized + Realized + Dividends ($1 tolerance) | ERROR |

### 3. Integration Points

**Rebuild scripts (lightweight):** After saving, call `validate_structural(workbook_path, tab_name)` — runs checks 1, 4, 5, 6 for that tab only. Prints issues but still saves.

**Weekly pipeline:** After `build_xlsx()`, call `validate_full(workbook_path)` — runs all 7 checks across all tabs. Results in pipeline log. Exit code 2 if errors found.

**Standalone CLI:** `python validate_workbook.py [--deep]` — runs all checks. `--deep` triggers COM pass.

**Error handling:** Warn and save. Never auto-fix financial data. Never block saving. Print clear report with pass/fail/warn per check per tab.

### 4. COM Deep Eval (optional, `--deep` flag)

Uses win32com to open workbook in Excel, force recalculation, and check:
- Formula cells that evaluate to error types
- Formula cells evaluating to 0 where non-zero expected
- Delta between COM-evaluated and openpyxl cached values (>$1 = WARN)

Graceful fallback if win32com or Excel unavailable.

### 5. Output Format

```
=== WORKBOOK VALIDATION ===
[PASS] Robinhood: Label matching (12/12 labels correct)
[PASS] Robinhood: Balance continuity (3 months checked)
[FAIL] Dashboard: Cross-sheet ref - C8 references '401(k)'!G8 but row 8 is "Q4" (expected current balance)
[WARN] Fidelity Brokerage: HUT cost basis is empty (row 23, col E)

Summary: 15 passed, 1 failed, 1 warning
```

### 6. File Structure

```
Project Finance/
  registry.py             -- cell location registry (shared)
  validate_workbook.py    -- standalone validator + all check functions
  rebuild_rh_tab.py       -- imports registry, calls validate after save
  rebuild_hsa_tab.py      -- same
  rebuild_roth_tab.py     -- same
  rebuild_brok_tab.py     -- same
  rebuild_dashboard.py    -- same
  weekly_pipeline.py      -- calls full validation after build
```

## Decision Log

- **When to run:** Both embedded in rebuild scripts (lightweight) and standalone (full)
- **Error behavior:** Warn and save, never auto-fix or block
- **Approach:** Hybrid openpyxl (structural) + optional COM (value evaluation)
- **Tolerances:** $0.01 for balance continuity and holdings totals, $1 for accounting identity and YTD gain consistency
