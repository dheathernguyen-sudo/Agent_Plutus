# Portfolio Analysis System Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 6 rebuild scripts + build_portfolio.py with a data-driven system: JSON data files, a portfolio model (pure computation), and a single declarative workbook builder. Remove Playwright dependency.

**Architecture:** Account data lives in `data/*.json`. `portfolio_model.py` merges JSON + live API data and computes all returns. `build_workbook.py` writes Excel using declarative section lists with auto-tracked row numbers and named ranges. Old rebuild scripts kept as fallback for 1 week.

**Tech Stack:** Python 3.12, openpyxl, json, pathlib. No new dependencies.

---

## Task Overview

| Task | What | Files |
|------|------|-------|
| 1 | Create JSON data files | `data/*.json` (7 files) |
| 2 | Build portfolio model | `portfolio_model.py` |
| 3 | Build shared Excel helpers | `build_workbook.py` (helpers only) |
| 4 | Build account tab writer | `build_workbook.py` (account tabs) |
| 5 | Build Dashboard writer | `build_workbook.py` (Dashboard) |
| 6 | Build Cash tab writer | `build_workbook.py` (Cash tab) |
| 7 | Wire into pipeline with fallback | `weekly_pipeline.py` |
| 8 | Simplify redact script | `redact_for_screenshot.py` |
| 9 | Verify end-to-end | Run pipeline, compare output |

---

### Task 1: Create JSON data files

**Files:**
- Create: `data/fidelity_brokerage.json`
- Create: `data/fidelity_roth_ira.json`
- Create: `data/fidelity_hsa.json`
- Create: `data/robinhood.json`
- Create: `data/k401.json`
- Create: `data/angel.json`
- Create: `data/cash.json`

- [ ] **Step 1: Create `data/` directory**

Run: `mkdir data`

- [ ] **Step 2: Create `data/fidelity_brokerage.json`**

Extract all hardcoded data from `rebuild_brok_tab.py` (holdings at lines 191-211, monthly at lines 257-264, sold at lines 318-322):

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
    {"ticker": "ASML", "qty": 2, "price": 1320.83, "mv": 2641.66, "cb": 2096.00},
    {"ticker": "AAPL", "qty": 17.383, "price": 253.79, "mv": 4411.63, "cb": 3999.91},
    {"ticker": "ARM", "qty": 20, "price": 151.28, "mv": 3025.60, "cb": 1196.00},
    {"ticker": "CAVA", "qty": 72.757, "price": 80.90, "mv": 5886.04, "cb": 3999.96},
    {"ticker": "CAT", "qty": 10, "price": 708.46, "mv": 7084.60, "cb": 2146.53},
    {"ticker": "C", "qty": 41.054, "price": 113.41, "mv": 4655.93, "cb": 4999.97},
    {"ticker": "DIS", "qty": 20, "price": 96.38, "mv": 1927.60, "cb": 1843.49},
    {"ticker": "META", "qty": 2, "price": 572.13, "mv": 1144.26, "cb": 1154.53},
    {"ticker": "GEV", "qty": 5, "price": 872.90, "mv": 4364.50, "cb": 3140.99},
    {"ticker": "HUT", "qty": 182.794, "price": 46.91, "mv": 8574.86, "cb": null},
    {"ticker": "LEN", "qty": 15, "price": 86.84, "mv": 1302.60, "cb": 1816.05},
    {"ticker": "MSFT", "qty": 10, "price": 370.17, "mv": 3701.70, "cb": 2605.70},
    {"ticker": "MRP", "qty": 7, "price": 28.00, "mv": 196.00, "cb": 164.43},
    {"ticker": "NKE", "qty": 20, "price": 52.82, "mv": 1056.40, "cb": 1542.00},
    {"ticker": "NOW", "qty": 25, "price": 104.55, "mv": 2613.75, "cb": 4605.00},
    {"ticker": "WMT", "qty": 140.526, "price": 124.28, "mv": 17464.57, "cb": 17473.00},
    {"ticker": "WDC", "qty": 11.829, "price": 270.49, "mv": 3199.62, "cb": 2499.89},
    {"ticker": "WY", "qty": 50, "price": 24.43, "mv": 1221.50, "cb": 1676.50}
  ],
  "cash_position": 80.15,
  "sold": [
    {"ticker": "WMT", "date": "Jan 2026", "qty": 136.806, "cb": 15258.96, "proceeds": 15847.46, "action": "RSU vest sells"},
    {"ticker": "HUT", "date": "Feb 2026", "qty": 73.206, "cb": null, "proceeds": 4000.00, "action": "Partial exit (cost unknown)"},
    {"ticker": "JPM", "date": "Feb 2026", "qty": 3.305, "cb": 999.73, "proceeds": 1019.46, "action": "Full exit"}
  ],
  "sector_map": {
    "ASML": {"sector": "Technology", "country": "Netherlands"},
    "AAPL": {"sector": "Technology", "country": "United States"},
    "ARM": {"sector": "Technology", "country": "United Kingdom"},
    "CAVA": {"sector": "Consumer Discretionary", "country": "United States"},
    "CAT": {"sector": "Industrials", "country": "United States"},
    "C": {"sector": "Financials", "country": "United States"},
    "DIS": {"sector": "Consumer Discretionary", "country": "United States"},
    "META": {"sector": "Communication Services", "country": "United States"},
    "GEV": {"sector": "Industrials", "country": "United States"},
    "HUT": {"sector": "Technology", "country": "Canada"},
    "LEN": {"sector": "Consumer Discretionary", "country": "United States"},
    "MSFT": {"sector": "Technology", "country": "United States"},
    "MRP": {"sector": "Other", "country": "United States"},
    "NKE": {"sector": "Consumer Discretionary", "country": "United States"},
    "NOW": {"sector": "Technology", "country": "United States"},
    "WMT": {"sector": "Consumer Discretionary", "country": "United States"},
    "WDC": {"sector": "Technology", "country": "United States"},
    "WY": {"sector": "Real Estate", "country": "United States"}
  }
}
```

- [ ] **Step 3: Create `data/fidelity_roth_ira.json`**

Same structure. Data from `rebuild_roth_tab.py`:

```json
{
  "account": {
    "name": "Fidelity Roth IRA",
    "tab_name": "Fidelity Roth IRA",
    "number": "266-209863",
    "type": "liquid",
    "provider": "snaptrade"
  },
  "monthly": {
    "Jan": {"begin": 0, "add": 24964.55, "sub": 50.00, "div": 1.16, "change": -427.76, "end": 24486.79},
    "Feb": {"begin": 24486.79, "add": 7430.24, "sub": 0, "div": 20.88, "change": -328.24, "end": 31588.79},
    "Mar": {"begin": 31588.79, "add": 0, "sub": 0, "div": 26.65, "change": -2027.81, "end": 29560.98}
  },
  "holdings": [
    {"ticker": "GOOGL", "qty": 15, "price": 287.56, "mv": 4313.40, "cb": 2301.71},
    {"ticker": "AMZN", "qty": 19.574, "price": 208.27, "mv": 4076.67, "cb": 3936.75},
    {"ticker": "BA", "qty": 10, "price": 199.03, "mv": 1990.30, "cb": 1906.80},
    {"ticker": "BLDR", "qty": 10, "price": 82.33, "mv": 823.30, "cb": 1729.30},
    {"ticker": "CRWD", "qty": 10, "price": 390.41, "mv": 3904.10, "cb": 2681.60},
    {"ticker": "FLJP", "qty": 105.392, "price": 36.18, "mv": 3813.08, "cb": 4000.00},
    {"ticker": "FLKR", "qty": 92.614, "price": 39.87, "mv": 3692.52, "cb": 3999.95},
    {"ticker": "UPS", "qty": 4, "price": 98.38, "mv": 393.52, "cb": 449.48}
  ],
  "cash_position": 6554.09,
  "sold": [
    {"ticker": "SPY", "date": "Feb 2026", "qty": 6.0, "cb": 3586.92, "proceeds": 4108.83, "action": "Sold to fund new positions"},
    {"ticker": "VB", "date": "Feb 2026", "qty": 4.0, "cb": 802.64, "proceeds": 915.56, "action": "Sold to fund new positions"},
    {"ticker": "COST", "date": "Mar 2026", "qty": 3.0, "cb": 3015.48, "proceeds": 2977.88, "action": "Full exit"}
  ],
  "sector_map": {
    "GOOGL": {"sector": "Technology", "country": "United States"},
    "AMZN": {"sector": "Technology", "country": "United States"},
    "BA": {"sector": "Industrials", "country": "United States"},
    "BLDR": {"sector": "Industrials", "country": "United States"},
    "CRWD": {"sector": "Technology", "country": "United States"},
    "FLJP": {"sector": "Diversified/ETF", "country": "Japan"},
    "FLKR": {"sector": "Diversified/ETF", "country": "South Korea"},
    "UPS": {"sector": "Industrials", "country": "United States"}
  },
  "cash_flow_labels": {"add": "Contributions", "sub": "Distributions"}
}
```

- [ ] **Step 4: Create `data/fidelity_hsa.json`**

```json
{
  "account": {
    "name": "Fidelity HSA",
    "tab_name": "Fidelity HSA",
    "number": "249-509651",
    "type": "liquid",
    "provider": "snaptrade"
  },
  "monthly": {
    "Jan": {"begin": 14036.28, "add": 0, "sub": 0, "div": 24.25, "change": 705.33, "end": 14741.61},
    "Feb": {"begin": 14741.61, "add": 3950.00, "sub": 0, "div": 7.64, "change": 950.93, "end": 19642.54},
    "Mar": {"begin": 19642.54, "add": 500.00, "sub": 0, "div": 30.39, "change": -1124.53, "end": 19018.01}
  },
  "holdings": [
    {"ticker": "CEG", "qty": 12, "price": 279.25, "mv": 3351.00, "cb": 2187.16},
    {"ticker": "DLR", "qty": 10, "price": 180.21, "mv": 1802.10, "cb": 1480.30},
    {"ticker": "KDEF", "qty": 49.636, "price": 52.73, "mv": 2617.30, "cb": 3000.00},
    {"ticker": "NFLX", "qty": 20, "price": 96.15, "mv": 1923.00, "cb": 2363.16},
    {"ticker": "STX", "qty": 12, "price": 391.76, "mv": 4701.12, "cb": 1112.16}
  ],
  "cash_position": 4623.49,
  "sold": [
    {"ticker": "SPY", "date": "Feb 2026", "qty": 1.551, "cb": 999.51, "proceeds": 1075.32, "action": "Sold to buy KDEF"},
    {"ticker": "VB", "date": "Feb 2026", "qty": 2.0, "cb": 401.32, "proceeds": 466.99, "action": "Sold to buy KDEF"},
    {"ticker": "QQQ", "date": "Feb 2026", "qty": 2.562, "cb": 1464.50, "proceeds": 1553.93, "action": "Sold to buy KDEF"}
  ],
  "realized_gl_override": 230.91,
  "sector_map": {
    "CEG": {"sector": "Utilities", "country": "United States"},
    "DLR": {"sector": "Real Estate", "country": "United States"},
    "KDEF": {"sector": "Diversified/ETF", "country": "Diversified Intl"},
    "NFLX": {"sector": "Communication Services", "country": "United States"},
    "STX": {"sector": "Technology", "country": "United States"}
  },
  "cash_flow_labels": {"add": "Contributions", "sub": "Distributions"}
}
```

- [ ] **Step 5: Create `data/robinhood.json`**

```json
{
  "account": {
    "name": "Robinhood",
    "tab_name": "Robinhood",
    "type": "liquid",
    "provider": "snaptrade",
    "is_margin": true
  },
  "monthly_source": "pdf_statements",
  "monthly": {},
  "holdings": [
    {"ticker": "AGIO", "qty": 50, "price": 35.19, "mv": 1759.50, "avg_cost": 35.14, "cb": 1757.00},
    {"ticker": "ISRG", "qty": 5, "price": 452.06, "mv": 2260.30, "avg_cost": 576.20, "cb": 2881.00},
    {"ticker": "MCK", "qty": 8, "price": 884.35, "mv": 7074.80, "avg_cost": 510.70, "cb": 4085.60},
    {"ticker": "MRVL", "qty": 20, "price": 107.11, "mv": 2142.20, "avg_cost": 118.62, "cb": 2372.40},
    {"ticker": "NVDA", "qty": 50, "price": 177.40, "mv": 8870.00, "avg_cost": 77.75, "cb": 3887.50},
    {"ticker": "RCL", "qty": 10, "price": 273.63, "mv": 2736.30, "avg_cost": 242.99, "cb": 2429.90},
    {"ticker": "RDDT", "qty": 15, "price": 136.05, "mv": 2040.75, "avg_cost": 155.82, "cb": 2337.30},
    {"ticker": "TSM", "qty": 14, "price": 338.945, "mv": 4745.23, "avg_cost": 194.69, "cb": 2725.66}
  ],
  "margin_debt": -14111.01,
  "margin_details": {
    "beginning_year": 14787.43,
    "ending": 14111.01
  },
  "sold": {
    "2026": [
      {"ticker": "NVO", "date": "Feb 2026", "qty": 40, "cb": 3556.00, "proceeds": 1955.20, "action": "Full exit"},
      {"ticker": "SPOT", "date": "Mar 2026", "qty": 6, "cb": 2829.60, "proceeds": 2875.14, "action": "Full exit"}
    ],
    "2025": [
      {"ticker": "ARM", "date": "Jan 2025", "qty": 1, "cb": null, "proceeds": 143.00, "action": "Full exit"},
      {"ticker": "PPLT", "date": "Jan 2025", "qty": 40, "cb": null, "proceeds": 3439.91, "action": "Full exit"},
      {"ticker": "MCK", "date": "Mar 2025", "qty": 1, "cb": 510.70, "proceeds": 656.02, "action": "Trim (9 to 8)"}
    ]
  },
  "sector_map": {
    "AGIO": {"sector": "Healthcare", "country": "United States"},
    "ISRG": {"sector": "Healthcare", "country": "United States"},
    "MCK": {"sector": "Healthcare", "country": "United States"},
    "MRVL": {"sector": "Technology", "country": "United States"},
    "NVDA": {"sector": "Technology", "country": "United States"},
    "RCL": {"sector": "Consumer Discretionary", "country": "United States"},
    "RDDT": {"sector": "Technology", "country": "United States"},
    "TSM": {"sector": "Technology", "country": "Taiwan"}
  }
}
```

- [ ] **Step 6: Create `data/k401.json`**

```json
{
  "account": {
    "name": "401(k)",
    "tab_name": "401(k)",
    "type": "illiquid",
    "provider": "plaid",
    "fiscal_year": "Nov-Oct"
  },
  "quarterly": [
    {
      "period": "Q1 (Nov 1 - Jan 31)",
      "beginning": 74631.09,
      "ee_contributions": 4236.94,
      "er_contributions": 2965.85,
      "fees": -0.06,
      "change_in_value": 1892.76,
      "ending": 83726.58
    }
  ],
  "holdings": [
    {"name": "BlackRock Russell 1000 Index", "beginning": 49775.97, "ending": 54939.88, "gain": 842.30},
    {"name": "BlackRock Russell 2000 Index", "beginning": 5918.93, "ending": 7707.55, "gain": 348.06},
    {"name": "BlackRock Intl Equity Index Trust", "beginning": 5771.16, "ending": 7776.75, "gain": 565.03},
    {"name": "JPMorgan Short Term Bond Trust", "beginning": 3893.32, "ending": 3941.72, "gain": 48.40},
    {"name": "BlackRock Gov't Money Market Fund", "beginning": 9271.71, "ending": 9360.68, "gain": 88.97}
  ],
  "twr_merrill_stated": 0.1441,
  "sector_map": {
    "BlackRock Russell 1000 Index": {"sector": "Diversified/Index", "country": "United States"},
    "BlackRock Russell 2000 Index": {"sector": "Diversified/Index", "country": "United States"},
    "BlackRock Intl Equity Index Trust": {"sector": "Diversified/Index", "country": "Diversified Intl"},
    "JPMorgan Short Term Bond Trust": {"sector": "Diversified/Index", "country": "United States"},
    "BlackRock Gov't Money Market Fund": {"sector": "Diversified/Index", "country": "United States"}
  }
}
```

- [ ] **Step 7: Create `data/angel.json`**

```json
{
  "account": {
    "name": "Angel Investments",
    "tab_name": "Angel Investments",
    "type": "illiquid",
    "provider": "manual"
  },
  "investments": [
    {"company": "Anduril", "sector": "Defense Tech", "year": 2022, "series": "Series E", "amount": 10000, "pm_invest": 8480000000, "pm_latest": 28500000000, "source": "Series H (pending), Mar 2026"},
    {"company": "Saronic", "sector": "Defense Tech", "year": 2024, "series": "Series B", "amount": 10000, "pm_invest": 1000000000, "pm_latest": 9250000000, "source": "Series D, Mar 2026"},
    {"company": "Auradine", "sector": "Technology", "year": 2025, "series": "Series C", "amount": 10000, "pm_invest": 845000000, "pm_latest": 845000000, "source": "At cost"},
    {"company": "Synchron", "sector": "Healthcare", "year": 2025, "series": "Series D", "amount": 10000, "pm_invest": 821500000, "pm_latest": 821500000, "source": "At cost"},
    {"company": "Deel", "sector": "Technology", "year": 2025, "series": "Series E", "amount": 10000, "pm_invest": 17300000000, "pm_latest": 17300000000, "source": "At cost"},
    {"company": "Upscale AI", "sector": "Technology", "year": 2025, "series": "Series A", "amount": 10000, "pm_invest": 1000000000, "pm_latest": 1000000000, "source": "At cost"},
    {"company": "Varda", "sector": "Industrials", "year": 2025, "series": "Series D", "amount": 10000, "pm_invest": 1580000000, "pm_latest": 1580000000, "source": "At cost"}
  ]
}
```

- [ ] **Step 8: Create `data/cash.json`**

```json
{
  "account": {
    "name": "Cash",
    "tab_name": "Cash",
    "type": "cash",
    "provider": "plaid"
  },
  "plaid_institutions": ["chase", "marcus"],
  "embedded_cash_accounts": {
    "fidelity_brokerage": "Fidelity Brokerage Core",
    "fidelity_roth_ira": "Fidelity Roth IRA Core",
    "fidelity_hsa": "Fidelity HSA Core"
  }
}
```

- [ ] **Step 9: Verify all JSON files parse**

Run: `python -c "import json, pathlib; [json.loads(f.read_text()) for f in pathlib.Path('data').glob('*.json')]; print('All 7 JSON files OK')"`

---

### Task 2: Build portfolio model

**Files:**
- Create: `portfolio_model.py`

This is a pure computation module. No openpyxl. Reads JSON data + optional live extraction, computes all returns, outputs a model dict.

- [ ] **Step 1: Create `portfolio_model.py` with data loading**

```python
"""portfolio_model.py — Pure computation model for portfolio analysis.

Reads account data from data/*.json, merges with live API extractions,
computes all return metrics. No Excel/openpyxl dependency.
"""

import json
import datetime
from pathlib import Path

MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _load_account_data(data_dir):
    """Load all account JSON files from data directory."""
    data_dir = Path(data_dir)
    accounts = {}
    for f in sorted(data_dir.glob("*.json")):
        d = json.loads(f.read_text())
        key = f.stem  # e.g. "fidelity_brokerage"
        accounts[key] = d
    return accounts


def _compute_twr(monthly):
    """Compute YTD Time-Weighted Return from monthly data using Modified Dietz."""
    populated = [m for m in MONTH_LABELS if m in monthly]
    if not populated:
        return None
    growth_factors = []
    for m in populated:
        d = monthly[m]
        begin = d.get("begin", 0) or 0
        end = d.get("end", 0) or 0
        add = d.get("add", 0) or 0
        sub = d.get("sub", 0) or 0
        net_flow = add - sub
        denom = begin + 0.5 * net_flow
        if denom == 0:
            continue
        ret = (end - begin - net_flow) / denom
        growth_factors.append(1 + ret)
    if not growth_factors:
        return None
    twr = 1
    for gf in growth_factors:
        twr *= gf
    return twr - 1


def _compute_mwrr(monthly):
    """Compute annualised Money-Weighted Return (IRR) from monthly data."""
    populated = [m for m in MONTH_LABELS if m in monthly]
    if not populated:
        return None
    first = monthly[populated[0]]
    last = monthly[populated[-1]]
    cfs = []
    t = 0
    cfs.append((t, -(first.get("begin", 0) or 0)))
    for m in populated:
        d = monthly[m]
        net = (d.get("add", 0) or 0) - (d.get("sub", 0) or 0)
        cfs.append((t + 0.5, -net))
        t += 1
    cfs.append((t, last.get("end", 0) or 0))
    r = 0.01
    for _ in range(200):
        npv = sum(cf / (1 + r) ** ti for ti, cf in cfs)
        dnpv = sum(-ti * cf / (1 + r) ** (ti + 1) for ti, cf in cfs)
        if abs(dnpv) < 1e-14:
            break
        r_new = r - npv / dnpv
        if abs(r_new - r) < 1e-12:
            r = r_new
            break
        r = r_new
    return (1 + r) ** 12 - 1


def _compute_gains(acct_data):
    """Compute gain breakdown from holdings and sold data."""
    holdings = acct_data.get("holdings", [])
    total_mv = sum(h.get("mv", 0) or 0 for h in holdings)
    total_cb = sum(h.get("cb", 0) or 0 for h in holdings if h.get("cb") is not None)
    unrealized = total_mv - total_cb

    # Dividends from monthly totals
    monthly = acct_data.get("monthly", {})
    dividends = sum(monthly.get(m, {}).get("div", 0) or 0
                    for m in MONTH_LABELS if m in monthly)

    # Realized from sold
    sold = acct_data.get("sold", [])
    if isinstance(sold, dict):
        # Robinhood has {"2026": [...], "2025": [...]}
        sold = sold.get("2026", [])
    realized = 0
    if acct_data.get("realized_gl_override") is not None:
        realized = acct_data["realized_gl_override"]
    else:
        for s in sold:
            cb = s.get("cb")
            proceeds = s.get("proceeds", 0) or 0
            if cb is not None:
                realized += proceeds - cb

    return {
        "dividends": round(dividends, 2),
        "unrealized": round(unrealized, 2),
        "realized": round(realized, 2),
        "total": round(dividends + unrealized + realized, 2),
        "total_mv": round(total_mv, 2),
        "total_cb": round(total_cb, 2),
    }


def _compute_cb_return(gains):
    """Cost basis return = unrealized / total cost basis."""
    if gains["total_cb"] == 0:
        return 0
    return gains["unrealized"] / gains["total_cb"]


def _merge_live_holdings(acct_data, live_extraction, acct_key):
    """If live extraction has holdings for this account, use them."""
    if not live_extraction:
        return acct_data.get("holdings", []), "statement"
    # Check SnapTrade/Plaid extraction for this account
    # Mapping from JSON key to extraction key
    key_map = {
        "fidelity_brokerage": "fidelity_Z23889908",
        "fidelity_roth_ira": "fidelity_266209863",
        "fidelity_hsa": "fidelity_249509651",
    }
    ext_key = key_map.get(acct_key, acct_key)
    if ext_key in live_extraction:
        live = live_extraction[ext_key]
        if isinstance(live, dict) and live:
            holdings = []
            for ticker, h in live.items():
                holdings.append({
                    "ticker": ticker,
                    "qty": h.get("qty", 0),
                    "price": h.get("price", 0),
                    "mv": h.get("mv", 0),
                    "cb": h.get("cb", 0),
                })
            if holdings:
                return holdings, "live"
    return acct_data.get("holdings", []), "statement"


def _compute_liquid_twr(accounts, model_accounts):
    """Compute aggregated Liquid Portfolio TWR across all liquid accounts."""
    liquid_keys = [k for k, v in accounts.items()
                   if v.get("account", {}).get("type") == "liquid"]
    growth_factors = []
    for i in range(12):
        m = MONTH_LABELS[i]
        cb = ce = ca = cs = 0
        for key in liquid_keys:
            monthly = accounts[key].get("monthly", {})
            if m not in monthly:
                continue
            d = monthly[m]
            cb += d.get("begin", 0) or 0
            ce += d.get("end", 0) or 0
            ca += d.get("add", 0) or 0
            cs += d.get("sub", 0) or 0
        if cb == 0 and ce == 0:
            continue
        net_flow = ca - cs
        denom = cb + 0.5 * net_flow
        if denom == 0:
            continue
        ret = (ce - cb - net_flow) / denom
        growth_factors.append(1 + ret)
    if not growth_factors:
        return None
    twr = 1
    for gf in growth_factors:
        twr *= gf
    return twr - 1


def _compute_sector_geo(all_accounts):
    """Compute sector and geographic concentration from all holdings."""
    sector_vals = {}
    sector_counts = {}
    sector_by_acct = {}
    geo_vals = {}

    acct_short = {
        "fidelity_brokerage": "Fidelity Brokerage",
        "fidelity_roth_ira": "Roth IRA",
        "fidelity_hsa": "HSA",
        "robinhood": "Robinhood",
        "angel": "Angel",
    }

    for acct_key, acct_data in all_accounts.items():
        short = acct_short.get(acct_key)
        if not short:
            continue
        smap = acct_data.get("sector_map", {})

        # For angel, use investments
        if acct_key == "angel":
            for inv in acct_data.get("investments", []):
                sector = inv.get("sector", "Other")
                amt = inv["amount"] * (inv["pm_latest"] / inv["pm_invest"]) if inv["pm_invest"] else inv["amount"]
                sector_vals[sector] = sector_vals.get(sector, 0) + amt
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                sector_by_acct.setdefault(sector, {})[short] = sector_by_acct.get(sector, {}).get(short, 0) + amt
            continue

        holdings = acct_data.get("holdings", [])
        margin_debt = acct_data.get("margin_debt", 0) or 0
        total_mv = sum(h.get("mv", 0) or 0 for h in holdings)
        scale = 1.0
        if margin_debt and total_mv:
            net = total_mv + margin_debt
            scale = net / total_mv if total_mv else 1.0

        for h in holdings:
            ticker = h.get("ticker", "")
            mv = (h.get("mv", 0) or 0) * scale
            info = smap.get(ticker, {"sector": "Other", "country": "United States"})
            sector = info["sector"]
            country = info["country"]

            sector_vals[sector] = sector_vals.get(sector, 0) + mv
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            sector_by_acct.setdefault(sector, {})[short] = sector_by_acct.get(sector, {}).get(short, 0) + mv
            geo_vals[country] = geo_vals.get(country, 0) + mv

    # Sort by value descending
    total = sum(sector_vals.values())
    sectors = []
    for sec in sorted(sector_vals, key=sector_vals.get, reverse=True):
        val = sector_vals[sec]
        sectors.append({
            "name": sec,
            "value": round(val, 2),
            "pct": round(val / total, 4) if total else 0,
            "count": sector_counts.get(sec, 0),
            "by_account": {k: round(v, 2) for k, v in sector_by_acct.get(sec, {}).items()},
        })

    geo_total = sum(geo_vals.values())
    us_val = geo_vals.pop("United States", 0)
    intl_val = geo_total - us_val
    geo = [
        {"region": "United States", "value": round(us_val, 2), "pct": round(us_val / geo_total, 4) if geo_total else 0},
        {"region": "International", "value": round(intl_val, 2), "pct": round(intl_val / geo_total, 4) if geo_total else 0},
    ]
    for country in sorted(geo_vals, key=geo_vals.get, reverse=True):
        val = geo_vals[country]
        geo.append({"region": f"  — {country}", "value": round(val, 2), "pct": round(val / geo_total, 4) if geo_total else 0})

    return sectors, geo


def build_model(data_dir="data/", live_extraction=None, benchmarks=None, snapshot_dir=None):
    """Build the complete portfolio model.

    Args:
        data_dir: path to JSON data files
        live_extraction: dict from pipeline extraction (fid_data format)
        benchmarks: dict like {"S&P 500": -0.0049, ...}
        snapshot_dir: path for daily snapshot comparison

    Returns:
        Model dict with all computed values.
    """
    accounts_raw = _load_account_data(data_dir)
    today = datetime.date.today()

    model = {
        "as_of": today.isoformat(),
        "year": today.year,
        "accounts": {},
        "liquid_accounts": [],
        "illiquid_accounts": [],
        "benchmarks": benchmarks or {},
        "daily_summary": None,
        "cash": {"external": {}, "embedded": {}},
        "sectors": [],
        "geo": [],
    }

    for key, raw in accounts_raw.items():
        acct_info = raw.get("account", {})
        acct_type = acct_info.get("type", "liquid")

        if acct_type == "cash":
            # Cash is handled separately
            continue

        monthly = raw.get("monthly", {})
        holdings, holdings_source = _merge_live_holdings(raw, live_extraction, key)
        gains = _compute_gains({**raw, "holdings": holdings})

        acct_model = {
            "name": acct_info.get("name", key),
            "tab_name": acct_info.get("tab_name", key),
            "type": acct_type,
            "provider": acct_info.get("provider", "manual"),
            "number": acct_info.get("number", ""),
            "is_margin": raw.get("is_margin", False),
            "monthly": monthly,
            "holdings": holdings,
            "holdings_source": holdings_source,
            "sold": raw.get("sold", []),
            "cash_position": raw.get("cash_position", 0),
            "margin_debt": raw.get("margin_debt", 0),
            "margin_details": raw.get("margin_details", {}),
            "cash_flow_labels": raw.get("cash_flow_labels", {"add": "Additions", "sub": "Subtractions"}),
            "returns": {
                "twr": _compute_twr(monthly),
                "mwrr": _compute_mwrr(monthly) if monthly else None,
                "cb_return": _compute_cb_return(gains),
            },
            "gains": gains,
            "sector_map": raw.get("sector_map", {}),
        }

        # Special handling for 401(k)
        if "quarterly" in raw:
            acct_model["quarterly"] = raw["quarterly"]
            acct_model["twr_merrill_stated"] = raw.get("twr_merrill_stated")
            # Compute 401k returns from quarterly data
            q_data = raw["quarterly"]
            if q_data:
                # Modified Dietz per quarter, then chain
                gfs = []
                for q in q_data:
                    b = q.get("beginning", 0)
                    contrib = q.get("ee_contributions", 0) + q.get("er_contributions", 0)
                    fees = q.get("fees", 0)
                    chg = q.get("change_in_value", 0)
                    e = q.get("ending", 0)
                    denom = b + 0.5 * (contrib + fees)
                    if denom:
                        gfs.append(1 + chg / denom)
                if gfs:
                    twr_q = 1
                    for gf in gfs:
                        twr_q *= gf
                    acct_model["returns"]["twr"] = twr_q - 1

        # Special handling for angel
        if "investments" in raw:
            acct_model["investments"] = raw["investments"]
            total_invested = sum(i["amount"] for i in raw["investments"])
            total_current = sum(
                i["amount"] * (i["pm_latest"] / i["pm_invest"]) if i["pm_invest"] else i["amount"]
                for i in raw["investments"]
            )
            acct_model["gains"] = {
                "total_invested": round(total_invested, 2),
                "total_current": round(total_current, 2),
                "total_mv": round(total_current, 2),
                "total_cb": round(total_invested, 2),
            }
            acct_model["returns"]["cb_return"] = (total_current - total_invested) / total_invested if total_invested else 0

        model["accounts"][key] = acct_model

        if acct_type == "liquid":
            model["liquid_accounts"].append(key)
        elif acct_type == "illiquid":
            model["illiquid_accounts"].append(key)

    # Liquid Portfolio TWR
    model["liquid_twr"] = _compute_liquid_twr(accounts_raw, model["accounts"])

    # Sector and geographic concentration
    model["sectors"], model["geo"] = _compute_sector_geo(accounts_raw)

    # Cash balances
    cash_config = accounts_raw.get("cash", {})
    model["cash"]["embedded"] = {
        k: accounts_raw.get(k, {}).get("cash_position", 0)
        for k in model["liquid_accounts"]
    }
    # External cash (Plaid) fetched at runtime by build_workbook or pipeline

    # Daily summary from snapshots
    if snapshot_dir:
        try:
            from daily_snapshot import load_snapshot, load_previous_snapshot, compute_daily_summary
            snap_today = load_snapshot(today.isoformat())
            snap_prev = load_previous_snapshot(today.isoformat())
            if snap_today and snap_prev:
                model["daily_summary"] = compute_daily_summary(snap_today, snap_prev)
        except Exception:
            pass

    return model
```

- [ ] **Step 2: Verify model builds from JSON data**

Run: `python -c "from portfolio_model import build_model; m = build_model(); print(f'Accounts: {list(m[\"accounts\"].keys())}'); print(f'Liquid TWR: {m[\"liquid_twr\"]:.4%}'); print(f'Sectors: {len(m[\"sectors\"])}')"`

Expected: Lists all 6 accounts, shows Liquid TWR ~10.71%, sectors > 0.

---

### Task 3: Build shared Excel helpers

**Files:**
- Create: `build_workbook.py` (shared helpers only in this task)

- [ ] **Step 1: Create `build_workbook.py` with styles and helpers**

```python
"""build_workbook.py — Declarative Excel workbook builder.

Reads a portfolio model dict and writes 2026_Portfolio_Analysis.xlsx.
Each tab is defined as an ordered list of sections. Row numbers are
auto-tracked. Named ranges are defined as cells are created.
"""

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.utils import get_column_letter
import datetime

# ---------------------------------------------------------------------------
# Shared styles
# ---------------------------------------------------------------------------
HEADER_FILL = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
HEADER_FONT = Font(name='Arial', size=10, bold=True, color='FFFFFF')
HEADER_ALIGN = Alignment(horizontal='center')
TITLE_FONT = Font(name='Arial', size=14, bold=True)
SECTION_FONT = Font(name='Arial', size=12, bold=True)
BOLD_FONT = Font(name='Arial', size=10, bold=True)
BLACK_FONT = Font(name='Arial', size=10)
BLUE_FONT = Font(name='Arial', size=10, color='0000FF')
GREEN_FONT = Font(name='Arial', size=10, color='008000')
NOTE_FONT = Font(name='Arial', size=9, italic=True, color='666666')
PROSE_FONT = Font(name='Arial', size=10)
THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin'),
)
DOLLAR = '$#,##0.00'
PCT = '0.00%'
QTY_FMT = '#,##0.000'
N_FMT = '0.0000'


# ---------------------------------------------------------------------------
# Cell and row helpers
# ---------------------------------------------------------------------------
def _cell(ws, row, col, value=None, font=None, fmt=None):
    """Write a cell with optional font and number format."""
    c = ws.cell(row=row, column=col, value=value)
    c.font = font or BLUE_FONT
    c.border = THIN_BORDER
    if fmt:
        c.number_format = fmt
    return c


def _header_row(ws, row, labels, col_start=1):
    """Write a formatted header row."""
    for i, label in enumerate(labels):
        c = ws.cell(row=row, column=col_start + i, value=label)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = HEADER_ALIGN
        c.border = THIN_BORDER


def _section_header(ws, row, title):
    """Write a section header."""
    ws.cell(row=row, column=1, value=title).font = SECTION_FONT
    return row + 1


# ---------------------------------------------------------------------------
# Named range helpers
# ---------------------------------------------------------------------------
_TAB_PREFIX = {
    "Fidelity Brokerage": "fid_brok",
    "Fidelity Roth IRA":  "roth_ira",
    "Fidelity HSA":       "fid_hsa",
    "401(k)":             "k401",
    "Robinhood":          "robinhood",
    "Angel Investments":  "angel",
    "Cash":               "cash",
    "Dashboard":          "dash",
}


def _define_name(wb, tab_name, key, col, row):
    """Define a single named range: {prefix}_{key} -> 'Tab'!$COL$ROW."""
    prefix = _TAB_PREFIX.get(tab_name)
    if not prefix:
        return
    name = f"{prefix}_{key}"
    if any(c in tab_name for c in " ()"):
        ref = f"'{tab_name}'!${col}${row}"
    else:
        ref = f"{tab_name}!${col}${row}"
    # Remove existing if present
    if name in wb.defined_names:
        del wb.defined_names[name]
    wb.defined_names.add(DefinedName(name=name, attr_text=ref))


# ---------------------------------------------------------------------------
# Section writer framework
# ---------------------------------------------------------------------------
def write_sections(wb, tab_name, title, subtitle, sections, col_widths, acct_data=None, model=None):
    """Create a sheet and write sections in order.

    Each section is (title_str, builder_func) where builder_func(ws, row, acct_data, model, wb)
    returns the next row number and a dict of {name_key: (col, row)} for named ranges.

    Returns (ws, row_map) where row_map has all named range entries.
    """
    ws = wb.create_sheet(tab_name)

    for col, w in col_widths.items():
        ws.column_dimensions[col].width = w

    row = 1
    ws.cell(row=row, column=1, value=title).font = TITLE_FONT
    row += 1
    ws.cell(row=row, column=1, value=subtitle).font = NOTE_FONT
    row += 2

    row_map = {}

    for section_title, builder_fn in sections:
        row = _section_header(ws, row, section_title)
        row, names = builder_fn(ws, row, acct_data, model, wb)
        row_map.update(names)
        row += 1  # gap between sections

    # Define named ranges
    for key, (col, r) in row_map.items():
        _define_name(wb, tab_name, key, col, r)

    ws.sheet_view.showGridLines = False
    return ws, row_map
```

- [ ] **Step 2: Verify helpers import**

Run: `python -c "from build_workbook import write_sections, _cell, _header_row; print('OK')"`

---

### Task 4: Build account tab writer

**Files:**
- Modify: `build_workbook.py` — add account tab section builders

- [ ] **Step 1: Add section builders for account tabs**

Add the following functions to `build_workbook.py`. Each returns `(next_row, {name_key: (col, row)})`.

```python
# ---------------------------------------------------------------------------
# Account tab section builders
# ---------------------------------------------------------------------------
def _build_return_section(ws, row, acct, model, wb):
    """YTD RETURN CALCULATIONS section."""
    _header_row(ws, row, ['Metric', 'Value', 'Note'])
    row += 1
    names = {}

    names["TWR"] = ("B", row)
    _cell(ws, row, 1, 'Time-Weighted Return (YTD)')
    _cell(ws, row, 2, None, fmt=PCT)  # forward-filled
    row += 1

    names["MWRR"] = ("B", row)
    _cell(ws, row, 1, 'Money-Weighted Return (YTD)')
    _cell(ws, row, 2, acct["returns"]["mwrr"], font=BLACK_FONT, fmt=PCT)
    _cell(ws, row, 3, '(computed from monthly cash flows)', font=NOTE_FONT)
    row += 1

    names["cb_return"] = ("B", row)
    _cell(ws, row, 1, 'Cost Basis Return')
    _cell(ws, row, 2, None, fmt=PCT)  # forward-filled
    _cell(ws, row, 3, 'Unrealized G/L / Cost Basis', font=NOTE_FONT)
    row += 1

    # Cash flow labels vary by account type
    labels = acct.get("cash_flow_labels", {"add": "Additions", "sub": "Subtractions"})
    _cell(ws, row, 1, f'Total {labels["add"]}')
    _cell(ws, row, 2, None, fmt=DOLLAR)  # forward-filled
    names["total_add"] = ("B", row)
    row += 1

    _cell(ws, row, 1, f'Total {labels["sub"]}')
    _cell(ws, row, 2, None, fmt=DOLLAR)  # forward-filled
    names["total_sub"] = ("B", row)
    row += 1

    return row, names


def _build_gain_section(ws, row, acct, model, wb):
    """YTD INVESTMENT GAIN SUMMARY section."""
    _header_row(ws, row, ['Metric', 'Value', 'Note'])
    row += 1
    names = {}
    gains = acct["gains"]

    names["dividends"] = ("B", row)
    _cell(ws, row, 1, 'Dividends/Income' if not acct.get("is_margin") else 'Dividends Received')
    _cell(ws, row, 2, None, fmt=DOLLAR)  # forward-filled
    row += 1

    names["unrealized"] = ("B", row)
    _cell(ws, row, 1, 'Unrealized Gain/Loss')
    _cell(ws, row, 2, None, fmt=DOLLAR)  # forward-filled
    _cell(ws, row, 3, 'Current holdings vs. cost basis (all-time)', font=NOTE_FONT)
    row += 1

    names["realized"] = ("B", row)
    _cell(ws, row, 1, 'Realized Gain/Loss (2026)')
    _cell(ws, row, 2, None, fmt=DOLLAR)  # forward-filled
    row += 1

    names["total_ytd"] = ("B", row)
    _cell(ws, row, 1, 'Total YTD Gain', font=BOLD_FONT)
    div_r = names["dividends"][1]
    unr_r = names["unrealized"][1]
    rea_r = names["realized"][1]
    _cell(ws, row, 2, f'=B{div_r}+B{unr_r}+B{rea_r}', font=BOLD_FONT, fmt=DOLLAR)
    _cell(ws, row, 3, 'Unrealized + Realized + Dividends', font=NOTE_FONT)
    row += 1

    return row, names


def _build_holdings_section(ws, row, acct, model, wb):
    """CURRENT HOLDINGS section."""
    names = {}
    holdings = acct["holdings"]
    is_rh = acct.get("is_margin", False)

    if is_rh:
        _header_row(ws, row, ['Security', 'Quantity', 'Price', 'Market Value', 'Average Cost', 'Cost Basis', 'Gain/Loss', 'Return %'])
    else:
        _header_row(ws, row, ['Security', 'Quantity', 'Price', 'Market Value', 'Cost Basis', 'Gain/Loss', 'Return %'])
    row += 1

    hold_first = row
    for h in holdings:
        _cell(ws, row, 1, h["ticker"])
        _cell(ws, row, 2, h["qty"], fmt=QTY_FMT if not isinstance(h["qty"], int) else '#,##0')
        _cell(ws, row, 3, h["price"], fmt=DOLLAR)
        _cell(ws, row, 4, h["mv"], fmt=DOLLAR)
        if is_rh:
            _cell(ws, row, 5, h.get("avg_cost", 0), fmt=DOLLAR)
            _cell(ws, row, 6, h.get("cb", 0), fmt=DOLLAR)
            _cell(ws, row, 7, f'=D{row}-F{row}', font=BLACK_FONT, fmt=DOLLAR)
            _cell(ws, row, 8, f'=IF(F{row}=0,"",G{row}/F{row})', font=BLACK_FONT, fmt=PCT)
        else:
            _cell(ws, row, 5, h.get("cb", 0), fmt=DOLLAR)
            _cell(ws, row, 6, f'=D{row}-E{row}', font=BLACK_FONT, fmt=DOLLAR)
            _cell(ws, row, 7, f'=IF(E{row}=0,"",F{row}/E{row})', font=BLACK_FONT, fmt=PCT)
        row += 1

    hold_last = row - 1

    # Cash position row if applicable
    cash_pos = acct.get("cash_position", 0)
    if cash_pos:
        _cell(ws, row, 1, 'Cash')
        _cell(ws, row, 4, cash_pos, fmt=DOLLAR)
        row += 1
        hold_last = row - 1

    # TOTAL row
    if is_rh:
        _cell(ws, row, 1, 'TOTAL SECURITIES', font=BOLD_FONT)
        _cell(ws, row, 4, f'=SUM(D{hold_first}:D{hold_last})', font=BOLD_FONT, fmt=DOLLAR)
        _cell(ws, row, 6, f'=SUM(F{hold_first}:F{hold_last})', font=BOLD_FONT, fmt=DOLLAR)
        _cell(ws, row, 7, f'=SUM(G{hold_first}:G{hold_last})', font=BOLD_FONT, fmt=DOLLAR)
        _cell(ws, row, 8, f'=IF(F{row}=0,"",G{row}/F{row})', font=BOLD_FONT, fmt=PCT)
        names["holdings_total_mv"] = ("D", row)
        names["holdings_total_cb"] = ("F", row)
        names["holdings_total_gl"] = ("G", row)
    else:
        _cell(ws, row, 1, 'TOTAL', font=BOLD_FONT)
        _cell(ws, row, 4, f'=SUM(D{hold_first}:D{hold_last})', font=BOLD_FONT, fmt=DOLLAR)
        _cell(ws, row, 5, f'=SUM(E{hold_first}:E{hold_last})', font=BOLD_FONT, fmt=DOLLAR)
        _cell(ws, row, 6, f'=SUM(F{hold_first}:F{hold_last})', font=BOLD_FONT, fmt=DOLLAR)
        _cell(ws, row, 7, f'=IF(E{row}=0,"",F{row}/E{row})', font=BOLD_FONT, fmt=PCT)
        names["holdings_total"] = ("D", row)
    total_row = row
    row += 1

    # Margin details for Robinhood
    if acct.get("is_margin"):
        margin = acct.get("margin_debt", 0)
        _cell(ws, row, 1, 'Margin Debt')
        _cell(ws, row, 4, margin, fmt=DOLLAR)
        names["margin_debt"] = ("D", row)
        row += 1
        _cell(ws, row, 1, 'NET PORTFOLIO VALUE', font=BOLD_FONT)
        _cell(ws, row, 4, f'=D{total_row}+D{row-1}', font=BOLD_FONT, fmt=DOLLAR)
        names["net_portfolio"] = ("D", row)
        row += 1

    names["_hold_first"] = hold_first
    names["_hold_last"] = hold_last
    names["_total_row"] = total_row

    return row, names


def _build_monthly_section(ws, row, acct, model, wb):
    """MONTHLY CALCULATIONS section."""
    names = {}
    monthly = acct["monthly"]
    labels = acct.get("cash_flow_labels", {"add": "Additions", "sub": "Subtractions"})

    _header_row(ws, row, ['Month', 'Beginning Value', labels["add"], labels["sub"],
                          'Dividends', 'Market Change', 'Ending Value', 'Monthly Return', 'Growth Factor'])
    row += 1

    monthly_first = row
    for m in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
        _cell(ws, row, 1, m)
        if m in monthly:
            d = monthly[m]
            mkt = (d.get("change", 0) or 0) - (d.get("div", 0) or 0)
            _cell(ws, row, 2, d.get("begin", 0), fmt=DOLLAR)
            _cell(ws, row, 3, d.get("add", 0), fmt=DOLLAR)
            _cell(ws, row, 4, d.get("sub", 0), fmt=DOLLAR)
            _cell(ws, row, 5, d.get("div", 0), fmt=DOLLAR)
            _cell(ws, row, 6, round(mkt, 2), fmt=DOLLAR)
            _cell(ws, row, 7, d.get("end", 0), fmt=DOLLAR)
        else:
            for col in range(2, 8):
                _cell(ws, row, col, None, fmt=DOLLAR)
        _cell(ws, row, 8, f'=IF(B{row}=0,"",((G{row}+D{row}-C{row})/B{row})-1)', font=BLACK_FONT, fmt=PCT)
        _cell(ws, row, 9, f'=IF(H{row}="","",1+H{row})', font=BLACK_FONT, fmt=N_FMT)
        row += 1

    monthly_last = row - 1
    row += 1

    # Totals
    _cell(ws, row, 1, 'Totals', font=BOLD_FONT)
    for col in [3, 4, 5, 6]:
        _cell(ws, row, col, f'=SUM({get_column_letter(col)}{monthly_first}:{get_column_letter(col)}{monthly_last})',
              font=BOLD_FONT, fmt=DOLLAR)

    names["monthly_jan"] = ("B", monthly_first)
    names["monthly_dec"] = ("B", monthly_last)
    names["monthly_totals"] = ("B", row)
    names["_monthly_first"] = monthly_first
    names["_monthly_last"] = monthly_last
    names["_monthly_totals_row"] = row
    row += 1

    return row, names


def _build_sold_section(ws, row, acct, model, wb):
    """SOLD POSITIONS section."""
    names = {}
    _header_row(ws, row, ['Security', 'Date', 'Quantity', 'Cost Basis', 'Proceeds', 'Realized Gain/Loss', 'Action'])
    row += 1

    sold = acct.get("sold", [])
    is_dict = isinstance(sold, dict)

    def _write_sold_group(ws, row, year_label, positions):
        _cell(ws, row, 1, year_label, font=BOLD_FONT)
        for col in range(2, 8):
            ws.cell(row=row, column=col).border = THIN_BORDER
        row += 1
        for s in positions:
            _cell(ws, row, 1, s["ticker"])
            _cell(ws, row, 2, s["date"])
            _cell(ws, row, 3, s["qty"], fmt=QTY_FMT)
            if s.get("cb") is not None:
                _cell(ws, row, 4, s["cb"], fmt=DOLLAR)
            _cell(ws, row, 5, s.get("proceeds", 0), fmt=DOLLAR)
            if s.get("cb") is not None:
                _cell(ws, row, 6, f'=E{row}-D{row}', font=BLACK_FONT, fmt=DOLLAR)
            _cell(ws, row, 7, s.get("action", ""), font=NOTE_FONT)
            row += 1
        return row

    if is_dict:
        for year in sorted(sold.keys(), reverse=True):
            row = _write_sold_group(ws, row, year, sold[year])
            # Total for this year
            # Find first sold row for this year group
            group_first = row - len(sold[year])
            _cell(ws, row, 1, f'{year} TOTAL', font=BOLD_FONT)
            _cell(ws, row, 5, f'=SUM(E{group_first}:E{row-1})', font=BOLD_FONT, fmt=DOLLAR)
            _cell(ws, row, 6, f'=SUM(F{group_first}:F{row-1})', font=BOLD_FONT, fmt=DOLLAR)
            if year == "2026":
                names["sold_2026_total"] = ("F", row)
            row += 2
    else:
        row = _write_sold_group(ws, row, '2026', sold)
        group_first = row - len(sold)
        _cell(ws, row, 1, '2026 TOTAL', font=BOLD_FONT)
        _cell(ws, row, 5, f'=SUM(E{group_first}:E{row-1})', font=BOLD_FONT, fmt=DOLLAR)
        _cell(ws, row, 6, f'=SUM(F{group_first}:F{row-1})', font=BOLD_FONT, fmt=DOLLAR)
        names["sold_2026_total"] = ("F", row)
        row += 1

    return row, names


def _fix_forward_refs(ws, row_map, acct):
    """Fill in forward-reference cells now that all row numbers are known."""
    # TWR = PRODUCT of growth factors
    if "_monthly_first" in row_map and "TWR" in row_map:
        mf = row_map["_monthly_first"]
        ml = row_map["_monthly_last"]
        twr_r = row_map["TWR"][1]
        ws.cell(row=twr_r, column=2, value=f'=IFERROR(PRODUCT(I{mf}:I{ml})-1,"")')
        ws.cell(row=twr_r, column=2).font = BLACK_FONT
        ws.cell(row=twr_r, column=2).number_format = PCT

    # CB Return
    if "cb_return" in row_map and "_total_row" in row_map:
        cbr_r = row_map["cb_return"][1]
        tr = row_map["_total_row"]
        if acct.get("is_margin"):
            # Robinhood: G/F columns
            ws.cell(row=cbr_r, column=2, value=f'=G{tr}/F{tr}')
        else:
            ws.cell(row=cbr_r, column=2, value=f'=F{tr}/E{tr}')
        ws.cell(row=cbr_r, column=2).font = BLACK_FONT
        ws.cell(row=cbr_r, column=2).number_format = PCT

    # Dividends = monthly totals div column
    if "dividends" in row_map and "_monthly_totals_row" in row_map:
        div_r = row_map["dividends"][1]
        mt = row_map["_monthly_totals_row"]
        ws.cell(row=div_r, column=2, value=f'=E{mt}')
        ws.cell(row=div_r, column=2).font = BLACK_FONT
        ws.cell(row=div_r, column=2).number_format = DOLLAR

    # Unrealized = holdings total G/L
    if "unrealized" in row_map and "_total_row" in row_map:
        ur = row_map["unrealized"][1]
        tr = row_map["_total_row"]
        gl_col = "G" if acct.get("is_margin") else "F"
        ws.cell(row=ur, column=2, value=f'={gl_col}{tr}')
        ws.cell(row=ur, column=2).font = BLACK_FONT
        ws.cell(row=ur, column=2).number_format = DOLLAR

    # Realized = sold total
    if "realized" in row_map and "sold_2026_total" in row_map:
        rr = row_map["realized"][1]
        st = row_map["sold_2026_total"][1]
        ws.cell(row=rr, column=2, value=f'=F{st}')
        ws.cell(row=rr, column=2).font = BLACK_FONT
        ws.cell(row=rr, column=2).number_format = DOLLAR

    # Total additions/subtractions
    if "total_add" in row_map and "_monthly_totals_row" in row_map:
        mt = row_map["_monthly_totals_row"]
        ws.cell(row=row_map["total_add"][1], column=2, value=f'=C{mt}')
        ws.cell(row=row_map["total_add"][1], column=2).font = BLACK_FONT
        ws.cell(row=row_map["total_add"][1], column=2).number_format = DOLLAR
    if "total_sub" in row_map and "_monthly_totals_row" in row_map:
        mt = row_map["_monthly_totals_row"]
        ws.cell(row=row_map["total_sub"][1], column=2, value=f'=D{mt}')
        ws.cell(row=row_map["total_sub"][1], column=2).font = BLACK_FONT
        ws.cell(row=row_map["total_sub"][1], column=2).number_format = DOLLAR


def build_account_tab(wb, acct, model):
    """Build a complete account tab."""
    tab_name = acct["tab_name"]
    title = f'{acct["name"]} — {model["year"]} Performance'
    subtitle = 'Blue = hardcoded from statement | Black = formula'

    sections = [
        ("YTD RETURN CALCULATIONS", _build_return_section),
        ("YTD INVESTMENT GAIN SUMMARY", _build_gain_section),
        ("CURRENT HOLDINGS", _build_holdings_section),
        ("MONTHLY CALCULATIONS", _build_monthly_section),
        ("SOLD POSITIONS", _build_sold_section),
    ]

    col_widths = {'A': 26, 'B': 16, 'C': 16, 'D': 16, 'E': 16, 'F': 19, 'G': 16, 'H': 16, 'I': 14}

    ws, row_map = write_sections(wb, tab_name, title, subtitle, sections, col_widths, acct, model)

    # Fix forward references
    _fix_forward_refs(ws, row_map, acct)

    return ws, row_map
```

- [ ] **Step 2: Verify account tab builds**

Run: `python -c "
from portfolio_model import build_model
from build_workbook import build_account_tab
import openpyxl
model = build_model()
wb = openpyxl.Workbook()
ws, rm = build_account_tab(wb, model['accounts']['fidelity_brokerage'], model)
print(f'Tab: {ws.title}, rows: {ws.max_row}')
print(f'Named ranges: {len([n for n in wb.defined_names.values()])}')
print(f'Row map keys: {list(rm.keys())[:10]}')
wb.save('_test_output.xlsx')
print('Saved _test_output.xlsx')
"`

---

### Task 5: Build Dashboard writer

**Files:**
- Modify: `build_workbook.py` — add `build_dashboard()` function

This task adds the Dashboard tab builder. Cross-tab values are **computed values from the model**, not formulas. Within-tab formulas (like subtotal SUMs) are kept.

- [ ] **Step 1: Add `build_dashboard()` to `build_workbook.py`**

The Dashboard writes all values from the model dict. No cross-sheet formula references. Named ranges are still defined for Excel Name Manager transparency.

This function should implement the same section order as the current Dashboard:
1. Daily Summary (prose)
2. YTD Benchmark Comparison (computed alpha values)
3. YTD Investment Gain (computed sums)
4. Account Overview (liquid accounts, subtotal, cash, illiquid, subtotal, total)
5. Sector Concentration
6. Geographic Concentration
7. Risk Metrics
8. Return Metric Definitions

All cross-tab values come from `model["accounts"][key]["returns"]`, `model["accounts"][key]["gains"]`, `model["liquid_twr"]`, `model["benchmarks"]`, etc.

The Account Overview section uses `model["liquid_accounts"]` and `model["illiquid_accounts"]` to determine grouping — no hardcoded account lists.

- [ ] **Step 2: Verify Dashboard builds**

Run the full build and check output.

---

### Task 6: Build Cash tab writer

**Files:**
- Modify: `build_workbook.py` — add `build_cash_tab()`

- [ ] **Step 1: Add Cash tab builder**

Fetches live Plaid balances (or uses fallback), writes External Cash and Embedded Cash sections. Same structure as current `rebuild_cash_tab.py` but using the model.

---

### Task 7: Wire into pipeline with fallback

**Files:**
- Modify: `weekly_pipeline.py`

- [ ] **Step 1: Add new builder call with fallback**

In `run_pipeline()`, replace the current build step:

```python
# Try new builder
try:
    from portfolio_model import build_model
    from build_workbook import build as build_new
    model = build_model(
        data_dir=str(SCRIPT_DIR / "data"),
        live_extraction=fid_data,
        benchmarks=benchmarks,
    )
    build_new(model, str(OUTPUT_XLSX))
    logging.info("Workbook built (new builder)")
except Exception as e:
    logging.warning(f"New builder failed ({e}), falling back to rebuild scripts")
    import traceback
    logging.warning(traceback.format_exc())
    _run_rebuild_scripts()
```

- [ ] **Step 2: Remove Playwright extraction from `extract_all()`**

Delete the entire Fidelity Playwright block (threading timeout, headless browser, etc.). Fidelity is now extracted via SnapTrade.

- [ ] **Step 3: Verify pipeline runs end-to-end**

Run: `python weekly_pipeline.py --skip-extract`

Expected: "Workbook built (new builder)" in logs, no fallback.

---

### Task 8: Simplify redact script

**Files:**
- Modify: `redact_for_screenshot.py`

- [ ] **Step 1: Verify redact still works**

Since Dashboard now uses computed values (not named-range formulas), the formula evaluator has less work. The named-range resolver is still present as a safety net.

Run: `python redact_for_screenshot.py`

Expected: "Evaluated N/N formula cells" with zero warnings.

---

### Task 9: Verify end-to-end

- [ ] **Step 1: Run full pipeline**

Run: `python weekly_pipeline.py --skip-extract`

Verify: new builder succeeds, no fallback.

- [ ] **Step 2: Open workbook in Excel and spot-check**

Verify: all tabs present, formulas calculate, named ranges visible in Name Manager, gridlines off.

- [ ] **Step 3: Generate redacted version**

Run: `python redact_for_screenshot.py`

Verify: all formulas evaluated, redaction correct.

- [ ] **Step 4: Compare with old workbook**

Key values to compare:
- Each account's TWR, MWRR, CB Return
- Dashboard benchmark alpha values
- Sector/geographic percentages
- Monthly return and growth factor values
