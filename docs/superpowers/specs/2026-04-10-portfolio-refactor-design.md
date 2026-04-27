# Portfolio Analysis System Refactor — Design Spec

## Goal

Replace the current multi-file, hardcoded-row workbook build system with a clean data-driven architecture: JSON data files, a pure computation model, and a single declarative workbook builder. Remove Playwright browser automation (Fidelity now via SnapTrade).

## Architecture

Data (JSON per account) flows into a portfolio model (pure Python computation), which feeds a single workbook builder (declarative sections, auto-generated named ranges). The old rebuild scripts remain as a fallback for one week, then are deleted.

```
data/*.json + live extraction + benchmarks
        |
        v
portfolio_model.py  (merge + compute all returns)
        |
        v
build_workbook.py   (declarative sections -> Excel)
        |
        v
2026_Portfolio_Analysis.xlsx
```

## Data Sources

| Source | Provider | Accounts |
|--------|----------|----------|
| SnapTrade | REST API | Robinhood, Fidelity Brokerage, Fidelity Roth IRA, Fidelity HSA |
| Plaid | REST API | Merrill 401(k) (investments), Chase (cash), Marcus (cash) |
| yfinance | Yahoo Finance | S&P 500, Dow Jones, NASDAQ benchmarks |
| JSON files | Manual | Monthly statements, angel investments, 401(k) quarterly |

Playwright browser automation is removed. Fidelity extraction moves to SnapTrade.

---

## Data Files

Location: `data/` directory, one JSON file per account.

### Standard account (Fidelity Brokerage, Roth IRA, HSA, Robinhood)

```json
{
  "account": {
    "name": "Fidelity Brokerage",
    "tab_name": "Fidelity Brokerage",
    "number": "Z23-889908",
    "type": "liquid",
    "provider": "snaptrade"
  },
  "monthly": {
    "Jan": {"begin": 25312.20, "add": 45018.97, "sub": 8397.53, "div": 84.70, "change": 525.17, "end": 62458.81},
    "Feb": {"begin": 62458.81, "add": 17.60, "sub": 5100.57, "div": 77.16, "change": 2533.26, "end": 59909.10},
    "Mar": {"begin": 59909.10, "add": 0, "sub": 0, "div": 79.27, "change": 14643.87, "end": 74552.97}
  },
  "holdings": [
    {"ticker": "AAPL", "qty": 17.383, "price": 253.79, "mv": 4411.63, "cb": 3999.91},
    {"ticker": "ARM", "qty": 20, "price": 151.28, "mv": 3025.60, "cb": 1196.00}
  ],
  "sold": [
    {"ticker": "WMT", "date": "Jan 2026", "qty": 1.386, "cb": 940.14, "proceeds": 1317.21, "action": "RSU vest sells"},
    {"ticker": "HUT", "date": "Feb 2026", "qty": 45, "cb": null, "proceeds": 1305.45, "action": "Partial exit (cost unknown)"}
  ]
}
```

### Robinhood additions
- Each holding adds `"avg_cost"` field
- Top-level adds `"margin_debt": -6834.31`

### 401(k)
- Uses `"quarterly"` instead of `"monthly"` with fields: `period`, `beginning`, `ee_contributions`, `er_contributions`, `fees`, `change_in_value`, `ending`
- Holdings are fund names, not tickers: `{"name": "BlackRock Russell 1000 Index", "beginning": 49775.97, "ending": 54939.88, "gain": 842.30}`
- `"type": "illiquid"`

### Angel Investments
- Uses `"investments"` array: `{"company": "Anduril", "sector": "Defense Tech", "year": 2024, "series": "Series E", "amount_invested": 10000, "post_money": 14000000000, "latest_valuation": 28500000000, "valuation_source": "Series H (pending), Mar 2026"}`
- `"type": "illiquid"`

### Cash
- `"plaid_institutions": ["chase", "marcus"]` — balances fetched live via Plaid API
- `"embedded_cash"` section for Fidelity core cash (already in account balances, reference only)

---

## Portfolio Model (`portfolio_model.py`)

Pure computation module. No openpyxl, no Excel. Reads data + live extractions, returns a dict.

### Interface

```python
model = build_model(data_dir="data/", live_extraction=None, benchmarks=None, snapshot_dir=None)
```

### Output structure

```python
{
    "as_of": "2026-04-10",
    "year": 2026,
    "accounts": {
        "fidelity_brokerage": {
            "name": "Fidelity Brokerage",
            "tab_name": "Fidelity Brokerage",
            "type": "liquid",
            "monthly": {"Jan": {...}, "Feb": {...}, ...},
            "holdings": [{"ticker": "AAPL", ...}, ...],
            "holdings_source": "live" | "statement",
            "sold": [...],
            "returns": {
                "twr": 0.3217,
                "mwrr": 2.1841,
                "cb_return": 0.1569,
            },
            "gains": {
                "dividends": 241.13,
                "unrealized": 11683.22,
                "realized": 1045.30,
                "total": 12969.65,
            },
        },
        ...
    },
    "liquid_accounts": ["fidelity_brokerage", "fidelity_roth_ira", "fidelity_hsa", "robinhood"],
    "illiquid_accounts": ["k401", "angel"],
    "liquid_twr": 0.1071,
    "benchmarks": {"S&P 500": -0.0049, "Dow Jones": -0.0041, "NASDAQ": -0.0178},
    "daily_summary": {
        "liquid_change": 2345.67,
        "liquid_change_pct": 0.017,
        "top_movers": [...],
        "stale_sources": [],
    } | None,
    "cash": {
        "external": {"chase": 2343.63, "marcus": 44487.65},
        "embedded": {"fidelity_brokerage": 88.35, "fidelity_roth_ira": 1.35, "fidelity_hsa": 4623.49},
    },
}
```

### Computation responsibilities

- **TWR**: `PRODUCT(monthly_growth_factors) - 1` per account
- **MWRR**: Newton-Raphson IRR from monthly cash flows, annualized
- **CB Return**: `total_unrealized_gl / total_cost_basis` from holdings
- **Liquid TWR**: Aggregated Modified Dietz across all liquid accounts
- **Gains**: Sum dividends from monthly totals, unrealized from holdings G/L, realized from sold proceeds
- **Live merge**: If live extraction has holdings for an account, replace JSON holdings. Track source in `holdings_source`.
- **Daily summary**: Load today's + previous snapshot, compute diff via `daily_snapshot.py`
- **Cash**: Fetch Plaid balances for external cash, read embedded from account JSON

---

## Workbook Builder (`build_workbook.py`)

### Entry point

```python
def build(model, output_path="2026_Portfolio_Analysis.xlsx"):
    wb = openpyxl.Workbook()
    build_dashboard(wb, model)
    for key in model["liquid_accounts"]:
        build_account_tab(wb, model["accounts"][key], model)
    for key in model["illiquid_accounts"]:
        build_account_tab(wb, model["accounts"][key], model)
    build_cash_tab(wb, model)
    wb.save(output_path)
```

### Declarative section structure

Each tab is defined as an ordered list of sections. A shared `write_sections()` function handles row tracking, section headers, and row map generation.

```python
def build_account_tab(wb, acct, model):
    sections = [
        ("YTD RETURN CALCULATIONS", build_return_section),
        ("YTD INVESTMENT GAIN SUMMARY", build_gain_section),
        ("CURRENT HOLDINGS", build_holdings_section),
        ("MONTHLY CALCULATIONS", build_monthly_section),
        ("SOLD POSITIONS", build_sold_section),
    ]
    ws, row_map = write_sections(wb, acct["tab_name"], acct, sections)
    define_names(wb, acct, row_map)
```

Reordering sections = reordering items in the list. Row numbers auto-adjust. Named ranges auto-adjust.

### Formula strategy

- **Within-tab**: Excel formulas for per-row computations (Gain/Loss = `=D{r}-E{r}`, Return % = `=IF(E{r}=0,"",F{r}/E{r})`, Monthly Return, Growth Factor, SUM totals)
- **Cross-tab (Dashboard)**: Computed values from the model, not formulas. Cell comments explain the computation.
- **Named ranges**: Defined as cells are created. Used by Excel Name Manager for transparency. Not used in formulas (since cross-tab refs are values).

### Dashboard sections

1. **Daily Summary** — prose format from `model["daily_summary"]`
2. **YTD Benchmark Comparison** — benchmarks + alpha (computed values)
3. **YTD Investment Gain** — aggregated gains (computed values)
4. **Account Overview** — liquid accounts, subtotal, external cash, illiquid accounts, subtotal, total. Liquid/illiquid grouping driven by `model["liquid_accounts"]` and `model["illiquid_accounts"]`.
5. **Sector Concentration**
6. **Geographic Concentration**
7. **Risk Metrics**
8. **Return Metric Definitions**

### Shared formatting

One set of style constants (fonts, fills, borders, number formats) used by all sections. No duplication across files.

---

## Pipeline Integration (`weekly_pipeline.py`)

### Extraction flow (Playwright removed)

```
SnapTrade (Robinhood + Fidelity)  → raw["robinhood"], raw["fidelity"]
Plaid investments (Merrill)        → raw["merrill"]
Plaid cash (Chase, Marcus)         → raw["chase"], raw["marcus"]
yfinance                           → benchmarks
```

No Playwright, no browser timeout, no 2FA issues.

### Build flow with fallback

```python
try:
    from portfolio_model import build_model
    from build_workbook import build
    model = build_model("data/", raw, benchmarks)
    build(model, output_path)
    save_snapshot_from_model(model)
except Exception as e:
    logging.warning(f"New builder failed ({e}), falling back")
    _run_rebuild_scripts()
```

After one week of successful runs, remove `_run_rebuild_scripts()` and delete old rebuild scripts.

### Fallback for missing sources

Same as current: `load_last_good_source()` fills missing extraction data from previous runs. The model's `holdings_source` field tracks which accounts used fallback data. Dashboard Daily Summary reports stale sources.

---

## Registry (`registry.py`)

Simplified role: the workbook builder generates the row map as it writes cells. Named ranges are defined inline during build. The registry becomes an output of the build process, not an input.

`registry_data.json` is still written (for the validator), but it's auto-generated — never hand-edited.

---

## Redact Script (`redact_for_screenshot.py`)

Simplified: Dashboard cross-tab cells are computed values, not formulas. The formula evaluator only handles within-tab formulas (SUM, arithmetic, IF, PRODUCT). Named range resolution is still available as a safety net but rarely needed.

---

## Migration Plan

1. Create `data/*.json` files from existing hardcoded data in rebuild scripts
2. Build `portfolio_model.py` — reads JSON, computes all returns, outputs model dict
3. Build `build_workbook.py` — reads model, writes Excel with declarative sections
4. Wire into pipeline with fallback to old rebuild scripts
5. Remove Playwright extraction from pipeline
6. Run both systems in parallel for 1 week
7. Delete old rebuild scripts + Playwright files

---

## Files Deleted After Migration

- `rebuild_brok_tab.py`
- `rebuild_roth_tab.py`
- `rebuild_hsa_tab.py`
- `rebuild_rh_tab.py`
- `rebuild_cash_tab.py`
- `rebuild_dashboard.py`
- `fidelity_extract.py`

## Success Criteria

- Pipeline runs daily at 4pm, builds workbook from model, zero fallback to old scripts for 7 consecutive days
- All current workbook features preserved (sections, formatting, named ranges, gridlines off)
- Adding a new month's statement data = editing one JSON file
- Reordering tab sections = reordering a Python list
- No hardcoded row numbers anywhere outside the builder's auto-tracked row map
