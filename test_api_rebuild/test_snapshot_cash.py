"""Verify daily_snapshot.py now records cash and net_mv for provider accounts.

Covers three scenarios:
  1. RAW SnapTrade format (the shape `prepare_builder_data` actually passes
     to save_snapshot in production): cash lives in accounts[i].balances.current
  2. PIPELINE format (produced by to_pipeline_format): cash lives at data.cash
  3. Backward compat when cash is absent entirely
"""
import json
import sys
from datetime import date
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
from paths import PIPELINE_DIR as PIPELINE
TEST_DIR = PROJECT / "test_api_rebuild"
TEST_SNAPSHOT_DIR = TEST_DIR / "snapshots"
TEST_SNAPSHOT_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PIPELINE))

import daily_snapshot
daily_snapshot.SNAPSHOT_DIR = TEST_SNAPSHOT_DIR  # isolate

# --- Scenario 1: RAW format (production path) ---
raw_format = {
    "robinhood": {
        "provider": "snaptrade",
        "institution": "Robinhood",
        "label": "robinhood",
        "accounts": [
            {
                "account_id": "b8a24ab8",
                "name": "Robinhood Individual",
                "balances": {"current": -14134.87, "currency": "USD"},
            }
        ],
        "holdings": [
            {"ticker": "NVDA", "quantity": 50.0, "institution_price": 204.02,
             "institution_value": 10201.00, "cost_basis": 3887.50, "gain_loss": 6313.50},
        ],
        "securities": [],
        "investment_transactions": [],
    }
}
out1 = daily_snapshot.save_snapshot(fid_data={}, rh_raw=raw_format, date_str="2026-04-24")
snap1 = json.loads(out1.read_text())
rh1 = snap1["accounts"]["robinhood"]
print("Scenario 1 (raw format):")
print(json.dumps(rh1, indent=2))
assert rh1["cash"] == -14134.87, f"raw format: expected cash=-14134.87, got {rh1['cash']}"
assert rh1["total_mv"] == 10201.0, f"raw format: expected total_mv=10201.0, got {rh1['total_mv']}"
assert abs(rh1["net_mv"] - (10201.0 - 14134.87)) < 0.01, f"raw format: net_mv mismatch: {rh1['net_mv']}"
print("PASS — raw format reads cash from accounts[].balances.current\n")

# --- Scenario 2: PIPELINE format (for when we feed processed data) ---
from plaid_extract import to_pipeline_format
pipeline = to_pipeline_format(raw_format, date(2026, 1, 1), date(2026, 4, 24))
rh_pipeline = pipeline["robinhood"]
assert rh_pipeline.get("cash") == -14134.87, "to_pipeline_format did not carry cash"

out2 = daily_snapshot.save_snapshot(
    fid_data={}, rh_raw={"robinhood": rh_pipeline}, date_str="2026-04-25",
)
snap2 = json.loads(out2.read_text())
rh2 = snap2["accounts"]["robinhood"]
print("Scenario 2 (pipeline format):")
print(json.dumps(rh2, indent=2))
assert rh2["cash"] == -14134.87, f"pipeline format: expected cash=-14134.87, got {rh2['cash']}"
assert abs(rh2["net_mv"] - (10201.0 - 14134.87)) < 0.01
print("PASS — pipeline format reads cash from data.cash\n")

# --- Scenario 3: no cash info at all ---
raw_no_cash = {
    "robinhood": {
        "provider": "snaptrade",
        "accounts": [{"name": "X", "balances": {}}],
        "holdings": [{"ticker": "NVDA", "quantity": 50.0, "institution_price": 204.02,
                       "institution_value": 10201.00}],
    }
}
out3 = daily_snapshot.save_snapshot(fid_data={}, rh_raw=raw_no_cash, date_str="2026-04-26")
snap3 = json.loads(out3.read_text())
rh3 = snap3["accounts"]["robinhood"]
print("Scenario 3 (no cash reported):")
print(json.dumps(rh3, indent=2))
assert rh3["cash"] == 0.0, f"missing cash: expected 0.0, got {rh3['cash']}"
assert rh3["net_mv"] == rh3["total_mv"], "when cash=0, net_mv should equal total_mv"
print("PASS — missing cash defaults to 0.0\n")

print("All three scenarios passed.")
