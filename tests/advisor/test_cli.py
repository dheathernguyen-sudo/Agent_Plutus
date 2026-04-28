"""Tests for the python -m advisor CLI entry point."""
import json
import sys
from pathlib import Path


def test_cli_prints_existing_brief_for_date(tmp_path, capsys, monkeypatch):
    from advisor import run_cli
    from advisor.state import save_findings
    from advisor.observations import Finding
    from datetime import date

    state_dir = tmp_path / "state"
    findings = [Finding(category="x", key="k", severity="attention",
                        headline="hello", detail={})]
    save_findings(findings, "# Brief\n\nHello world body.\n", date(2026, 4, 25), state_dir)

    monkeypatch.setattr("advisor.DEFAULT_STATE_DIR", state_dir)
    rc = run_cli(["--date", "2026-04-25"])
    out = capsys.readouterr().out
    assert "Hello world body" in out
    assert rc == 0


def test_cli_prints_findings_json_with_flag(tmp_path, capsys, monkeypatch):
    from advisor import run_cli
    from advisor.state import save_findings
    from advisor.observations import Finding
    from datetime import date

    state_dir = tmp_path / "state"
    findings = [Finding(category="cat", key="k", severity="urgent",
                        headline="HL", detail={"foo": 1})]
    save_findings(findings, "brief", date(2026, 4, 25), state_dir)

    monkeypatch.setattr("advisor.DEFAULT_STATE_DIR", state_dir)
    rc = run_cli(["--date", "2026-04-25", "--findings"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed[0]["category"] == "cat"
    assert rc == 0


def test_cli_returns_nonzero_when_no_brief_exists(tmp_path, capsys, monkeypatch):
    from advisor import run_cli

    state_dir = tmp_path / "empty"
    monkeypatch.setattr("advisor.DEFAULT_STATE_DIR", state_dir)
    rc = run_cli(["--date", "2026-04-25"])
    assert rc != 0
