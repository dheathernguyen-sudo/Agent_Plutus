# Cash Account Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Chase and Marcus by Goldman Sachs cash accounts via Plaid, with a dedicated Cash tab (current balances + monthly history) and Dashboard integration.

**Architecture:** Extend the existing Plaid integration with a new `extract_plaid_cash()` function that uses `accounts_get()` for deposit accounts. Balance snapshots are persisted to `extract_output/cash_history.json` each pipeline run. A new `build_cash_tab()` renders the Cash worksheet, and `build_dashboard()` gains a Cash row in the account summary and liquidity breakdown.

**Tech Stack:** Python, plaid-python SDK, openpyxl, existing pipeline infrastructure

**Spec:** `docs/superpowers/specs/2026-04-05-cash-account-integration-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `repo/plaid_extract.py` | Modify | Add `extract_plaid_cash()`, update `setup_plaid()` for cash institutions, add Chase/Marcus to label maps |
| `repo/weekly_pipeline.py` | Modify | Call `extract_plaid_cash()`, persist to `cash_history.json`, pass cash data to builder |
| `repo/build_portfolio.py` | Modify | Add `build_cash_tab()`, update `build_dashboard()` (Cash row, liquidity), update `build_workbook()` signature |
| `extract_output/cash_history.json` | Created at runtime | Persistent append-only balance history |

---

### Task 1: Add Cash Institution Labels and Provider Mapping (plaid_extract.py)

**Files:**
- Modify: `repo/plaid_extract.py:67-79`

- [ ] **Step 1: Add Chase and Marcus to PROVIDER_MAP and INSTITUTION_LABELS**

In `repo/plaid_extract.py`, add the new institutions to both dicts:

```python
# Line 67-72: PROVIDER_MAP — add after "merrill" entry
PROVIDER_MAP = {
    "robinhood": "snaptrade",
    "fidelity":  "snaptrade",
    "schwab":    "plaid",
    "merrill":   "plaid",
    "chase":     "plaid",
    "marcus":    "plaid",
}

# Line 74-79: INSTITUTION_LABELS — add after "fidelity" entry
INSTITUTION_LABELS = {
    "robinhood": "Robinhood",
    "schwab":    "Charles Schwab",
    "merrill":   "Merrill Lynch (Bank of America)",
    "fidelity":  "Fidelity",
    "chase":     "Chase",
    "marcus":    "Marcus (Goldman Sachs)",
}
```

- [ ] **Step 2: Verify no import errors**

Run: `python -c "import repo.plaid_extract; print('OK')"`

If that doesn't work due to path issues, run from the repo directory:
```bash
cd repo && python -c "from plaid_extract import PROVIDER_MAP, INSTITUTION_LABELS; print('chase' in PROVIDER_MAP, 'marcus' in INSTITUTION_LABELS)"
```
Expected: `True True`

- [ ] **Step 3: Commit**

```bash
git add repo/plaid_extract.py
git commit -m "feat: add Chase and Marcus to provider and label maps"
```

---

### Task 2: Update setup_plaid() to Support Cash Institutions (plaid_extract.py)

**Files:**
- Modify: `repo/plaid_extract.py:446-513`

- [ ] **Step 1: Update setup_plaid() header text and institution filtering**

Change line 448 to include cash institutions:
```python
    print("  PLAID SETUP (Merrill Lynch, Chase, Marcus)")
```

Currently line 464 filters to only Plaid-mapped institutions:
```python
    plaid_insts = {k: v for k, v in INSTITUTION_LABELS.items() if PROVIDER_MAP.get(k) == "plaid"}
```
This already works — Chase and Marcus were added to both maps in Task 1, so they'll appear automatically.

- [ ] **Step 2: Add institution type prompt after linking**

After the user selects an institution to link (line 482), before calling `_plaid_link`, ask whether it's an investment or cash account. Update the loop at lines 482-484:

```python
    for l in labels:
        # Ask if this is a cash-only institution (checking/savings)
        inst_name = INSTITUTION_LABELS.get(l, l)
        # Default cash institutions
        cash_defaults = {"chase", "marcus"}
        if l in cash_defaults:
            inst_type = "cash"
            print(f"  {inst_name}: setting as cash account (checking/savings)")
        else:
            type_choice = input(f"  Is {inst_name} an investment or cash account? [investment/cash]: ").strip().lower()
            inst_type = "cash" if type_choice == "cash" else "investment"
        _plaid_link(client, config, l, inst_type=inst_type)
    save_config(config)
```

- [ ] **Step 3: Update _plaid_link() to accept inst_type and use correct Plaid products**

Modify `_plaid_link` at line 487 to accept `inst_type` and choose products accordingly:

```python
def _plaid_link(client, config, label, inst_type="investment"):
    name = INSTITUTION_LABELS[label]
    pc = config["plaid"]
    print(f"\n  --- Linking {name} via Plaid ({inst_type}) ---")

    # Use appropriate Plaid products based on institution type
    if inst_type == "cash":
        products = [Products("transactions")]
    else:
        products = [Products("investments")]

    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=f"portfolio-{label}"),
        client_name="Portfolio Analyzer",
        products=products,
        country_codes=[CountryCode("US")], language="en",
    )
    link_token = client.link_token_create(req)["link_token"]
    print(f"  Starting local server...\n")
    pub = _serve_plaid_link(client, link_token, name, None)
    if not pub:
        print(f"  No token received. Skipping.")
        return
    ex = client.item_public_token_exchange(ItemPublicTokenExchangeRequest(public_token=pub))
    at, iid = ex["access_token"], ex["item_id"]
    accts = [
        {"account_id": a["account_id"], "name": a["name"],
         "type": str(a["type"]), "subtype": str(a.get("subtype") or ""), "mask": a.get("mask")}
        for a in client.accounts_get(AccountsGetRequest(access_token=at))["accounts"]
    ]
    inst_config = {"access_token": at, "item_id": iid, "accounts": accts}
    if inst_type == "cash":
        inst_config["type"] = "cash"
    pc.setdefault("institutions", {})[label] = inst_config
    print(f"  Linked {name}: {len(accts)} accounts ({inst_type})")
```

- [ ] **Step 4: Verify syntax**

```bash
cd repo && python -c "from plaid_extract import setup_plaid; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add repo/plaid_extract.py
git commit -m "feat: update setup_plaid to support cash institution type (Chase, Marcus)"
```

---

### Task 3: Add extract_plaid_cash() Function (plaid_extract.py)

**Files:**
- Modify: `repo/plaid_extract.py` (insert after `extract_plaid()` function, before line 657)

- [ ] **Step 1: Add the extract_plaid_cash() function**

Insert this function after `extract_plaid()` (after line 654) and before the `# Pipeline output` section comment at line 657:

```python
def extract_plaid_cash(config):
    """Extract balances from cash-only Plaid institutions (checking/savings).
    
    Returns dict like:
    {
        "chase": {"accounts": [{"name": "...", "balance": 123.45, ...}], "total": 123.45},
        "marcus": {"accounts": [...], "total": 456.78},
    }
    """
    if not PLAID_AVAILABLE:
        return {}
    
    insts = config["plaid"].get("institutions", {})
    cash_insts = {k: v for k, v in insts.items() if v.get("type") == "cash"}
    
    if not cash_insts:
        return {}
    
    client = get_plaid_client(config)
    results = {}
    
    for label, idata in cash_insts.items():
        name = INSTITUTION_LABELS.get(label, label)
        at = idata["access_token"]
        print(f"\n{'='*60}\n  Extracting cash balances: {name}\n{'='*60}")
        
        try:
            resp = client.accounts_get(AccountsGetRequest(access_token=at))
            accounts = []
            total = 0.0
            for a in resp["accounts"]:
                bal = _num(a["balances"].get("current", 0))
                accounts.append({
                    "name": a["name"],
                    "balance": bal,
                    "type": str(a["type"]),
                    "subtype": str(a.get("subtype", "")),
                    "account_id": a["account_id"],
                    "mask": a.get("mask", ""),
                })
                total += bal
                print(f"  {a['name']}: ${bal:,.2f}")
            
            results[label] = {"accounts": accounts, "total": round(total, 2)}
            print(f"  Total {name}: ${total:,.2f}")
        except Exception as e:
            print(f"  ERROR extracting {name}: {e}")
    
    return results
```

- [ ] **Step 2: Verify the function imports and compiles**

```bash
cd repo && python -c "from plaid_extract import extract_plaid_cash; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add repo/plaid_extract.py
git commit -m "feat: add extract_plaid_cash() for Chase and Marcus balance extraction"
```

---

### Task 4: Integrate Cash Extraction into Pipeline (weekly_pipeline.py)

**Files:**
- Modify: `repo/weekly_pipeline.py:111-165` (extract_all function)
- Modify: `repo/weekly_pipeline.py:210-262` (prepare_builder_data function)
- Modify: `repo/weekly_pipeline.py:268-353` (run_pipeline function)

- [ ] **Step 1: Update the import in extract_all()**

At line 113, add `extract_plaid_cash` to the import:

```python
    from plaid_extract import load_config, extract_snaptrade, extract_plaid, extract_plaid_cash, to_pipeline_format
```

- [ ] **Step 2: Add cash extraction call in extract_all()**

After the Plaid extraction block (after line 145), add a cash extraction block:

```python
    # Plaid Cash (Chase, Marcus)
    cash_accounts = {}
    try:
        logging.info("Extracting Plaid cash accounts (Chase, Marcus)...")
        cash_accounts = extract_plaid_cash(config)
        if cash_accounts:
            logging.info(f"  Cash accounts: {list(cash_accounts.keys())}")
            for label, data in cash_accounts.items():
                logging.info(f"    {label}: ${data['total']:,.2f}")
        else:
            logging.info("  No cash accounts configured")
    except Exception as e:
        msg = f"Cash account extraction failed: {e}"
        logging.error(msg)
        errors.append(msg)
```

- [ ] **Step 3: Include cash_accounts in the raw output**

At line 156, after `raw_file.write_text(...)`, the raw dict is saved. Add `cash_accounts` to the raw dict before saving. Change lines 152-157 to:

```python
    # Save raw extraction
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    EXTRACT_OUTPUT.mkdir(parents=True, exist_ok=True)

    # Include cash accounts in raw output
    if cash_accounts:
        raw["_cash_accounts"] = cash_accounts

    raw_file = EXTRACT_OUTPUT / f"weekly_raw_{ts}.json"
    raw_file.write_text(json.dumps(raw, indent=2, default=str))
    logging.info(f"Raw extraction saved: {raw_file}")
```

- [ ] **Step 4: Add cash history persistence function**

Add this function after `load_latest_extraction()` (after line 187):

```python
CASH_HISTORY_FILE = EXTRACT_OUTPUT / "cash_history.json"


def persist_cash_snapshot(cash_accounts):
    """Append today's cash balances to the persistent cash_history.json."""
    if not cash_accounts:
        return

    today = datetime.date.today().isoformat()
    entry = {"date": today}
    for label, data in cash_accounts.items():
        entry[label] = data["total"]
    entry["total"] = round(sum(d["total"] for d in cash_accounts.values()), 2)

    # Load existing history
    history = []
    if CASH_HISTORY_FILE.exists():
        try:
            history = json.loads(CASH_HISTORY_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            history = []

    # Deduplicate by date (overwrite same-day entry)
    history = [h for h in history if h.get("date") != today]
    history.append(entry)
    history.sort(key=lambda h: h["date"])

    CASH_HISTORY_FILE.write_text(json.dumps(history, indent=2))
    logging.info(f"Cash snapshot saved: {CASH_HISTORY_FILE} ({len(history)} entries)")


def load_cash_history():
    """Load the persistent cash history file."""
    if CASH_HISTORY_FILE.exists():
        try:
            return json.loads(CASH_HISTORY_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            return []
    return []
```

- [ ] **Step 5: Update prepare_builder_data() to return cash data**

Modify `prepare_builder_data()` at line 210 to also return cash info. Change the function signature and add cash extraction at the end:

```python
def prepare_builder_data(raw, pipeline):
    """Convert raw/pipeline extraction data into the format build_portfolio expects.

    build_portfolio.py expects:
      - fid_data: dict keyed by account (e.g. "fidelity_BROKERAGE") with holdings
      - rh_raw: dict with "robinhood" key containing accounts, holdings, etc.
      - merrill_raw: dict with Merrill raw extraction data
      - cash_current: dict from extract_plaid_cash output (or from raw["_cash_accounts"])
      - cash_history: list of historical snapshots from cash_history.json
    """
    fid_data = {}
    rh_raw = None
    merrill_raw = None
    cash_current = None

    # Process raw data for all providers
    if raw:
        # Extract cash accounts if present in raw data
        cash_current = raw.get("_cash_accounts")

        for label, data in raw.items():
            if label.startswith("_"):
                continue
            if "robinhood" in label.lower():
                rh_raw = {label: data}
            elif "fidelity" in label.lower():
                # Fidelity comes from SnapTrade — convert holdings to the
                # dict-by-account format that build_portfolio expects
                for acct in data.get("accounts", []):
                    acct_id = acct.get("account_id", "")
                    acct_number = acct.get("number", acct_id)
                    key = f"fidelity_{acct_number}"
                    acct_holdings = {}
                    for h in data.get("holdings", []):
                        if h.get("account_id") == acct_id:
                            ticker = h.get("ticker", "UNKNOWN")
                            if ticker and ticker != "UNKNOWN":
                                acct_holdings[ticker] = {
                                    "qty": h.get("quantity", 0),
                                    "price": h.get("institution_price", 0),
                                    "mv": h.get("institution_value", 0),
                                    "cb": h.get("cost_basis", 0),
                                    "gl": h.get("gain_loss", 0),
                                    "name": h.get("name", ""),
                                }
                    fid_data[key] = acct_holdings
            elif "merrill" in label.lower():
                merrill_raw = data

    # Fallback: check pipeline data for Fidelity if not found in raw
    if not fid_data and pipeline:
        today = datetime.date.today().isoformat()
        for label, acct in pipeline.items():
            if label.startswith("_") or label == "benchmarks":
                continue
            if label.startswith("fidelity"):
                holdings = acct.get("holdings", {})
                date_key = sorted(holdings.keys())[-1] if holdings else today
                fid_data[label] = holdings.get(date_key, {})

    cash_history = load_cash_history()

    return fid_data, rh_raw, merrill_raw, cash_current, cash_history
```

- [ ] **Step 6: Update run_pipeline() to call cash persistence and pass cash to builder**

In `run_pipeline()`, after the extraction step (around line 293), add cash persistence. Find the block after `extract_all` returns (line 289-293):

After line 290 (`errors.extend(extract_errors)`), add:
```python
        # Persist cash snapshot
        cash_from_raw = raw.get("_cash_accounts") if raw else None
        if cash_from_raw:
            persist_cash_snapshot(cash_from_raw)
```

Then update the builder call. At line 322, `prepare_builder_data` now returns 5 values:

```python
            fid_data, rh_raw, merrill_raw, cash_current, cash_history = prepare_builder_data(raw, pipeline)
```

And update the `build_xlsx` call at line 333 and the fallback at line 326 to pass cash data. This requires updating `build_xlsx()` too.

- [ ] **Step 7: Update build_xlsx() to accept and pass cash data**

Modify the `build_xlsx()` function at line 193:

```python
def build_xlsx(fid_pipeline_data, rh_raw_data, benchmarks, merrill_raw=None,
               cash_current=None, cash_history=None):
    """Build the portfolio analysis Excel workbook."""
    from build_portfolio import build_workbook

    logging.info("Building Excel workbook...")
    output = build_workbook(
        output_path=str(OUTPUT_XLSX),
        manual_json_path=str(MANUAL_DATA),
        benchmarks=benchmarks,
        fid_data_dict=fid_pipeline_data,
        rh_raw_dict=rh_raw_data,
        merrill_raw=merrill_raw,
        cash_current=cash_current,
        cash_history=cash_history,
    )
    logging.info(f"Workbook saved: {output}")
    return output
```

Update the call sites in `run_pipeline()`. The main call at line 333:
```python
                build_xlsx(fid_data, rh_raw, benchmarks, merrill_raw=merrill_raw,
                           cash_current=cash_current, cash_history=cash_history)
```

The fallback call at lines 326-331:
```python
                build_workbook(
                    output_path=str(OUTPUT_XLSX),
                    manual_json_path=str(MANUAL_DATA),
                    benchmarks=benchmarks,
                    merrill_raw=merrill_raw,
                    cash_current=cash_current,
                    cash_history=cash_history,
                )
```

- [ ] **Step 8: Verify syntax**

```bash
cd repo && python -c "from weekly_pipeline import extract_all, prepare_builder_data, persist_cash_snapshot, load_cash_history; print('OK')"
```
Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add repo/weekly_pipeline.py
git commit -m "feat: integrate cash extraction into pipeline with history persistence"
```

---

### Task 5: Add build_cash_tab() Function (build_portfolio.py)

**Files:**
- Modify: `repo/build_portfolio.py` (insert after `build_angel_tab()` and before `build_dashboard()`)

- [ ] **Step 1: Find the insertion point**

The `build_angel_tab()` function ends around line 567 and `build_dashboard()` starts at line 569. Insert the new function between them.

- [ ] **Step 2: Add build_cash_tab()**

Insert after `build_angel_tab()` ends and before `build_dashboard()`:

```python
# ============================================================
# CASH TAB
# ============================================================
def build_cash_tab(wb, cash_current, cash_history):
    """Build the Cash tab showing current balances and monthly history.
    
    cash_current: dict from extract_plaid_cash, e.g.
        {"chase": {"accounts": [...], "total": 15234.56}, "marcus": {...}}
    cash_history: list of snapshots, e.g.
        [{"date": "2026-04-04", "chase": 15234.56, "marcus": 42000.00, "total": 57234.56}]
    
    Returns (ws, total_row) where total_row is the TOTAL CASH row number.
    """
    ws = wb.create_sheet("Cash")

    ws.cell(1, 1, "Cash Accounts").font = TITLE
    ws.cell(2, 1, "Blue = hardcoded from Plaid | Black = formula").font = GRAY

    # --- Current Balances ---
    r = 4
    ws.cell(r, 1, "CURRENT BALANCES").font = SECTION
    r += 1
    hdr(ws, r, ["Account", "Institution", "Balance"], [30, 24, 16])
    r += 1

    acct_start = r
    inst_labels = {
        "chase": "Chase",
        "marcus": "Marcus (Goldman Sachs)",
    }

    if cash_current:
        for inst_key in sorted(cash_current.keys()):
            inst_data = cash_current[inst_key]
            inst_name = inst_labels.get(inst_key, inst_key)
            for acct in inst_data["accounts"]:
                ws.cell(r, 1, acct["name"]).font = BLUE
                ws.cell(r, 2, inst_name).font = BLUE
                ws.cell(r, 3, acct["balance"]).font = BLUE
                ws.cell(r, 3).number_format = D_FMT
                brd(ws, r, r, 1, 3); zb(ws, r, 3)
                r += 1

    # TOTAL row
    total_row = r
    ws.cell(r, 1, "TOTAL CASH").font = BOLD
    ws.cell(r, 2, "").font = BOLD
    if r > acct_start:
        ws.cell(r, 3).value = f"=SUM(C{acct_start}:C{r-1})"
    else:
        ws.cell(r, 3, 0)
    ws.cell(r, 3).font = BOLD
    ws.cell(r, 3).number_format = D_FMT
    brd(ws, r, r, 1, 3)

    # --- Monthly Balance History ---
    r += 2
    ws.cell(r, 1, "MONTHLY BALANCE HISTORY").font = SECTION
    r += 1

    # Determine which institutions appear in history
    inst_keys = sorted(set(
        k for entry in (cash_history or [])
        for k in entry.keys()
        if k not in ("date", "total")
    ))
    if not inst_keys and cash_current:
        inst_keys = sorted(cash_current.keys())

    hist_headers = ["Month"] + [inst_labels.get(k, k) for k in inst_keys] + ["Total"]
    hist_widths = [18] + [16] * len(inst_keys) + [16]
    hdr(ws, r, hist_headers, hist_widths)
    r += 1

    # Build monthly lookup: for each month, find the latest snapshot
    monthly = {}
    for entry in (cash_history or []):
        month_key = entry["date"][:7]  # "2026-04"
        if month_key not in monthly or entry["date"] > monthly[month_key]["date"]:
            monthly[month_key] = entry

    import datetime as _dt
    year = _dt.date.today().year
    history_start_row = r
    first_data_row = None

    for m in range(1, 13):
        month_key = f"{year}-{m:02d}"
        month_name = _dt.date(year, m, 1).strftime("%B %Y")
        ws.cell(r, 1, month_name).font = BLACK

        entry = monthly.get(month_key)
        if entry:
            if first_data_row is None:
                first_data_row = r
            for ci, inst_key in enumerate(inst_keys, 2):
                val = entry.get(inst_key, 0)
                ws.cell(r, ci, val).font = BLUE
                ws.cell(r, ci).number_format = D_FMT
            # Total column = sum of institution columns
            total_col = len(inst_keys) + 2
            start_col_letter = cl(2)
            end_col_letter = cl(total_col - 1)
            ws.cell(r, total_col).value = f"=SUM({start_col_letter}{r}:{end_col_letter}{r})"
            ws.cell(r, total_col).font = BLACK
            ws.cell(r, total_col).number_format = D_FMT
        else:
            for ci in range(2, len(inst_keys) + 3):
                ws.cell(r, ci, "--").font = GRAY
                ws.cell(r, ci).alignment = C_CENTER

        brd(ws, r, r, 1, len(inst_keys) + 2)
        zb(ws, r, len(inst_keys) + 2)
        r += 1

    return ws, total_row, first_data_row
```

- [ ] **Step 3: Verify syntax**

```bash
cd repo && python -c "from build_portfolio import build_cash_tab; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add repo/build_portfolio.py
git commit -m "feat: add build_cash_tab() for Cash worksheet"
```

---

### Task 6: Update build_dashboard() for Cash Row and Liquidity (build_portfolio.py)

**Files:**
- Modify: `repo/build_portfolio.py:569-744`

- [ ] **Step 1: Add "cash" to acct_rows**

At line 587-594, add the Cash row after Robinhood:

```python
    acct_rows = [
        ("Fidelity Brokerage", "'Fidelity Brokerage'", "fid_brokerage"),
        ("Fidelity Roth IRA", "'Fidelity Roth IRA'", "standard"),
        ("401(k)", "'401(k)'", "401k"),
        ("Fidelity HSA", "'Fidelity HSA'", "fid_hsa"),
        ("Angel Investments", "'Angel Investments'", "angel"),
        ("Robinhood", "'Robinhood'", "robinhood"),
        ("Cash", "'Cash'", "cash"),
    ]
```

- [ ] **Step 2: Add the "cash" account type handler in the rendering loop**

In the loop at lines 598-647, add a handler for `atype == "cash"` after the `elif atype == "robinhood":` block (after line 636). Insert before the `else:` clause:

```python
        elif atype == "cash":
            cash_total_row = acct_info.get("cash_total_row")
            cash_first_data_row = acct_info.get("cash_first_data_row")
            if cash_total_row:
                ws.cell(r, 3).value = f"='Cash'!C{cash_total_row}"
                ws.cell(r, 3).font = GREEN; ws.cell(r, 3).number_format = D_FMT
            else:
                ws.cell(r, 3, 0).font = GRAY; ws.cell(r, 3).number_format = D_FMT
            # Beginning = earliest month's total from history tab
            if cash_first_data_row:
                total_col_letter = acct_info.get("cash_total_col_letter", "D")
                ws.cell(r, 2).value = f"='Cash'!{total_col_letter}{cash_first_data_row}"
                ws.cell(r, 2).font = GREEN; ws.cell(r, 2).number_format = D_FMT
            else:
                ws.cell(r, 2).value = ws.cell(r, 3).value  # same as ending if no history
                ws.cell(r, 2).font = GREEN; ws.cell(r, 2).number_format = D_FMT
            ws.cell(r, 4, "N/A").font = GRAY
            ws.cell(r, 5, "N/A").font = GRAY
            ws.cell(r, 6, "N/A").font = GRAY
            ws.cell(r, 7, "N/A").font = GRAY
```

- [ ] **Step 3: Update the Benchmark Comparison alpha loop**

The benchmark alpha loop at lines 681-683 hardcodes account row offsets. With Cash added as the 7th row (index 6, offset `first_r+6`), Cash must be excluded since TWR is N/A.

The current code at line 681:
```python
        for ci, acct_r in enumerate([first_r, first_r+1, first_r+2, first_r+3, first_r+5], 3):
```

Update to keep the same accounts (skip Angel at +4 and Cash at +6):
```python
        for ci, acct_r in enumerate([first_r, first_r+1, first_r+2, first_r+3, first_r+5], 3):
```

This stays the same — Robinhood is still at `first_r+5`, Cash at `first_r+6` is simply not included. The alpha column header row at line 667 also stays the same (no "Cash" column needed).

Similarly, the alpha fill loop at line 688:
```python
    for i, acct_r in enumerate([first_r, first_r+1, first_r+2, first_r+3, first_r+5]):
```
This also stays the same — it already skips Angel (first_r+4), and Cash (first_r+6) is likewise excluded by not being listed.

No changes needed to these loops.

- [ ] **Step 4: Update the Liquidity Breakdown**

At lines 720-742, update the Liquid row formula to include Cash. The Cash row is at `first_r+6`.

Change line 726 from:
```python
    ws.cell(r, 2).value = f"=C{first_r}+C{first_r+1}+C{first_r+3}+C{first_r+5}"
```
to:
```python
    ws.cell(r, 2).value = f"=C{first_r}+C{first_r+1}+C{first_r+3}+C{first_r+5}+C{first_r+6}"
```

Change line 729 from:
```python
    ws.cell(r, 4, "4 accounts").font = GRAY
    ws.cell(r, 5, "Fid Brok + Roth IRA + HSA + Robinhood").font = GRAY
```
to:
```python
    ws.cell(r, 4, "5 accounts").font = GRAY
    ws.cell(r, 5, "Fid Brok + Roth IRA + HSA + Robinhood + Cash").font = GRAY
```

- [ ] **Step 5: Verify syntax**

```bash
cd repo && python -c "from build_portfolio import build_dashboard; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add repo/build_portfolio.py
git commit -m "feat: update dashboard with Cash row and liquidity breakdown"
```

---

### Task 7: Update build_workbook() to Wire Cash Tab (build_portfolio.py)

**Files:**
- Modify: `repo/build_portfolio.py:921-1015`

- [ ] **Step 1: Update build_workbook() signature to accept cash parameters**

At line 921, add `cash_current` and `cash_history` parameters:

```python
def build_workbook(fid_json_path=None, rh_json_path=None, output_path=None,
                   manual_json_path=None, benchmarks=None,
                   fid_data_dict=None, rh_raw_dict=None, merrill_raw=None,
                   cash_current=None, cash_history=None):
```

- [ ] **Step 2: Build the Cash tab in the workbook assembly**

After `build_angel_tab()` call at line 989 (`ws6, angel_total = build_angel_tab(wb)`), add:

```python
        # Build Cash tab
        cash_total_row = None
        cash_first_data_row = None
        if cash_current or cash_history:
            ws7, cash_total_row, cash_first_data_row = build_cash_tab(
                wb, cash_current, cash_history or [])
        
```

- [ ] **Step 3: Pass cash info to acct_info for the Dashboard**

After line 1004 (`acct_info["ig_row_angel"] = None`), add:

```python
        acct_info["cash_total_row"] = cash_total_row
        acct_info["cash_first_data_row"] = cash_first_data_row
        # Determine total column letter for Cash history tab
        # Total column = len(institution_keys) + 2
        if cash_current:
            n_inst = len(cash_current)
            from openpyxl.utils import get_column_letter as _gcl
            acct_info["cash_total_col_letter"] = _gcl(n_inst + 2)
        else:
            acct_info["cash_total_col_letter"] = "D"
```

- [ ] **Step 4: Verify full build with no data (dry run)**

```bash
cd repo && python -c "
from build_portfolio import build_workbook
# Test with no cash data — should still build fine
import tempfile, os
out = os.path.join(tempfile.gettempdir(), 'test_portfolio.xlsx')
try:
    build_workbook(output_path=out)
    print('Build OK (no cash)')
except Exception as e:
    print(f'Error: {e}')
"
```
Expected: `Build OK (no cash)` (or existing error unrelated to cash changes)

- [ ] **Step 5: Test with mock cash data**

```bash
cd repo && python -c "
from build_portfolio import build_workbook
import tempfile, os
out = os.path.join(tempfile.gettempdir(), 'test_portfolio_cash.xlsx')
cash_current = {
    'chase': {'accounts': [{'name': 'Chase Checking', 'balance': 15234.56, 'type': 'depository', 'subtype': 'checking', 'account_id': 'test1', 'mask': '1234'}], 'total': 15234.56},
    'marcus': {'accounts': [{'name': 'Marcus Savings', 'balance': 42000.00, 'type': 'depository', 'subtype': 'savings', 'account_id': 'test2', 'mask': '5678'}], 'total': 42000.00},
}
cash_history = [
    {'date': '2026-03-28', 'chase': 15100.00, 'marcus': 41500.00, 'total': 56600.00},
    {'date': '2026-04-04', 'chase': 15234.56, 'marcus': 42000.00, 'total': 57234.56},
]
try:
    build_workbook(output_path=out, cash_current=cash_current, cash_history=cash_history)
    print(f'Build OK with cash: {out}')
except Exception as e:
    print(f'Error: {e}')
    import traceback; traceback.print_exc()
"
```
Expected: `Build OK with cash: ...`

- [ ] **Step 6: Commit**

```bash
git add repo/build_portfolio.py
git commit -m "feat: wire cash tab and data into build_workbook()"
```

---

### Task 8: Update extract_plaid() to Skip Cash Institutions (plaid_extract.py)

**Files:**
- Modify: `repo/plaid_extract.py:601-654`

The existing `extract_plaid()` function iterates over ALL Plaid institutions and calls `investments_holdings_get`. This will fail for Chase and Marcus since they don't have investment products. We need to skip institutions marked as `type: "cash"`.

- [ ] **Step 1: Add a type filter at the top of extract_plaid()**

At line 605-606, after getting `insts`, filter out cash institutions:

Change:
```python
    insts = config["plaid"].get("institutions", {})
    results = {}
    for label, idata in insts.items():
```

To:
```python
    insts = config["plaid"].get("institutions", {})
    results = {}
    for label, idata in insts.items():
        if idata.get("type") == "cash":
            continue  # Cash institutions handled by extract_plaid_cash()
```

- [ ] **Step 2: Verify syntax**

```bash
cd repo && python -c "from plaid_extract import extract_plaid; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add repo/plaid_extract.py
git commit -m "fix: skip cash institutions in extract_plaid() to avoid API errors"
```

---

### Task 9: End-to-End Verification

- [ ] **Step 1: Test the full pipeline in dry-run mode (no API calls needed)**

Create a mock test that validates the entire data flow with synthetic cash data:

```bash
cd repo && python -c "
import json, tempfile, os
from pathlib import Path

# Test 1: cash_history.json persistence
print('Test 1: Cash history persistence')
from weekly_pipeline import persist_cash_snapshot, load_cash_history, CASH_HISTORY_FILE

# Use a temp file for testing
original_path = str(CASH_HISTORY_FILE)

cash_data = {
    'chase': {'accounts': [], 'total': 15234.56},
    'marcus': {'accounts': [], 'total': 42000.00},
}

# Persist and load
persist_cash_snapshot(cash_data)
history = load_cash_history()
assert len(history) >= 1, f'Expected at least 1 entry, got {len(history)}'
latest = history[-1]
assert latest['chase'] == 15234.56, f'Chase balance mismatch: {latest}'
assert latest['marcus'] == 42000.00, f'Marcus balance mismatch: {latest}'
assert latest['total'] == 57234.56, f'Total mismatch: {latest}'
print(f'  PASS: {len(history)} entries, latest total: \${latest[\"total\"]:,.2f}')

# Test 2: Build workbook with cash
print('Test 2: Full workbook build with cash')
from build_portfolio import build_workbook

out = os.path.join(tempfile.gettempdir(), 'test_full_cash.xlsx')
cash_current = {
    'chase': {'accounts': [{'name': 'Chase Checking', 'balance': 15234.56, 'type': 'depository', 'subtype': 'checking', 'account_id': 't1', 'mask': '1234'}], 'total': 15234.56},
    'marcus': {'accounts': [{'name': 'Marcus Savings', 'balance': 42000.00, 'type': 'depository', 'subtype': 'savings', 'account_id': 't2', 'mask': '5678'}], 'total': 42000.00},
}
cash_hist = [
    {'date': '2026-03-28', 'chase': 15100.00, 'marcus': 41500.00, 'total': 56600.00},
    {'date': '2026-04-04', 'chase': 15234.56, 'marcus': 42000.00, 'total': 57234.56},
]
build_workbook(output_path=out, cash_current=cash_current, cash_history=cash_hist)
print(f'  PASS: Workbook saved to {out}')

# Test 3: Verify Cash tab exists
from openpyxl import load_workbook
wb = load_workbook(out)
assert 'Cash' in wb.sheetnames, f'Cash tab missing. Tabs: {wb.sheetnames}'
assert 'Dashboard' in wb.sheetnames, f'Dashboard missing. Tabs: {wb.sheetnames}'
print(f'  PASS: Tabs present: {wb.sheetnames}')

# Test 4: Verify Cash tab content
ws = wb['Cash']
assert ws.cell(1, 1).value == 'Cash Accounts', f'Title wrong: {ws.cell(1,1).value}'
# Find TOTAL CASH row
found_total = False
for row in range(1, ws.max_row + 1):
    if ws.cell(row, 1).value == 'TOTAL CASH':
        found_total = True
        break
assert found_total, 'TOTAL CASH row not found'
print(f'  PASS: Cash tab has correct structure')

# Test 5: Verify Dashboard has Cash row
ws_d = wb['Dashboard']
found_cash = False
for row in range(1, ws_d.max_row + 1):
    if ws_d.cell(row, 1).value == 'Cash':
        found_cash = True
        break
assert found_cash, 'Cash row not found in Dashboard'
print(f'  PASS: Dashboard has Cash row')

print()
print('All tests passed!')
"
```

Expected: `All tests passed!`

- [ ] **Step 2: Commit all remaining changes**

```bash
git add -A
git commit -m "test: verify end-to-end cash account integration"
```

---

### Task 10: Link Chase and Marcus via Plaid (Interactive Setup)

This task requires user interaction — it cannot be automated by the agent.

- [ ] **Step 1: Run Plaid setup for Chase**

```bash
cd repo && python plaid_extract.py --setup --provider plaid
```

Select Chase from the menu. A browser window will open for credential-based Plaid Link. Log in with your Chase credentials. After successful linking, the config will be saved with `"type": "cash"`.

- [ ] **Step 2: Run Plaid setup for Marcus**

```bash
cd repo && python plaid_extract.py --setup --provider plaid
```

Select Marcus from the menu. Same browser-based flow.

- [ ] **Step 3: Verify both are linked**

```bash
cd repo && python -c "
from plaid_extract import load_config
config = load_config()
insts = config['plaid'].get('institutions', {})
for k in ['chase', 'marcus']:
    if k in insts:
        t = insts[k].get('type', 'investment')
        n = len(insts[k].get('accounts', []))
        print(f'  {k}: linked ({t}), {n} accounts')
    else:
        print(f'  {k}: NOT linked')
"
```
Expected: Both show as linked with type `cash`.

- [ ] **Step 4: Test live extraction**

```bash
cd repo && python -c "
from plaid_extract import load_config, extract_plaid_cash
config = load_config()
result = extract_plaid_cash(config)
for k, v in result.items():
    print(f'{k}: \${v[\"total\"]:,.2f} ({len(v[\"accounts\"])} accounts)')
"
```

- [ ] **Step 5: Run full pipeline**

```bash
cd repo && python weekly_pipeline.py
```

Verify:
- `extract_output/cash_history.json` exists and has an entry
- `2026_Portfolio_Analysis.xlsx` has a Cash tab
- Dashboard shows Cash row in account summary
