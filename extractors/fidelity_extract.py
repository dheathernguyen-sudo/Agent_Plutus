#!/usr/bin/env python3
"""
fidelity_extract.py — Fidelity data extraction via fidelity-api (Playwright)
=============================================================================
Uses browser automation to pull holdings, balances, and account info from
Fidelity. Supports SMS 2FA (manual code entry on first run, then cached).

Usage:
    python fidelity_extract.py                # Extract all accounts
    python fidelity_extract.py --headless     # Run without visible browser
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

CONFIG_DIR = Path.home() / ".portfolio_extract"
CONFIG_FILE = CONFIG_DIR / "config.json"
OUTPUT_DIR = Path(__file__).parent.resolve()

# Account number -> pipeline label mapping
# Populate with your own Fidelity account numbers, e.g.:
#   "XXXXXXXXX": "fidelity_brokerage",
#   "XXXXXXXXX": "fidelity_roth_ira",
# Or load from ~/.portfolio_extract/config.json under key "fidelity_accounts".
ACCOUNT_LABELS = {}
if CONFIG_FILE.exists():
    import json as _json_boot
    _cfg = _json_boot.loads(CONFIG_FILE.read_text())
    ACCOUNT_LABELS = _cfg.get("fidelity_accounts", {})


def _scrape_positions(page):
    """Scrape positions directly from Fidelity's portfolio page."""
    import re

    # Navigate to portfolio POSITIONS page (shows per-stock holdings)
    page.goto("https://digital.fidelity.com/ftgw/digital/portfolio/positions", timeout=30000,
              wait_until="domcontentloaded")
    import time
    time.sleep(8)  # Let JS render positions data

    # Try to get data from the page's JavaScript/API
    # Fidelity loads position data via XHR — try to intercept it
    try:
        # Check if there's a portfolio summary API response in the page
        data = page.evaluate("""() => {
            // Try common Fidelity data stores
            if (window.__NEXT_DATA__) return JSON.stringify(window.__NEXT_DATA__);
            if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
            return null;
        }""")
        if data:
            print(f"  Found page data store ({len(data)} chars)")
    except Exception:
        pass

    # Save page text for debugging regardless
    try:
        text = page.inner_text("main") if page.locator("main").count() > 0 else page.inner_text("body")
        debug_file = Path(__file__).parent / "fidelity_debug_page.txt"
        debug_file.write_text(text, encoding="utf-8")
        print(f"  Debug page text saved ({len(text)} chars)")
    except Exception as e:
        text = ""
        print(f"  Could not save debug text: {e}")

    # Try to extract data via Fidelity's internal CSV download
    # Fidelity has a "Download" button on the positions page
    results = {}
    try:
        # Method 1: Use AG Grid — extract from both pinned (symbol) and body columns
        grid_data = page.evaluate("""() => {
            const rows = document.querySelectorAll('.ag-row');
            const data = [];
            rows.forEach(row => {
                const rowIdx = row.getAttribute('row-index');
                const rowId = row.getAttribute('row-id');
                const cells = row.querySelectorAll('.ag-cell');
                const rowData = {_rowIdx: rowIdx, _rowId: rowId || ''};
                cells.forEach(cell => {
                    const colId = cell.getAttribute('col-id');
                    if (colId) rowData[colId] = cell.innerText.trim();
                });
                // Check for full-width rows (account headers, totals)
                const fullWidth = row.querySelector('.ag-full-width-row, [class*="full-width"]');
                if (fullWidth) rowData._fullWidth = fullWidth.innerText.trim();
                if (Object.keys(rowData).length > 2) data.push(rowData);
            });
            return JSON.stringify(data);
        }""")

        if grid_data:
            import json as _json
            raw_rows = _json.loads(grid_data)
            print(f"  AG Grid: {len(raw_rows)} raw rows extracted")
            for row in raw_rows[:5]:
                print(f"    {row}")

            # Merge pinned (sym) and body (values) rows by _rowIdx
            by_idx = {}
            for row in raw_rows:
                idx = row.get("_rowIdx", "")
                if idx not in by_idx:
                    by_idx[idx] = {}
                by_idx[idx].update(row)

            rows = list(by_idx.values())
            print(f"  Merged to {len(rows)} rows")
            for row in rows[:5]:
                keys = [k for k in row.keys() if not k.startswith("_")]
                print(f"    keys={keys} sym={row.get('sym','')[:40]}")

            # Parse merged AG Grid data
            results = _parse_ag_grid(rows)

    except Exception as e:
        print(f"  AG Grid extraction error: {e}")

    # Method 2: Parse from page text
    if not results and text:
        results = _parse_positions_text(text)

    # Method 3: Try the Download CSV approach
    if not results:
        try:
            dl_btn = page.locator("button:has-text('Download'), [aria-label*='download'], [aria-label*='Download']")
            if dl_btn.first.is_visible(timeout=3000):
                print("  Found Download button — attempting CSV export...")
        except Exception:
            pass

    return results if results else None


def _parse_ag_grid(rows):
    """Parse AG Grid row data into pipeline format.
    Fidelity AG Grid columns: symbol (pinned), lstPrStk, todGLStk, totGLStk,
    curVal, actPer, qty, cstBasStk, fifTwo
    """
    import re
    results = {}
    current_account = None

    def parse_dollar(val):
        if not val: return 0
        val = str(val).split("\n")[0]  # Take first line only
        val = val.replace("−", "-").replace("–", "-").replace(",", "")
        m = re.search(r'[\$\+\-]?([\d]+\.?\d*)', val)
        return float(m.group(1)) if m else 0

    for row in rows:
        sym_text = row.get("sym", row.get("symbol", ""))
        if not sym_text:
            continue

        # Account header detection: "Account:\xa0\nIndividual - TODXXXXXXXXX..."
        if "Account:" in sym_text or sym_text.startswith("Account"):
            matched = False
            for acct_num, label in ACCOUNT_LABELS.items():
                if acct_num in sym_text:
                    current_account = label
                    if label not in results:
                        results[label] = {"account_id": acct_num, "holdings": {}, "cash": 0, "balance": 0}
                    matched = True
                    break
            if not matched:
                # Unknown account — don't let it inherit from previous
                current_account = None
            continue

        # First line of symbol cell is the ticker
        lines = [l.strip() for l in sym_text.split("\n") if l.strip()]
        ticker = lines[0] if lines else ""

        if not ticker or ticker in ("Pending activity", "Account total", "Grand total"):
            continue

        if not current_account:
            continue

        # Cash row
        if ticker == "Cash":
            cash_val = parse_dollar(row.get("curVal", ""))
            if cash_val:
                results[current_account]["cash"] = round(cash_val, 2)
            continue

        # Skip non-ticker rows
        if len(ticker) > 10 or " " in ticker or ticker.startswith("Not "):
            continue

        # Get description — skip "Not Priced Today" lines
        name = ""
        for line in lines[1:]:
            if line and "Not Priced" not in line and "HELD IN" not in line:
                name = line
                break

        price = parse_dollar(row.get("lstPrStk", ""))
        mv = parse_dollar(row.get("curVal", ""))
        qty = parse_dollar(row.get("qty", ""))
        cb = parse_dollar(row.get("cstBasStk", ""))
        gl = parse_dollar(row.get("totGLStk", ""))

        # Debug first few positions
        if len([r for r in results.values() for _ in r.get("holdings", {})]) < 3:
            print(f"    DEBUG {ticker}: price={row.get('lstPrStk','')!r} mv={row.get('curVal','')!r} qty={row.get('qty','')!r} cb={row.get('cstBasStk','')!r}")

        # Determine gain/loss sign
        gl_text = str(row.get("totGLStk", ""))
        if gl_text.lstrip().startswith("-") or "−" in gl_text or "–" in gl_text:
            gl = -abs(gl)

        if mv > 0 or qty > 0:
            results[current_account]["holdings"][ticker] = {
                "qty": round(qty, 6), "price": round(price, 4),
                "mv": round(mv, 2), "cb": round(cb, 2), "gl": round(gl, 2),
                "name": name,
            }

    if results:
        for label, data in results.items():
            total = sum(h["mv"] for h in data["holdings"].values()) + data["cash"]
            data["balance"] = round(total, 2)

    return results if any(r["holdings"] for r in results.values()) else None


def _parse_positions_text(text):
    """Parse account positions from raw page text."""
    import re

    results = {}
    current_account = None
    current_acct_num = None
    lines = [l.strip() for l in text.split("\n")]

    # Find account sections and their tickers
    i = 0
    while i < len(lines):
        line = lines[i]

        # Match account headers like "Individual - TODXXXXXXXXX" or "ROTH IRAXXXXXXXXX"
        acct_match = re.search(r'([A-Z]?\d{6,})', line)
        if acct_match and ("Account:" in lines[i-1] if i > 0 else False):
            acct_num = acct_match.group(1)
            label = ACCOUNT_LABELS.get(acct_num, f"fidelity_{acct_num}")
            current_account = label
            current_acct_num = acct_num
            if label not in results:
                results[label] = {
                    "account_id": acct_num,
                    "holdings": {},
                    "cash": 0,
                    "balance": 0,
                }
            i += 1
            continue

        # Also match inline format: "Account:\nIndividual - TODXXXXXXXXX"
        if "Account:" in line or line.startswith("Account:"):
            # Next non-empty line may have the account number
            j = i + 1
            while j < len(lines) and not lines[j]:
                j += 1
            if j < len(lines):
                am = re.search(r'([A-Z]?\d{6,})', lines[j])
                if am:
                    acct_num = am.group(1)
                    label = ACCOUNT_LABELS.get(acct_num, f"fidelity_{acct_num}")
                    current_account = label
                    current_acct_num = acct_num
                    if label not in results:
                        results[label] = {
                            "account_id": acct_num,
                            "holdings": {},
                            "cash": 0,
                            "balance": 0,
                        }

        i += 1

    # Now get balance data from the summary section at the top
    for i, line in enumerate(lines):
        for acct_num, label in ACCOUNT_LABELS.items():
            if acct_num in line and label in results:
                # Look for balance in nearby lines
                for j in range(i, min(i+5, len(lines))):
                    bal_match = re.search(r'\$([0-9,]+\.\d{2})', lines[j])
                    if bal_match and "balance" in lines[j-1].lower() if j > 0 else False:
                        results[label]["balance"] = float(bal_match.group(1).replace(",", ""))
                        break

    if results:
        print(f"  Found {len(results)} accounts from text: {list(results.keys())}")

    return results


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def extract_fidelity(headless=True):
    """Extract all Fidelity account data via browser automation."""
    from fidelity.fidelity import FidelityAutomation

    config = load_config()
    fid = config.get("fidelity", {})
    username = fid.get("username")

    # Try OS keyring first, fall back to config.json
    password = None
    if username:
        try:
            import keyring
            password = keyring.get_password("agent-plutus-fidelity", username)
        except ImportError:
            pass
    if not password:
        password = fid.get("password")

    if not username or not password:
        print("  ERROR: Fidelity credentials not set.")
        print("  Run: python extractors/fidelity_ofx.py --setup")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Fidelity Extraction (Playwright)")
    print(f"  User: {username}")
    print(f"  Mode: {'headless' if headless else 'visible browser'}")
    print(f"{'='*60}")

    # Use save_state to persist cookies/session across runs
    state_path = str(CONFIG_DIR / "fidelity_state")
    fidelity = FidelityAutomation(headless=headless, save_state=True, profile_path=state_path)

    try:
        # Login
        print("\n  Logging in...")
        import time

        # First try: check if saved session is still valid by navigating directly
        page = fidelity.page
        page.goto("https://digital.fidelity.com/ftgw/digital/portfolio/summary",
                  timeout=30000, wait_until="domcontentloaded")
        time.sleep(5)

        if "summary" in page.title().lower() or "portfolio" in page.title().lower():
            print("  Logged in via saved session!")
            logged_in = True
        else:
            # Need fresh login
            print("  Session expired. Logging in with credentials...")
            page.goto("https://digital.fidelity.com/prgw/digital/login/full-page",
                      timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)

            page.get_by_label("Username", exact=True).fill(username)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Log in").click()
            print("  Credentials submitted.")

            # Wait for 2FA page, then try to click "Send notification"
            time.sleep(5)
            try:
                send_btn = page.locator("button:has-text('Send notification'), [role='button']:has-text('Send notification')")
                if send_btn.first.is_visible(timeout=8000):
                    send_btn.first.click()
                    print("  Clicked 'Send notification'. Approve on your Fidelity mobile app.")
                else:
                    print("  2FA page loaded (may have auto-sent). Approve on your phone.")
            except Exception:
                print("  Waiting for 2FA approval...")

        # Wait for redirect to summary page (up to 120 seconds for push approval)
        import time
        logged_in = False
        for i in range(120):
            time.sleep(1)
            try:
                url = page.url
                if "summary" in url or "portfolio" in url or "digital.fidelity.com/ftgw" in url:
                    logged_in = True
                    print(f"  Login confirmed! (after {i+1}s)")
                    break
                # Log page content changes for debugging
                if i == 10 or i == 30 or i == 60:
                    title = page.title()
                    # Check for any visible buttons/links that might need clicking
                    buttons = page.locator("button:visible").all_text_contents()
                    links = page.locator("a:visible").all_text_contents()
                    print(f"  [{i}s] URL: {url}")
                    print(f"  [{i}s] Title: {title}")
                    if buttons:
                        print(f"  [{i}s] Buttons: {buttons[:5]}")
                    if links:
                        print(f"  [{i}s] Links: {[l for l in links[:5] if l.strip()]}")
            except Exception as e:
                if i % 30 == 29:
                    print(f"  [{i}s] Error checking page: {e}")
            if i % 15 == 14:
                print(f"  Still waiting for approval... ({i+1}s)")

        if not logged_in:
            try:
                print(f"  Current URL: {page.url}")
            except Exception:
                pass
            print("  Login failed — approval may have timed out.")
            return None

        # Save session state for future runs
        try:
            fidelity.save_storage_state()
            print("  Session saved for future runs.")
        except Exception:
            pass

        # Navigate to portfolio summary if not already there
        if "summary" not in page.url:
            page.goto("https://digital.fidelity.com/ftgw/digital/portfolio/summary",
                      timeout=30000, wait_until="domcontentloaded")
            time.sleep(5)

        fidelity.page.set_default_timeout(30000)

        # Get accounts
        print("\n  Fetching accounts...")
        try:
            fidelity.get_list_of_accounts(set_flag=True)
        except Exception as e:
            print(f"  get_list_of_accounts error: {e}")

        # Get summary holdings
        print("  Fetching holdings summary...")
        summary = None
        try:
            summary = fidelity.summary_holdings()
        except Exception as e:
            print(f"  summary_holdings error: {e}")

        # If library method failed, scrape positions page directly
        if not summary:
            print("  Library method returned no data. Scraping positions page...")
            scraped = _scrape_positions(page)
            if scraped:
                # Scraped data is already in final format — return directly
                for label, data in scraped.items():
                    total_mv = sum(h["mv"] for h in data["holdings"].values())
                    print(f"\n  {label} ({data['account_id']}):")
                    print(f"    Holdings: {len(data['holdings'])} positions, ${total_mv:,.2f}")
                    print(f"    Cash: ${data['cash']:,.2f}")
                    print(f"    Balance: ${data['balance']:,.2f}")
                return scraped

        if not summary:
            print("  No holdings data returned.")
            return None

        # Build pipeline-compatible output
        results = {}

        for acct_num, acct_data in summary.items():
            # Clean account number
            clean_num = acct_num.strip().replace("-", "")
            label = ACCOUNT_LABELS.get(clean_num, f"fidelity_{clean_num}")

            holdings = {}
            cash = 0

            stocks = acct_data.get("stocks", [])
            if isinstance(stocks, list):
                for stock in stocks:
                    if isinstance(stock, dict):
                        ticker = stock.get("ticker", stock.get("symbol", ""))
                        if not ticker or ticker in ("Pending Activity", ""):
                            continue

                        # Check if it's a cash position
                        if ticker.upper() in ("SPAXX", "FCASH", "FDRXX", "CORE"):
                            cash += float(stock.get("market_value", 0) or 0)
                            continue

                        qty = float(stock.get("quantity", 0) or 0)
                        price = float(stock.get("last_price", 0) or stock.get("price", 0) or 0)
                        mv = float(stock.get("market_value", 0) or stock.get("current_value", 0) or 0)
                        cb = float(stock.get("cost_basis", 0) or stock.get("cost_basis_total", 0) or 0)
                        gl = float(stock.get("gain_loss", 0) or stock.get("total_gain_loss_dollar", 0) or 0)

                        if mv < 1 and qty < 0.001:
                            continue

                        holdings[ticker] = {
                            "qty": round(qty, 6),
                            "price": round(price, 4),
                            "mv": round(mv, 2),
                            "cb": round(cb, 2),
                            "gl": round(gl, 2),
                            "name": stock.get("description", stock.get("name", "")),
                        }

            balance = float(acct_data.get("balance", 0) or acct_data.get("total_value", 0) or 0)

            results[label] = {
                "account_id": clean_num,
                "holdings": holdings,
                "cash": round(cash, 2),
                "balance": round(balance, 2),
            }

            total_mv = sum(h["mv"] for h in holdings.values())
            print(f"\n  {label} ({clean_num}):")
            print(f"    Holdings: {len(holdings)} positions, ${total_mv:,.2f}")
            print(f"    Cash: ${cash:,.2f}")
            print(f"    Balance: ${balance:,.2f}")

        return results

    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        try:
            fidelity.close_browser()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Fidelity Extraction (Playwright)")
    parser.add_argument("--headless", action="store_true", default=False,
                        help="Run in headless mode (no visible browser)")
    args = parser.parse_args()

    results = extract_fidelity(headless=args.headless)

    if results:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = OUTPUT_DIR / f"fidelity_extract_{ts}.json"
        out_file.write_text(json.dumps(results, indent=2, default=str))
        print(f"\n  Saved: {out_file}")

        for label, data in results.items():
            total_mv = sum(h["mv"] for h in data["holdings"].values())
            print(f"\n  {label}:")
            print(f"    Total: ${total_mv + data['cash']:,.2f}")
            for ticker, h in sorted(data["holdings"].items(),
                                     key=lambda x: x[1]["mv"], reverse=True)[:10]:
                print(f"      {ticker:8s}  qty={h['qty']:>10.3f}  ${h['mv']:>12,.2f}")
    else:
        print("\n  Extraction failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
