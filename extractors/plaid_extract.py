#!/usr/bin/env python3
"""
plaid_extract.py — Portfolio data extraction (SnapTrade + Plaid)
================================================================
Step 1 of the portfolio analysis pipeline. Replaces manual PDF downloads.

Current setup:
  - SnapTrade: Robinhood, Fidelity (connected)
  - Plaid:     Merrill Lynch (connected)
  - Manual:    Angel investments, benchmarks, MWRR values

Usage:
    python plaid_extract.py --setup
    python plaid_extract.py --start 2025-01-01 --end 2025-12-31
    python plaid_extract.py --start 2025-01-01 --end 2025-12-31 --format pipeline

Requirements:
    pip install snaptrade-python-sdk flask
    pip install plaid-python  (when Plaid production access is ready)
"""

import argparse
import json
import os
import sys
import time
import datetime
from pathlib import Path
from typing import Optional
from collections import defaultdict

# ---------------------------------------------------------------------------
# Conditional imports
# ---------------------------------------------------------------------------

PLAID_AVAILABLE = False
try:
    import plaid
    from plaid.api import plaid_api
    from plaid.model.country_code import CountryCode
    from plaid.model.products import Products
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
    from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
    from plaid.model.investments_transactions_get_request import InvestmentsTransactionsGetRequest
    from plaid.model.investments_transactions_get_request_options import InvestmentsTransactionsGetRequestOptions
    from plaid.model.accounts_get_request import AccountsGetRequest
    from plaid.model.transactions_get_request import TransactionsGetRequest
    from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
    PLAID_AVAILABLE = True
except ImportError:
    pass

SNAPTRADE_AVAILABLE = False
try:
    from snaptrade_client import SnapTrade
    SNAPTRADE_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".portfolio_extract"
CONFIG_FILE = CONFIG_DIR / "config.json"

PROVIDER_MAP = {
    "robinhood":           "snaptrade",
    "fidelity":            "snaptrade",
    "schwab":              "plaid",
    "merrill":             "plaid",
    "fidelity_netbenefits": "plaid",
    "chase":               "plaid",
    "marcus":              "plaid",
}

INSTITUTION_LABELS = {
    "robinhood":           "Robinhood",
    "schwab":              "Charles Schwab",
    "merrill":             "Merrill Lynch (Bank of America)",
    "fidelity":            "Fidelity",
    "fidelity_netbenefits": "Fidelity NetBenefits 401(k)",
    "chase":               "Chase",
    "marcus":              "Marcus (Goldman Sachs)",
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {
        "plaid": {"client_id": "", "secret": "", "environment": "production", "institutions": {}},
        "snaptrade": {"client_id": "", "consumer_key": "", "user_id": "", "user_secret": "", "connections": {}},
    }


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass
    print(f"  Config saved to {CONFIG_FILE}")


# ---------------------------------------------------------------------------
# SnapTrade symbol parser
# ---------------------------------------------------------------------------

def _parse_st_symbol(sym_obj) -> dict:
    """
    Parse SnapTrade's nested symbol structure.
    Structure: position["symbol"]["symbol"]["symbol"] = ticker string
               position["symbol"]["symbol"]["description"] = name string
               position["symbol"]["id"] = security_id
    """
    if not isinstance(sym_obj, dict):
        return {"ticker": str(sym_obj) if sym_obj else "", "name": "", "sec_id": ""}

    # The outer "symbol" dict contains an inner "symbol" dict with actual security info
    inner = sym_obj.get("symbol", {})
    sec_id = str(sym_obj.get("id", ""))

    if isinstance(inner, dict):
        ticker = inner.get("symbol", "") or inner.get("raw_symbol", "") or ""
        name = inner.get("description", "") or ""
        if not sec_id:
            sec_id = str(inner.get("id", ""))
    elif isinstance(inner, str):
        ticker = inner
        name = ""
    else:
        ticker = ""
        name = ""

    return {"ticker": ticker, "name": name, "sec_id": sec_id}


# ===========================================================================
# SNAPTRADE PROVIDER
# ===========================================================================

def get_snaptrade_client(config: dict) -> "SnapTrade":
    if not SNAPTRADE_AVAILABLE:
        print("ERROR: snaptrade-python-sdk not installed.")
        print("  Run: pip install snaptrade-python-sdk")
        sys.exit(1)
    st = config["snaptrade"]
    return SnapTrade(consumer_key=st["consumer_key"], client_id=st["client_id"])


def setup_snaptrade(config: dict):
    """Interactive SnapTrade setup."""
    print("\n" + "=" * 60)
    print("  SNAPTRADE SETUP")
    print("=" * 60)

    if not SNAPTRADE_AVAILABLE:
        print("\n  ERROR: snaptrade-python-sdk not installed.")
        return

    st = config["snaptrade"]

    if not st.get("client_id") or not st.get("consumer_key"):
        print("\n  Get SnapTrade API keys at https://dashboard.snaptrade.com\n")
        st["client_id"]    = input("  SnapTrade Client ID:    ").strip()
        st["consumer_key"] = input("  SnapTrade Consumer Key: ").strip()
        save_config(config)
    else:
        print(f"\n  Using saved credentials (client_id: {st['client_id'][:8]}...)")

    client = get_snaptrade_client(config)

    if not st.get("user_id") or not st.get("user_secret"):
        print("\n  Registering SnapTrade user...")
        user_id = f"portfolio-user-{int(time.time())}"
        try:
            resp = client.authentication.register_snap_trade_user(body={"userId": user_id})
            st["user_id"] = user_id
            st["user_secret"] = resp.body["userSecret"]
            save_config(config)
            print(f"  Registered user: {user_id}")
        except Exception as e:
            print(f"  ERROR: {e}")
            return
    else:
        print(f"  Using saved user: {st['user_id']}")

    print("\n  Generating connection link...")
    try:
        resp = client.authentication.login_snap_trade_user(
            user_id=st["user_id"],
            user_secret=st["user_secret"],
        )
        redirect_url = None
        if hasattr(resp, 'body'):
            body = resp.body
            if isinstance(body, dict):
                redirect_url = body.get("redirectURI") or body.get("loginRedirectURI")
            elif isinstance(body, str):
                redirect_url = body

        if redirect_url:
            print(f"\n  Opening browser to connect your brokerage...\n")
            import webbrowser
            webbrowser.open(redirect_url)
            print("  After connecting in the browser, press Enter here...")
            input()
        else:
            print(f"  Could not extract redirect URL. Response: {resp}")
            return
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    print("  Fetching linked accounts...")
    _refresh_snaptrade_accounts(client, config)
    print("\n  SnapTrade setup complete.\n")


def _refresh_snaptrade_accounts(client, config: dict):
    st = config["snaptrade"]
    try:
        resp = client.account_information.list_user_accounts(
            user_id=st["user_id"], user_secret=st["user_secret"],
        )
        connections = {}
        for acct in resp.body:
            ad = acct if isinstance(acct, dict) else (acct.to_dict() if hasattr(acct, 'to_dict') else {})
            account_id = str(ad.get("id") or ad.get("account_id", ""))
            acct_name = ad.get("name", "")
            acct_number = ad.get("number", "")
            meta = ad.get("meta", {})
            inst_name = ""
            if isinstance(meta, dict):
                inst_name = meta.get("institution_name", "") or meta.get("type", "")
            if not inst_name:
                inst_name = ad.get("institution_name", "")

            combined = (inst_name + " " + acct_name).lower()
            if "robinhood" in combined:
                label = "robinhood"
            elif "schwab" in combined:
                label = "schwab"
            elif "fidelity" in combined:
                label = "fidelity"
            elif "merrill" in combined or "bank of america" in combined:
                label = "merrill"
            elif "netbenefits" in combined or ("fidelity" in combined and "401" in combined):
                label = "fidelity_netbenefits"
            else:
                label = inst_name.lower().replace(" ", "_") or "unknown"

            if label not in connections:
                connections[label] = {"accounts": [], "institution_name": inst_name}
            connections[label]["accounts"].append({
                "account_id": account_id, "name": acct_name,
                "number": acct_number,
                "type": str(meta.get("type", "")) if isinstance(meta, dict) else "",
            })

        st["connections"] = connections
        save_config(config)

        for label, conn in connections.items():
            disp = INSTITUTION_LABELS.get(label, label)
            print(f"\n  {disp}:")
            for a in conn["accounts"]:
                print(f"    - {a['name']} ({a['type']}) #{a.get('number', '????')}")

    except Exception as e:
        print(f"  ERROR fetching accounts: {e}")


def extract_snaptrade(
    config: dict,
    start_date: datetime.date,
    end_date: datetime.date,
    institution_filter: Optional[str] = None,
) -> dict:
    """Pull data from SnapTrade-linked accounts."""
    if not SNAPTRADE_AVAILABLE:
        print("  SKIP: snaptrade-python-sdk not installed")
        return {}

    st = config["snaptrade"]
    if not st.get("user_id") or not st.get("user_secret"):
        print("  SKIP: SnapTrade not configured. Run --setup first.")
        return {}

    client = get_snaptrade_client(config)
    user_id = st["user_id"]
    user_secret = st["user_secret"]
    connections = st.get("connections", {})

    if not connections:
        print("  No connections found. Refreshing...")
        _refresh_snaptrade_accounts(client, config)
        connections = st.get("connections", {})

    results = {}

    for label, conn in connections.items():
        if institution_filter and label != institution_filter:
            continue

        disp_name = INSTITUTION_LABELS.get(label, label)

        print(f"\n{'='*60}")
        print(f"  Extracting via SnapTrade: {disp_name}")
        print(f"  Period: {start_date} to {end_date}")
        print(f"{'='*60}")

        result = {
            "provider": "snaptrade", "institution": disp_name, "label": label,
            "accounts": [], "holdings": [], "securities": [],
            "investment_transactions": [],
        }

        for acct_info in conn["accounts"]:
            account_id = acct_info["account_id"]
            acct_name = acct_info["name"]

            result["accounts"].append({
                "account_id": account_id, "name": acct_name,
                "number": acct_info.get("number", ""), "type": acct_info.get("type", ""),
                "balances": {},
            })

            # --- Holdings ---
            print(f"  Fetching holdings for {acct_name}...")
            try:
                hold_resp = client.account_information.get_user_holdings(
                    account_id=account_id,
                    user_id=user_id,
                    user_secret=user_secret,
                )
                hdata = hold_resp.body if isinstance(hold_resp.body, dict) else {}

                # Balances
                for bal in hdata.get("balances", []):
                    bd = bal if isinstance(bal, dict) else {}
                    result["accounts"][-1]["balances"] = {
                        "current": _num(bd.get("cash") or bd.get("amount")),
                        "currency": (bd.get("currency", {}).get("code", "USD")
                                     if isinstance(bd.get("currency"), dict) else "USD"),
                    }

                # Positions
                n_pos = 0
                for pos in hdata.get("positions", []):
                    pd = pos if isinstance(pos, dict) else {}

                    # Parse the nested symbol structure
                    sym_info = _parse_st_symbol(pd.get("symbol", {}))
                    ticker = sym_info["ticker"]
                    sec_name = sym_info["name"]
                    sec_id = sym_info["sec_id"]

                    qty = _num(pd.get("units"))
                    price = _num(pd.get("price"))
                    mv = qty * price if qty and price else 0
                    avg_price = _num(pd.get("average_purchase_price"))
                    cb = avg_price * qty if avg_price and qty else 0
                    gl = _num(pd.get("open_pnl"))
                    if not gl and mv and cb:
                        gl = mv - cb

                    result["securities"].append({
                        "security_id": sec_id, "name": sec_name,
                        "ticker_symbol": ticker, "close_price": round(price, 4),
                    })
                    result["holdings"].append({
                        "account_id": account_id, "account_name": acct_name,
                        "security_id": sec_id, "ticker": ticker, "name": sec_name,
                        "quantity": round(qty, 6),
                        "institution_price": round(price, 4) if price else 0,
                        "institution_value": round(mv, 2) if mv else 0,
                        "cost_basis": round(cb, 2) if cb else 0,
                        "gain_loss": round(gl, 2) if gl else 0,
                    })
                    n_pos += 1

                print(f"    {acct_name}: {n_pos} positions")

            except Exception as e:
                print(f"    ERROR fetching holdings: {e}")

            # --- Transactions ---
            print(f"  Fetching transactions for {acct_name}...")
            try:
                txn_resp = client.account_information.get_account_activities(
                    account_id=account_id,
                    user_id=user_id,
                    user_secret=user_secret,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
                body = txn_resp.body if hasattr(txn_resp, 'body') else txn_resp
                txn_list = body if isinstance(body, list) else [body]

                count = 0
                for t in txn_list:
                    td = t if isinstance(t, dict) else {}
                    if not td:
                        continue

                    sym_info = _parse_st_symbol(td.get("symbol", {}))

                    result["investment_transactions"].append({
                        "account_id": account_id, "account_name": acct_name,
                        "date": str(td.get("trade_date") or td.get("settlement_date", "")),
                        "ticker": sym_info["ticker"],
                        "name": sym_info["name"],
                        "type": str(td.get("type", "")).upper(),
                        "description": td.get("description", ""),
                        "quantity": _num(td.get("units") or td.get("quantity")),
                        "price": _num(td.get("price")),
                        "amount": _num(td.get("amount")),
                        "fees": _num(td.get("fee") or td.get("commission")),
                        "currency": (td.get("currency", {}).get("code", "USD")
                                     if isinstance(td.get("currency"), dict) else "USD"),
                    })
                    count += 1

                print(f"    {acct_name}: {count} transactions")

            except Exception as e:
                print(f"    ERROR fetching transactions: {e}")

        results[label] = result

    return results


# ===========================================================================
# PLAID PROVIDER (for future use)
# ===========================================================================

def get_plaid_client(config: dict):
    if not PLAID_AVAILABLE:
        print("ERROR: plaid-python not installed.")
        sys.exit(1)
    pc = config["plaid"]
    env_map = {"sandbox": plaid.Environment.Sandbox, "production": plaid.Environment.Production}
    configuration = plaid.Configuration(
        host=env_map.get(pc.get("environment", "production"), plaid.Environment.Production),
        api_key={"clientId": pc["client_id"], "secret": pc["secret"], "plaidVersion": "2020-09-14"},
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


def setup_plaid(config: dict):
    print("\n" + "=" * 60)
    print("  PLAID SETUP (401k, Chase, Marcus)")
    print("=" * 60)
    if not PLAID_AVAILABLE:
        print("\n  plaid-python not installed. Run: pip install plaid-python")
        print("  (Also requires full production + OAuth access from Plaid.)")
        return
    pc = config["plaid"]
    if not pc.get("client_id") or not pc.get("secret"):
        print("\n  Get keys at https://dashboard.plaid.com/team/keys\n")
        pc["client_id"]   = input("  Plaid Client ID: ").strip()
        pc["secret"]      = input("  Plaid Secret:    ").strip()
        pc["environment"] = input("  Environment [production]: ").strip() or "production"
        save_config(config)
    else:
        print(f"\n  Using saved credentials (client_id: {pc['client_id'][:8]}...)")
    client = get_plaid_client(config)
    plaid_insts = {k: v for k, v in INSTITUTION_LABELS.items() if PROVIDER_MAP.get(k) == "plaid"}
    print("\n  Which institutions to link?\n")
    items = list(plaid_insts.items())
    for i, (l, n) in enumerate(items, 1):
        s = "LINKED" if l in pc.get("institutions", {}) else "not linked"
        print(f"    {i}. {n:40s} [{s}]")
    print(f"    {len(items)+1}. Link ALL unlinked")
    print(f"    0. Skip\n")
    choice = input("  Selection: ").strip()
    if choice == "0":
        return
    labels = []
    if choice == str(len(items) + 1):
        labels = [l for l, _ in items if l not in pc.get("institutions", {})]
    else:
        idx = int(choice) - 1
        if 0 <= idx < len(items):
            labels = [items[idx][0]]
    for l in labels:
        inst_name = INSTITUTION_LABELS.get(l, l)
        cash_defaults = {"chase", "marcus"}
        if l in cash_defaults:
            inst_type = "cash"
            print(f"  {inst_name}: setting as cash account (checking/savings)")
        else:
            type_choice = input(f"  Is {inst_name} an investment or cash account? [investment/cash]: ").strip().lower()
            inst_type = "cash" if type_choice == "cash" else "investment"
        _plaid_link(client, config, l, inst_type=inst_type)
    save_config(config)


def _plaid_link(client, config, label, inst_type="investment"):
    name = INSTITUTION_LABELS[label]
    pc = config["plaid"]
    print(f"\n  --- Linking {name} via Plaid ({inst_type}) ---")

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


def _serve_plaid_link(client, link_token, institution_name, redirect_uri=None):
    """Serve Plaid Link for credential-based institution linking."""
    try:
        from flask import Flask, request as fr, jsonify
    except ImportError:
        return input("  Paste public_token (Enter to skip): ").strip() or None

    app = Flask(__name__)
    result = {"t": None}
    state = {"done": False}

    html = f"""<!DOCTYPE html><html><head><title>Link {institution_name}</title>
    <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
    <style>body{{font-family:sans-serif;max-width:500px;margin:80px auto;text-align:center}}
    button{{padding:12px 32px;font-size:16px;background:#1a73e8;color:white;border:none;border-radius:6px;cursor:pointer}}
    #s{{margin-top:20px;padding:16px;border-radius:8px;display:none}}
    .ok{{background:#e8f5e9;color:#2e7d32}}.err{{background:#fce4ec;color:#c62828}}
    #manual{{margin-top:30px;padding:20px;border:1px solid #ddd;border-radius:8px;text-align:left;display:none}}
    #manual input{{width:100%;padding:8px;margin:8px 0;font-family:monospace;font-size:12px}}
    #manual button{{margin-top:8px}}</style></head>
    <body><h1>Link {institution_name}</h1>
    <button id="b" onclick="handler.open()">Connect</button><div id="s"></div>
    <div id="manual"><p><strong>Manual token entry</strong> (if the popup closed before success):</p>
    <p style="font-size:12px;color:#666">Open browser console on the Plaid popup, or check Plaid Dashboard logs for the public_token.</p>
    <input id="mt" placeholder="Paste public_token here..."/>
    <button onclick="fetch('/cb',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{public_token:document.getElementById('mt').value}})}}).then(()=>{{document.getElementById('s').className='ok';document.getElementById('s').style.display='block';document.getElementById('s').textContent='Token submitted!';}})">Submit Token</button></div>
    <script>
    let linkOpen=false;
    const handler=Plaid.create({{token:'{link_token}',
    onSuccess:(t,m)=>{{
      console.log('Plaid onSuccess, public_token:',t);
      document.getElementById('s').className='ok';
      document.getElementById('s').style.display='block';
      document.getElementById('s').textContent='Success! Linking account...';
      document.getElementById('b').style.display='none';
      document.getElementById('manual').style.display='none';
      fetch('/cb',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{public_token:t}})}})
      .then(()=>{{document.getElementById('s').textContent='Done! You can close this tab.';}})
      .catch(e=>{{document.getElementById('s').textContent='Callback error: '+e;}});
    }},
    onExit:(e,m)=>{{
      console.log('Plaid onExit',e,m);
      if(e){{let s=document.getElementById('s');s.style.display='block';
        s.className='err';s.textContent='Error: '+(e.display_message||e.error_message||JSON.stringify(e));}}
      document.getElementById('manual').style.display='block';
    }}
    }});
    </script></body></html>"""

    @app.route("/")
    def index():
        return html

    @app.route("/cb", methods=["POST"])
    def cb():
        result["t"] = fr.get_json().get("public_token")
        state["done"] = True
        print(f"  Public token received!")
        return jsonify({"ok": True})

    import threading, webbrowser
    print(f"  Opening browser at http://localhost:8234")
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8234")).start()

    # Use threaded server so we can shut it down after receiving the token
    import signal

    def _run_server():
        try:
            app.run(port=8234, debug=False, use_reloader=False, threaded=True)
        except Exception:
            pass

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    # Wait for the public token (up to 5 minutes)
    for _ in range(300):
        if state["done"]:
            break
        time.sleep(1)

    return result.get("t")


def extract_plaid(config, start_date, end_date, institution_filter=None):
    if not PLAID_AVAILABLE:
        return {}
    client = get_plaid_client(config)
    insts = config["plaid"].get("institutions", {})
    results = {}
    for label, idata in insts.items():
        if idata.get("type") == "cash":
            continue  # Cash institutions handled by extract_plaid_cash()
        if institution_filter and label != institution_filter:
            continue
        name = INSTITUTION_LABELS.get(label, label)
        at = idata["access_token"]
        print(f"\n{'='*60}\n  Extracting via Plaid: {name}\n{'='*60}")
        r = {"provider": "plaid", "institution": name, "label": label,
             "accounts": [], "holdings": [], "securities": [], "investment_transactions": []}
        try:
            for a in client.accounts_get(AccountsGetRequest(access_token=at))["accounts"]:
                r["accounts"].append({"account_id": a["account_id"], "name": a["name"],
                    "type": str(a["type"]), "subtype": str(a.get("subtype", "")),
                    "balances": {"current": _num(a["balances"].get("current")),
                                 "available": _num(a["balances"].get("available"))}})
        except plaid.ApiException as e:
            print(f"  ERROR accounts: {_plaid_error(e)}")
        try:
            hr = client.investments_holdings_get(InvestmentsHoldingsGetRequest(access_token=at))
            for s in hr["securities"]:
                r["securities"].append({"security_id": s["security_id"], "name": s.get("name"),
                    "ticker_symbol": s.get("ticker_symbol"), "close_price": _num(s.get("close_price"))})
            for h in hr["holdings"]:
                r["holdings"].append({"account_id": h["account_id"], "security_id": h["security_id"],
                    "quantity": _num(h.get("quantity")), "institution_price": _num(h.get("institution_price")),
                    "institution_value": _num(h.get("institution_value")), "cost_basis": _num(h.get("cost_basis"))})
        except plaid.ApiException as e:
            print(f"  ERROR holdings: {_plaid_error(e)}")
        try:
            off, tot = 0, 0
            while True:
                tr = client.investments_transactions_get(InvestmentsTransactionsGetRequest(
                    access_token=at, start_date=start_date, end_date=end_date,
                    options=InvestmentsTransactionsGetRequestOptions(count=500, offset=off)))
                ta = tr["total_investment_transactions"]
                for t in tr["investment_transactions"]:
                    r["investment_transactions"].append({"account_id": t["account_id"],
                        "security_id": t.get("security_id"), "date": str(t["date"]),
                        "type": str(t.get("type", "")), "subtype": str(t.get("subtype", "")),
                        "quantity": _num(t.get("quantity")), "price": _num(t.get("price")),
                        "amount": _num(t.get("amount")), "fees": _num(t.get("fees"))})
                tot += len(tr["investment_transactions"])
                if tot >= ta: break
                off = tot
                time.sleep(0.5)
        except plaid.ApiException as e:
            print(f"  ERROR transactions: {_plaid_error(e)}")
        results[label] = r
    return results


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


def compute_historical_cash_balances(config, start_date, end_date):
    """Compute month-end balances for cash institutions by pulling transactions
    and working backwards from current balances.

    Returns list of monthly snapshots:
    [{"date": "2026-01-31", "chase": 1234.56, "marcus": 5678.90, "total": 6913.46}, ...]
    """
    if not PLAID_AVAILABLE:
        return []

    insts = config["plaid"].get("institutions", {})
    cash_insts = {k: v for k, v in insts.items() if v.get("type") == "cash"}
    if not cash_insts:
        return []

    client = get_plaid_client(config)

    # For each institution, get current balance per account and all transactions
    inst_account_balances = {}  # {label: {account_id: current_balance}}
    inst_transactions = {}      # {label: [{date, amount, account_id}, ...]}

    for label, idata in cash_insts.items():
        name = INSTITUTION_LABELS.get(label, label)
        at = idata["access_token"]
        print(f"\n{'='*60}\n  Fetching history for {name}\n{'='*60}")

        # Get current balances per account
        try:
            resp = client.accounts_get(AccountsGetRequest(access_token=at))
            acct_bals = {}
            for a in resp["accounts"]:
                acct_bals[a["account_id"]] = _num(a["balances"].get("current", 0))
                print(f"  {a['name']}: current ${acct_bals[a['account_id']]:,.2f}")
            inst_account_balances[label] = acct_bals
        except Exception as e:
            print(f"  ERROR getting balances for {name}: {e}")
            continue

        # Get all transactions in date range
        try:
            txns = []
            offset = 0
            while True:
                tr = client.transactions_get(TransactionsGetRequest(
                    access_token=at,
                    start_date=start_date,
                    end_date=end_date,
                    options=TransactionsGetRequestOptions(count=500, offset=offset),
                ))
                txns.extend([
                    {"date": str(t["date"]), "amount": _num(t["amount"]),
                     "account_id": t["account_id"]}
                    for t in tr["transactions"]
                ])
                total_txns = tr["total_transactions"]
                offset += len(tr["transactions"])
                if offset >= total_txns:
                    break
                time.sleep(0.5)
            inst_transactions[label] = txns
            print(f"  {name}: {len(txns)} transactions fetched")
        except Exception as e:
            print(f"  ERROR getting transactions for {name}: {e}")
            inst_transactions[label] = []

    # Compute month-end balances by rolling back from current balance
    # Plaid transaction amounts: positive = money leaving account (debit),
    # negative = money entering account (credit)
    # So to go backwards: balance_earlier = balance_later + sum(txns between)
    import calendar

    year = start_date.year
    month_ends = []
    for m in range(1, 13):
        last_day = calendar.monthrange(year, m)[1]
        me = datetime.date(year, m, last_day)
        if me <= end_date:
            month_ends.append(me)

    snapshots = []
    for me in month_ends:
        entry = {"date": me.isoformat()}
        total = 0.0
        for label in sorted(cash_insts.keys()):
            acct_bals = inst_account_balances.get(label, {})
            txns = inst_transactions.get(label, [])

            # For each account, compute balance at month-end
            inst_total = 0.0
            for acct_id, current_bal in acct_bals.items():
                # Sum transactions AFTER month-end (these happened between month-end and now)
                # Adding them back reverses their effect
                txns_after = sum(
                    t["amount"] for t in txns
                    if t["account_id"] == acct_id and t["date"] > me.isoformat()
                )
                bal_at_month_end = current_bal + txns_after
                inst_total += bal_at_month_end

            entry[label] = round(inst_total, 2)
            total += inst_total

        entry["total"] = round(total, 2)
        snapshots.append(entry)
        print(f"  {me}: {', '.join(f'{k}=${v:,.2f}' for k, v in entry.items() if k not in ('date', 'total'))} | Total: ${entry['total']:,.2f}")

    return snapshots


# ===========================================================================
# Pipeline output
# ===========================================================================

def to_pipeline_format(raw, start_date, end_date):
    pipeline = {}
    for label, data in raw.items():
        prov = data.get("provider", "unknown")
        hd = {}
        for h in data.get("holdings", []):
            tk = h.get("ticker") or h.get("ticker_symbol") or "UNKNOWN"
            if not tk or tk == "UNKNOWN":
                continue  # skip unidentified positions (crypto dust, etc.)
            hd[tk] = {
                "qty": round(h.get("quantity", 0), 6),
                "price": round(h.get("institution_price", 0), 4),
                "mv": round(h.get("institution_value", 0), 2),
                "cb": round(h.get("cost_basis", 0), 2),
                "gl": round(h.get("gain_loss", 0), 2),
                "name": h.get("name", ""),
            }
        monthly = _monthly_summaries(data.get("investment_transactions", []), start_date, end_date)
        divs = sum(abs(t.get("amount", 0) or 0) for t in data.get("investment_transactions", [])
                   if "dividend" in (t.get("type") or "").lower())
        pipeline[label] = {
            "provider": prov, "monthly": monthly,
            "holdings": {end_date.isoformat(): hd},
            "total_dividends": round(divs, 2),
            "unrealized": round(sum(v.get("gl", 0) for v in hd.values()), 2),
            "account_names": [a.get("name", "") for a in data.get("accounts", [])],
        }
    pipeline["benchmarks"] = {"S&P 500": None, "Dow Jones": None, "NASDAQ": None,
                               "_note": "Source from Yahoo Finance"}
    pipeline["_metadata"] = {"extracted_at": datetime.datetime.now().isoformat(),
                              "period_start": start_date.isoformat(), "period_end": end_date.isoformat()}
    return pipeline


def _monthly_summaries(txns, start_date, end_date):
    md = defaultdict(lambda: {"deposits": 0, "withdrawals": 0, "dividends": 0, "buys": 0, "sells": 0, "fees": 0})
    for t in txns:
        try:
            d = datetime.date.fromisoformat(str(t.get("date", ""))[:10])
        except (ValueError, TypeError):
            continue
        k = d.strftime("%Y-%m")
        a = _num(t.get("amount", 0))
        f = _num(t.get("fees", 0))
        tp = (t.get("type") or "").lower()
        sb = (t.get("subtype") or "").lower()
        if tp in ("contribution", "deposit") or "transfer" in sb:
            if a > 0:
                md[k]["withdrawals"] += abs(a)
            else:
                md[k]["deposits"] += abs(a)
        elif tp == "withdrawal":
            md[k]["withdrawals"] += abs(a)
        elif "dividend" in tp or "dividend" in sb or tp == "rei":
            md[k]["dividends"] += abs(a)
        elif tp == "buy" or "buy" in sb:
            md[k]["buys"] += abs(a)
        elif tp == "sell" or "sell" in sb:
            md[k]["sells"] += abs(a)
        elif "fee" in tp or "interest" in tp:
            md[k]["fees"] += abs(a)
        if f:
            md[k]["fees"] += abs(f)
    result = []
    cur = start_date.replace(day=1)
    while cur <= end_date:
        k = cur.strftime("%Y-%m")
        last = (cur.replace(day=31) if cur.month == 12
                else cur.replace(month=cur.month + 1, day=1) - datetime.timedelta(days=1))
        d = md.get(k, {})
        result.append({"date": last.isoformat(), "month": cur.strftime("%B %Y"),
            "deposits": round(d.get("deposits", 0), 2), "withdrawals": round(d.get("withdrawals", 0), 2),
            "dividends": round(d.get("dividends", 0), 2), "buys": round(d.get("buys", 0), 2),
            "sells": round(d.get("sells", 0), 2), "fees": round(d.get("fees", 0), 2)})
        cur = (cur.replace(year=cur.year + 1, month=1) if cur.month == 12
               else cur.replace(month=cur.month + 1))
    return result


# ===========================================================================
# Utilities
# ===========================================================================

def _num(v):
    if v is None: return 0.0
    try: return float(v)
    except: return 0.0

def _plaid_error(e):
    try:
        b = json.loads(e.body)
        return f"{b.get('error_code')}: {b.get('error_message')}"
    except: return str(e)

def write_output(data, filename, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fp = output_dir / filename
    fp.write_text(json.dumps(data, indent=2, default=str))
    print(f"\n  Output written to: {fp}")
    return fp


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Extract portfolio data via SnapTrade + Plaid.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python plaid_extract.py --setup
  python plaid_extract.py --start 2025-01-01 --end 2025-12-31
  python plaid_extract.py --start 2025-01-01 --end 2025-12-31 --format pipeline
  python plaid_extract.py --start 2025-01-01 --end 2025-12-31 --institution robinhood""")

    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--provider", choices=["plaid", "snaptrade", "all"], default="all")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--format", choices=["raw", "pipeline"], default="raw")
    parser.add_argument("--institution", type=str, choices=list(INSTITUTION_LABELS.keys()))
    parser.add_argument("--output", type=str, default="./extract_output")

    args = parser.parse_args()
    config = load_config()

    if args.setup:
        if args.provider in ("snaptrade", "all"):
            setup_snaptrade(config)
        if args.provider in ("plaid", "all"):
            if PLAID_AVAILABLE:
                setup_plaid(config)
            else:
                print("\n  Skipping Plaid (not installed).")
        if not args.start:
            return

    if not args.start or not args.end:
        parser.error("--start and --end required (or use --setup)")

    start_date = datetime.date.fromisoformat(args.start)
    end_date = datetime.date.fromisoformat(args.end)
    output_dir = Path(args.output)

    print(f"\n  Portfolio Data Extractor")
    print(f"  Period: {start_date} to {end_date}")
    print(f"  Format: {args.format}")
    if args.institution:
        print(f"  Institution: {INSTITUTION_LABELS.get(args.institution, args.institution)}")
    print()

    raw = {}
    if args.institution:
        prov = PROVIDER_MAP.get(args.institution, "snaptrade")
        if prov == "plaid":
            raw.update(extract_plaid(config, start_date, end_date, args.institution))
        else:
            raw.update(extract_snaptrade(config, start_date, end_date, args.institution))
    else:
        if args.provider in ("snaptrade", "all"):
            raw.update(extract_snaptrade(config, start_date, end_date))
        if args.provider in ("plaid", "all"):
            raw.update(extract_plaid(config, start_date, end_date))

    if not raw:
        print("\n  No data extracted. Run --setup to link accounts.")
        sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = write_output(raw, f"extract_raw_{ts}.json", output_dir)

    if args.format == "pipeline":
        pipe = to_pipeline_format(raw, start_date, end_date)
        write_output(pipe, f"parsed_data_{ts}.json", output_dir)

    # Summary
    print(f"\n{'='*60}")
    print(f"  EXTRACTION SUMMARY")
    print(f"{'='*60}")
    for label, data in raw.items():
        name = INSTITUTION_LABELS.get(label, label)
        prov = data.get("provider", "?")
        na = len(data.get("accounts", []))
        nh = len(data.get("holdings", []))
        nt = len(data.get("investment_transactions", []))
        print(f"  {name:30s} [{prov:9s}]  {na} accts | {nh} holdings | {nt} txns")

        # Print holdings detail
        if nh > 0:
            print(f"    {'Ticker':<8s} {'Qty':>8s} {'Price':>10s} {'Value':>10s} {'Cost':>10s} {'G/L':>10s}")
            print(f"    {'-'*56}")
            for h in data["holdings"]:
                tk = h.get("ticker") or "???"
                print(f"    {tk:<8s} {h['quantity']:>8.2f} ${h['institution_price']:>9.2f} "
                      f"${h['institution_value']:>9.2f} ${h['cost_basis']:>9.2f} ${h['gain_loss']:>9.2f}")

    print(f"\n  Output: {raw_file}")
    print(f"\n  Still needs manual sourcing:")
    print(f"    - Angel investments (manual)")
    print(f"    - Benchmarks & MWRR values")
    print()


if __name__ == "__main__":
    main()
