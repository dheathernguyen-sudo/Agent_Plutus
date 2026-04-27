"""Tests for advisor.asset_classifier — ticker → asset class tagging."""
import logging
import pytest


def test_known_equity_tickers():
    from advisor.asset_classifier import classify
    assert classify("AAPL") == "equity"
    assert classify("NVDA") == "equity"
    assert classify("VOO") == "equity"


def test_known_bond_tickers():
    from advisor.asset_classifier import classify
    assert classify("AGG") == "bond"
    assert classify("BND") == "bond"
    assert classify("TLT") == "bond"


def test_known_cash_tickers():
    from advisor.asset_classifier import classify
    assert classify("FCASH") == "cash"
    assert classify("SPAXX") == "cash"
    assert classify("FDRXX") == "cash"


def test_known_tips_tickers():
    from advisor.asset_classifier import classify
    assert classify("TIP") == "tips"
    assert classify("SCHP") == "tips"


def test_known_reit_tickers():
    from advisor.asset_classifier import classify
    assert classify("VNQ") == "reit"
    assert classify("IYR") == "reit"


def test_known_commodity_tickers():
    from advisor.asset_classifier import classify
    assert classify("GLD") == "commodity"
    assert classify("SLV") == "commodity"


def test_known_international_tickers():
    from advisor.asset_classifier import classify
    assert classify("VXUS") == "international_equity"
    assert classify("VEA") == "international_equity"


def test_unknown_ticker_falls_through_to_equity_with_warning(caplog):
    from advisor.asset_classifier import classify
    with caplog.at_level(logging.WARNING):
        result = classify("ZZZZ")
    assert result == "equity"
    assert "ZZZZ" in caplog.text


def test_classify_by_name_keywords_for_401k_funds():
    """401(k) holdings often have full names rather than tickers."""
    from advisor.asset_classifier import classify
    assert classify("FXAIX", name="Russell 1000 Index Fund") == "equity"
    assert classify("UNKNOWN1", name="Short Term Bond Trust") == "bond"
    assert classify("UNKNOWN2", name="Money Market Trust") == "cash"
    assert classify("UNKNOWN3", name="Intl Eqty Index Tst") == "international_equity"
