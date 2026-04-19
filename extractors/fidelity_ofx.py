#!/usr/bin/env python3
"""
fidelity_ofx.py — Fidelity OFX/Direct Connect data extraction
==============================================================
Pulls investment holdings, balances, and transactions directly from
Fidelity's OFX server using ofxtools. No third-party API dependency.

Usage:
    python fidelity_ofx.py                    # Extract all accounts
    python fidelity_ofx.py --account roth_ira # Extract single account
    python fidelity_ofx.py --setup            # Interactive credential setup
"""

import argparse
import json
import os
import sys
from datetime import datetime, date
from io import BytesIO
from pathlib import Path

from ofxtools import OFXClient
from ofxtools.Client import InvStmtRq
from ofxtools.Parser import OFXTree
from ofxtools.utils import UTC

CONFIG_DIR = Path.home() / ".portfolio_extract"
CONFIG_FILE = CONFIG_DIR / "config.json"
OUTPUT_DIR = Path(__file__).parent.resolve()


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def setup_credentials(config):
    print("\n  Fidelity OFX Setup")
    print("  " + "=" * 40)
    fid = config.get("fidelity", {})
    fid["username"] = input(f"  Username [{fid.get('username', '')}]: ").strip() or fid.get("username", "")
    password = input("  Password: ").strip() or fid.get("password", "")
    fid.setdefault("ofx_config", {
        "url": "https://ofx.fidelity.com/ftgw/OFX/clients/download",
        "org": "fidelity.com", "fid": "7776", "brokerid": "fidelity.com",
        "ofxver": 220, "appid": "QWIN", "appver": "2700",
    })
    # Store password in OS keyring if available, otherwise fall back to config
    try:
        import keyring
        keyring.set_password("agent-plutus-fidelity", fid["username"], password)
        fid.pop("password", None)  # Remove from plaintext config
        print("  Password saved to OS keyring.")
    except ImportError:
        fid["password"] = password
        print("  Password saved to config (install 'keyring' for secure storage).")
    config["fidelity"] = fid
    save_config(config)
    print("  Config saved.")


def extract_account(client, password, account_id, account_label, brokerid,
                    start_date, end_date):
    """Extract holdings and transactions for a single Fidelity account via OFX."""
    print(f"\n  Extracting {account_label} ({account_id})...")

    dtstart = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)
    dtend = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=UTC)

    # Build investment statement request
    inv_req = InvStmtRq(
        acctid=account_id,
        dtstart=dtstart,
        dtend=dtend,
        inctran=True,
        incpos=True,
        incbal=True,
    )

    try:
        response = client.request_statements(password, inv_req, timeout=30)
    except Exception as e:
        print(f"    OFX request failed: {e}")
        return None

    # Parse response
    parser = OFXTree()
    parser.parse(response)
    ofx = parser.convert()

    # Check signon status
    status_code = int(ofx.sonrsmsgsv1.sonrs.status.code)
    if status_code != 0:
        severity = ofx.sonrsmsgsv1.sonrs.status.severity
        msg = getattr(ofx.sonrsmsgsv1.sonrs.status, "message", "")
        print(f"    OFX error ({status_code}/{severity}): {msg}")
        return None

    result = {
        "label": account_label,
        "account_id": account_id,
        "holdings": {},
        "cash": 0,
        "transactions": [],
    }

    # Security list lookup
    sec_map = {}
    if hasattr(ofx, "seclistmsgsv1") and ofx.seclistmsgsv1:
        seclist = ofx.seclistmsgsv1.seclist
        if seclist:
            for sec in seclist:
                si = sec.secinfo
                secid = str(si.secid.uniqueid)
                ticker = str(getattr(si, "ticker", "") or secid)
                name = str(getattr(si, "secname", "") or "")
                price = float(si.unitprice) if hasattr(si, "unitprice") and si.unitprice else 0
                sec_map[secid] = {"ticker": ticker, "name": name, "price": price}

    # Investment statement
    if not ofx.invstmtmsgsv1:
        print(f"    No investment statement in response")
        return result

    stmtrs = ofx.invstmtmsgsv1.invstmttrnrs.invstmtrs

    # Positions
    if stmtrs.invposlist:
        for pos in stmtrs.invposlist:
            invpos = pos.invpos
            secid = str(invpos.secid.uniqueid)
            sec = sec_map.get(secid, {"ticker": secid, "name": "", "price": 0})

            units = float(invpos.units) if invpos.units else 0
            price = float(invpos.unitprice) if invpos.unitprice else 0
            mktval = float(invpos.mktval) if invpos.mktval else units * price

            ticker = sec["ticker"]
            if abs(units) < 0.001:
                continue

            result["holdings"][ticker] = {
                "qty": round(units, 6),
                "price": round(price, 4),
                "mv": round(mktval, 2),
                "cb": 0,
                "gl": 0,
                "name": sec["name"],
            }

    # Cash balance
    if stmtrs.invbal:
        result["cash"] = round(float(stmtrs.invbal.availcash or 0), 2)

    # Transactions
    if stmtrs.invtranlist:
        for txn in stmtrs.invtranlist:
            td = _parse_transaction(txn, sec_map)
            if td:
                result["transactions"].append(td)

    print(f"    Holdings: {len(result['holdings'])} positions")
    print(f"    Cash: ${result['cash']:,.2f}")
    print(f"    Transactions: {len(result['transactions'])}")

    return result


def _parse_transaction(txn, sec_map):
    try:
        td = {"type": type(txn).__name__}

        # Get date from invtran
        invtran = None
        if hasattr(txn, "invbuy") and txn.invbuy:
            invtran = txn.invbuy.invtran
            td["units"] = float(txn.invbuy.units or 0)
            td["unitprice"] = float(txn.invbuy.unitprice or 0)
            td["total"] = float(txn.invbuy.total or 0)
            secid = str(txn.invbuy.secid.uniqueid) if txn.invbuy.secid else ""
            td["ticker"] = sec_map.get(secid, {}).get("ticker", secid)
        elif hasattr(txn, "invsell") and txn.invsell:
            invtran = txn.invsell.invtran
            td["units"] = float(txn.invsell.units or 0)
            td["unitprice"] = float(txn.invsell.unitprice or 0)
            td["total"] = float(txn.invsell.total or 0)
            secid = str(txn.invsell.secid.uniqueid) if txn.invsell.secid else ""
            td["ticker"] = sec_map.get(secid, {}).get("ticker", secid)
        elif hasattr(txn, "invtran") and txn.invtran:
            invtran = txn.invtran

        if invtran:
            td["date"] = invtran.dttrade.date().isoformat() if invtran.dttrade else ""

        if hasattr(txn, "secid") and txn.secid:
            secid = str(txn.secid.uniqueid)
            td["ticker"] = sec_map.get(secid, {}).get("ticker", secid)

        if hasattr(txn, "total") and txn.total:
            td["total"] = float(txn.total)
        if hasattr(txn, "incometype") and txn.incometype:
            td["income_type"] = str(txn.incometype)

        return td
    except Exception:
        return None


def extract_all(config, start_date=None, end_date=None):
    """Extract all Fidelity accounts via OFX."""
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
    ofx_config = fid.get("ofx_config", {})
    accounts = fid.get("accounts", {})

    if not username or not password:
        print("  ERROR: Fidelity credentials not set. Run --setup")
        return None
    if not accounts:
        print("  ERROR: No accounts configured. Run --setup")
        return None

    if not start_date:
        start_date = date(date.today().year, 1, 1)
    if not end_date:
        end_date = date.today()

    print(f"\n{'='*60}")
    print(f"  Fidelity OFX Extraction")
    print(f"  Period: {start_date} to {end_date}")
    print(f"  Accounts: {len(accounts)}")
    print(f"{'='*60}")

    client = OFXClient(
        url=ofx_config["url"],
        userid=username,
        org=ofx_config.get("org", "fidelity.com"),
        fid=ofx_config.get("fid", "7776"),
        brokerid=ofx_config.get("brokerid", "fidelity.com"),
        version=ofx_config.get("ofxver", 220),
        appid=ofx_config.get("appid", "QWIN"),
        appver=ofx_config.get("appver", "2700"),
    )

    brokerid = ofx_config.get("brokerid", "fidelity.com")
    results = {}

    for label, acct_id in accounts.items():
        data = extract_account(client, password, acct_id, label, brokerid,
                               start_date, end_date)
        if data:
            results[label] = data

    return results


def main():
    parser = argparse.ArgumentParser(description="Fidelity OFX Extraction")
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--account", type=str)
    parser.add_argument("--start", type=str)
    parser.add_argument("--end", type=str)
    args = parser.parse_args()

    config = load_config()

    if args.setup:
        setup_credentials(config)
        return

    start_date = date.fromisoformat(args.start) if args.start else None
    end_date = date.fromisoformat(args.end) if args.end else None

    if args.account:
        fid = config.get("fidelity", {})
        accounts = fid.get("accounts", {})
        matching = {k: v for k, v in accounts.items() if args.account.lower() in k.lower()}
        if not matching:
            print(f"  No account matching '{args.account}'")
            sys.exit(1)
        config["fidelity"]["accounts"] = matching

    results = extract_all(config, start_date, end_date)

    if results:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = OUTPUT_DIR / f"fidelity_ofx_{ts}.json"
        out_file.write_text(json.dumps(results, indent=2, default=str))
        print(f"\n  Saved: {out_file}")

        for label, data in results.items():
            total_mv = sum(h["mv"] for h in data["holdings"].values())
            print(f"\n  {label}:")
            print(f"    Total: ${total_mv + data['cash']:,.2f} ({len(data['holdings'])} positions + ${data['cash']:,.2f} cash)")
            for ticker, h in sorted(data["holdings"].items(),
                                     key=lambda x: x[1]["mv"], reverse=True)[:10]:
                print(f"      {ticker:8s}  qty={h['qty']:>10.3f}  ${h['mv']:>12,.2f}  {h['name'][:30]}")


if __name__ == "__main__":
    main()
