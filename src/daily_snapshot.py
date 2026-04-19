"""daily_snapshot.py — Save and compare daily portfolio snapshots.

Snapshot JSON format on disk:
{
    "date": "2026-04-09",
    "accounts": {
        "fidelity_XXXXXXXXX": {
            "total_mv": 75265.76,
            "holdings": {
                "AAPL": {"price": 150.0, "mv": 3000.0, "qty": 20.0},
                ...
            }
        },
        ...
    },
    "liquid_total_mv": 95000.0,   # everything except 401k
    "total_mv": 120000.0
}
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "snapshots"

# Any account key that contains this substring is considered illiquid (401k)
_ILLIQUID_SUBSTRINGS = ("401k", "merrill_401k")


def _is_illiquid(acct_key: str) -> bool:
    key_lower = acct_key.lower()
    return any(s in key_lower for s in _ILLIQUID_SUBSTRINGS)


def _latest_date_holdings(holdings_value: dict) -> dict:
    """Return ticker-keyed holdings regardless of whether the dict is:
    - Direct:   {ticker: {qty, price, mv, ...}}
    - Date-keyed: {"2026-04-04": {ticker: {qty, price, mv, ...}}}
    """
    if not holdings_value:
        return {}
    first_key = next(iter(holdings_value))
    first_val = holdings_value[first_key]
    # If the first key looks like a date (YYYY-MM-DD) and maps to a dict, treat as date-keyed
    if isinstance(first_val, dict) and len(first_key) == 10 and first_key[4] == "-" and first_key[7] == "-":
        # Pick the most recent date
        latest_date_key = max(holdings_value.keys())
        return holdings_value[latest_date_key] or {}
    # Already direct ticker-keyed
    return holdings_value


def _extract_fidelity_accounts(fid_data: dict) -> dict:
    """Convert fid_data into normalised account dicts ready for snapshot.

    fid_data is keyed by account label such as "fidelity_XXXXXXXXX".
    Values are either:
      - {ticker: {qty, price, mv, cb, gl, ...}}   (direct holdings)
      - {"2026-04-04": {ticker: {qty, price, mv, ...}}}  (date-keyed holdings)
    """
    accounts: dict = {}
    for acct_key, acct_value in fid_data.items():
        if not isinstance(acct_value, dict):
            continue
        raw_holdings = _latest_date_holdings(acct_value)
        holdings = {}
        total_mv = 0.0
        for ticker, info in raw_holdings.items():
            if not isinstance(info, dict):
                continue
            mv = float(info.get("mv", 0) or 0)
            price = float(info.get("price", 0) or 0)
            qty = float(info.get("qty", 0) or 0)
            holdings[ticker] = {"price": price, "mv": mv, "qty": qty}
            total_mv += mv
        accounts[acct_key] = {"total_mv": round(total_mv, 2), "holdings": holdings}
    return accounts


def _extract_provider_accounts(raw: dict, provider_label: str) -> dict:
    """Extract normalised accounts from an rh_raw or k401_raw dict.

    Expected shape:
      raw = {
          "<provider_label>": {
              "holdings": {"2026-04-05": {ticker: {qty, price, mv, cb, gl}}},
              "accounts": [{"account_id": ..., "number": ..., "name": ...}],
              ...
          }
      }

    Returns dict keyed by account key (e.g. "robinhood") or falls back to
    provider_label when no per-account breakdown is present.
    """
    accounts: dict = {}
    if not raw or not isinstance(raw, dict):
        return accounts

    # If raw itself has a "holdings" key, treat it as the provider data directly
    if "holdings" in raw:
        data = raw
        acct_label = provider_label
    else:
        # Find the sub-dict for this provider (first matching key containing provider_label)
        data = None
        for key, val in raw.items():
            if isinstance(val, dict) and provider_label in key.lower():
                data = val
                acct_label = key
                break
        # Fallback: pick the first dict value if no key matched
        if data is None:
            for key, val in raw.items():
                if isinstance(val, dict):
                    data = val
                    acct_label = key
                    break
    if data is None:
        return accounts

    raw_holdings_outer = data.get("holdings", {})
    # Flatten date-keyed holdings
    flat_holdings = _latest_date_holdings(raw_holdings_outer)

    # Build holdings dict
    holdings: dict = {}
    total_mv = 0.0
    for ticker, info in flat_holdings.items():
        if not isinstance(info, dict):
            continue
        mv = float(info.get("mv", 0) or 0)
        price = float(info.get("price", 0) or 0)
        qty = float(info.get("qty", 0) or 0)
        holdings[ticker] = {"price": price, "mv": mv, "qty": qty}
        total_mv += mv

    accounts[acct_label] = {"total_mv": round(total_mv, 2), "holdings": holdings}
    return accounts


def save_snapshot(
    fid_data: dict,
    rh_raw: dict,
    k401_raw: Optional[dict] = None,
    date_str: Optional[str] = None,
) -> Path:
    """Save a portfolio snapshot to disk as JSON.

    Parameters
    ----------
    fid_data:
        Dict keyed by account label (e.g. ``"fidelity_XXXXXXXXX"``).
        Values are either direct ``{ticker: {qty, price, mv, cb, gl}}`` or
        date-keyed ``{"2026-04-04": {ticker: {...}}}``.
    rh_raw:
        Dict with one provider key (e.g. ``"robinhood"``) whose value contains
        ``{"holdings": {"2026-04-05": {ticker: {...}}}, "accounts": [...]}``.
    k401_raw:
        401(k) data from any provider (Merrill, Fidelity NetBenefits, etc.),
        or ``None``.
    date_str:
        Date string in ``YYYY-MM-DD`` format.  Defaults to today.

    Returns
    -------
    Path
        Absolute path to the written snapshot file.
    """
    if date_str is None:
        date_str = date.today().isoformat()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    accounts: dict = {}

    # --- Fidelity accounts ---
    if fid_data:
        accounts.update(_extract_fidelity_accounts(fid_data))

    # --- Robinhood (or other SnapTrade) accounts ---
    if rh_raw:
        accounts.update(_extract_provider_accounts(rh_raw, "robinhood"))

    # --- 401(k) (any provider) ---
    if k401_raw:
        accounts.update(_extract_provider_accounts(k401_raw, "401k"))

    # --- Compute totals ---
    liquid_total_mv = sum(
        v["total_mv"] for k, v in accounts.items() if not _is_illiquid(k)
    )
    total_mv = sum(v["total_mv"] for v in accounts.values())

    snapshot = {
        "date": date_str,
        "accounts": accounts,
        "liquid_total_mv": round(liquid_total_mv, 2),
        "total_mv": round(total_mv, 2),
    }
    snapshot["stale_sources"] = []

    out_path = SNAPSHOT_DIR / f"snapshot_{date_str}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2)

    logger.info(f"Snapshot saved: {out_path}  (total_mv={total_mv:,.2f})")
    return out_path


def load_snapshot(date_str: str) -> Optional[dict]:
    """Load snapshot for the given date string (``YYYY-MM-DD``).

    Returns the parsed dict, or ``None`` if no file exists for that date.
    """
    path = SNAPSHOT_DIR / f"snapshot_{date_str}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to load snapshot {path}: {exc}")
        return None


def load_previous_snapshot(before_date_str: Optional[str] = None) -> Optional[dict]:
    """Return the most recent snapshot that is strictly before *before_date_str*.

    Parameters
    ----------
    before_date_str:
        Upper bound date (``YYYY-MM-DD``).  Defaults to today.

    Returns
    -------
    dict or None
        Parsed snapshot contents, or ``None`` if no earlier snapshot exists.
    """
    if before_date_str is None:
        before_date_str = date.today().isoformat()

    if not SNAPSHOT_DIR.exists():
        return None

    cutoff = datetime.strptime(before_date_str, "%Y-%m-%d").date()

    candidates = []
    for path in SNAPSHOT_DIR.glob("snapshot_*.json"):
        stem = path.stem  # e.g. "snapshot_2026-04-08"
        date_part = stem[len("snapshot_"):]
        try:
            d = datetime.strptime(date_part, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < cutoff:
            candidates.append((d, path))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, latest_path = candidates[0]

    try:
        with open(latest_path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to load previous snapshot {latest_path}: {exc}")
        return None


def compute_daily_summary(current: dict, previous: dict) -> dict:
    """Compare two snapshot dicts and return a daily change summary.

    Parameters
    ----------
    current:
        Today's snapshot (from ``load_snapshot`` or ``save_snapshot``).
    previous:
        Yesterday's (or most recent prior) snapshot.

    Returns
    -------
    dict with keys:
        - ``liquid_change`` / ``liquid_change_pct``
        - ``total_change`` / ``total_change_pct``
        - ``top_movers``: list of ``{ticker, account, price_today,
          price_yesterday, change_pct}`` for securities with >10% daily
          price change, sorted by absolute change descending.
    """
    def _safe_pct(change: float, base: float) -> float:
        if base == 0:
            return 0.0
        return round(change / base * 100, 4)

    cur_liquid = current.get("liquid_total_mv", 0.0)
    prev_liquid = previous.get("liquid_total_mv", 0.0)
    cur_total = current.get("total_mv", 0.0)
    prev_total = previous.get("total_mv", 0.0)

    liquid_change = round(cur_liquid - prev_liquid, 2)
    total_change = round(cur_total - prev_total, 2)

    # --- Top movers: securities with >10% price change ---
    top_movers = []
    cur_accounts = current.get("accounts", {})
    prev_accounts = previous.get("accounts", {})

    for acct_key, cur_acct in cur_accounts.items():
        prev_acct = prev_accounts.get(acct_key, {})
        cur_holdings = cur_acct.get("holdings", {})
        prev_holdings = prev_acct.get("holdings", {})

        for ticker, cur_info in cur_holdings.items():
            prev_info = prev_holdings.get(ticker)
            if prev_info is None:
                continue  # new position — skip
            price_today = cur_info.get("price", 0.0) or 0.0
            price_yesterday = prev_info.get("price", 0.0) or 0.0
            if price_yesterday == 0:
                continue
            change_pct = (price_today - price_yesterday) / price_yesterday * 100
            if abs(change_pct) > 10:
                top_movers.append(
                    {
                        "ticker": ticker,
                        "account": acct_key,
                        "price_today": round(price_today, 4),
                        "price_yesterday": round(price_yesterday, 4),
                        "change_pct": round(change_pct, 4),
                    }
                )

    top_movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

    return {
        "liquid_change": liquid_change,
        "liquid_change_pct": _safe_pct(liquid_change, prev_liquid),
        "total_change": total_change,
        "total_change_pct": _safe_pct(total_change, prev_total),
        "top_movers": top_movers,
    }
