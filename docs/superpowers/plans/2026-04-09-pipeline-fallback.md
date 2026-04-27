# Pipeline Fallback & Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the daily pipeline resilient to individual source failures by falling back to the most recent successful extraction, adding timeouts to Playwright, retrying API sources once, falling back to cached benchmarks, and marking stale data in the Dashboard.

**Architecture:** A new `load_last_good_source()` function in `weekly_pipeline.py` scans previous extraction files for a specific source's data. The `extract_all()` function gets per-source timeouts and single retries for API sources. The `run_pipeline()` function merges fresh + fallback data before building. The Dashboard's Daily Summary prose gets a staleness note when fallback data is used.

**Tech Stack:** Python, json, pathlib, subprocess (for Playwright timeout), openpyxl.

---

### Task 1: Add `load_last_good_source()` to find fallback data from previous extractions

**Files:**
- Modify: `weekly_pipeline.py`

This function scans previous `weekly_raw_*.json` files for a specific source key (e.g., `_fidelity`, `robinhood`) and returns the most recent data found.

- [ ] **Step 1: Add the function after `load_latest_extraction()`**

```python
def load_last_good_source(source_key):
    """Find the most recent extraction that contains data for a given source.

    Scans weekly_raw_*.json files in reverse chronological order.
    Returns (data_dict, filename) or (None, None) if never found.
    """
    raw_files = sorted(EXTRACT_OUTPUT.glob("weekly_raw_*.json"), reverse=True)
    for f in raw_files:
        try:
            raw = json.loads(f.read_text())
            if source_key in raw and raw[source_key]:
                logging.info(f"  Fallback: found {source_key} in {f.name}")
                return raw[source_key], f.name
        except Exception:
            continue
    return None, None
```

- [ ] **Step 2: Verify it finds Fidelity data from previous extractions**

Run: `python -c "from weekly_pipeline import load_last_good_source, setup_logging; setup_logging(); d, f = load_last_good_source('_fidelity'); print(f'Found: {f}, keys: {list(d.keys()) if d else None}')"`

Expected: Should find `_fidelity` data from the Apr 5 extraction file.

---

### Task 2: Add Playwright timeout wrapper for Fidelity extraction

**Files:**
- Modify: `weekly_pipeline.py` — wrap the Fidelity extraction in `extract_all()` with a 120-second timeout

- [ ] **Step 1: Import `signal` (Unix) or use `threading` (Windows) for timeout**

Since this is Windows, use `threading.Timer` to kill the extraction if it hangs. Replace the Fidelity extraction block in `extract_all()`:

```python
    # Fidelity (Playwright browser automation) — with timeout
    fidelity_data = None
    try:
        logging.info("Extracting Fidelity (Playwright)...")
        import threading
        fid_result = [None]
        fid_error = [None]

        def _run_fidelity():
            try:
                from fidelity_extract import extract_fidelity
                fid_result[0] = extract_fidelity(headless=True)
            except Exception as e:
                fid_error[0] = e

        t = threading.Thread(target=_run_fidelity, daemon=True)
        t.start()
        t.join(timeout=120)  # 2 minute timeout

        if t.is_alive():
            msg = "Fidelity extraction timed out after 120 seconds"
            logging.error(msg)
            errors.append(msg)
            # Thread will die on its own since daemon=True
        elif fid_error[0]:
            raise fid_error[0]
        else:
            fidelity_data = fid_result[0]
            if fidelity_data:
                logging.info(f"  Fidelity: {len(fidelity_data)} accounts extracted")
                for label, data in fidelity_data.items():
                    n = len(data.get("holdings", {}))
                    bal = data.get("balance", 0)
                    logging.info(f"    {label}: {n} positions, ${bal:,.2f}")
            else:
                logging.warning("  Fidelity: no data returned")
    except Exception as e:
        msg = f"Fidelity extraction failed: {e}"
        logging.error(msg)
        errors.append(msg)
```

---

### Task 3: Add single retry for API sources (SnapTrade, Plaid)

**Files:**
- Modify: `weekly_pipeline.py` — add retry wrapper in `extract_all()`

- [ ] **Step 1: Add a retry helper at module level**

```python
def _extract_with_retry(name, func, *args, max_retries=1, delay=10):
    """Call an extraction function with one retry on failure."""
    for attempt in range(max_retries + 1):
        try:
            result = func(*args)
            return result
        except Exception as e:
            if attempt < max_retries:
                logging.warning(f"  {name} attempt {attempt+1} failed: {e}. Retrying in {delay}s...")
                import time
                time.sleep(delay)
            else:
                raise
```

- [ ] **Step 2: Wrap SnapTrade and Plaid calls with the retry helper**

Replace the SnapTrade block:
```python
    # SnapTrade (Robinhood) — with retry
    try:
        logging.info("Extracting SnapTrade (Robinhood)...")
        st_data = _extract_with_retry("SnapTrade", extract_snaptrade, config, start_date, end_date)
        if st_data:
            raw.update(st_data)
            logging.info(f"  SnapTrade: {len(st_data)} institutions extracted")
        else:
            logging.warning("  SnapTrade: no data returned")
    except Exception as e:
        msg = f"SnapTrade extraction failed after retry: {e}"
        logging.error(msg)
        errors.append(msg)
```

Same pattern for Plaid:
```python
    # Plaid (Merrill) — with retry
    try:
        logging.info("Extracting Plaid (Merrill)...")
        plaid_data = _extract_with_retry("Plaid", extract_plaid, config, start_date, end_date)
        if plaid_data:
            raw.update(plaid_data)
            logging.info(f"  Plaid: {len(plaid_data)} institutions extracted")
        else:
            logging.warning("  Plaid: no data returned (may not be configured)")
    except Exception as e:
        msg = f"Plaid extraction failed after retry: {e}"
        logging.error(msg)
        errors.append(msg)
```

---

### Task 4: Merge fallback data for missing sources in `run_pipeline()`

**Files:**
- Modify: `weekly_pipeline.py` — after extraction, check which sources are missing and fill from fallback

- [ ] **Step 1: Add fallback merge logic after extraction and before `prepare_builder_data()`**

After the extraction save and before `prepare_builder_data()` is called, add:

```python
        # Merge fallback data for any missing sources
        stale_sources = []

        # Check Fidelity
        if "_fidelity" not in raw:
            fid_fallback, fid_file = load_last_good_source("_fidelity")
            if fid_fallback:
                raw["_fidelity"] = fid_fallback
                stale_sources.append(f"Fidelity (from {fid_file})")
                logging.warning(f"  Using fallback Fidelity data from {fid_file}")
            else:
                logging.warning("  No Fidelity data available (current or historical)")

        # Check Robinhood
        if "robinhood" not in raw:
            rh_fallback, rh_file = load_last_good_source("robinhood")
            if rh_fallback:
                raw["robinhood"] = rh_fallback
                stale_sources.append(f"Robinhood (from {rh_file})")
                logging.warning(f"  Using fallback Robinhood data from {rh_file}")

        # Check Merrill
        if "merrill" not in raw:
            merrill_fallback, merrill_file = load_last_good_source("merrill")
            if merrill_fallback:
                raw["merrill"] = merrill_fallback
                stale_sources.append(f"Merrill (from {merrill_file})")
                logging.warning(f"  Using fallback Merrill data from {merrill_file}")

        if stale_sources:
            logging.warning(f"  Stale data sources: {', '.join(stale_sources)}")
```

---

### Task 5: Add benchmark fallback to cached file

**Files:**
- Modify: `weekly_pipeline.py` — if `fetch_benchmarks()` returns empty, load most recent cached benchmark file

- [ ] **Step 1: Add fallback after benchmark fetch**

After the existing benchmark fetch block, add:

```python
    # Benchmark fallback: use most recent cached file if fetch failed
    if not benchmarks:
        bench_files = sorted(EXTRACT_OUTPUT.glob("benchmarks_*.json"), reverse=True)
        if bench_files:
            try:
                benchmarks = json.loads(bench_files[0].read_text())
                # Filter out non-benchmark keys like _note
                benchmarks = {k: v for k, v in benchmarks.items() if not k.startswith("_") and v is not None}
                if benchmarks:
                    logging.warning(f"  Using cached benchmarks from {bench_files[0].name}")
            except Exception:
                pass
```

---

### Task 6: Fix `daily_snapshot.py` to handle pipeline data formats correctly

**Files:**
- Modify: `daily_snapshot.py`

The snapshot save crashed with the pipeline's raw data format. The issue is that `rh_raw` is passed as the full `raw` dict (containing all providers), not just the Robinhood provider. Also, Fidelity data from `fid_data` (via `prepare_builder_data`) is in a different format than from Playwright.

- [ ] **Step 1: Update `save_snapshot()` to handle pipeline formats**

The function needs to handle:
- `fid_data`: dict like `{"fidelity_Z23889908": {"AAPL": {qty, price, mv, cb, gl}, ...}}` (from prepare_builder_data)
- `rh_raw`: could be full raw dict `{"robinhood": {...}, "merrill": {...}}` or just `{"robinhood": {...}}`
- Holdings may be date-keyed `{"2026-04-04": {tickers...}}` or direct `{tickers...}`

Update `save_snapshot` to defensively handle these formats. Key fix: when iterating `rh_raw`, only process provider keys that contain "robinhood". When reading holdings, handle both date-keyed and direct dict formats. When a holding dict has no `qty` key but has other keys, skip it gracefully.

---

### Task 7: Add stale data note to Dashboard Daily Summary

**Files:**
- Modify: `rebuild_dashboard.py` — when snapshot data includes staleness info, add a note to the prose

- [ ] **Step 1: Update daily snapshot to store staleness metadata**

In `daily_snapshot.py`, add a `stale_sources` field to the snapshot:

```python
    snapshot["stale_sources"] = []  # populated by pipeline when fallback data is used
```

- [ ] **Step 2: In `weekly_pipeline.py`, write stale_sources to snapshot**

After the fallback merge and snapshot save, update the snapshot file with stale source info:

```python
        # Update snapshot with staleness metadata
        if stale_sources:
            try:
                snap_path_str = str(snap_path)
                snap_data = json.loads(Path(snap_path_str).read_text())
                snap_data["stale_sources"] = stale_sources
                Path(snap_path_str).write_text(json.dumps(snap_data, indent=2))
            except Exception:
                pass
```

- [ ] **Step 3: Update Dashboard prose to include staleness warning**

In `rebuild_dashboard.py`, after the main prose line, add:

```python
        stale = snap_today.get('stale_sources', [])
        if stale:
            ws.cell(row=row, column=1,
                    value=f'Note: The following sources used fallback data: {", ".join(stale)}.').font = NOTE_FONT
            row += 1
```
