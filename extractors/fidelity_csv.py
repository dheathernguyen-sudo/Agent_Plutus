#!/usr/bin/env python3
"""
fidelity_csv.py — Fidelity CSV data extraction for portfolio pipeline.

Parses Fidelity CSV exports (positions + transaction history) and converts
them to pipeline-compatible JSON matching plaid_extract.py output format.

Usage:
    python fidelity_csv.py --positions FILE [FILE ...]              # Parse position CSVs
    python fidelity_csv.py --positions FILE --history FILE           # Positions + history
    python fidelity_csv.py --positions FILE --format pipeline        # Pipeline JSON output
    python fidelity_csv.py --dir ./fidelity_exports/                 # Auto-find CSVs in folder

CSV files are downloaded from Fidelity.com:
    Positions:  Accounts & Trade → Portfolio → Download
    History:    Accounts & Trade → Activity & Orders → History → Download

No external dependencies required — uses only Python standard library.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("extract_output")

# ---------------------------------------------------------------------------
# Account label mapping — maps account numbers to pipeline labels
# ---------------------------------------------------------------------------
ACCOUNT_LABELS = {
    # Will be populated from config or auto-detected
}

CONFIG_DIR  = Path.home() / ".portfolio_extract"
CONFIG_FILE = CONFIG_DIR / "config.json"

def _load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}

def _get_account_label(acct_num: str) -> str:
    """Map account number to a pipeline label."""
    cfg = _load_config()
    fid_accounts = cfg.get("fidelity", {}).get("accounts", {})
    # Reverse lookup: accounts dict is {label: acct_num}
    for label, num in fid_accounts.items():
        if num == acct_num:
            return label
    # Fallback: use account name from CSV or generic label
    return f"fidelity_{acct_num}"

# ---------------------------------------------------------------------------
# Number parsing helpers
# ---------------------------------------------------------------------------

def _parse_num(val: str) -> float:
    """Parse a number string, handling $, +, -, commas, and -- (missing)."""
    if not val or val.strip() in ("", "--", "n/a", "N/A"):
        return 0.0
    s = val.strip().replace("$", "").replace(",", "").replace("+", "")
    # Handle percentage signs
    s = s.replace("%", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

def _parse_date(val: str) -> str:
    """Parse Fidelity date format (MM/DD/YYYY) to YYYY-MM-DD."""
    if not val or not val.strip():
        return ""
    try:
        dt = datetime.strptime(val.strip(), "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return val.strip()

# ---------------------------------------------------------------------------
# Positions CSV parser
# ---------------------------------------------------------------------------

def parse_positions_csv(filepath: str) -> dict:
    """
    Parse a Fidelity Portfolio_Positions CSV file.

    Expected columns:
        Account Number, Account Name, Symbol, Description, Quantity,
        Last Price, Last Price Change, Current Value, Today's Gain/Loss Dollar,
        Today's Gain/Loss Percent, Total Gain/Loss Dollar, Total Gain/Loss Percent,
        Percent Of Account, Cost Basis Total, Average Cost Basis, Type

    Returns: {account_number: {account_name, holdings: [...]}}
    """
    accounts = {}

    with open(filepath, "r", encoding="utf-8-sig") as f:
        # Read all lines, stopping at disclaimer text
        lines = []
        for line in f:
            stripped = line.strip()
            # Stop at disclaimer or empty lines followed by quotes
            if stripped.startswith('"The data and information'):
                break
            if stripped:
                lines.append(line)

    if not lines:
        print(f"  WARNING: No data found in {filepath}")
        return {}

    reader = csv.DictReader(lines)

    for row in reader:
        acct_num = row.get("Account Number", "").strip()
        acct_name = row.get("Account Name", "").strip()
        symbol = row.get("Symbol", "").strip()

        if not acct_num or not symbol:
            continue

        # Skip cash positions with ** suffix (like FCASH**)
        is_cash = symbol.endswith("**") or symbol.startswith("FCASH")

        if acct_num not in accounts:
            accounts[acct_num] = {
                "account_name": acct_name,
                "holdings": [],
                "cash": 0.0,
            }

        if is_cash:
            accounts[acct_num]["cash"] = _parse_num(row.get("Current Value", "0"))
            continue

        qty = _parse_num(row.get("Quantity", "0"))
        price = _parse_num(row.get("Last Price", "0"))
        current_val = _parse_num(row.get("Current Value", "0"))
        cost_basis = _parse_num(row.get("Cost Basis Total", "0"))
        avg_cost = _parse_num(row.get("Average Cost Basis", "0"))
        gain_loss = _parse_num(row.get("Total Gain/Loss Dollar", "0"))
        description = row.get("Description", "").strip()

        # Skip "Pending Activity" placeholder rows
        if "pending" in symbol.lower() or "pending" in description.lower():
            continue

        # Skip holdings with no quantity and no value (phantom/pending rows)
        if qty == 0 and current_val == 0:
            continue

        accounts[acct_num]["holdings"].append({
            "ticker":       symbol,
            "name":         description,
            "quantity":     qty,
            "price":        price,
            "market_value": current_val,
            "cost_basis":   cost_basis,
            "avg_cost":     avg_cost,
            "gain_loss":    gain_loss,
            "currency":     "USD",
        })

    return accounts

# ---------------------------------------------------------------------------
# History CSV parser
# ---------------------------------------------------------------------------

def parse_history_csv(filepath: str) -> dict:
    """
    Parse a Fidelity History CSV file.

    Expected columns:
        Run Date, Action, Symbol, Description, Type, Price ($),
        Quantity, Commission ($), Fees ($), Accrued Interest ($),
        Amount ($), Cash Balance ($), Settlement Date

    Returns: {account_number: [transactions...]}
    """
    # Fidelity history CSVs don't always include the account number in each row.
    # The filename typically contains it: History_for_Account_XXXXXXX.csv
    # We'll extract it from the filename.
    fname = Path(filepath).stem
    acct_match = re.search(r'_([A-Z0-9]{6,12})$', fname) or re.search(r'Account_([A-Z0-9]+)', fname)
    acct_num = acct_match.group(1) if acct_match else "unknown"

    transactions = []

    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = []
        for line in f:
            stripped = line.strip()
            if stripped.startswith('"The data and information'):
                break
            if stripped:
                lines.append(line)

    if not lines:
        print(f"  WARNING: No data found in {filepath}")
        return {acct_num: []}

    reader = csv.DictReader(lines)

    for row in reader:
        run_date = row.get("Run Date", "").strip()
        action = row.get("Action", "").strip()
        symbol = row.get("Symbol", "").strip()
        description = row.get("Description", "").strip()
        price = _parse_num(row.get("Price ($)", "0"))
        quantity = _parse_num(row.get("Quantity", "0"))
        commission = _parse_num(row.get("Commission ($)", "0"))
        fees = _parse_num(row.get("Fees ($)", "0"))
        amount = _parse_num(row.get("Amount ($)", "0"))
        settle_date = row.get("Settlement Date", "").strip()

        if not run_date:
            continue

        # Classify transaction type from action text
        action_lower = action.lower()
        if "dividend" in action_lower:
            txn_type = "dividend"
        elif "interest" in action_lower:
            txn_type = "interest"
        elif "you bought" in action_lower:
            txn_type = "buy"
        elif "you sold" in action_lower:
            txn_type = "sell"
        elif "transfer" in action_lower:
            txn_type = "transfer"
        elif "reinvestment" in action_lower:
            txn_type = "reinvestment"
        elif "electronic funds" in action_lower:
            txn_type = "eft"
        elif "foreign tax" in action_lower:
            txn_type = "tax"
        else:
            txn_type = "other"

        transactions.append({
            "date":         _parse_date(run_date),
            "type":         txn_type,
            "action":       action,
            "ticker":       symbol if symbol and not symbol.startswith("3") else "",  # Filter CUSIP-like symbols
            "name":         description,
            "quantity":     quantity,
            "price":        price,
            "amount":       amount,
            "commission":   commission,
            "fees":         fees,
            "settle_date":  _parse_date(settle_date),
        })

    return {acct_num: transactions}

# ---------------------------------------------------------------------------
# Pipeline format conversion (matches plaid_extract.py output)
# ---------------------------------------------------------------------------

def _to_pipeline_format(acct_num: str, acct_data: dict, transactions: list = None) -> dict:
    """Convert parsed CSV data to pipeline-compatible JSON."""
    label = _get_account_label(acct_num)
    holdings_dict = {}
    as_of = datetime.now().strftime("%Y-%m-%d")

    for h in acct_data.get("holdings", []):
        ticker = h["ticker"]
        if not ticker:
            continue
        holdings_dict[ticker] = {
            "qty":   h["quantity"],
            "price": h["price"],
            "mv":    h["market_value"],
            "cb":    h["cost_basis"],
            "gl":    h["gain_loss"],
        }

    # Monthly cash flow from transactions
    monthly = {}
    if transactions:
        for txn in transactions:
            if not txn["date"]:
                continue
            month_key = txn["date"][:7]  # YYYY-MM
            if month_key not in monthly:
                monthly[month_key] = {
                    "deposits": 0, "withdrawals": 0, "dividends": 0, "other": 0
                }
            amount = txn["amount"]
            ttype = txn["type"]
            if ttype in ("buy", "transfer") and amount > 0:
                monthly[month_key]["deposits"] += abs(amount)
            elif ttype in ("sell",) and amount > 0:
                monthly[month_key]["withdrawals"] += abs(amount)
            elif ttype == "eft" and amount < 0:
                monthly[month_key]["withdrawals"] += abs(amount)
            elif ttype == "eft" and amount > 0:
                monthly[month_key]["deposits"] += abs(amount)
            elif ttype in ("dividend", "interest"):
                monthly[month_key]["dividends"] += abs(amount)
            else:
                monthly[month_key]["other"] += amount

    result = {
        label: {
            "holdings": {as_of: holdings_dict},
        }
    }
    if monthly:
        result[label]["monthly"] = [
            {"date": f"{k}-01", **v} for k, v in sorted(monthly.items())
        ]

    return result

# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def do_extract(args):
    """Parse CSV files and produce output."""
    all_positions = {}
    all_transactions = {}

    # Parse position files
    if args.positions:
        for f in args.positions:
            print(f"\nParsing positions: {f}")
            parsed = parse_positions_csv(f)
            for acct_num, data in parsed.items():
                all_positions[acct_num] = data
                label = _get_account_label(acct_num)
                n = len(data["holdings"])
                cash = data["cash"]
                print(f"  ✓ {label} ({acct_num}): {n} holdings, ${cash:,.2f} cash")

    # Parse history files
    if args.history:
        for f in args.history:
            print(f"\nParsing history: {f}")
            parsed = parse_history_csv(f)
            for acct_num, txns in parsed.items():
                all_transactions[acct_num] = txns
                print(f"  ✓ Account {acct_num}: {len(txns)} transactions")

    # Auto-find CSVs in directory
    if args.dir:
        dirpath = Path(args.dir)
        for f in sorted(dirpath.glob("Portfolio_Positions*.csv")):
            print(f"\nParsing positions: {f}")
            parsed = parse_positions_csv(str(f))
            for acct_num, data in parsed.items():
                all_positions[acct_num] = data
                label = _get_account_label(acct_num)
                print(f"  ✓ {label} ({acct_num}): {len(data['holdings'])} holdings")

        for f in sorted(dirpath.glob("History_for_Account*.csv")):
            print(f"\nParsing history: {f}")
            parsed = parse_history_csv(str(f))
            for acct_num, txns in parsed.items():
                all_transactions[acct_num] = txns
                print(f"  ✓ Account {acct_num}: {len(txns)} transactions")

    # Apply account exclusions
    if args.exclude:
        exclude_labels = set(args.exclude)
        exclude_nums = set()
        for acct_num in list(all_positions.keys()):
            label = _get_account_label(acct_num)
            if label in exclude_labels or acct_num in exclude_labels:
                exclude_nums.add(acct_num)
                print(f"\n  ✗ Excluding {label} ({acct_num})")
        for num in exclude_nums:
            all_positions.pop(num, None)
            all_transactions.pop(num, None)

    if not all_positions:
        print("\nERROR: No position data found. Provide --positions or --dir.")
        sys.exit(1)

    # Build output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.format == "pipeline":
        pipeline = {}
        for acct_num, data in all_positions.items():
            txns = all_transactions.get(acct_num, [])
            acct_pipeline = _to_pipeline_format(acct_num, data, txns)
            pipeline.update(acct_pipeline)

        out_file = OUTPUT_DIR / f"fidelity_pipeline_{ts}.json"
        with open(out_file, "w") as f:
            json.dump(pipeline, f, indent=2)
        print(f"\n✓ Pipeline JSON saved: {out_file}")
    else:
        raw = {}
        for acct_num, data in all_positions.items():
            label = _get_account_label(acct_num)
            raw[label] = {
                "account_id": acct_num,
                "account_name": data["account_name"],
                "as_of": datetime.now().strftime("%Y-%m-%d"),
                "cash": data["cash"],
                "holdings": data["holdings"],
                "transactions": all_transactions.get(acct_num, []),
            }

        out_file = OUTPUT_DIR / f"fidelity_raw_{ts}.json"
        with open(out_file, "w") as f:
            json.dump(raw, f, indent=2, default=str)
        print(f"\n✓ Raw JSON saved: {out_file}")

    # Print summary
    print(f"\n{'='*60}")
    print("  EXTRACTION SUMMARY")
    print(f"{'='*60}")
    for acct_num, data in all_positions.items():
        label = _get_account_label(acct_num)
        holdings = data["holdings"]
        total_mv = sum(h["market_value"] for h in holdings)
        total_cb = sum(h["cost_basis"] for h in holdings)
        total_gl = sum(h["gain_loss"] for h in holdings)

        print(f"\n  {label} ({acct_num}) — {data['account_name']}")
        print(f"    Holdings:     {len(holdings)}")
        print(f"    Cash:         ${data['cash']:>11,.2f}")
        print(f"    Market Value: ${total_mv:>11,.2f}")
        print(f"    Cost Basis:   ${total_cb:>11,.2f}")
        print(f"    Gain/Loss:    ${total_gl:>+11,.2f}")

        txn_count = len(all_transactions.get(acct_num, []))
        if txn_count:
            print(f"    Transactions: {txn_count}")

        if holdings:
            print(f"\n    {'Ticker':<8} {'Qty':>8} {'Price':>10} {'Mkt Value':>12} {'Cost Basis':>12} {'Gain/Loss':>12}")
            print(f"    {'-'*8} {'-'*8} {'-'*10} {'-'*12} {'-'*12} {'-'*12}")
            for h in sorted(holdings, key=lambda x: x["market_value"], reverse=True):
                print(f"    {h['ticker']:<8} {h['quantity']:>8.3f} ${h['price']:>9.2f} ${h['market_value']:>11,.2f} ${h['cost_basis']:>11,.2f} ${h['gain_loss']:>+11,.2f}")

    if args.output:
        import shutil
        shutil.copy(out_file, args.output)
        print(f"\n✓ Also copied to: {args.output}")

    return out_file

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fidelity CSV data extraction for portfolio pipeline"
    )
    parser.add_argument("--positions", nargs="+",
                        help="Fidelity Portfolio_Positions CSV file(s)")
    parser.add_argument("--history", nargs="+",
                        help="Fidelity History CSV file(s)")
    parser.add_argument("--dir", type=str,
                        help="Directory containing Fidelity CSV exports")
    parser.add_argument("--format", choices=["raw", "pipeline"], default="raw",
                        help="Output format (default: raw)")
    parser.add_argument("--output", type=str,
                        help="Copy output to this path")
    parser.add_argument("--exclude", nargs="*", default=[],
                        help="Account labels to exclude (e.g., fidelity_traditional_ira)")

    args = parser.parse_args()

    if not args.positions and not args.dir:
        parser.print_help()
        print("\n\nExample usage:")
        print('  python fidelity_csv.py --positions "Portfolio_Positions_Mar-01-2026.csv"')
        print('  python fidelity_csv.py --positions positions.csv --history history.csv --format pipeline')
        print('  python fidelity_csv.py --dir ./exports/ --format pipeline')
        sys.exit(0)

    do_extract(args)

if __name__ == "__main__":
    main()
