"""Tests for advisor.profile — load/validate user_profile.json."""
import json
import logging

import pytest


def test_load_profile_with_valid_file(tmp_path):
    from advisor.profile import load_profile

    p = tmp_path / "user_profile.json"
    p.write_text(json.dumps({
        "name": "Test User",
        "birth_year": 1985,
        "target_retirement_year": 2050,
        "risk_tolerance": "moderate-aggressive",
        "tax_situation": {"filing_status": "single",
                          "federal_bracket": "24%", "state": "CA"},
        "employment": {"employer_ticker": "WMT", "monthly_expenses": 8000},
        "concentration_limits": {"max_single_position": 0.10, "max_sector": 0.30},
        "liquidity": {"emergency_fund_target": 50000,
                      "known_upcoming_expenses": []},
        "hard_rules": ["never sell Anduril"],
        "goals": ["retire by 2050"],
    }))
    prof = load_profile(p)
    assert prof.profile_missing is False
    assert prof.birth_year == 1985
    assert prof.risk_tolerance == "moderate-aggressive"
    assert prof.tax_situation.federal_bracket == "24%"
    assert prof.employment.employer_ticker == "WMT"
    assert prof.concentration_limits.max_sector == 0.30
    assert prof.liquidity.emergency_fund_target == 50000
    assert prof.hard_rules == ["never sell Anduril"]


def test_load_profile_missing_file_returns_defaults(tmp_path, caplog):
    from advisor.profile import load_profile

    nonexistent = tmp_path / "does_not_exist.json"
    with caplog.at_level(logging.WARNING):
        prof = load_profile(nonexistent)
    assert prof.profile_missing is True
    assert prof.risk_tolerance == "moderate"
    assert prof.concentration_limits.max_sector == 0.30
    assert "missing" in caplog.text.lower()


def test_load_profile_malformed_json_returns_defaults(tmp_path, caplog):
    from advisor.profile import load_profile

    p = tmp_path / "bad.json"
    p.write_text("{ this is not json")
    with caplog.at_level(logging.WARNING):
        prof = load_profile(p)
    assert prof.profile_missing is True
    assert "malformed" in caplog.text.lower() or "decode" in caplog.text.lower()


def test_load_profile_partial_applies_defaults(tmp_path):
    from advisor.profile import load_profile

    p = tmp_path / "partial.json"
    p.write_text(json.dumps({"birth_year": 1990, "risk_tolerance": "moderate"}))
    prof = load_profile(p)
    assert prof.profile_missing is False
    assert prof.birth_year == 1990
    # Defaults filled in for missing sections:
    assert prof.concentration_limits.max_sector == 0.30
    assert prof.tax_situation.state == ""
    assert prof.hard_rules == []


def test_load_profile_with_non_numeric_concentration_returns_defaults(tmp_path, caplog):
    from advisor.profile import load_profile

    p = tmp_path / "bad_limits.json"
    p.write_text(json.dumps({
        "concentration_limits": {"max_single_position": "not_a_number"}
    }))
    with caplog.at_level(logging.WARNING):
        prof = load_profile(p)
    assert prof.profile_missing is True
    # Defaults populated:
    assert prof.concentration_limits.max_single_position == 0.10


def test_load_profile_with_missing_expense_field_returns_defaults(tmp_path, caplog):
    from advisor.profile import load_profile

    p = tmp_path / "bad_expense.json"
    # Missing both "amount" and "target_year"
    p.write_text(json.dumps({
        "liquidity": {"known_upcoming_expenses": [{"purpose": "house"}]}
    }))
    with caplog.at_level(logging.WARNING):
        prof = load_profile(p)
    assert prof.profile_missing is True


def test_load_profile_with_non_utf8_file_returns_defaults(tmp_path, caplog):
    from advisor.profile import load_profile

    p = tmp_path / "binary.json"
    # Write bytes that are not valid UTF-8 (a stray 0xFF byte sequence)
    p.write_bytes(b'\xff\xfe\xfd not utf-8')
    with caplog.at_level(logging.WARNING):
        prof = load_profile(p)
    assert prof.profile_missing is True
