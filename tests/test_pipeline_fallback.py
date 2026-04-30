"""Regression tests for daily_pipeline's fallback-on-empty-extraction logic.

Bug: 2026-04-29 daily run produced a workbook with no 401(k) market value
because Plaid's Merrill extraction returned content-empty (accounts=[],
holdings=[], securities=[]) — but the pipeline's fallback logic only
checked for KEY presence, not content. So the existing-but-empty merrill
entry blocked the fallback to the most recent good extraction.

These tests pin the fix: any extraction shape with no accounts AND no
holdings is treated as empty and triggers `load_last_good_source`.
"""
from daily_pipeline import _is_extraction_empty


def test_extraction_with_holdings_is_not_empty():
    """The shape from a healthy extraction should NOT be empty."""
    raw = {
        "accounts": [{"account_id": "A1", "name": "Walmart 401(k)"}],
        "holdings": [{"account_id": "A1", "security_id": "S1",
                      "quantity": 33.0, "institution_value": 800.0}],
        "securities": [{"security_id": "S1", "name": "Vanguard Target 2055"}],
    }
    assert _is_extraction_empty(raw) is False


def test_extraction_with_accounts_only_is_not_empty():
    """If accounts populated but holdings empty, still treat as usable —
    the holdings call may have failed independently but accounts data is
    enough to render a partial view."""
    raw = {
        "accounts": [{"account_id": "A1", "name": "Walmart 401(k)",
                      "balances": {"current": 111565.74}}],
        "holdings": [],
        "securities": [],
    }
    assert _is_extraction_empty(raw) is False


def test_plaid_silent_failure_shape_is_empty():
    """The exact shape Plaid returned for Merrill on 2026-04-29:
    empty accounts AND empty holdings. This MUST trigger fallback."""
    raw = {
        "provider": "plaid",
        "institution": "Merrill Lynch (Bank of America)",
        "label": "merrill",
        "accounts": [],
        "holdings": [],
        "securities": [],
        "investment_transactions": [],
    }
    assert _is_extraction_empty(raw) is True


def test_none_is_empty():
    assert _is_extraction_empty(None) is True


def test_empty_dict_is_empty():
    assert _is_extraction_empty({}) is True


def test_non_dict_passes_through():
    """Don't mis-classify list/scalar shapes — leave them to the existing
    code path so changes are minimally invasive."""
    assert _is_extraction_empty([]) is False
    assert _is_extraction_empty("not a dict") is False
