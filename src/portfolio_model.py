"""portfolio_model.py — Pure computation model for portfolio analysis.

Reads account data from data/*.json, merges with live API extractions,
computes all return metrics. No Excel/openpyxl dependency.
"""

import json
import datetime
from pathlib import Path

MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _load_account_data(data_dir):
    """Load all account JSON files from data directory."""
    data_dir = Path(data_dir)
    accounts = {}
    for f in sorted(data_dir.glob("*.json")):
        d = json.loads(f.read_text())
        key = f.stem  # e.g. "fidelity_brokerage"
        accounts[key] = d
    return accounts


def _compute_twr(monthly):
    """Compute YTD Time-Weighted Return from monthly data using Modified Dietz."""
    populated = [m for m in MONTH_LABELS if m in monthly]
    if not populated:
        return None
    growth_factors = []
    for m in populated:
        d = monthly[m]
        begin = d.get("begin", 0) or 0
        end = d.get("end", 0) or 0
        add = d.get("add", 0) or 0
        sub = d.get("sub", 0) or 0
        net_flow = add - sub
        denom = begin + 0.5 * net_flow
        if denom == 0:
            continue
        ret = (end - begin - net_flow) / denom
        growth_factors.append(1 + ret)
    if not growth_factors:
        return None
    twr = 1
    for gf in growth_factors:
        twr *= gf
    return twr - 1


def _compute_mwrr(monthly):
    """Compute annualised Money-Weighted Return (IRR) from monthly data."""
    populated = [m for m in MONTH_LABELS if m in monthly]
    if not populated:
        return None
    first = monthly[populated[0]]
    last = monthly[populated[-1]]
    cfs = []
    t = 0
    cfs.append((t, -(first.get("begin", 0) or 0)))
    for m in populated:
        d = monthly[m]
        net = (d.get("add", 0) or 0) - (d.get("sub", 0) or 0)
        cfs.append((t + 0.5, -net))
        t += 1
    cfs.append((t, last.get("end", 0) or 0))
    r = 0.01
    for _ in range(200):
        npv = sum(cf / (1 + r) ** ti for ti, cf in cfs)
        dnpv = sum(-ti * cf / (1 + r) ** (ti + 1) for ti, cf in cfs)
        if abs(dnpv) < 1e-14:
            break
        r_new = r - npv / dnpv
        if abs(r_new - r) < 1e-12:
            r = r_new
            break
        r = r_new
    return (1 + r) ** 12 - 1


def _compute_gains(acct_data):
    """Compute gain breakdown from holdings and sold data."""
    holdings = acct_data.get("holdings", [])
    total_mv = sum(h.get("mv", 0) or 0 for h in holdings)
    total_cb = sum(h.get("cb", 0) or 0 for h in holdings if h.get("cb") is not None)
    unrealized = total_mv - total_cb

    # Dividends from monthly totals
    monthly = acct_data.get("monthly", {})
    dividends = sum(monthly.get(m, {}).get("div", 0) or 0
                    for m in MONTH_LABELS if m in monthly)

    # Realized from sold
    sold = acct_data.get("sold", [])
    if isinstance(sold, dict):
        # Robinhood has {"2026": [...], "2025": [...]}
        sold = sold.get("2026", [])
    realized = 0
    if acct_data.get("realized_gl_override") is not None:
        realized = acct_data["realized_gl_override"]
    else:
        for s in sold:
            cb = s.get("cb")
            proceeds = s.get("proceeds", 0) or 0
            if cb is not None:
                realized += proceeds - cb

    return {
        "dividends": round(dividends, 2),
        "unrealized": round(unrealized, 2),
        "realized": round(realized, 2),
        "total": round(dividends + unrealized + realized, 2),
        "total_mv": round(total_mv, 2),
        "total_cb": round(total_cb, 2),
    }


def _compute_cb_return(gains):
    """Cost basis return = unrealized / total cost basis."""
    if gains["total_cb"] == 0:
        return 0
    return gains["unrealized"] / gains["total_cb"]


def _merge_live_401k(live_extraction):
    """Extract live 401(k) fund holdings from Plaid data.

    Supports any 401(k) provider (Merrill Lynch, Fidelity NetBenefits, Schwab, etc.).
    Returns list of {name, current_value, cost_basis, unrealized_gl, return_pct}
    or empty list if no 401(k) data available.
    """
    if not live_extraction:
        return []

    # Look for any key that represents a 401(k) provider
    k401_raw = None
    for key in live_extraction:
        key_lower = key.lower()
        if any(s in key_lower for s in ("merrill", "401k", "401(k)", "netbenefits")):
            if isinstance(live_extraction[key], dict):
                k401_raw = live_extraction[key]
                break

    if not k401_raw:
        return []

    # Build security name lookup
    sec_map = {}
    for s in k401_raw.get("securities", []):
        sec_map[s["security_id"]] = s.get("name") or s.get("ticker_symbol") or "Unknown Fund"

    holdings = []
    for h in k401_raw.get("holdings", []):
        name = sec_map.get(h.get("security_id", ""), "Unknown Fund")
        val = h.get("institution_value", 0) or 0
        cb = h.get("cost_basis", 0) or 0
        qty = h.get("quantity", 0) or 0
        if val < 1:
            continue
        holdings.append({
            "name": name,
            "current_value": round(val, 2),
            "cost_basis": round(cb, 2),
            "quantity": round(qty, 4),
            "unrealized_gl": round(val - cb, 2),
            "return_pct": round((val - cb) / cb, 4) if cb else 0,
        })

    # Sort by value descending
    holdings.sort(key=lambda x: x["current_value"], reverse=True)
    return holdings


def _merge_live_holdings(acct_data, live_extraction, acct_key):
    """If live extraction has holdings for this account, use them."""
    if not live_extraction:
        return acct_data.get("holdings", []), "statement"
    # Check SnapTrade/Plaid extraction for this account
    # Build extraction key dynamically from account number
    acct_num = acct_data.get("account", {}).get("number", "").replace("-", "")
    ext_key = f"fidelity_{acct_num}" if acct_num else acct_key
    if ext_key in live_extraction:
        live = live_extraction[ext_key]
        if isinstance(live, dict) and live:
            holdings = []
            for ticker, h in live.items():
                holdings.append({
                    "ticker": ticker,
                    "qty": h.get("qty", 0),
                    "price": h.get("price", 0),
                    "mv": h.get("mv", 0),
                    "cb": h.get("cb", 0),
                })
            if holdings:
                return holdings, "live"
    return acct_data.get("holdings", []), "statement"


def _compute_liquid_twr(accounts, model_accounts):
    """Compute aggregated Liquid Portfolio TWR across all liquid accounts."""
    liquid_keys = [k for k, v in accounts.items()
                   if v.get("account", {}).get("type") == "liquid"]
    growth_factors = []
    for i in range(12):
        m = MONTH_LABELS[i]
        cb = ce = ca = cs = 0
        for key in liquid_keys:
            monthly = accounts[key].get("monthly", {})
            if m not in monthly:
                continue
            d = monthly[m]
            cb += d.get("begin", 0) or 0
            ce += d.get("end", 0) or 0
            ca += d.get("add", 0) or 0
            cs += d.get("sub", 0) or 0
        if cb == 0 and ce == 0:
            continue
        net_flow = ca - cs
        denom = cb + 0.5 * net_flow
        if denom == 0:
            continue
        ret = (ce - cb - net_flow) / denom
        growth_factors.append(1 + ret)
    if not growth_factors:
        return None
    twr = 1
    for gf in growth_factors:
        twr *= gf
    return twr - 1


def _compute_sector_geo(all_accounts):
    """Compute sector and geographic concentration from all holdings."""
    sector_vals = {}
    sector_counts = {}
    sector_by_acct = {}
    geo_vals = {}

    acct_short = {
        "fidelity_brokerage": "Fidelity Brokerage",
        "fidelity_roth_ira": "Roth IRA",
        "fidelity_hsa": "HSA",
        "robinhood": "Robinhood",
        "angel": "Angel",
    }

    for acct_key, acct_data in all_accounts.items():
        short = acct_short.get(acct_key)
        if not short:
            continue
        smap = acct_data.get("sector_map", {})

        # For angel, use investments
        if acct_key == "angel":
            for inv in acct_data.get("investments", []):
                sector = inv.get("sector", "Other")
                amt = inv["amount"] * (inv["pm_latest"] / inv["pm_invest"]) if inv["pm_invest"] else inv["amount"]
                sector_vals[sector] = sector_vals.get(sector, 0) + amt
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                sector_by_acct.setdefault(sector, {})[short] = sector_by_acct.get(sector, {}).get(short, 0) + amt
            continue

        holdings = acct_data.get("holdings", [])
        margin_debt = acct_data.get("margin_debt", 0) or 0
        total_mv = sum(h.get("mv", 0) or 0 for h in holdings)
        scale = 1.0
        if margin_debt and total_mv:
            net = total_mv + margin_debt
            scale = net / total_mv if total_mv else 1.0

        for h in holdings:
            ticker = h.get("ticker", "")
            mv = (h.get("mv", 0) or 0) * scale
            info = smap.get(ticker, {"sector": "Other", "country": "United States"})
            sector = info["sector"]
            country = info["country"]

            sector_vals[sector] = sector_vals.get(sector, 0) + mv
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            sector_by_acct.setdefault(sector, {})[short] = sector_by_acct.get(sector, {}).get(short, 0) + mv
            geo_vals[country] = geo_vals.get(country, 0) + mv

    # Sort by value descending
    total = sum(sector_vals.values())
    sectors = []
    for sec in sorted(sector_vals, key=sector_vals.get, reverse=True):
        val = sector_vals[sec]
        sectors.append({
            "name": sec,
            "value": round(val, 2),
            "pct": round(val / total, 4) if total else 0,
            "count": sector_counts.get(sec, 0),
            "by_account": {k: round(v, 2) for k, v in sector_by_acct.get(sec, {}).items()},
        })

    geo_total = sum(geo_vals.values())
    us_val = geo_vals.pop("United States", 0)
    intl_val = geo_total - us_val
    geo = [
        {"region": "United States", "value": round(us_val, 2), "pct": round(us_val / geo_total, 4) if geo_total else 0},
        {"region": "International", "value": round(intl_val, 2), "pct": round(intl_val / geo_total, 4) if geo_total else 0},
    ]
    for country in sorted(geo_vals, key=geo_vals.get, reverse=True):
        val = geo_vals[country]
        geo.append({"region": f"  — {country}", "value": round(val, 2), "pct": round(val / geo_total, 4) if geo_total else 0})

    return sectors, geo


def build_model(data_dir="data/", live_extraction=None, raw_extraction=None, benchmarks=None, cash_data=None, snapshot_dir=None):
    """Build the complete portfolio model.

    Args:
        data_dir: path to JSON data files
        live_extraction: dict from pipeline extraction (fid_data format — Fidelity/Robinhood holdings)
        raw_extraction: full raw extraction dict (includes 401k Plaid data with securities list)
        benchmarks: dict like {"S&P 500": -0.0049, ...}
        cash_data: dict from extract_plaid_cash, e.g. {"chase": {"accounts": [...], "total": X}, ...}
        snapshot_dir: path for daily snapshot comparison

    Returns:
        Model dict with all computed values.
    """
    accounts_raw = _load_account_data(data_dir)
    today = datetime.date.today()

    model = {
        "as_of": today.isoformat(),
        "year": today.year,
        "accounts": {},
        "liquid_accounts": [],
        "illiquid_accounts": [],
        "benchmarks": benchmarks or {},
        "daily_summary": None,
        "cash": {"external": {}, "embedded": {}},
        "sectors": [],
        "geo": [],
    }

    for key, raw in accounts_raw.items():
        acct_info = raw.get("account", {})
        acct_type = acct_info.get("type", "liquid")

        if acct_type == "cash":
            # Cash is handled separately
            continue

        monthly = raw.get("monthly", {})
        holdings, holdings_source = _merge_live_holdings(raw, live_extraction, key)
        gains = _compute_gains({**raw, "holdings": holdings})

        acct_model = {
            "name": acct_info.get("name", key),
            "tab_name": acct_info.get("tab_name", key),
            "type": acct_type,
            "provider": acct_info.get("provider", "manual"),
            "number": acct_info.get("number", ""),
            "is_margin": raw.get("is_margin", False),
            "monthly": monthly,
            "holdings": holdings,
            "holdings_source": holdings_source,
            "sold": raw.get("sold", []),
            "cash_position": raw.get("cash_position", 0),
            "margin_debt": raw.get("margin_debt", 0),
            "margin_details": raw.get("margin_details", {}),
            "cash_flow_labels": raw.get("cash_flow_labels", {"add": "Additions", "sub": "Subtractions"}),
            "returns": {
                "twr": _compute_twr(monthly),
                "mwrr": _compute_mwrr(monthly) if monthly else None,
                "cb_return": _compute_cb_return(gains),
            },
            "gains": gains,
            "sector_map": raw.get("sector_map", {}),
        }

        # Special handling for 401(k)
        if "quarterly" in raw:
            acct_model["quarterly"] = raw["quarterly"]
            acct_model["twr_provider_stated"] = raw.get("twr_provider_stated", raw.get("twr_merrill_stated"))

            # Merge live Plaid holdings for 401(k)
            acct_model["live_holdings"] = _merge_live_401k(raw_extraction)
            # Compute 401k returns from quarterly data
            q_data = raw["quarterly"]
            if q_data:
                # Modified Dietz per quarter, then chain
                gfs = []
                for q in q_data:
                    b = q.get("beginning", 0)
                    contrib = q.get("ee_contributions", 0) + q.get("er_contributions", 0)
                    fees = q.get("fees", 0)
                    chg = q.get("change_in_value", 0)
                    e = q.get("ending", 0)
                    denom = b + 0.5 * (contrib + fees)
                    if denom:
                        gfs.append(1 + chg / denom)
                if gfs:
                    twr_q = 1
                    for gf in gfs:
                        twr_q *= gf
                    acct_model["returns"]["twr"] = twr_q - 1

        # Special handling for angel
        if "investments" in raw:
            acct_model["investments"] = raw["investments"]
            total_invested = sum(i["amount"] for i in raw["investments"])
            total_current = sum(
                i["amount"] * (i["pm_latest"] / i["pm_invest"]) if i["pm_invest"] else i["amount"]
                for i in raw["investments"]
            )
            acct_model["gains"] = {
                "total_invested": round(total_invested, 2),
                "total_current": round(total_current, 2),
                "total_mv": round(total_current, 2),
                "total_cb": round(total_invested, 2),
            }
            acct_model["returns"]["cb_return"] = (total_current - total_invested) / total_invested if total_invested else 0

        model["accounts"][key] = acct_model

        if acct_type == "liquid":
            model["liquid_accounts"].append(key)
        elif acct_type == "illiquid":
            model["illiquid_accounts"].append(key)

    # Liquid Portfolio TWR
    model["liquid_twr"] = _compute_liquid_twr(accounts_raw, model["accounts"])

    # Sector and geographic concentration
    model["sectors"], model["geo"] = _compute_sector_geo(accounts_raw)

    # Cash balances
    cash_config = accounts_raw.get("cash", {})
    model["cash"]["embedded"] = {
        k: accounts_raw.get(k, {}).get("cash_position", 0)
        for k in model["liquid_accounts"]
    }

    # External cash — populated by caller (pipeline passes Plaid data in)
    if cash_data:
        model["cash"]["external"] = cash_data

    # Daily summary from snapshots
    if snapshot_dir:
        try:
            from daily_snapshot import load_snapshot, load_previous_snapshot, compute_daily_summary
            snap_today = load_snapshot(today.isoformat())
            snap_prev = load_previous_snapshot(today.isoformat())
            if snap_today and snap_prev:
                model["daily_summary"] = compute_daily_summary(snap_today, snap_prev)
        except Exception:
            pass

    return model
