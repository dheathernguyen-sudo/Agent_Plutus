"""
registry.py — Reference registry for 2026_Portfolio_Analysis.xlsx

Defines expected cell locations for all tabs. Used by:
  1. Workbook validator to verify cells haven't drifted
  2. Named range generator so Dashboard formulas never hardcode row numbers
  3. Any cross-sheet reference that needs a stable cell address

Row numbers are auto-updated by each rebuild script via update_registry().
The canonical data lives in registry_data.json (written by rebuild scripts,
read here). If the JSON file doesn't exist, hardcoded defaults below are used.
"""
import json
from pathlib import Path
from openpyxl.workbook.defined_name import DefinedName

_DATA_FILE = Path(__file__).parent / "registry_data.json"

# ---------------------------------------------------------------------------
# REGISTRY
# Maps: tab_name -> key_name -> (column_letter, row_number, expected_label_in_col_A)
# ---------------------------------------------------------------------------

REGISTRY = {
    "Fidelity Brokerage": {
        "TWR":                ("B",  6, "Time-Weighted Return (YTD)"),
        "MWRR":               ("B",  7, "Money-Weighted Return (YTD)"),
        "cb_return":          ("B",  8, "Cost Basis Return"),
        "dividends":          ("B", 14, "Dividends"),
        "unrealized":         ("B", 15, "Unrealized"),
        "realized":           ("B", 16, "Realized"),
        "total_ytd":          ("B", 17, "Total YTD"),
        "holdings_total":     ("D", 40, "TOTAL"),
        "monthly_jan":        ("B", 44, "Jan"),
        "monthly_dec":        ("B", 55, "Dec"),
        "monthly_totals":     ("B", 57, "Totals"),
        "sold_2026_total":    ("F", 65, "2026 TOTAL"),
    },

    "Fidelity Roth IRA": {
        "TWR":                ("B",  6, "Time-Weighted Return (YTD)"),
        "MWRR":               ("B",  7, "Money-Weighted Return (YTD)"),
        "cb_return":          ("B",  8, "Cost Basis Return"),
        "dividends":          ("B", 14, "Dividends"),
        "unrealized":         ("B", 15, "Unrealized"),
        "realized":           ("B", 16, "Realized"),
        "total_ytd":          ("B", 17, "Total YTD"),
        "holdings_total":     ("D", 30, "TOTAL"),
        "monthly_jan":        ("B", 34, "Jan"),
        "monthly_dec":        ("B", 45, "Dec"),
        "monthly_totals":     ("B", 47, "Totals"),
        "sold_2026_total":    ("F", 55, "2026 TOTAL"),
    },

    "Fidelity HSA": {
        "TWR":                ("B",  6, "Time-Weighted Return (YTD)"),
        "MWRR":               ("B",  7, "Money-Weighted Return (YTD)"),
        "cb_return":          ("B",  8, "Cost Basis Return"),
        "dividends":          ("B", 14, "Dividends"),
        "unrealized":         ("B", 15, "Unrealized"),
        "realized":           ("B", 16, "Realized"),
        "total_ytd":          ("B", 17, "Total YTD"),
        "holdings_total":     ("D", 27, "TOTAL"),
        "monthly_jan":        ("B", 31, "Jan"),
        "monthly_dec":        ("B", 42, "Dec"),
        "monthly_totals":     ("B", 44, "Totals"),
        "sold_2026_total":    ("F", 52, "2026 TOTAL"),
    },

    "401(k)": {
        "quarterly_first":    ("B",  5, "Q1 (Nov 1 - Jan 31)"),
        "ytd_totals":         ("C", 10, "YTD Totals"),
        "TWR":                ("B", 13, "Time-Weighted Return (YTD)"),
        "MWRR":               ("B", 15, "Money-Weighted Return (YTD)"),
        "cb_return":          ("B", 16, "Cost Basis Return"),
        "holdings_total":     ("B", 28, "TOTAL"),
        "total_inv_gain":     ("B", 33, "Total Investment Gain"),
    },

    "Robinhood": {
        "TWR":                ("B",  6, "Time-Weighted Return (YTD)"),
        "MWRR":               ("B",  7, "Money-Weighted Return (YTD)"),
        "cb_return":          ("B",  8, "Cost Basis Return"),
        "dividends":          ("B", 13, "Dividends Received"),
        "unrealized":         ("B", 14, "Unrealized"),
        "realized":           ("B", 15, "Realized"),
        "total_ytd":          ("B", 16, "Total YTD"),
        "holdings_total_mv":  ("D", 28, "TOTAL SECURITIES"),
        "holdings_total_cb":  ("F", 28, "TOTAL SECURITIES"),
        "holdings_total_gl":  ("G", 28, "TOTAL SECURITIES"),
        "margin_debt":        ("D", 29, "Margin Debt"),
        "net_portfolio":      ("D", 30, "NET PORTFOLIO VALUE"),
        "monthly_jan":        ("B", 42, "Jan"),
        "monthly_dec":        ("B", 53, "Dec"),
        "monthly_totals":     ("B", 55, "Totals"),
        "sold_2026_total":    ("F", 62, "2026 TOTAL"),
    },

    "Angel Investments": {
        "total_invested":     ("E", 12, "TOTAL"),
        "total_current":      ("I", 12, "TOTAL"),
    },

    "Cash": {
        "total_cash":         ("C", 10, "TOTAL EXTERNAL CASH"),
    },

    "Dashboard": {
        "sp500":              ("A",  9, "S&P 500"),
        "dow":                ("A", 10, "Dow Jones"),
        "nasdaq":             ("A", 11, "NASDAQ"),
        "dividends":          ("A", 15, "Dividends"),
        "unrealized":         ("A", 16, "Unrealized"),
        "realized":           ("A", 17, "Realized"),
        "total_inv_gain":     ("B", 19, "Total YTD Investment Gain"),
        "fid_brok":           ("A", 23, "Fidelity Brokerage"),
        "roth_ira":           ("A", 24, "Fidelity Roth IRA"),
        "hsa":                ("A", 25, "Fidelity HSA"),
        "robinhood":          ("A", 26, "Robinhood"),
        "liquid":             ("B", 27, "LIQUID SUBTOTAL"),
        "cash":               ("A", 29, "CASH"),
        "k401":               ("A", 31, "401(k)"),
        "angel":              ("A", 32, "Angel Investments"),
        "illiquid":           ("B", 33, "ILLIQUID SUBTOTAL"),
        "total_portfolio":    ("B", 35, "TOTAL PORTFOLIO"),
    },
}

# ---------------------------------------------------------------------------
# MONTHLY_COLUMNS
# Maps: tab_name -> column_letter -> field_name
# All tabs share the same 9-column layout (B through I).
# ---------------------------------------------------------------------------

_STANDARD_MONTHLY_COLUMNS = {
    "B": "beginning",
    "C": "deposits_additions_contributions",
    "D": "withdrawals_subtractions_distributions",
    "E": "dividends",
    "F": "market_change",
    "G": "ending",
    "H": "monthly_return",
    "I": "growth_factor",
}

MONTHLY_COLUMNS = {
    "Robinhood":           _STANDARD_MONTHLY_COLUMNS,
    "Fidelity Brokerage":  _STANDARD_MONTHLY_COLUMNS,
    "Fidelity Roth IRA":   _STANDARD_MONTHLY_COLUMNS,
    "Fidelity HSA":        _STANDARD_MONTHLY_COLUMNS,
}

# ---------------------------------------------------------------------------
# HOLDINGS_ROWS
# Maps: tab_name -> {first, last, total, mv_col, cb_col, gl_col}
# first/last = first and last data rows of the holdings table
# total      = row number of the TOTAL/summary row
# mv_col     = column letter for Market Value
# cb_col     = column letter for Cost Basis
# gl_col     = column letter for Gain/Loss
# ---------------------------------------------------------------------------

HOLDINGS_ROWS = {
    "Fidelity Brokerage": {
        "first":  20,
        "last":   39,
        "total":  40,
        "mv_col": "D",
        "cb_col": "E",
        "gl_col": "F",
    },
    "Fidelity Roth IRA": {
        "first":  20,
        "last":   29,
        "total":  30,
        "mv_col": "D",
        "cb_col": "E",
        "gl_col": "F",
    },
    "Fidelity HSA": {
        "first":  20,
        "last":   26,
        "total":  27,
        "mv_col": "D",
        "cb_col": "E",
        "gl_col": "F",
    },
    "401(k)": {
        "first":  20,
        "last":   27,
        "total":  28,
        "mv_col": "B",
        "cb_col": "C",
        "gl_col": "D",
    },
    "Robinhood": {
        "first":  19,
        "last":   27,
        "total":  28,
        "mv_col": "D",
        "cb_col": "F",
        "gl_col": "G",
    },
}


# ---------------------------------------------------------------------------
# AUTO-UPDATE: Load row numbers from JSON if available (written by rebuild scripts)
# ---------------------------------------------------------------------------
def _load_json_overrides():
    """Merge registry_data.json into REGISTRY and HOLDINGS_ROWS."""
    if not _DATA_FILE.exists():
        return
    try:
        data = json.loads(_DATA_FILE.read_text())
        for tab, entries in data.get("REGISTRY", {}).items():
            if tab in REGISTRY:
                for key, val in entries.items():
                    if key in REGISTRY[tab]:
                        col, _old_row, label = REGISTRY[tab][key]
                        REGISTRY[tab][key] = (col, val, label)
        for tab, entries in data.get("HOLDINGS_ROWS", {}).items():
            if tab in HOLDINGS_ROWS:
                HOLDINGS_ROWS[tab].update(entries)
    except Exception:
        pass  # fall back to hardcoded defaults


_load_json_overrides()


def update_registry(tab_name, rows=None, holdings=None):
    """Called by rebuild scripts to persist actual row numbers.

    Args:
        tab_name: e.g. "Fidelity Brokerage"
        rows: dict of {key: row_number} matching REGISTRY keys
              e.g. {"TWR": 6, "MWRR": 7, "dividends": 14, ...}
        holdings: dict of {first, last, total} row numbers
    """
    # Load existing JSON or start fresh
    if _DATA_FILE.exists():
        try:
            data = json.loads(_DATA_FILE.read_text())
        except Exception:
            data = {}
    else:
        data = {}

    if rows:
        reg = data.setdefault("REGISTRY", {})
        reg[tab_name] = rows

    if holdings:
        hr = data.setdefault("HOLDINGS_ROWS", {})
        hr[tab_name] = holdings

    _DATA_FILE.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# NAMED RANGES
# ---------------------------------------------------------------------------
# Tab name prefixes for named ranges (Excel names can't contain spaces or parens)
_TAB_PREFIX = {
    "Fidelity Brokerage": "fid_brok",
    "Fidelity Roth IRA":  "roth_ira",
    "Fidelity HSA":       "fid_hsa",
    "401(k)":             "k401",
    "Robinhood":          "robinhood",
    "Angel Investments":  "angel",
    "Cash":               "cash",
    "Dashboard":          "dash",
}


def _make_ref(tab_name, col, row):
    """Build a sheet-qualified cell reference like 'Fidelity Brokerage'!$B$6."""
    if any(c in tab_name for c in " ()"):
        return f"'{tab_name}'!${col}${row}"
    return f"{tab_name}!${col}${row}"


def define_named_ranges(wb):
    """Create/update Excel named ranges from the REGISTRY.

    Each entry becomes: {tab_prefix}_{key} -> 'Tab Name'!$COL$ROW
    e.g. fid_brok_TWR -> 'Fidelity Brokerage'!$B$6

    Call this after all tabs are built. Safe to call multiple times —
    existing names are overwritten.
    """
    # Clear old auto-generated names
    existing = list(wb.defined_names.values())
    for n in existing:
        if any(n.name.startswith(p + "_") for p in _TAB_PREFIX.values()):
            del wb.defined_names[n.name]

    created = 0
    for tab_name, entries in REGISTRY.items():
        prefix = _TAB_PREFIX.get(tab_name)
        if not prefix:
            continue
        for key, (col, row, _label) in entries.items():
            name = f"{prefix}_{key}"
            ref = _make_ref(tab_name, col, row)
            wb.defined_names.add(DefinedName(name=name, attr_text=ref))
            created += 1

    # Additional computed names not in REGISTRY but useful for Dashboard
    # Monthly totals columns (additions/subtractions) for net cash flow calc
    for tab_name, prefix in _TAB_PREFIX.items():
        if tab_name not in REGISTRY:
            continue
        entries = REGISTRY[tab_name]
        if "monthly_totals" in entries:
            _, totals_row, _ = entries["monthly_totals"]
            wb.defined_names.add(DefinedName(
                name=f"{prefix}_monthly_totals_add",
                attr_text=_make_ref(tab_name, "C", totals_row)))
            wb.defined_names.add(DefinedName(
                name=f"{prefix}_monthly_totals_sub",
                attr_text=_make_ref(tab_name, "D", totals_row)))
            created += 2
        if "monthly_jan" in entries:
            _, jan_row, _ = entries["monthly_jan"]
            wb.defined_names.add(DefinedName(
                name=f"{prefix}_monthly_begin",
                attr_text=_make_ref(tab_name, "B", jan_row)))
            created += 1

    # Holdings total MV column (for "Ending" in Account Overview)
    for tab_name, h in HOLDINGS_ROWS.items():
        prefix = _TAB_PREFIX.get(tab_name)
        if not prefix:
            continue
        wb.defined_names.add(DefinedName(
            name=f"{prefix}_holdings_total_mv",
            attr_text=_make_ref(tab_name, h["mv_col"], h["total"])))
        wb.defined_names.add(DefinedName(
            name=f"{prefix}_holdings_total_cb",
            attr_text=_make_ref(tab_name, h["cb_col"], h["total"])))
        wb.defined_names.add(DefinedName(
            name=f"{prefix}_holdings_total_gl",
            attr_text=_make_ref(tab_name, h["gl_col"], h["total"])))
        created += 3

    return created
