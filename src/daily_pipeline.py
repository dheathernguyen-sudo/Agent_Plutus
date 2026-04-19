#!/usr/bin/env python3
"""
daily_pipeline.py — Daily Portfolio Data Pipeline
=========================================================
Orchestrates data extraction from multiple brokerage platforms
(SnapTrade: Robinhood + Fidelity, Plaid: 401k + cash accounts),
fetches benchmark returns, and rebuilds the portfolio analysis workbook.

Runs weekdays at 4:00 PM PT via Windows Task Scheduler.
Skips weekends and US market holidays automatically.

Usage:
    python daily_pipeline.py                  # Full pipeline run
    python daily_pipeline.py --dry-run        # Extract data only, no Excel build
    python daily_pipeline.py --benchmarks-only # Only update benchmark returns
    python daily_pipeline.py --skip-extract   # Rebuild Excel from last extraction
"""

import argparse
import datetime
import json
import logging
import os
import re
import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent.resolve()
PIPELINE_DIR = Path(os.environ.get("PLUTUS_PIPELINE_DIR", str(Path.home() / ".portfolio_extract" / "pipeline")))
MANUAL_DATA = PROJECT_DIR / "manual_data.json"
EXTRACT_OUTPUT = PIPELINE_DIR / "extract_output"
LOG_DIR = PROJECT_DIR / "logs"
OUTPUT_XLSX = PROJECT_DIR / "2026_Portfolio_Analysis.xlsx"

# Add pipeline directory and extractors to path so we can import existing modules
sys.path.insert(0, str(PIPELINE_DIR))
sys.path.insert(0, str(PROJECT_DIR / "extractors"))

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


def _extract_with_retry(name, func, *args, max_retries=1, delay=10):
    """Call an extraction function with one retry on failure."""
    import time as _time
    for attempt in range(max_retries + 1):
        try:
            return func(*args)
        except Exception as e:
            if attempt < max_retries:
                logging.warning(f"  {name} attempt {attempt+1} failed: {e}. Retrying in {delay}s...")
                _time.sleep(delay)
            else:
                raise


def is_trading_day(date=None):
    """Return True if the given date is a US stock market trading day."""
    if date is None:
        date = datetime.date.today()
    if date.weekday() >= 5:
        return False
    if date.isoformat() in US_MARKET_HOLIDAYS_2026:
        return False
    return True


def _last_run_date():
    """Detect the date of the most recent successful pipeline run.

    Checks extraction files (weekly_raw_*.json) and snapshot files
    (snapshot_YYYY-MM-DD.json) for the most recent timestamp.
    Returns a datetime.date or None if no prior run found.
    """
    # Check extraction files
    raw_files = sorted(EXTRACT_OUTPUT.glob("weekly_raw_*.json"), reverse=True) if EXTRACT_OUTPUT.exists() else []
    last_extract = None
    if raw_files:
        # Filename format: weekly_raw_YYYYMMDD_HHMMSS.json
        try:
            ts_str = raw_files[0].stem.split("_", 2)[-1]  # "YYYYMMDD_HHMMSS"
            last_extract = datetime.datetime.strptime(ts_str, "%Y%m%d_%H%M%S").date()
        except (ValueError, IndexError):
            pass

    # Check snapshot files
    snap_dir = SCRIPT_DIR / "snapshots"
    snap_files = sorted(snap_dir.glob("snapshot_*.json"), reverse=True) if snap_dir.exists() else []
    last_snap = None
    if snap_files:
        try:
            date_str = snap_files[0].stem.replace("snapshot_", "")
            last_snap = datetime.date.fromisoformat(date_str)
        except ValueError:
            pass

    # Return the most recent of the two
    candidates = [d for d in (last_extract, last_snap) if d is not None]
    return max(candidates) if candidates else None


def _missed_trading_days(since_date):
    """Return a list of trading days between since_date (exclusive) and today (inclusive).

    Used to detect gaps when the pipeline was unable to run (e.g., laptop was off).
    """
    if since_date is None:
        return []
    missed = []
    d = since_date + datetime.timedelta(days=1)
    today = datetime.date.today()
    while d <= today:
        if is_trading_day(d):
            missed.append(d)
        d += datetime.timedelta(days=1)
    return missed


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"pipeline_{ts}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info(f"Log file: {log_file}")
    return log_file


# ---------------------------------------------------------------------------
# Benchmark fetching
# ---------------------------------------------------------------------------
def fetch_benchmarks(year=None):
    """Fetch YTD returns for S&P 500, Dow Jones, and NASDAQ via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        logging.error("yfinance not installed. Run: pip install yfinance")
        return {}

    if year is None:
        year = datetime.date.today().year

    start = f"{year}-01-01"
    end = datetime.date.today().isoformat()

    tickers = {
        "^GSPC": "S&P 500",
        "^DJI": "Dow Jones",
        "^IXIC": "NASDAQ",
    }

    benchmarks = {}
    for symbol, name in tickers.items():
        try:
            logging.info(f"Fetching {name} ({symbol})...")
            data = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
            if data.empty:
                logging.warning(f"No data for {name}")
                continue

            # Handle multi-level columns from yfinance
            close_col = data["Close"]
            if hasattr(close_col, "columns"):
                close_col = close_col.iloc[:, 0]

            first_close = float(close_col.iloc[0])
            last_close = float(close_col.iloc[-1])
            ytd_return = (last_close / first_close) - 1
            benchmarks[name] = round(ytd_return, 6)
            logging.info(f"  {name}: {ytd_return:.2%} (${first_close:.2f} -> ${last_close:.2f})")
        except Exception as e:
            logging.error(f"Failed to fetch {name}: {e}")

    return benchmarks


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------
def extract_all(start_date, end_date):
    """Extract holdings from all connected brokerages."""
    from plaid_extract import load_config, extract_snaptrade, extract_plaid, to_pipeline_format

    config = load_config()
    raw = {}
    errors = []

    # SnapTrade (Robinhood + Fidelity)
    try:
        logging.info("Extracting SnapTrade (Robinhood + Fidelity)...")
        st_data = _extract_with_retry("SnapTrade", extract_snaptrade, config, start_date, end_date)
        if st_data:
            raw.update(st_data)
            logging.info(f"  SnapTrade: {len(st_data)} institutions extracted")
        else:
            logging.warning("  SnapTrade: no data returned")
    except Exception as e:
        msg = f"SnapTrade extraction failed: {e}"
        logging.error(msg)
        errors.append(msg)

    # Plaid (401k — Merrill, Fidelity NetBenefits, etc.)
    try:
        logging.info("Extracting Plaid (401k)...")
        plaid_data = _extract_with_retry("Plaid", extract_plaid, config, start_date, end_date)
        if plaid_data:
            raw.update(plaid_data)
            logging.info(f"  Plaid: {len(plaid_data)} institutions extracted")
        else:
            logging.warning("  Plaid: no data returned (may not be configured)")
    except Exception as e:
        msg = f"Plaid extraction failed: {e}"
        logging.error(msg)
        errors.append(msg)

    # Plaid Cash (Chase, Marcus) — separate API call for cash-only institutions
    try:
        # extract_plaid_cash lives in extractors/plaid_extract.py
        import importlib, importlib.util
        _repo_plaid = PROJECT_DIR / "extractors" / "plaid_extract.py"
        _spec = importlib.util.spec_from_file_location("repo_plaid_extract", str(_repo_plaid))
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        extract_plaid_cash = _mod.extract_plaid_cash

        logging.info("Extracting Plaid cash accounts (Chase, Marcus)...")
        cash_data = _extract_with_retry("Plaid Cash", extract_plaid_cash, config)
        if cash_data:
            raw.update(cash_data)
            for label, cdata in cash_data.items():
                logging.info(f"  {label}: ${cdata.get('total', 0):,.2f}")
        else:
            logging.warning("  Plaid Cash: no data returned")
    except Exception as e:
        msg = f"Plaid cash extraction failed: {e}"
        logging.error(msg)
        errors.append(msg)

    if not raw:
        logging.error("No data extracted from any source.")
        return None, None, errors

    # Save raw extraction
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    EXTRACT_OUTPUT.mkdir(parents=True, exist_ok=True)

    raw_file = EXTRACT_OUTPUT / f"weekly_raw_{ts}.json"
    raw_file.write_text(json.dumps(raw, indent=2, default=str))
    logging.info(f"Raw extraction saved: {raw_file}")

    # Convert to pipeline format
    pipeline = to_pipeline_format(raw, start_date, end_date)
    pipe_file = EXTRACT_OUTPUT / f"weekly_pipeline_{ts}.json"
    pipe_file.write_text(json.dumps(pipeline, indent=2, default=str))
    logging.info(f"Pipeline data saved: {pipe_file}")

    return raw, pipeline, errors


def load_latest_extraction():
    """Load the most recent extraction files."""
    raw_files = sorted(EXTRACT_OUTPUT.glob("weekly_raw_*.json"), reverse=True)
    pipe_files = sorted(EXTRACT_OUTPUT.glob("weekly_pipeline_*.json"), reverse=True)

    if not raw_files:
        # Fall back to any raw extraction
        raw_files = sorted(EXTRACT_OUTPUT.glob("extract_raw_*.json"), reverse=True)
    if not pipe_files:
        pipe_files = sorted(EXTRACT_OUTPUT.glob("*pipeline_*.json"), reverse=True)

    raw = json.loads(raw_files[0].read_text()) if raw_files else None
    pipeline = json.loads(pipe_files[0].read_text()) if pipe_files else None

    if raw_files:
        logging.info(f"Loaded raw: {raw_files[0].name}")
    if pipe_files:
        logging.info(f"Loaded pipeline: {pipe_files[0].name}")

    return raw, pipeline


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


# ---------------------------------------------------------------------------
# Build workbook
# ---------------------------------------------------------------------------
def build_xlsx(fid_pipeline_data, rh_raw_data, benchmarks, k401_raw=None):
    """Build the portfolio analysis Excel workbook (legacy pipeline builder)."""
    from build_portfolio import build_workbook

    logging.info("Building Excel workbook...")
    output = build_workbook(
        output_path=str(OUTPUT_XLSX),
        manual_json_path=str(MANUAL_DATA),
        benchmarks=benchmarks,
        fid_data_dict=fid_pipeline_data,
        rh_raw_dict=rh_raw_data,
        merrill_raw=k401_raw,
    )
    logging.info(f"Workbook saved: {output}")
    return output


def _run_rebuild_scripts():
    """Rebuild the workbook using the canonical rebuild scripts.

    Each script opens the existing xlsx, replaces its tab, and saves.
    Order matters: account tabs first, then Dashboard (which references them).
    Individual script failures are logged but do not block other scripts.
    """
    import subprocess
    python = sys.executable

    scripts = [
        "rebuild_brok_tab.py",
        "rebuild_roth_tab.py",
        "rebuild_hsa_tab.py",
        "rebuild_rh_tab.py",
        "rebuild_cash_tab.py",
        "rebuild_dashboard.py",
    ]

    ok = 0
    failed = 0
    for script in scripts:
        script_path = SCRIPT_DIR / script
        if not script_path.exists():
            logging.warning(f"  Rebuild script not found: {script}")
            failed += 1
            continue
        logging.info(f"  Running {script}...")
        try:
            result = subprocess.run(
                [python, str(script_path)],
                cwd=str(PROJECT_DIR),
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                logging.info(f"    {script}: OK")
                ok += 1
            else:
                # rebuild_dashboard.py exits 1 due to Unicode print but still saves OK
                if "rebuilt successfully" in (result.stdout or ""):
                    logging.info(f"    {script}: OK (non-fatal print error)")
                    ok += 1
                else:
                    logging.warning(f"    {script}: exit {result.returncode}")
                    if result.stderr:
                        logging.warning(f"    stderr: {result.stderr[:200]}")
                    failed += 1
        except subprocess.TimeoutExpired:
            logging.error(f"    {script}: timed out after 60s")
            failed += 1
        except Exception as e:
            logging.error(f"    {script}: {e}")
            failed += 1

    logging.info(f"  Rebuild scripts: {ok} succeeded, {failed} failed out of {len(scripts)}")


def _is_401k_label(label):
    """Check if a raw extraction label represents a 401(k) provider."""
    lower = label.lower()
    return any(s in lower for s in ("merrill", "401k", "401(k)", "netbenefits"))


def prepare_builder_data(raw, pipeline):
    """Convert raw/pipeline extraction data into the format build_portfolio expects.

    build_portfolio.py expects:
      - fid_data: dict keyed by account (e.g. "fidelity_XXXXXXXXX") with holdings
      - rh_raw: dict with "robinhood" key containing accounts, holdings, etc.
      - k401_raw: dict with 401(k) raw extraction data (any provider)
    """
    fid_data = {}
    rh_raw = None
    k401_raw = None

    # Process raw data for all providers
    if raw:
        for label, data in raw.items():
            if label.startswith("_"):
                continue
            if "robinhood" in label.lower():
                rh_raw = {label: data}
            elif _is_401k_label(label):
                k401_raw = data
            elif "fidelity" in label.lower():
                # Fidelity from SnapTrade (brokerage accounts, not 401k)
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

    # Fallback: check pipeline data for Fidelity if not found
    if not fid_data and pipeline:
        today = datetime.date.today().isoformat()
        for label, acct in pipeline.items():
            if label.startswith("_") or label == "benchmarks":
                continue
            if label.startswith("fidelity"):
                holdings = acct.get("holdings", {})
                date_key = sorted(holdings.keys())[-1] if holdings else today
                fid_data[label] = holdings.get(date_key, {})

    return fid_data, rh_raw, k401_raw


# ---------------------------------------------------------------------------
# Angel investment valuation check
# ---------------------------------------------------------------------------
def _parse_valuation(text, company_name=None):
    """Extract a company valuation from text, distinguishing it from fundraise amounts.

    Prioritizes valuation-context matches (e.g. 'valued at $X', 'valuation of $X',
    '$XB valuation') over bare dollar amounts to avoid confusing the amount raised
    with the company's valuation.

    If company_name is provided, only considers matches within 200 characters of
    the company name mention — prevents picking up valuations of other companies
    mentioned in the same article.
    """
    def _to_num(match_str, multiplier):
        return int(float(match_str.replace(",", "")) * multiplier)

    def _company_distance(match_pos, text, company_name):
        """Return min distance (chars) between a match position and any company name mention.
        Returns float('inf') if company_name not found."""
        if not company_name:
            return 0
        text_lower = text.lower()
        name_lower = company_name.lower()
        min_dist = float('inf')
        idx = 0
        while True:
            pos = text_lower.find(name_lower, idx)
            if pos == -1:
                break
            dist = abs(match_pos - pos)
            min_dist = min(min_dist, dist)
            idx = pos + 1
        return min_dist

    def _find_best_match(patterns, text, company_name, max_distance=150):
        """Find the valuation match closest to the company name.
        Only considers matches within max_distance characters.
        Among qualifying matches, returns the one closest to the company name."""
        best_val = None
        best_dist = float('inf')
        for pat, multiplier in patterns:
            for m in re.finditer(pat, text):
                dist = _company_distance(m.start(), text, company_name)
                if dist <= max_distance and dist < best_dist:
                    best_val = _to_num(m.group(1), multiplier)
                    best_dist = dist
        return best_val

    # Priority 1: Patterns with explicit valuation context, closest to company name
    valuation_patterns = [
        (r'(?:valued?\s+at|valuation\s*(?:of|to|:)?)\s*\$\s*([\d,.]+)\s*[Bb]illion', 1e9),
        (r'(?:valued?\s+at|valuation\s*(?:of|to|:)?)\s*\$\s*([\d,.]+)\s*[Bb]', 1e9),
        (r'(?:valued?\s+at|valuation\s*(?:of|to|:)?)\s*\$\s*([\d,.]+)\s*[Tt]rillion', 1e12),
        (r'(?:valued?\s+at|valuation\s*(?:of|to|:)?)\s*\$\s*([\d,.]+)\s*[Mm]illion', 1e6),
        (r'(?:valued?\s+at|valuation\s*(?:of|to|:)?)\s*\$\s*([\d,.]+)\s*[Mm]', 1e6),
        (r'\$\s*([\d,.]+)\s*[Bb](?:illion)?\s*[Vv]aluation', 1e9),
        (r'\$\s*([\d,.]+)\s*[Mm](?:illion)?\s*[Vv]aluation', 1e6),
        (r'at\s+a\s+\$\s*([\d,.]+)\s*[Bb]', 1e9),
        (r'at\s+a\s+\$\s*([\d,.]+)\s*[Mm]', 1e6),
    ]
    val = _find_best_match(valuation_patterns, text, company_name)
    if val:
        return val

    # Priority 2: Fall back to any dollar amount closest to company name
    fallback_patterns = [
        (r'\$\s*([\d,.]+)\s*[Bb]illion', 1e9),
        (r'\$\s*([\d,.]+)\s*[Bb]', 1e9),
        (r'\$\s*([\d,.]+)\s*[Mm]illion', 1e6),
        (r'\$\s*([\d,.]+)\s*[Mm]', 1e6),
    ]
    return _find_best_match(fallback_patterns, text, company_name)


def check_angel_valuations(manual_data_path, interactive=True):
    """Search for recent funding/liquidity events for angel investments.

    Returns a list of proposed updates (company, old_val, new_val, source, snippet).
    If interactive=True, prompts the user to approve each update and writes approved
    changes to manual_data.json. If interactive=False, only detects and reports
    changes without writing anything.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        logging.warning("duckduckgo-search not installed. Skipping angel valuation check.")
        return []

    data = json.loads(Path(manual_data_path).read_text())
    angels = data.get("angel_data", [])
    if not angels:
        logging.info("No angel investments to check.")
        return []

    logging.info("=" * 60)
    logging.info("Checking angel investment valuations...")
    logging.info("=" * 60)

    proposed_updates = []

    with DDGS() as ddgs:
        for inv in angels:
            company = inv["company"]
            current_val = inv["pm_latest"]
            current_source = inv.get("source", "")

            year = datetime.date.today().year
            query = f"{company} funding round valuation {year}"
            logging.info(f"  Searching: {company} (current: ${current_val/1e9:.2f}B — {current_source})")

            try:
                # Search recent results first (past month), then fall back to past year
                results = list(ddgs.text(query, timelimit='m', max_results=5))
                if not results:
                    results = list(ddgs.text(query, timelimit='y', max_results=5))
                if not results:
                    results = list(ddgs.text(query, max_results=5))
            except Exception as e:
                logging.warning(f"  Search failed for {company}: {e}")
                continue

            # Look through results for valuation mentions.
            # Only consider results that mention the company name to avoid
            # false positives from unrelated companies in the same snippet.
            found_val = None
            found_source = None
            found_snippet = None
            found_url = None

            company_lower = company.lower()
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                combined = (title + " " + body).lower()

                # Skip results that don't mention the company name
                if company_lower not in combined:
                    continue

                # Parse title first (usually has "at $XB Valuation"),
                # then body, then combined. Proximity filter ensures
                # we only pick up valuations near THIS company's name.
                for text in [title, body, title + " " + body]:
                    val = _parse_valuation(text, company_name=company)
                    if val and val != current_val and val > inv["pm_invest"]:
                        if found_val is None or val > found_val:
                            found_val = val
                            found_source = title[:80]
                            found_snippet = body[:200]
                            found_url = r.get("href", "")

            if found_val and found_val != current_val:
                change_pct = (found_val - current_val) / current_val * 100
                direction = "UP" if change_pct > 0 else "DOWN"

                logging.info(f"  >>> {company}: potential valuation change detected!")
                logging.info(f"      Current:  ${current_val/1e9:.2f}B ({current_source})")
                logging.info(f"      Found:    ${found_val/1e9:.2f}B ({direction} {abs(change_pct):.1f}%)")
                logging.info(f"      Source:   {found_source}")
                logging.info(f"      Snippet:  {found_snippet}")
                if found_url:
                    logging.info(f"      URL:      {found_url}")

                if interactive:
                    print(f"\n  {'='*60}")
                    print(f"  VALUATION UPDATE: {company}")
                    print(f"  {'='*60}")
                    print(f"  Current: ${current_val/1e9:.2f}B ({current_source})")
                    print(f"  New:     ${found_val/1e9:.2f}B ({direction} {abs(change_pct):.1f}%)")
                    print(f"  Source:  {found_source}")
                    print(f"  Detail:  {found_snippet}")
                    if found_url:
                        print(f"  URL:     {found_url}")
                    approval = input(f"\n  Apply this update? [y/N]: ").strip().lower()
                    if approval in ("y", "yes"):
                        proposed_updates.append({
                            "company": company,
                            "old_val": current_val,
                            "new_val": found_val,
                            "source": found_source,
                        })
                        logging.info(f"  {company}: update APPROVED")
                    else:
                        logging.info(f"  {company}: update SKIPPED")
                else:
                    proposed_updates.append({
                        "company": company,
                        "old_val": current_val,
                        "new_val": found_val,
                        "source": found_source,
                    })
            else:
                logging.info(f"  {company}: no valuation change found")

    # Apply approved updates (only in interactive mode)
    if proposed_updates and interactive:
        for update in proposed_updates:
            for inv in angels:
                if inv["company"] == update["company"]:
                    inv["pm_latest"] = update["new_val"]
                    inv["source"] = update["source"]
                    break

        # Update manual_data.json (legacy)
        data["angel_data"] = angels
        data["_notes"]["last_updated"] = datetime.date.today().isoformat()
        Path(manual_data_path).write_text(json.dumps(data, indent=2))
        logging.info(f"  Updated {len(proposed_updates)} angel valuation(s) in {manual_data_path}")

        # Also update data/angel.json (new builder's source of truth)
        angel_json = Path(manual_data_path).parent / "data" / "angel.json"
        if angel_json.exists():
            try:
                angel_data = json.loads(angel_json.read_text())
                for update in proposed_updates:
                    for inv in angel_data.get("investments", []):
                        if inv["company"] == update["company"]:
                            inv["pm_latest"] = update["new_val"]
                            inv["source"] = update["source"]
                            break
                angel_json.write_text(json.dumps(angel_data, indent=2))
                logging.info(f"  Also updated data/angel.json")
            except Exception as e:
                logging.warning(f"  Could not update data/angel.json: {e}")

    return proposed_updates


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline(args):
    log_file = setup_logging()

    # --- Catch-up detection ---
    last_run = _last_run_date()
    missed = _missed_trading_days(last_run) if last_run else []
    today = datetime.date.today()
    today_is_trading = is_trading_day(today)

    if missed and len(missed) > 1:
        # More than just today was missed
        missed_not_today = [d for d in missed if d != today]
        if missed_not_today:
            logging.info(f"Catch-up: {len(missed_not_today)} missed trading day(s) detected "
                         f"since last run on {last_run.isoformat()}: "
                         f"{', '.join(d.isoformat() for d in missed_not_today)}")
            logging.info("Catch-up: pipeline will run with fresh extraction to cover the gap.")

    if not today_is_trading and not missed:
        logging.info("Not a trading day (weekend or holiday) and no missed days. Skipping.")
        return 0

    if not today_is_trading and missed:
        # Laptop was off during trading days, now on during weekend/holiday.
        # Run with --skip-extract to rebuild from the most recent cached data.
        logging.info(f"Not a trading day, but {len(missed)} missed day(s) detected. "
                     f"Rebuilding workbook from latest cached extraction.")
        args.skip_extract = True

    logging.info("=" * 60)
    logging.info("Agent Plutus — Daily Pipeline Starting")
    logging.info(f"Date: {datetime.datetime.now().isoformat()}")
    if last_run:
        logging.info(f"Last successful run: {last_run.isoformat()}")
    logging.info("=" * 60)

    year = datetime.date.today().year
    start_date = datetime.date(year, 1, 1)
    end_date = datetime.date.today()
    errors = []

    # Step 1: Extract data (unless skipped)
    raw, pipeline = None, None
    if args.skip_extract:
        logging.info("Skipping extraction, loading latest data...")
        raw, pipeline = load_latest_extraction()
        if not raw and not pipeline:
            logging.error("No existing extraction data found.")
            return 1
    elif not args.benchmarks_only:
        raw, pipeline, extract_errors = extract_all(start_date, end_date)
        errors.extend(extract_errors)
        if not raw:
            logging.warning("Extraction failed. Trying to load latest data...")
            raw, pipeline = load_latest_extraction()

    # Step 2: Fetch benchmarks
    benchmarks = {}
    try:
        benchmarks = fetch_benchmarks(year)
        if benchmarks:
            # Save benchmarks for reference
            bench_file = EXTRACT_OUTPUT / f"benchmarks_{end_date.isoformat()}.json"
            bench_file.write_text(json.dumps(benchmarks, indent=2))
            logging.info(f"Benchmarks saved: {bench_file}")
    except Exception as e:
        logging.error(f"Benchmark fetch failed: {e}")
        errors.append(f"Benchmarks: {e}")

    # Benchmark fallback: use most recent cached file if fetch failed
    if not benchmarks:
        bench_files = sorted(EXTRACT_OUTPUT.glob("benchmarks_*.json"), reverse=True)
        if bench_files:
            try:
                cached = json.loads(bench_files[0].read_text())
                benchmarks = {k: v for k, v in cached.items() if not k.startswith("_") and v is not None}
                if benchmarks:
                    logging.warning(f"  Using cached benchmarks from {bench_files[0].name}")
            except Exception:
                pass

    if args.benchmarks_only:
        logging.info("Benchmarks-only mode. Done.")
        return 0

    # Step 3: Angel valuation check — interactive only, not part of automated daily run
    # Run manually: python daily_pipeline.py --check-angels
    angel_updates = []
    if getattr(args, 'check_angels', False):
        try:
            logging.info("Running angel valuation check (interactive)...")
            angel_updates = check_angel_valuations(
                str(MANUAL_DATA), interactive=True
            )
            if angel_updates:
                logging.info(f"Applied {len(angel_updates)} angel valuation update(s)")
        except Exception as e:
            logging.error(f"Angel valuation check failed: {e}")
            errors.append(f"Angel check: {e}")

    # Step 4: Build Excel workbook
    if args.dry_run:
        logging.info("Dry run mode - skipping Excel build.")
        logging.info(f"Raw data sources: {list(raw.keys()) if raw else 'None'}")
        logging.info(f"Pipeline accounts: {list(pipeline.keys()) if pipeline else 'None'}")
        logging.info(f"Benchmarks: {benchmarks}")
        logging.info(f"Angel updates: {len(angel_updates)}")
        return 0

    if raw or pipeline:
        try:
            # Merge fallback data for any missing sources
            stale_sources = []

            if "fidelity" not in raw:
                fid_fallback, fid_file = load_last_good_source("fidelity")
                if fid_fallback:
                    raw["fidelity"] = fid_fallback
                    stale_sources.append(f"Fidelity (from {fid_file})")
                    logging.warning(f"  Using fallback Fidelity data from {fid_file}")
                else:
                    logging.warning("  No Fidelity data available (current or historical)")

            if "robinhood" not in raw:
                rh_fallback, rh_file = load_last_good_source("robinhood")
                if rh_fallback:
                    raw["robinhood"] = rh_fallback
                    stale_sources.append(f"Robinhood (from {rh_file})")
                    logging.warning(f"  Using fallback Robinhood data from {rh_file}")

            # 401(k) fallback — check for any known 401k provider key
            if not any(_is_401k_label(k) for k in raw):
                for src in ("merrill", "fidelity_netbenefits"):
                    fb, ff = load_last_good_source(src)
                    if fb:
                        raw[src] = fb
                        stale_sources.append(f"401k/{src} (from {ff})")
                        logging.warning(f"  Using fallback 401k data from {ff}")
                        break

            if stale_sources:
                logging.warning(f"  Stale data sources: {', '.join(stale_sources)}")

            fid_data, rh_raw, k401_raw = prepare_builder_data(raw, pipeline)

            # Save daily snapshot for day-over-day comparison
            try:
                from daily_snapshot import save_snapshot
                snap_path = save_snapshot(
                    fid_data=fid_data,
                    rh_raw=rh_raw,
                    k401_raw=k401_raw,
                )
                logging.info(f"Daily snapshot saved: {snap_path}")
            except Exception as e:
                logging.warning(f"Snapshot save failed (non-fatal): {e}")

            # Build workbook using new data-driven builder
            try:
                from portfolio_model import build_model
                from build_workbook import build as build_new
                # Extract cash data from raw (already fetched during extraction)
                cash_data = {}
                for ck in ("chase", "marcus"):
                    if ck in raw and isinstance(raw[ck], dict) and "accounts" in raw[ck]:
                        cash_data[ck] = raw[ck]

                # Fetch live Plaid cash if not in raw (e.g. --skip-extract)
                if not cash_data:
                    try:
                        import importlib.util as _ilu
                        _rp = PROJECT_DIR / "extractors" / "plaid_extract.py"
                        _sp = _ilu.spec_from_file_location("repo_plaid", str(_rp))
                        _md = _ilu.module_from_spec(_sp)
                        _sp.loader.exec_module(_md)
                        cash_data = _md.extract_plaid_cash(_md.load_config())
                    except Exception:
                        pass

                model = build_model(
                    data_dir=str(PROJECT_DIR / "data"),
                    live_extraction=fid_data,
                    raw_extraction=raw,
                    benchmarks=benchmarks,
                    cash_data=cash_data,
                )
                build_new(model, str(OUTPUT_XLSX))
                logging.info("Workbook built (new builder)")
            except Exception as e:
                logging.warning(f"New builder failed ({e}), falling back to rebuild scripts")
                import traceback as _tb
                logging.warning(_tb.format_exc())
                # Fallback: try old pipeline builder + rebuild scripts
                try:
                    build_xlsx(fid_data, rh_raw, benchmarks, k401_raw=k401_raw)
                except Exception:
                    pass
                _run_rebuild_scripts()

            # Note: redacted version is generated separately via redact_for_screenshot.py
        except Exception as e:
            logging.error(f"Workbook build failed: {e}")
            logging.error(traceback.format_exc())
            errors.append(f"Build: {e}")
    else:
        logging.error("No data available to build workbook.")
        errors.append("No extraction data available")

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

    # Summary
    logging.info("=" * 60)
    logging.info("Pipeline Complete")
    if errors:
        logging.warning(f"Errors ({len(errors)}):")
        for e in errors:
            logging.warning(f"  - {e}")
        logging.info(f"Exit code: 2 (partial success)")
        return 2
    else:
        logging.info("All steps completed successfully.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Daily Portfolio Data Pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Extract data and fetch benchmarks but don't build Excel")
    parser.add_argument("--skip-extract", action="store_true",
                        help="Skip extraction, rebuild from latest saved data")
    parser.add_argument("--benchmarks-only", action="store_true",
                        help="Only fetch and save benchmark returns")
    parser.add_argument("--check-angels", action="store_true",
                        help="Run interactive angel investment valuation check")
    args = parser.parse_args()

    try:
        exit_code = run_pipeline(args)
    except Exception as e:
        logging.error(f"Unhandled error: {e}")
        logging.error(traceback.format_exc())
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
