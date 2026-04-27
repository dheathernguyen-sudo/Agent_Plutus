# Cash Account Integration — Chase & Marcus by Goldman Sachs

## Overview

Add Chase and Marcus by Goldman Sachs cash accounts to the portfolio tracker via Plaid automated balance pulling. Includes a dedicated Cash tab with current balances and monthly history, plus Dashboard integration.

## Data Flow

```
Plaid API (Chase, Marcus)
  -> extract_plaid_cash()          [plaid_extract.py — new function]
  -> raw extraction output         [weekly_raw_TIMESTAMP.json]
  -> cash_history.json             [extract_output/ — persistent, append-only]
  -> build_portfolio.py            [reads history + current balances]
  -> Cash tab + Dashboard row      [2026_Portfolio_Analysis.xlsx]
```

## 1. Plaid Connection (plaid_extract.py)

### Config changes (~/.portfolio_extract/config.json)

Add Chase and Marcus under `config["plaid"]["institutions"]`:

```json
{
  "plaid": {
    "institutions": {
      "merrill": { "access_token": "...", "account_ids": ["..."] },
      "chase": { "access_token": "...", "account_ids": ["..."], "type": "cash" },
      "marcus": { "access_token": "...", "account_ids": ["..."], "type": "cash" }
    }
  }
}
```

The `"type": "cash"` flag distinguishes cash-only institutions from investment institutions (like Merrill).

### New function: extract_plaid_cash(config)

- Iterates over Plaid institutions where `type == "cash"`
- Calls `accounts_get()` (NOT `investments_holdings_get`) — these are deposit accounts
- Returns dict:

```python
{
  "chase": {
    "accounts": [
      {"name": "Chase Checking", "balance": 15234.56, "type": "depository", "account_id": "..."}
    ],
    "total": 15234.56
  },
  "marcus": {
    "accounts": [
      {"name": "Marcus Savings", "balance": 42000.00, "type": "depository", "account_id": "..."}
    ],
    "total": 42000.00
  }
}
```

### Setup flow

Reuse existing `setup_plaid()` OAuth flow. The user runs `python plaid_extract.py --setup` and selects Chase or Marcus. The `transactions` product (or just `auth`) is sufficient for balance reads — no `investments` product needed.

Update `setup_plaid()` to:
- Ask whether the institution is investment or cash type
- Store `"type": "cash"` in config for cash institutions
- Use appropriate Plaid products (`["transactions"]` for cash vs `["investments"]` for investment accounts)

## 2. Pipeline Integration (weekly_pipeline.py)

### extract_all() changes

After existing SnapTrade and Plaid investment extractions, call `extract_plaid_cash(config)`. Include results in the raw extraction output under a `"cash_accounts"` key.

### Cash history persistence

After extraction, append a timestamped snapshot to `extract_output/cash_history.json`:

```json
[
  {"date": "2026-04-04", "chase": 15234.56, "marcus": 42000.00, "total": 57234.56},
  {"date": "2026-04-11", "chase": 14890.12, "marcus": 42000.00, "total": 56890.12}
]
```

Logic:
- Load existing `cash_history.json` (or start empty list)
- Append new entry with today's date and per-institution totals
- Deduplicate by date (if pipeline runs twice on same day, overwrite that day's entry)
- Save back to file

### prepare_builder_data() changes

Pass cash data (current balances + history) to `build_workbook()` as a new parameter.

## 3. Cash Tab (build_portfolio.py)

### New function: build_cash_tab(wb, cash_current, cash_history)

**Top section: Current Balances (rows 3-7)**

| Account | Institution | Balance |
|---|---|---|
| Chase Checking | Chase | $15,234.56 |
| Marcus Savings | Marcus (Goldman Sachs) | $42,000.00 |
| **TOTAL CASH** | | **$57,234.56** |

- Account names and balances: BLUE (hardcoded from Plaid)
- TOTAL row: SUM formula (BLACK)
- Returns the row number of the TOTAL CASH row for Dashboard cross-references

**Bottom section: Monthly Balance History (rows 9+)**

| Month | Chase | Marcus | Total |
|---|---|---|---|
| January 2026 | -- | -- | -- |
| February 2026 | -- | -- | -- |
| March 2026 | $15,234.56 | $42,000.00 | $57,234.56 |
| April 2026 | $14,890.12 | $42,000.00 | $56,890.12 |

- For each month Jan-Dec, find the latest snapshot in that month from cash_history.json
- Months with no data show "--"
- Total column: SUM formula across institutions
- All values BLUE (hardcoded from historical data)

## 4. Dashboard Changes (build_portfolio.py)

### Account Summary

Add a **"Cash"** row after Robinhood (before TOTAL):

```python
acct_rows = [
    ("Fidelity Brokerage", "'Fidelity Brokerage'", "fid_brokerage"),
    ("Fidelity Roth IRA", "'Fidelity Roth IRA'", "standard"),
    ("401(k)", "'401(k)'", "401k"),
    ("Fidelity HSA", "'Fidelity HSA'", "fid_hsa"),
    ("Angel Investments", "'Angel Investments'", "angel"),
    ("Robinhood", "'Robinhood'", "robinhood"),
    ("Cash", "'Cash'", "cash"),  # NEW
]
```

Cash row values:
- **Beginning**: cross-sheet ref to earliest month's Total in Cash tab (GREEN)
- **Ending**: cross-sheet ref to TOTAL CASH row in Cash tab (GREEN)
- **Net Cash Flow**: "N/A" (GRAY) — deposits/withdrawals not tracked
- **TWR/MWRR/CB Return/Alpha**: "N/A" (GRAY) — cash has no market returns

### Liquidity Breakdown

Update Liquid row formula to include Cash:
- Currently: `Fid Brok + Roth IRA + HSA + Robinhood` (4 accounts)
- New: `Fid Brok + Roth IRA + HSA + Robinhood + Cash` (5 accounts)
- Update description text: "5 accounts", "Fid Brok + Roth IRA + HSA + Robinhood + Cash"

### Key Metrics

Total Portfolio Value and Capital Deployed already use SUM over the account rows, so adding a new row automatically includes Cash.

### Sector & Geographic Concentration

Cash is excluded — it's not a security, so no sector/geo mapping needed.

### Benchmark Comparison

Cash row excluded from alpha calculations (TWR is N/A). The existing alpha loops in `build_dashboard()` (lines 681-689) hardcode account row offsets like `first_r+5` for Robinhood. These must be updated to skip the new Cash row, since Cash has no TWR to compare against benchmarks.

## 5. manual_data.json cleanup

The existing `cash_balances` key in manual_data.json stores Fidelity per-account cash. These Fidelity cash balances are actually part of the SnapTrade holdings data (FCASH positions). This key can remain as-is for Fidelity — it's a separate concept from the Chase/Marcus external cash accounts.

No changes to manual_data.json needed.

## 6. Files Modified

| File | Change |
|---|---|
| `plaid_extract.py` | Add `extract_plaid_cash()`, update `setup_plaid()` for cash institution type |
| `weekly_pipeline.py` | Call `extract_plaid_cash()` in pipeline, persist to `cash_history.json`, pass to builder |
| `build_portfolio.py` | Add `build_cash_tab()`, update `build_dashboard()` for Cash row + liquidity, update `build_workbook()` signature |
| `~/.portfolio_extract/config.json` | Add chase + marcus institutions after Plaid OAuth setup |

## 7. New Files

| File | Purpose |
|---|---|
| `extract_output/cash_history.json` | Persistent append-only balance history (gitignored) |

## 8. No Changes Needed

- `fidelity_csv.py` — unrelated
- `manual_data.json` — Fidelity cash balances stay as-is
- `schedule_task.xml` / `run_pipeline.bat` — pipeline entry point unchanged
