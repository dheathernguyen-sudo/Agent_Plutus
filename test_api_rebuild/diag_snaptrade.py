"""Diagnostic: what does SnapTrade actually return for the Robinhood account?

We want to know whether SnapTrade exposes:
  - Month-end portfolio values (opening/closing) — needed for TWR/MWRR monthly math
  - Return rates (TWR) for standard periods — potentially a direct replacement
  - Historical transactions (flows) — already confirmed via get_account_activities
"""
import json
from datetime import date
from pathlib import Path

from snaptrade_client import SnapTrade

CONFIG = json.loads(Path.home().joinpath(".portfolio_extract/config.json").read_text())
st_cfg = CONFIG["snaptrade"]

client = SnapTrade(consumer_key=st_cfg["consumer_key"], client_id=st_cfg["client_id"])

# Find the Robinhood account
accts = client.account_information.list_user_accounts(
    user_id=st_cfg["user_id"], user_secret=st_cfg["user_secret"],
).body
rh_acct = None
for a in accts:
    inst = (a.get("institution_name") or "").lower()
    if "robinhood" in inst:
        rh_acct = a
        break

if not rh_acct:
    print("No Robinhood account found in SnapTrade. Available institutions:")
    for a in accts:
        print(f"  - {a.get('institution_name')} ({a.get('id')})")
    raise SystemExit(1)

acct_id = rh_acct["id"]
print(f"Robinhood account id: {acct_id}")
print(f"  name: {rh_acct.get('name')}")
print(f"  balance: {rh_acct.get('balance', {}).get('total', {})}")

# --- Return rates endpoint ---
print("\n--- get_user_account_return_rates ---")
try:
    rr = client.account_information.get_user_account_return_rates(
        user_id=st_cfg["user_id"],
        user_secret=st_cfg["user_secret"],
        account_id=acct_id,
    ).body
    print(json.dumps(rr, indent=2, default=str)[:2500])
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# --- Account details (may include historical returns) ---
print("\n--- get_user_account_details ---")
try:
    det = client.account_information.get_user_account_details(
        user_id=st_cfg["user_id"],
        user_secret=st_cfg["user_secret"],
        account_id=acct_id,
    ).body
    print(json.dumps(det, indent=2, default=str)[:1500])
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# --- Current balance ---
print("\n--- get_user_account_balance ---")
try:
    bal = client.account_information.get_user_account_balance(
        user_id=st_cfg["user_id"],
        user_secret=st_cfg["user_secret"],
        account_id=acct_id,
    ).body
    print(json.dumps(bal, indent=2, default=str)[:1000])
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# --- Activities for Jan-Mar 2026 (to confirm we can get monthly flows) ---
print("\n--- get_account_activities (2026-01-01 to 2026-03-31) ---")
try:
    act = client.account_information.get_account_activities(
        user_id=st_cfg["user_id"],
        user_secret=st_cfg["user_secret"],
        account_id=acct_id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
    ).body
    activities = act if isinstance(act, list) else act.get("data", [])
    print(f"  total returned: {len(activities)}")
    # summarize by type
    by_type = {}
    for a in activities:
        t = a.get("type", "?")
        by_type[t] = by_type.get(t, 0) + 1
    print(f"  by type: {by_type}")
    if activities:
        print(f"  sample (first): {json.dumps(activities[0], indent=2, default=str)[:500]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
