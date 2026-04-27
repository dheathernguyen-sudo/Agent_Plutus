"""Diagnostic for rh.get_historical_portfolio returning zero equity values.

Logs in using the cached session, then probes the historical endpoint with
different parameters and prints raw responses so we can see what the API
actually returns today.
"""
import json
import os
from pathlib import Path

import robin_stocks.robinhood as rh

CONFIG_DIR = Path.home() / ".portfolio_extract"
TOKEN_DIR = CONFIG_DIR / "tokens"
config = json.loads((CONFIG_DIR / "config.json").read_text())
rh_cfg = config.get("robinhood_login", {})

print("Logging in (using cached session if valid)...")
result = rh.login(
    rh_cfg["email"], rh_cfg["password"],
    store_session=True,
    pickle_path=str(TOKEN_DIR),
)
print(f"  detail: {result.get('detail', '')[:80]}")

# Probe 1: get account profile so we have an account number
print("\n--- Account profile ---")
acct = rh.load_account_profile()
if isinstance(acct, dict):
    print(f"  account_number: {acct.get('account_number')}")
    print(f"  url: {acct.get('url')}")
    print(f"  portfolio_cash: {acct.get('portfolio_cash')}")

# Probe 2: get_historical_portfolio with default args
print("\n--- get_historical_portfolio(interval='day', span='year') ---")
hist = rh.get_historical_portfolio(interval='day', span='year')
print(f"  type: {type(hist).__name__}")
if isinstance(hist, list):
    print(f"  len: {len(hist)}")
    if hist:
        print(f"  first entry: {json.dumps(hist[0], indent=2, default=str)[:600]}")
        print(f"  last entry:  {json.dumps(hist[-1], indent=2, default=str)[:600]}")
elif isinstance(hist, dict):
    print(f"  keys: {list(hist.keys())}")
    print(f"  sample: {json.dumps(hist, indent=2, default=str)[:800]}")
else:
    print(f"  repr: {repr(hist)[:400]}")

# Probe 3: try other spans
for span in ("5year", "all"):
    print(f"\n--- span={span!r} ---")
    h = rh.get_historical_portfolio(interval='day', span=span)
    if isinstance(h, list):
        print(f"  len: {len(h)}")
        if h:
            print(f"  first: {json.dumps(h[0], indent=2, default=str)[:400]}")
    elif isinstance(h, dict):
        print(f"  keys: {list(h.keys())}")
        print(f"  repr: {repr(h)[:400]}")

# Probe 4: look at the raw portfolio URL directly (more control)
print("\n--- load_portfolio_profile (current/live portfolio) ---")
pp = rh.load_portfolio_profile()
if isinstance(pp, dict):
    for k in ("market_value", "equity", "extended_hours_equity", "equity_previous_close", "withdrawable_amount"):
        print(f"  {k}: {pp.get(k)}")

rh.logout()
print("\nLogged out.")
