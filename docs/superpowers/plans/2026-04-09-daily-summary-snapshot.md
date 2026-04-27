# Daily Summary & Snapshot System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily snapshot system that saves portfolio holdings each run, compares to the previous day's snapshot, and writes a "DAILY SUMMARY" section to the Dashboard showing portfolio value change and top movers (>10% daily price change). Also rename "Account Summary" to "Account Overview" and switch scheduling from weekly to daily weekdays at 4:00 PM PT.

**Architecture:** A new `daily_snapshot.py` module handles saving/loading JSON snapshots (one per trading day) to `extract_output/snapshots/`. The pipeline calls it after extraction, and `rebuild_dashboard.py` reads the latest two snapshots to populate the Summary section. The scheduler XML is updated from weekly-Friday to daily-weekday.

**Tech Stack:** Python, openpyxl, json, pathlib. No new dependencies.

---

### Task 1: Create the daily snapshot module

**Files:**
- Create: `daily_snapshot.py`

This module saves a normalized portfolio snapshot after each extraction and computes the diff between two snapshots.

- [ ] **Step 1: Create `daily_snapshot.py`**

```python
"""daily_snapshot.py — Save and compare daily portfolio snapshots.

Each snapshot is a JSON file capturing all holdings with prices and
portfolio-level totals. Stored in extract_output/snapshots/ with
one file per trading day: snapshot_YYYY-MM-DD.json
"""

import json
import datetime
from pathlib import Path

from paths import SNAPSHOT_DIR  # resolves via env/config — see paths.py


def _today_str():
    return datetime.date.today().isoformat()


def save_snapshot(fid_data, rh_raw, merrill_raw=None, date_str=None):
    """Save a portfolio snapshot from extraction data.

    Args:
        fid_data: dict keyed by account label, each with {ticker: {qty, price, mv, cb, gl}}
        rh_raw: dict with "robinhood" key containing accounts/holdings
        merrill_raw: optional Merrill data
        date_str: override date (default: today)

    Returns:
        Path to saved snapshot file.
    """
    date_str = date_str or _today_str()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    snapshot = {"date": date_str, "accounts": {}}

    # Fidelity accounts (from Playwright or SnapTrade extraction)
    if fid_data:
        for acct_key, holdings in fid_data.items():
            # holdings may be a dict of {ticker: {qty, price, mv, cb, gl}}
            # or nested under a date key
            if isinstance(holdings, dict):
                # Check if it's date-keyed: {"2026-04-04": {ticker: ...}}
                first_val = next(iter(holdings.values()), None)
                if isinstance(first_val, dict) and "qty" in first_val:
                    acct_holdings = holdings
                elif isinstance(first_val, dict):
                    # Date-keyed — take the latest date
                    latest_date = sorted(holdings.keys())[-1]
                    acct_holdings = holdings[latest_date]
                else:
                    acct_holdings = {}
            else:
                acct_holdings = {}

            total_mv = sum(h.get("mv", 0) or 0 for h in acct_holdings.values())
            snapshot["accounts"][acct_key] = {
                "total_mv": round(total_mv, 2),
                "holdings": {
                    ticker: {
                        "price": h.get("price", 0),
                        "mv": h.get("mv", 0),
                        "qty": h.get("qty", 0),
                    }
                    for ticker, h in acct_holdings.items()
                },
            }

    # Robinhood
    if rh_raw:
        for provider_key, provider_data in rh_raw.items():
            if "robinhood" not in provider_key.lower():
                continue
            # Holdings may be date-keyed
            raw_holdings = provider_data.get("holdings", {})
            if raw_holdings:
                latest_date = sorted(raw_holdings.keys())[-1]
                rh_holdings = raw_holdings[latest_date]
            else:
                rh_holdings = {}

            total_mv = sum(h.get("mv", 0) or 0 for h in rh_holdings.values())
            snapshot["accounts"]["robinhood"] = {
                "total_mv": round(total_mv, 2),
                "holdings": {
                    ticker: {
                        "price": h.get("price", 0),
                        "mv": h.get("mv", 0),
                        "qty": h.get("qty", 0),
                    }
                    for ticker, h in rh_holdings.items()
                },
            }

    # Merrill 401(k)
    if merrill_raw:
        raw_holdings = merrill_raw.get("holdings", {})
        if raw_holdings and isinstance(raw_holdings, dict):
            latest_date = sorted(raw_holdings.keys())[-1] if raw_holdings else None
            m_holdings = raw_holdings.get(latest_date, {}) if latest_date else {}
        else:
            m_holdings = {}
        total_mv = sum(h.get("mv", 0) or 0 for h in m_holdings.values())
        snapshot["accounts"]["merrill_401k"] = {
            "total_mv": round(total_mv, 2),
            "holdings": {
                name: {"price": h.get("price", 0), "mv": h.get("mv", 0), "qty": h.get("qty", 0)}
                for name, h in m_holdings.items()
            },
        }

    # Compute liquid total (all accounts except merrill_401k)
    liquid_mv = sum(
        acct["total_mv"]
        for key, acct in snapshot["accounts"].items()
        if key != "merrill_401k"
    )
    snapshot["liquid_total_mv"] = round(liquid_mv, 2)
    snapshot["total_mv"] = round(
        sum(acct["total_mv"] for acct in snapshot["accounts"].values()), 2
    )

    path = SNAPSHOT_DIR / f"snapshot_{date_str}.json"
    path.write_text(json.dumps(snapshot, indent=2))
    return path


def load_snapshot(date_str):
    """Load a snapshot by date string. Returns None if not found."""
    path = SNAPSHOT_DIR / f"snapshot_{date_str}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_previous_snapshot(before_date_str=None):
    """Load the most recent snapshot before the given date."""
    before_date_str = before_date_str or _today_str()
    if not SNAPSHOT_DIR.exists():
        return None
    files = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), reverse=True)
    for f in files:
        date_part = f.stem.replace("snapshot_", "")
        if date_part < before_date_str:
            return json.loads(f.read_text())
    return None


def compute_daily_summary(current, previous):
    """Compute daily changes between two snapshots.

    Returns:
        dict with:
          - liquid_change: dollar change in liquid portfolio
          - liquid_change_pct: percentage change
          - total_change: dollar change in total portfolio
          - total_change_pct: percentage change
          - top_movers: list of {ticker, account, price_today, price_yesterday, change_pct}
                        for securities with >10% daily price change
    """
    if not current or not previous:
        return None

    liquid_now = current.get("liquid_total_mv", 0)
    liquid_prev = previous.get("liquid_total_mv", 0)
    total_now = current.get("total_mv", 0)
    total_prev = previous.get("total_mv", 0)

    result = {
        "date": current.get("date", ""),
        "prev_date": previous.get("date", ""),
        "liquid_change": round(liquid_now - liquid_prev, 2),
        "liquid_change_pct": round((liquid_now - liquid_prev) / liquid_prev, 6) if liquid_prev else 0,
        "total_change": round(total_now - total_prev, 2),
        "total_change_pct": round((total_now - total_prev) / total_prev, 6) if total_prev else 0,
        "top_movers": [],
    }

    # Find securities with >10% daily price change
    for acct_key, acct_now in current.get("accounts", {}).items():
        acct_prev = previous.get("accounts", {}).get(acct_key, {})
        holdings_now = acct_now.get("holdings", {})
        holdings_prev = acct_prev.get("holdings", {})

        for ticker, h_now in holdings_now.items():
            h_prev = holdings_prev.get(ticker)
            if not h_prev:
                continue
            price_now = h_now.get("price", 0) or 0
            price_prev = h_prev.get("price", 0) or 0
            if price_prev == 0:
                continue
            change_pct = (price_now - price_prev) / price_prev
            if abs(change_pct) >= 0.10:
                result["top_movers"].append({
                    "ticker": ticker,
                    "account": acct_key,
                    "price_today": price_now,
                    "price_yesterday": price_prev,
                    "change_pct": round(change_pct, 4),
                })

    # Sort by absolute change descending
    result["top_movers"].sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return result
```

- [ ] **Step 2: Verify module loads without errors**

Run: `python -c "import daily_snapshot; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add daily_snapshot.py
git commit -m "feat: add daily snapshot save/load/diff module"
```

---

### Task 2: Rename "Account Summary" to "Account Overview" everywhere

**Files:**
- Modify: `rebuild_dashboard.py` — section header and header_row call
- Modify: `repo/build_portfolio.py` — section header
- Modify: `redact_for_screenshot.py` — any references in comments/print
- Modify: `registry.py` — if referenced

- [ ] **Step 1: Update `rebuild_dashboard.py`**

Change the SECTION 1 comment and cell value:
```python
# Line with 'ACCOUNT SUMMARY' → 'ACCOUNT OVERVIEW'
ws.cell(row=row, column=1, value='ACCOUNT OVERVIEW').font = SECTION_FONT
```

- [ ] **Step 2: Update `repo/build_portfolio.py`**

Change:
```python
ws.cell(4, 1, "ACCOUNT OVERVIEW").font = SECTION
```

- [ ] **Step 3: Update any print statements or comments that reference "Account Summary"**

In `rebuild_dashboard.py`, the print statement:
```python
print('  Order: Account Overview → Liquidity → ...')
```

- [ ] **Step 4: Run rebuild and verify**

Run: `python rebuild_dashboard.py`
Expected: Dashboard rebuilt successfully, heading reads "ACCOUNT OVERVIEW"

- [ ] **Step 5: Commit**

```bash
git add rebuild_dashboard.py repo/build_portfolio.py
git commit -m "refactor: rename Account Summary to Account Overview"
```

---

### Task 3: Add DAILY SUMMARY section to Dashboard

**Files:**
- Modify: `rebuild_dashboard.py` — add Summary section before Account Overview, read snapshots

- [ ] **Step 1: Add snapshot import and Summary section before Account Overview**

At the top of `rebuild_dashboard.py`, add import:
```python
from daily_snapshot import load_snapshot, load_previous_snapshot, compute_daily_summary
import datetime
```

In `main()`, after creating the sheet and setting column widths, before the title row, add the Summary computation:
```python
    # Load daily snapshots for summary
    today_str = datetime.date.today().isoformat()
    snap_today = load_snapshot(today_str)
    snap_prev = load_previous_snapshot(today_str)
    daily_summary = compute_daily_summary(snap_today, snap_prev) if snap_today and snap_prev else None
```

Then after the title/subtitle rows (rows 1-2), insert the DAILY SUMMARY section at row 4 (before Account Overview):

```python
    # ==================================================================
    # SECTION 1: DAILY SUMMARY
    # ==================================================================
    ws.cell(row=row, column=1, value='DAILY SUMMARY').font = SECTION_FONT
    row += 1

    if daily_summary:
        prev_date = daily_summary['prev_date']
        cell(ws, row, 1, 'Liquid Portfolio Value')
        cell(ws, row, 2, snap_today['liquid_total_mv'], font=BLUE_FONT, fmt=DOLLAR)
        row += 1

        chg = daily_summary['liquid_change']
        pct = daily_summary['liquid_change_pct']
        direction = 'up' if chg >= 0 else 'down'
        cell(ws, row, 1, f'Daily Change (vs {prev_date})')
        cell(ws, row, 2, chg, font=BLACK_FONT, fmt=DOLLAR)
        cell(ws, row, 3, pct, font=BLACK_FONT, fmt=PCT)
        row += 1

        # Top movers
        movers = daily_summary.get('top_movers', [])
        if movers:
            row += 1
            cell(ws, row, 1, 'Top Movers (>10% daily price change)', font=BOLD_FONT)
            row += 1
            header_row(ws, row, ['Security', 'Account', 'Yesterday', 'Today', 'Change'])
            row += 1
            for m in movers[:10]:  # cap at 10
                cell(ws, row, 1, m['ticker'])
                cell(ws, row, 2, m['account'])
                cell(ws, row, 3, m['price_yesterday'], fmt=DOLLAR)
                cell(ws, row, 4, m['price_today'], fmt=DOLLAR)
                cell(ws, row, 5, m['change_pct'], fmt=PCT)
                row += 1
        else:
            row += 1
            ws.cell(row=row, column=1, value='No securities with >10% daily price change.').font = NOTE_FONT
            row += 1
    else:
        ws.cell(row=row, column=1, value='Daily summary requires at least 2 pipeline runs. Will populate after next run.').font = NOTE_FONT
        row += 1

    row += 1  # spacing before Account Overview
```

- [ ] **Step 2: Shift Account Overview to SECTION 2**

Update the Account Overview section comment from SECTION 1 to SECTION 2, and renumber all subsequent sections.

- [ ] **Step 3: Run rebuild and verify**

Run: `python rebuild_dashboard.py`
Expected: Dashboard rebuilt. DAILY SUMMARY section appears at top with "requires at least 2 pipeline runs" message (since no snapshots exist yet).

- [ ] **Step 4: Commit**

```bash
git add rebuild_dashboard.py
git commit -m "feat: add Daily Summary section to Dashboard with snapshot comparison"
```

---

### Task 4: Wire snapshot saving into the pipeline

**Files:**
- Modify: `weekly_pipeline.py` — call `save_snapshot()` after extraction

- [ ] **Step 1: Add snapshot save after extraction in `run_pipeline()`**

After the extraction data is saved (around line 187), add:
```python
    # Save daily snapshot for day-over-day comparison
    try:
        from daily_snapshot import save_snapshot
        snap_path = save_snapshot(
            fid_data=fid_data,
            rh_raw=raw,
            merrill_raw=merrill_raw,
        )
        logging.info(f"Daily snapshot saved: {snap_path}")
    except Exception as e:
        logging.warning(f"Snapshot save failed (non-fatal): {e}")
```

This should be placed in `run_pipeline()` after `prepare_builder_data()` returns `fid_data`, `rh_raw`, and `merrill_raw`, but before `build_xlsx()`.

- [ ] **Step 2: Verify pipeline still runs**

Run: `python weekly_pipeline.py --skip-extract`
Expected: Pipeline loads latest extraction, saves snapshot, builds workbook.

- [ ] **Step 3: Commit**

```bash
git add weekly_pipeline.py
git commit -m "feat: save daily snapshot after extraction for day-over-day comparison"
```

---

### Task 5: Add weekend/holiday skip logic to pipeline

**Files:**
- Modify: `weekly_pipeline.py` — add `is_trading_day()` check at start of `run_pipeline()`

- [ ] **Step 1: Add trading day check**

At the top of `weekly_pipeline.py`, add:
```python
# US market holidays for 2026 (NYSE/NASDAQ closed)
US_MARKET_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Day
    "2026-02-16",  # Presidents' Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}


def is_trading_day(date=None):
    """Return True if the given date is a US stock market trading day."""
    if date is None:
        date = datetime.date.today()
    # Skip weekends (Saturday=5, Sunday=6)
    if date.weekday() >= 5:
        return False
    # Skip holidays
    if date.isoformat() in US_MARKET_HOLIDAYS_2026:
        return False
    return True
```

In `run_pipeline()`, add early exit:
```python
    if not is_trading_day():
        logging.info("Not a trading day (weekend or holiday). Skipping.")
        return 0
```

- [ ] **Step 2: Verify skip logic**

Run: `python -c "from weekly_pipeline import is_trading_day; import datetime; print(is_trading_day(datetime.date(2026,4,11)))"`  (Saturday)
Expected: `False`

Run: `python -c "from weekly_pipeline import is_trading_day; import datetime; print(is_trading_day(datetime.date(2026,4,9)))"`  (Wednesday)
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add weekly_pipeline.py
git commit -m "feat: skip pipeline on weekends and US market holidays"
```

---

### Task 6: Update scheduler from weekly to daily weekday at 4:00 PM PT

**Files:**
- Modify: `schedule_task.xml`
- Modify: `run_pipeline.bat` (if any changes needed)

- [ ] **Step 1: Update `schedule_task.xml`**

Replace the `<Triggers>` section:
```xml
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-04-10T16:00:00-07:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek>
          <Monday />
          <Tuesday />
          <Wednesday />
          <Thursday />
          <Friday />
        </DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
```

Update `<Description>`:
```xml
    <Description>Daily Portfolio Analysis Pipeline - Runs weekdays at 4:00 PM PST to extract brokerage data and rebuild portfolio workbook. Skips weekends and US market holidays.</Description>
```

- [ ] **Step 2: Register updated task**

Run (elevated prompt): `schtasks /create /xml schedule_task.xml /tn "Portfolio Pipeline" /f`

- [ ] **Step 3: Commit**

```bash
git add schedule_task.xml
git commit -m "feat: switch scheduler from weekly Friday to daily weekday 4pm PT"
```

---

### Task 7: Update memory and rename pipeline references

**Files:**
- Modify: `weekly_pipeline.py` — update docstring and logging references from "weekly" to "daily"
- Modify: memory file `project_pipeline.md` — update schedule description

- [ ] **Step 1: Update `weekly_pipeline.py` docstring**

Change the module docstring from "Weekly Portfolio Data Pipeline" to "Daily Portfolio Data Pipeline" and update the description to mention daily weekday runs at 4:00 PM PT with weekend/holiday skip.

- [ ] **Step 2: Update memory file**

Update the project memory file (`~\.claude\projects\<project-key>\memory\project_pipeline.md`) to reflect daily 4:00 PM PT schedule.

- [ ] **Step 3: Commit**

```bash
git add weekly_pipeline.py
git commit -m "docs: update pipeline references from weekly to daily"
```
