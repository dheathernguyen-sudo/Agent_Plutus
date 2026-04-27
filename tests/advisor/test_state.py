"""Tests for advisor.state — persist and dedup findings across days."""
import json
from datetime import date


def _f(category, key, severity="attention"):
    from advisor.observations import Finding
    return Finding(category=category, key=key, severity=severity,
                   headline=f"{category}/{key}", detail={})


def test_save_and_load_roundtrip(tmp_path):
    from advisor.state import save_findings, load_findings_for_date

    findings = [_f("sector_concentration", "Tech")]
    save_findings(findings, "sample brief\n", date(2026, 4, 25), tmp_path)

    out = load_findings_for_date(date(2026, 4, 25), tmp_path)
    assert len(out) == 1
    assert out[0].category == "sector_concentration"
    assert out[0].key == "Tech"


def test_load_most_recent_before(tmp_path):
    from advisor.state import save_findings, load_most_recent_before

    save_findings([_f("a", "x")], "", date(2026, 4, 23), tmp_path)
    save_findings([_f("b", "y")], "", date(2026, 4, 24), tmp_path)

    prev = load_most_recent_before(date(2026, 4, 25), tmp_path)
    assert len(prev) == 1
    assert prev[0].key == "y"


def test_load_most_recent_returns_empty_when_no_history(tmp_path):
    from advisor.state import load_most_recent_before
    prev = load_most_recent_before(date(2026, 4, 25), tmp_path)
    assert prev == []


def test_diff_classifies_new_standing_changed():
    from advisor.state import diff_findings

    today = [
        _f("a", "x", "attention"),  # standing
        _f("b", "y", "urgent"),     # changed (was attention)
        _f("c", "z", "attention"),  # new
    ]
    yesterday = [
        _f("a", "x", "attention"),
        _f("b", "y", "attention"),  # different severity
        _f("d", "old", "attention"),  # gone today
    ]
    classified = diff_findings(today, yesterday)
    assert classified["new"][0].key == "z"
    assert classified["standing"][0].key == "x"
    assert classified["changed"][0].key == "y"


def test_diff_first_run_treats_all_as_new():
    from advisor.state import diff_findings
    today = [_f("a", "x"), _f("b", "y")]
    classified = diff_findings(today, [])
    assert len(classified["new"]) == 2
    assert classified["standing"] == []
    assert classified["changed"] == []
