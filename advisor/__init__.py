# advisor/__init__.py
"""Portfolio advisory agent — entry points.

Public API:
- run_daily(model, workbook_path, ...) — called from daily_pipeline.py.
- run_cli() — used by `python -m advisor`.

Failure modes are documented in spec §9; nothing here propagates exceptions
to callers, except programmer errors (bad arguments).
"""
from __future__ import annotations

import logging
from datetime import date as _date
from pathlib import Path
from typing import Any, Optional

from .observations import Finding, run as run_observations
from .profile import Profile, load_profile
from .state import save_findings, load_most_recent_before, diff_findings
from .narrator import compose
from .writer import write_recommendations_tab

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = Path(__file__).parent.parent / "advisor_state"
DEFAULT_PROFILE_PATH = Path(__file__).parent.parent / "user_profile.json"


def run_daily(model: dict, workbook_path, *,
              profile: Optional[Profile] = None,
              state_dir: Optional[Path] = None,
              client: Optional[Any] = None,
              today: Optional[_date] = None) -> None:
    """Run the full daily advisor pipeline. Failures are logged, never raised.

    Side effects:
      - Writes findings_YYYY-MM-DD.json + brief_YYYY-MM-DD.md in state_dir.
      - Adds/replaces a Recommendations tab in workbook_path.
    """
    today = today or _date.today()
    state_dir = state_dir or DEFAULT_STATE_DIR
    profile = profile if profile is not None else load_profile(DEFAULT_PROFILE_PATH)

    try:
        findings_today = run_observations(model, profile)
    except Exception as exc:
        logger.warning(f"observations.run() raised ({exc}); using empty list")
        findings_today = []

    findings_yesterday = load_most_recent_before(today, state_dir)
    classified = diff_findings(findings_today, findings_yesterday)

    brief_md = compose(classified, profile, client=client)
    save_findings(findings_today, brief_md, today, state_dir)
    write_recommendations_tab(workbook_path, brief_md, findings_today)


import argparse
import json as _json
import sys


def run_cli(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="advisor",
        description="Portfolio advisory agent — read today's or a previous day's brief.")
    parser.add_argument("--date", default=_date.today().isoformat(),
                        help="ISO date (YYYY-MM-DD); defaults to today.")
    parser.add_argument("--findings", action="store_true",
                        help="Print structured findings as JSON instead of the brief.")
    parser.add_argument("--state-dir", default=None,
                        help="Override state directory (defaults to advisor_state/).")
    args = parser.parse_args(argv)

    state_dir = Path(args.state_dir) if args.state_dir else DEFAULT_STATE_DIR
    target_date = _date.fromisoformat(args.date)

    if args.findings:
        from .state import load_findings_for_date
        findings = load_findings_for_date(target_date, state_dir)
        if not findings:
            print(f"No findings stored for {target_date}.", file=sys.stderr)
            return 1
        from dataclasses import asdict as _asdict
        print(_json.dumps([_asdict(f) for f in findings], indent=2, default=str))
        return 0

    brief = state_dir / f"brief_{target_date.isoformat()}.md"
    if not brief.exists():
        print(f"No brief at {brief}.", file=sys.stderr)
        return 1
    print(brief.read_text(encoding="utf-8"))
    return 0


__all__ = ["run_daily", "run_cli", "Finding", "Profile", "load_profile"]
