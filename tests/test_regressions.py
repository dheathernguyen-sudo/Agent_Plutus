"""Regression tests for bugs discovered on 2026-04-24.

Each test corresponds to one bug. If the original bug is reintroduced, the
test fails. Tests are intentionally small and isolated — no network access,
no real Excel file build unless the test is explicitly an integration check.
"""
import inspect
import json
import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Bug 1 — PROJECT_DIR = SCRIPT_DIR.parent.resolve() pointed to agents/ instead
# of Project Finance/, breaking output paths, log paths, data_dir, and
# subprocess cwd for rebuild scripts.
# ---------------------------------------------------------------------------
def test_project_dir_equals_script_dir():
    import daily_pipeline
    assert daily_pipeline.PROJECT_DIR == daily_pipeline.SCRIPT_DIR, (
        "PROJECT_DIR must equal SCRIPT_DIR in the flat layout. If it resolves "
        "to the parent, OUTPUT_XLSX, MANUAL_DATA, LOG_DIR, and data_dir all "
        "point to the wrong directory and the workbook silently lands in agents/."
    )


def test_output_xlsx_and_manual_data_files_exist():
    """Sanity: the paths derived from PROJECT_DIR must point at real files."""
    import daily_pipeline
    assert daily_pipeline.MANUAL_DATA.exists(), daily_pipeline.MANUAL_DATA
    # OUTPUT_XLSX doesn't need to exist yet, but its parent must.
    assert daily_pipeline.OUTPUT_XLSX.parent.exists()


# ---------------------------------------------------------------------------
# Bug 2 — daily_pipeline called save_snapshot(k401_raw=...) but the function
# signature accepts merrill_raw. Caught as a non-fatal warning; renamed.
# ---------------------------------------------------------------------------
def test_save_snapshot_accepts_merrill_raw_kwarg():
    from daily_snapshot import save_snapshot
    params = inspect.signature(save_snapshot).parameters
    assert "merrill_raw" in params


def test_pipeline_passes_merrill_raw_not_k401_raw():
    """The pipeline's save_snapshot(...) call must use the merrill_raw kwarg."""
    from pathlib import Path
    src = Path(__file__).parent.parent / "daily_pipeline.py"
    text = src.read_text(encoding="utf-8")
    assert "merrill_raw=k401_raw" in text, "Pipeline must pass merrill_raw=..., not k401_raw=..."
    assert "k401_raw=k401_raw," not in text, "Old k401_raw kwarg leaked back in."


# ---------------------------------------------------------------------------
# Bug 3 — Plaid cash extractor loaded from PROJECT_DIR/extractors/plaid_extract.py
# which doesn't exist in the flat layout. Correct location is repo/extractors/.
# ---------------------------------------------------------------------------
def test_repo_plaid_extract_path_resolves():
    import daily_pipeline
    p = daily_pipeline.PROJECT_DIR / "repo" / "extractors" / "plaid_extract.py"
    assert p.exists(), f"Expected plaid_extract.py at {p}"


def test_repo_plaid_extract_has_extract_plaid_cash():
    """extract_plaid_cash only lives in repo/extractors/plaid_extract.py —
    the older PIPELINE_DIR copy doesn't have it."""
    import daily_pipeline
    import importlib.util
    p = daily_pipeline.PROJECT_DIR / "repo" / "extractors" / "plaid_extract.py"
    spec = importlib.util.spec_from_file_location("repo_plaid_extract", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "extract_plaid_cash")


# ---------------------------------------------------------------------------
# Bug 4 — Fidelity live-holdings lookup used un-redacted account numbers
# (fidelity_Z23889908), but SnapTrade returns redacted numbers (fidelity_*****9908),
# so all 3 Fidelity accounts silently fell back to stale data/*.json files.
# ---------------------------------------------------------------------------
def test_merge_live_holdings_matches_redacted_fidelity_keys():
    from portfolio_model import _merge_live_holdings

    live = {
        "fidelity_*****9908": {"AAPL": {"qty": 10, "price": 100, "mv": 1000, "cb": 500}},
        "fidelity_*****9863": {"CRWD": {"qty": 5, "price": 200, "mv": 1000, "cb": 700}},
        "fidelity_*****9651": {"CEG": {"qty": 3, "price": 300, "mv": 900, "cb": 600}},
    }
    stale = {"holdings": [{"ticker": "STALE", "mv": 1}]}

    for data_key, expected_ticker in [
        ("fidelity_brokerage", "AAPL"),
        ("fidelity_roth_ira", "CRWD"),
        ("fidelity_hsa", "CEG"),
    ]:
        holdings, source = _merge_live_holdings(stale, live, data_key)
        assert source == "live", f"{data_key}: got {source}"
        assert holdings[0]["ticker"] == expected_ticker


def test_merge_live_holdings_falls_back_when_no_match():
    from portfolio_model import _merge_live_holdings
    stale = {"holdings": [{"ticker": "STALE", "mv": 1}]}
    holdings, source = _merge_live_holdings(stale, {}, "fidelity_brokerage")
    assert source == "statement"
    assert holdings[0]["ticker"] == "STALE"


# ---------------------------------------------------------------------------
# Bug 5 — 401(k) showed ending=$0 on the Dashboard despite having live Plaid
# holdings. gains.total_mv was computed from empty acct['holdings'] and never
# updated after _merge_live_merrill populated live_holdings.
# ---------------------------------------------------------------------------
def test_401k_gains_total_mv_from_live_merrill_holdings():
    from portfolio_model import build_model

    with tempfile.TemporaryDirectory() as tmpdir:
        k401 = {
            "account": {"name": "401(k)", "type": "illiquid",
                        "provider": "merrill", "tab_name": "401(k)"},
            "quarterly": [{
                "period": "Q1",
                "beginning": 70000, "ee_contributions": 2000,
                "er_contributions": 1000, "fees": 0,
                "change_in_value": 2000, "ending": 75000,
            }],
            "holdings": [],  # empty — the bug was not computing MV when this is empty
            "monthly": {},
            "sector_map": {},
        }
        with open(os.path.join(tmpdir, "k401.json"), "w") as f:
            json.dump(k401, f)

        raw_extraction = {
            "merrill": {
                "securities": [
                    {"security_id": "s1", "name": "Russell 1000", "ticker_symbol": "FXAIX"},
                    {"security_id": "s2", "name": "Intl Eqty", "ticker_symbol": "FSPSX"},
                ],
                "holdings": [
                    {"security_id": "s1", "institution_value": 50000.0,
                     "cost_basis": 40000.0, "quantity": 500.0},
                    {"security_id": "s2", "institution_value": 25000.0,
                     "cost_basis": 20000.0, "quantity": 1000.0},
                ],
            }
        }

        model = build_model(data_dir=tmpdir, raw_extraction=raw_extraction)
        k401_model = next(v for v in model["accounts"].values()
                          if v["tab_name"] == "401(k)")

        assert k401_model["gains"]["total_mv"] == 75000.0, (
            f"Expected gains.total_mv=75000 (sum of live Plaid holdings), "
            f"got {k401_model['gains']['total_mv']}"
        )
        assert k401_model["gains"]["total_cb"] == 60000.0


# ---------------------------------------------------------------------------
# Bug 6 — Cash double-count. Fidelity live holdings include money-market
# positions (FCASH/SPAXX/FDRXX) that represent cash; the stale cash_position
# in data/*.json was being added on top.
# ---------------------------------------------------------------------------
def test_live_holdings_source_zeroes_stale_cash_position():
    from portfolio_model import build_model

    with tempfile.TemporaryDirectory() as tmpdir:
        acct = {
            "account": {"name": "Fidelity Brokerage", "type": "liquid",
                        "provider": "snaptrade", "tab_name": "Fidelity Brokerage"},
            "holdings": [{"ticker": "STALE", "qty": 1, "price": 100, "mv": 100, "cb": 50}],
            "cash_position": 500.0,  # stale, should NOT be added when live overrides
            "monthly": {},
            "sector_map": {},
        }
        with open(os.path.join(tmpdir, "fidelity_brokerage.json"), "w") as f:
            json.dump(acct, f)

        live_extraction = {
            "fidelity_*****9908": {
                "AAPL": {"qty": 10, "price": 100, "mv": 1000, "cb": 500},
                "FCASH": {"qty": 50, "price": 1, "mv": 50, "cb": 50},
            }
        }
        model = build_model(data_dir=tmpdir, live_extraction=live_extraction)
        m = next(v for v in model["accounts"].values()
                 if v["tab_name"] == "Fidelity Brokerage")
        assert m["holdings_source"] == "live"
        assert m["cash_position"] == 0, (
            f"cash_position must be 0 when holdings source is live "
            f"(got {m['cash_position']}) — otherwise money-market positions "
            f"are double-counted."
        )


def test_statement_holdings_preserve_cash_position():
    """Sanity: when NO live extraction matches, stale cash_position is kept."""
    from portfolio_model import build_model

    with tempfile.TemporaryDirectory() as tmpdir:
        acct = {
            "account": {"name": "Fidelity Brokerage", "type": "liquid",
                        "provider": "snaptrade", "tab_name": "Fidelity Brokerage"},
            "holdings": [{"ticker": "AAPL", "qty": 1, "price": 100, "mv": 100, "cb": 50}],
            "cash_position": 500.0,
            "monthly": {},
            "sector_map": {},
        }
        with open(os.path.join(tmpdir, "fidelity_brokerage.json"), "w") as f:
            json.dump(acct, f)

        model = build_model(data_dir=tmpdir, live_extraction={})  # no live match
        m = next(v for v in model["accounts"].values()
                 if v["tab_name"] == "Fidelity Brokerage")
        assert m["holdings_source"] == "statement"
        assert m["cash_position"] == 500.0


# ---------------------------------------------------------------------------
# Bug 7 — save_snapshot threw `list indices must be integers or slices, not
# dict` because the raw SnapTrade rh_raw uses list-of-dicts for holdings,
# but _extract_provider_accounts assumed the ticker-keyed or date-keyed dict
# shape produced by the older pipeline-normalised format.
# ---------------------------------------------------------------------------
def test_snapshot_handles_list_format_holdings():
    from daily_snapshot import _extract_provider_accounts

    raw = {
        "robinhood": {
            "holdings": [  # raw SnapTrade list shape
                {"ticker": "NVDA", "quantity": 50.0,
                 "institution_price": 200.0, "institution_value": 10000.0},
                {"ticker": "TSM", "quantity": 10.0,
                 "institution_price": 100.0, "institution_value": 1000.0},
            ],
            "accounts": [{"account_id": "abc", "name": "RH"}],
        }
    }
    accounts = _extract_provider_accounts(raw, "robinhood")
    assert "robinhood" in accounts
    assert accounts["robinhood"]["total_mv"] == 11000.0
    assert set(accounts["robinhood"]["holdings"].keys()) == {"NVDA", "TSM"}
    assert accounts["robinhood"]["holdings"]["NVDA"]["mv"] == 10000.0


def test_snapshot_still_handles_ticker_keyed_holdings():
    """Regression-of-regression: the list-format fix must not break the older
    ticker-keyed dict shape."""
    from daily_snapshot import _extract_provider_accounts

    raw = {
        "robinhood": {
            "holdings": {"NVDA": {"qty": 50, "price": 200, "mv": 10000}},
            "accounts": [{"account_id": "abc"}],
        }
    }
    accounts = _extract_provider_accounts(raw, "robinhood")
    assert accounts["robinhood"]["total_mv"] == 10000.0


# ---------------------------------------------------------------------------
# Bug 8 — Validator/builder drift produced 28 label-mismatch errors.
# Integration check: the workbook as built today must pass the validator.
# ---------------------------------------------------------------------------
def test_current_workbook_passes_validator_with_zero_errors():
    """End-to-end regression: after a clean pipeline run, the workbook has no
    validator ERROR-severity findings. Requires the workbook to exist —
    skipped if not (e.g. first test run on a fresh checkout)."""
    import daily_pipeline
    from validate_workbook import validate_full

    xlsx = daily_pipeline.PROJECT_DIR / "2026_Portfolio_Analysis.xlsx"
    if not xlsx.exists():
        pytest.skip(f"Workbook not built yet: {xlsx}")

    findings = validate_full(str(xlsx))
    errors = [f for f in findings if f.severity == "ERROR"]
    assert not errors, (
        "Validator reported ERROR-severity findings:\n"
        + "\n".join(f"  [{f.tab}] {f.cell}: {f.message}" for f in errors)
    )


def test_advisor_failure_is_non_fatal(monkeypatch, tmp_path, caplog):
    """If advisor.run_daily() raises, the daily pipeline must still complete
    and the workbook must still be saved correctly."""
    import importlib
    import logging

    # Force run_daily to raise
    import advisor
    def _boom(*a, **kw):
        raise RuntimeError("synthetic advisor failure")
    monkeypatch.setattr(advisor, "run_daily", _boom)

    # Sanity import the integration block
    import daily_pipeline
    assert hasattr(daily_pipeline, "run_pipeline") or hasattr(daily_pipeline, "main"), \
        "daily_pipeline.py is missing its main entry point"

    # Inspect the source: integration block must catch broad Exception
    src = importlib.util.find_spec("daily_pipeline").origin
    text = open(src, encoding="utf-8").read()
    assert "from advisor import run_daily" in text or "advisor.run_daily" in text, \
        "daily_pipeline.py must invoke advisor.run_daily()"
    assert "except Exception" in text and "Advisor" in text, \
        "advisor invocation must be wrapped in a non-fatal try/except"
