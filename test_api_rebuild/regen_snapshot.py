"""One-off: patch today's snapshot with cash + net_mv for Robinhood.

Rather than re-running the full pipeline, we make a single SnapTrade call to
get the current Robinhood cash balance, load the existing snapshot, and
augment the robinhood entry in place. Other accounts are left untouched.
"""
import json
from pathlib import Path
from datetime import date

from snaptrade_client import SnapTrade

PROJECT = Path(__file__).resolve().parent.parent
import sys as _sys
_sys.path.insert(0, str(PROJECT))
from paths import SNAPSHOT_DIR

cfg = json.loads(Path.home().joinpath(".portfolio_extract/config.json").read_text())
st_cfg = cfg["snaptrade"]
client = SnapTrade(consumer_key=st_cfg["consumer_key"], client_id=st_cfg["client_id"])

# Find Robinhood account id
accts = client.account_information.list_user_accounts(
    user_id=st_cfg["user_id"], user_secret=st_cfg["user_secret"],
).body
rh_acct_id = None
for a in accts:
    if "robinhood" in (a.get("institution_name") or "").lower():
        rh_acct_id = a["id"]
        break
if not rh_acct_id:
    raise SystemExit("No Robinhood account in SnapTrade")

# Get balance
bal = client.account_information.get_user_account_balance(
    user_id=st_cfg["user_id"], user_secret=st_cfg["user_secret"],
    account_id=rh_acct_id,
).body
cash = 0.0
for entry in (bal if isinstance(bal, list) else [bal]):
    if isinstance(entry, dict):
        val = entry.get("cash")
        if val is not None:
            cash += float(val)
cash = round(cash, 2)
print(f"Current Robinhood cash balance: {cash}")

# Load and patch today's snapshot
today = date.today().isoformat()
snap_path = SNAPSHOT_DIR / f"snapshot_{today}.json"
if not snap_path.exists():
    raise SystemExit(f"No snapshot at {snap_path}")

snap = json.loads(snap_path.read_text())
rh = snap["accounts"].get("robinhood")
if not rh:
    raise SystemExit("No 'robinhood' entry in snapshot")

total_mv = float(rh.get("total_mv", 0))
# Rebuild with the same key order fresh snapshots use: total_mv, cash, net_mv, holdings
new_rh = {
    "total_mv": rh.get("total_mv"),
    "cash": cash,
    "net_mv": round(total_mv + cash, 2),
    "holdings": rh.get("holdings", {}),
}
snap["accounts"]["robinhood"] = new_rh

# Write back (pretty-printed, same indent as original)
snap_path.write_text(json.dumps(snap, indent=2))
print(f"Patched {snap_path.name}")
print(f"  robinhood.total_mv: {rh['total_mv']}")
print(f"  robinhood.cash:     {rh['cash']}")
print(f"  robinhood.net_mv:   {rh['net_mv']}")
