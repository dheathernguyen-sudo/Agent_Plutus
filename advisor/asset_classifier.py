"""Classify a holding's asset class from its ticker (and optional name).

Used by glide_path_drift, asset_location_inefficiency, and
inflation_hedge_exposure observations.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

AssetClass = str  # "equity" | "bond" | "cash" | "tips" | "reit" | "commodity" | "international_equity"

# Lookup tables — extend as new holdings appear.
_BOND_TICKERS = {
    "AGG", "BND", "BSV", "BIV", "BLV", "TLT", "IEF", "SHY", "GOVT",
    "VCIT", "VCLT", "VCSH", "LQD", "HYG", "JNK", "EMB",
}
_CASH_TICKERS = {
    "FCASH", "SPAXX", "FDRXX", "CASH", "VMFXX", "SWVXX", "BIL",
}
_TIPS_TICKERS = {"TIP", "VTIP", "SCHP", "STIP", "SPIP"}
_REIT_TICKERS = {"VNQ", "IYR", "SCHH", "RWR", "XLRE", "USRT", "REZ", "MORT"}
_COMMODITY_TICKERS = {"GLD", "IAU", "SLV", "DBC", "PDBC", "USO", "UNG"}
_INTL_TICKERS = {
    "VXUS", "VEA", "VWO", "IEFA", "IEMG", "EFA", "EEM",
    "SCHF", "SCHE", "VPL", "VGK", "FLJP", "FLKR",
}

# Keyword fallback for funds named rather than tickered (e.g. 401k).
_NAME_KEYWORDS = [
    ("international_equity", ("intl", "international", "global ex-us", "ex-us", "europe", "asia", "emerging")),
    ("bond", ("bond", "fixed income", "treasury", "credit", "aggregate")),
    ("cash", ("money market", "cash reserve", "stable value")),
    ("tips", ("tips", "inflation-protected", "inflation protected")),
    ("reit", ("reit", "real estate")),
    ("commodity", ("gold", "silver", "commodity", "commodities")),
]


def classify(ticker: str, name: Optional[str] = None) -> AssetClass:
    """Return the asset class of a holding.

    Lookup order:
      1. Ticker-based exact match against known lists.
      2. Name-based keyword match (case-insensitive).
      3. Fallback to "equity" with a warning logged once per ticker.
    """
    t = (ticker or "").upper()
    if t in _BOND_TICKERS:
        return "bond"
    if t in _CASH_TICKERS:
        return "cash"
    if t in _TIPS_TICKERS:
        return "tips"
    if t in _REIT_TICKERS:
        return "reit"
    if t in _COMMODITY_TICKERS:
        return "commodity"
    if t in _INTL_TICKERS:
        return "international_equity"

    if name:
        n = name.lower()
        for cls, keywords in _NAME_KEYWORDS:
            if any(k in n for k in keywords):
                return cls

    logger.warning(
        f"Unknown ticker {ticker!r} (name={name!r}); defaulting to 'equity'. "
        f"Add to advisor/asset_classifier.py if it should classify differently."
    )
    return "equity"
